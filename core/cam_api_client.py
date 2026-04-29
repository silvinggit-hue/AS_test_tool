from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote, urljoin, urlparse, urlsplit

import requests

from models.dto import ApiError
from core.http_client import HttpResponse, _build_session
from core.http_client import http_get
from core.digest import DigestChallenge, parse_www_authenticate_digest

log = logging.getLogger(__name__)


# ----------------------------
# helpers
# ----------------------------
def _pick_digest_header(www_list: list[str]) -> str | None:
    for h in (www_list or []):
        if h and "digest" in h.lower():
            return h
    return www_list[0] if www_list else None


def _pick_qop(qop_raw: str) -> str:
    if not qop_raw:
        return "auth"
    items = [x.strip().lower() for x in qop_raw.split(",") if x.strip()]
    return "auth" if "auth" in items else (items[0] if items else "auth")


def _uri_from_full_url(url: str) -> str:
    sp = urlsplit(url)
    path = sp.path or "/"
    if not path.startswith("/"):
        path = "/" + path
    return path


def _looks_like_auth_error(body: str | None) -> bool:
    """
    일부 장비는 digest 실패 시에도 200을 반환하고 바디에 인증 오류를 포함한다.
    """
    if not body:
        return False
    t = body.lower()
    needles = [
        "authentication error",
        "access denied",
        "denied",
        "auth error",
        "unauthorized",
        "<h2>authentication error",
    ]
    return any(n in t for n in needles)


@dataclass
class _DigestState:
    challenge: DigestChallenge
    nc: int = 0
    cnonce: str = ""

    def reset(self, new_challenge: DigestChallenge) -> None:
        self.challenge = new_challenge
        self.nc = 0
        self.cnonce = ""

    def next_nc_hex(self) -> str:
        if not self.cnonce:
            self.cnonce = os.urandom(8).hex()
        self.nc += 1
        return f"{self.nc:08x}"


@dataclass
class CamApiClient:
    base_url: str
    root_path: str
    username: str
    password: str
    auth_scheme: str  # "digest" | "basic" | "none"
    timeout: object   # settings.timeout (read_sec)
    retry: object     # settings.retry (unused here)
    verify_tls: bool = False

    _session: Optional[requests.Session] = None
    _digest_state: Optional[_DigestState] = None

    # -------------------------
    # session / url helpers
    # -------------------------
    def _get_session(self) -> requests.Session:
        if self._session is None:
            self._session = _build_session(verify_tls=bool(self.verify_tls))
        return self._session

    def with_shared_session(self, sess: requests.Session) -> "CamApiClient":
        self._session = sess
        return self

    def _make_url(self, tail: str) -> str:
        root = self.root_path or ""
        if root and not root.endswith("/"):
            root += "/"
        if tail.startswith("/"):
            tail = tail[1:]
        return urljoin(self.base_url.rstrip("/") + "/", root.lstrip("/") + tail)

    def _make_abs_url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return self.base_url.rstrip("/") + path

    # -------------------------
    # headers
    # -------------------------
    def _default_headers_for_url(self, url: str) -> dict[str, str]:
        p = urlparse(url)
        path = p.path or "/"

        if path == "/" or path == "":
            return {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AS_test_tool_v4",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Upgrade-Insecure-Requests": "1",
                "Connection": "keep-alive",
            }

        if (
            ("/ReadParam" in path)
            or ("/WriteParam" in path)
            or ("/GetState" in path)
            or ("/SendPTZ" in path)
            or ("/SetState" in path)
        ):
            return {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AS_test_tool_v4",
                "Accept": "text/plain, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": self.base_url.rstrip("/") + "/",
                "Connection": "keep-alive",
            }

        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AS_test_tool_v4",
            "Accept": "*/*",
            "Connection": "keep-alive",
        }

    def _merge_headers(self, url: str, extra: dict[str, str] | None) -> dict[str, str]:
        h = dict(self._default_headers_for_url(url))
        if extra:
            h.update(extra)
        return h

    # -------------------------
    # request core (RemoteDisconnected 1회 재시도)
    # -------------------------
    def _request_raw(self, url: str, headers: dict[str, str] | None = None, *, read_body: bool = True) -> HttpResponse:
        sess = self._get_session()
        timeout_sec = float(getattr(self.timeout, "read_sec", 6.0) or 6.0)

        for attempt in range(1, 3):
            try:
                r = sess.get(
                    url,
                    headers=headers or {},
                    timeout=timeout_sec,
                    allow_redirects=False,
                    verify=bool(self.verify_tls),
                )
                body = r.text if read_body else ""
                hdrs = {k: v for k, v in r.headers.items()}
                return HttpResponse(status=int(r.status_code), body=body, headers=hdrs)

            except requests.exceptions.Timeout as e:
                log.warning(
                    "[REQ-FAIL] timeout attempt=%s url=%s timeout=%ss err=%s",
                    attempt,
                    url,
                    timeout_sec,
                    e,
                )
                raise ApiError(kind="timeout", message="timeout", detail=str(e))

            except requests.exceptions.ConnectionError as e:
                msg = str(e)
                log.warning("[REQ-FAIL] connerror attempt=%s url=%s err=%s", attempt, url, msg)
                if ("RemoteDisconnected" in msg or "Remote end closed connection" in msg) and attempt < 2:
                    time.sleep(0.25)
                    continue
                raise ApiError(kind="network", message="request failed", detail=msg)

            except requests.exceptions.SSLError as e:
                log.warning("[REQ-FAIL] ssl attempt=%s url=%s err=%s", attempt, url, e)
                raise ApiError(kind="ssl", message="ssl handshake error", detail=str(e))

            except requests.exceptions.RequestException as e:
                log.warning("[REQ-FAIL] requestexc attempt=%s url=%s err=%s", attempt, url, e)
                raise ApiError(kind="network", message="request failed", detail=str(e))

        raise ApiError(kind="network", message="request failed", detail="unexpected")

    # -------------------------
    # digest
    # -------------------------
    def _ensure_digest_state(self) -> _DigestState:
        """
        Digest challenge(401 + WWW-Authenticate)를 얻는다.

        일부 펌웨어에서 requests 기반의 최초 요청이 무응답/timeout이 발생할 수 있어,
        challenge 획득은 urllib 기반(http_get)으로 수행한다.
        """
        if self._digest_state is not None:
            return self._digest_state

        timeout_sec = 2.0
        headers = {"User-Agent": "AS_test_tool_v4/probe"}

        candidates = [
            self._make_url("ReadParam?action=readparam&ETC_MIN_PASSWORD_LEN=0"),
            self._make_url("ReadParam?action=readparam&SYS_VERSION=0"),
            self._make_url("GetState?action=getrate&GRS_VENCFRAME1=0"),
            self._make_abs_url("/"),
        ]

        last_status: int | None = None
        last_detail: str | None = None

        for url in candidates:
            try:
                r0 = http_get(
                    url=url,
                    headers=headers,
                    timeout_sec=timeout_sec,
                    verify_tls=bool(self.verify_tls),
                    read_body=False,
                )
                last_status = int(r0.status)

                if r0.status == 401:
                    www = r0.header_all("WWW-Authenticate")
                    h = _pick_digest_header(www)
                    if not h:
                        last_detail = "401 but no WWW-Authenticate"
                        continue

                    chall = parse_www_authenticate_digest(h)
                    self._digest_state = _DigestState(challenge=chall)
                    return self._digest_state

                continue

            except ApiError as e:
                last_detail = f"{e.kind}:{e.message}:{(e.detail or '')[:120]}"
                continue
            except Exception as e:
                last_detail = str(e)[:200]
                continue

        raise ApiError(
            kind="auth",
            message="cannot obtain digest challenge (no 401 with WWW-Authenticate)",
            status_code=last_status,
            detail=last_detail,
        )

    def _build_digest_authz(self, method: str, url: str) -> str:
        st = self._ensure_digest_state()
        chall = st.challenge

        uri = _uri_from_full_url(url)
        qop = _pick_qop(getattr(chall, "qop", "") or "")
        nc = st.next_nc_hex()
        cnonce = st.cnonce

        algo = (getattr(chall, "algorithm", "") or "MD5").upper()
        H = hashlib.sha256 if "SHA-256" in algo else hashlib.md5

        def Hhex(s: str) -> str:
            return H(s.encode("utf-8")).hexdigest()

        realm = chall.realm
        nonce = chall.nonce

        ha1 = Hhex(f"{self.username}:{realm}:{self.password}")
        ha2 = Hhex(f"{method}:{uri}")
        response = Hhex(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}")

        base = (
            f'Digest username="{self.username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", algorithm={algo}, response="{response}", '
            f'qop={qop}, nc={nc}, cnonce="{cnonce}"'
        )
        if getattr(chall, "opaque", None) is not None:
            base += f', opaque="{chall.opaque}"'
        return base

    def _maybe_refresh_digest_challenge(self, resp: HttpResponse) -> bool:
        www = resp.header_all("WWW-Authenticate")
        h = _pick_digest_header(www)
        if not h or "digest" not in h.lower():
            return False

        try:
            new_chall = parse_www_authenticate_digest(h)
        except Exception:
            return False

        if self._digest_state is None:
            self._digest_state = _DigestState(challenge=new_chall)
            return True

        old = self._digest_state.challenge
        if (old.nonce != new_chall.nonce) or (old.realm != new_chall.realm) or (old.algorithm != new_chall.algorithm):
            self._digest_state.reset(new_chall)
        else:
            self._digest_state.challenge = new_chall
        return True

    def _auth_headers(self, method: str, url: str) -> dict[str, str]:
        scheme = (self.auth_scheme or "").lower().strip()

        if scheme == "none":
            return {}

        if scheme == "basic":
            token = base64.b64encode(f"{self.username}:{self.password}".encode()).decode()
            return {"Authorization": f"Basic {token}"}

        if scheme == "digest":
            return {"Authorization": self._build_digest_authz(method, url)}

        raise ApiError(kind="param", message="invalid auth_scheme", detail=scheme)

    # -------------------------
    # main request
    # -------------------------
    def _request(self, tail: str) -> HttpResponse:
        url = self._make_url(tail)
        log.info("[REQ] GET %s", url)

        scheme = (self.auth_scheme or "").lower().strip()
        auth = self._auth_headers("GET", url) if scheme != "none" else {}
        headers = self._merge_headers(url, auth)

        resp = self._request_raw(url, headers=headers)
        log.info("[RESP] %s %s", resp.status, url)

        if scheme == "digest" and resp.status == 401:
            if self._maybe_refresh_digest_challenge(resp):
                auth2 = self._auth_headers("GET", url)
                headers2 = self._merge_headers(url, auth2)
                resp2 = self._request_raw(url, headers=headers2)
                log.info("[RESP-RETRY] %s %s", resp2.status, url)
                return resp2

        return resp

    # -------------------------
    # ReadParam
    # -------------------------
    def read_param_text(self, key: str) -> str:
        tail = f"ReadParam?action=readparam&{quote(key, safe='')}=0"
        resp = self._request(tail)

        if resp.status == 200:
            if _looks_like_auth_error(resp.body):
                raise ApiError(
                    kind="auth",
                    message="authentication failed",
                    status_code=200,
                    detail=(resp.body or "")[:200],
                )
            return resp.body or ""

        if resp.status in (401, 403):
            raise ApiError(kind="auth", message="authentication failed", status_code=resp.status, detail=(resp.body or "")[:200])

        raise ApiError(kind="http", message="read_param failed", status_code=resp.status, detail=(resp.body or "")[:200])

    def read_param_value(self, key: str) -> str:
        txt = self.read_param_text(key)
        prefix = key + "="
        for line in (txt or "").splitlines():
            if line.startswith(prefix):
                return line.split("=", 1)[1].strip()
        return ""

    def read_params_text(self, keys: list[str]) -> str:
        if not keys:
            return ""

        parts: list[str] = []
        for k in keys:
            parts.append(f"{quote(k, safe='')}=0")

        tail = "ReadParam?action=readparam&" + "&".join(parts)
        resp = self._request(tail)

        if resp.status == 200:
            return resp.body or ""

        if resp.status in (401, 403):
            raise ApiError(
                kind="auth",
                message="authentication failed",
                status_code=resp.status,
                detail=(resp.body or "")[:200],
            )

        raise ApiError(
            kind="http",
            message="read_params failed",
            status_code=resp.status,
            detail=(resp.body or "")[:200],
        )

    # -------------------------
    # WriteParam
    # -------------------------
    def write_param_raw(self, kv: dict[str, str]) -> HttpResponse:
        if not kv:
            raise ApiError(kind="param", message="write_param_raw: empty kv")

        parts: list[str] = ["WriteParam?action=writeparam"]
        for k, v in kv.items():
            kq = quote(str(k), safe="")
            vq = quote(str(v), safe=".")  # IP '.' 유지
            parts.append(f"{kq}={vq}")

        tail = "&".join(parts)
        resp = self._request(tail)

        if resp.status == 200 and _looks_like_auth_error(resp.body):
            raise ApiError(
                kind="auth",
                message="authentication failed",
                status_code=200,
                detail=(resp.body or "")[:200],
            )

        return resp

    # -------------------------
    # GetState
    # -------------------------
    def get_state_text(self, action: str, params: dict[str, str]) -> str:
        if not action:
            raise ApiError(kind="param", message="get_state_text: empty action")

        parts = [f"GetState?action={quote(action, safe='')}"]
        for k, v in (params or {}).items():
            parts.append(f"{quote(str(k), safe='')}={quote(str(v), safe='.')}")

        tail = "&".join(parts)
        resp = self._request(tail)

        if resp.status == 200:
            if _looks_like_auth_error(resp.body):
                raise ApiError(
                    kind="auth",
                    message="authentication failed",
                    status_code=200,
                    detail=(resp.body or "")[:200],
                )
            return resp.body or ""

        if resp.status in (401, 403):
            raise ApiError(
                kind="auth",
                message="authentication failed",
                status_code=resp.status,
                detail=(resp.body or "")[:200],
            )

        raise ApiError(
            kind="http",
            message="get_state failed",
            status_code=resp.status,
            detail=(resp.body or "")[:200],
        )

    def get_state_values_text(self, action: str, keys: list[str]) -> str:
        """
        예) action=getrate, keys=["GRS_VENCFRAME1", "GRS_VENCBITRATE1", ...]
        -> GetState?action=getrate&KEY=0&KEY2=0...
        """
        if not keys:
            return ""
        params = {k: "0" for k in keys}
        return self.get_state_text(action=action, params=params)

    # -------------------------
    # absolute GET
    # -------------------------
    def get_abs(self, path: str) -> HttpResponse:
        url = self._make_abs_url(path)
        log.info("[REQ] GET %s", url)

        scheme = (self.auth_scheme or "").lower().strip()
        auth = self._auth_headers("GET", url) if scheme != "none" else {}
        headers = self._merge_headers(url, auth)

        resp = self._request_raw(url, headers=headers)
        log.info("[RESP] %s %s", resp.status, url)

        if scheme == "digest" and resp.status == 401:
            if self._maybe_refresh_digest_challenge(resp):
                auth2 = self._auth_headers("GET", url)
                headers2 = self._merge_headers(url, auth2)
                resp2 = self._request_raw(url, headers=headers2)
                log.info("[RESP-RETRY] %s %s", resp2.status, url)
                return resp2

        return resp

    def _looks_like_auth_error_body(self, body: str) -> bool:
        if not body:
            return False
        b = body.lower()
        return (
            "authentication error" in b
            or "access denied" in b
            or "<h2>authentication error" in b
            or "ss denied" in b
        )