from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class DigestChallenge:
    realm: str
    nonce: str
    qop: str = "auth"
    algorithm: str = "MD5"  # "MD5" | "SHA-256"
    opaque: str | None = None


def parse_www_authenticate_digest(header: str) -> DigestChallenge:
    """
    Digest WWW-Authenticate challenge를 파싱한다.

    Example:
      WWW-Authenticate: Digest realm="...", nonce="...", qop="auth", algorithm=SHA-256, opaque="..."
    """
    if not header:
        raise ValueError("empty WWW-Authenticate")

    h = header.strip()
    if h.lower().startswith("digest"):
        h = h[len("digest") :].strip()

    parts: Dict[str, str] = {}
    for m in re.finditer(r'(\w+)=(".*?"|[^,]+)', h):
        k = m.group(1).strip().lower()
        v = m.group(2).strip()
        if v.startswith('"') and v.endswith('"'):
            v = v[1:-1]
        parts[k] = v

    realm = parts.get("realm") or ""
    nonce = parts.get("nonce") or ""
    qop = parts.get("qop") or "auth"
    algo = (parts.get("algorithm") or "MD5").upper()
    opaque = parts.get("opaque")  # keep opaque="" too

    if not realm or not nonce:
        raise ValueError(f"invalid digest challenge: realm/nonce missing ({parts})")

    algo = "SHA-256" if "SHA-256" in algo else "MD5"
    return DigestChallenge(realm=realm, nonce=nonce, qop=qop, algorithm=algo, opaque=opaque)


def build_digest_authorization(
    *,
    method: str,
    url: str,
    username: str,
    password: str,
    challenge: DigestChallenge,
    nc_int: int,
    cnonce: Optional[str] = None,
) -> str:
    """
    Authorization: Digest ... 헤더 값을 생성한다.

    - url: full url
    - uri: path+query extracted from url
    - nc는 호출자(client)가 요청마다 증가시키는 값이다.
    """
    uri = "/" + url.split("://", 1)[-1].split("/", 1)[-1]
    if not uri.startswith("/"):
        uri = "/" + uri

    nc = f"{int(nc_int):08x}"
    cnonce = cnonce or os.urandom(8).hex()
    qop = "auth"

    H = hashlib.sha256 if challenge.algorithm == "SHA-256" else hashlib.md5

    def Hhex(s: str) -> str:
        return H(s.encode("utf-8")).hexdigest()

    ha1 = Hhex(f"{username}:{challenge.realm}:{password}")
    ha2 = Hhex(f"{method}:{uri}")
    resp = Hhex(f"{ha1}:{challenge.nonce}:{nc}:{cnonce}:{qop}:{ha2}")

    base = (
        f'Digest username="{username}", realm="{challenge.realm}", nonce="{challenge.nonce}", '
        f'uri="{uri}", response="{resp}", algorithm={challenge.algorithm}, '
        f'qop={qop}, nc={nc}, cnonce="{cnonce}"'
    )
    if challenge.opaque is not None:
        base += f', opaque="{challenge.opaque}"'

    return base