from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from core.http_client import http_get_with_retry
from models.dto import ApiError

log = logging.getLogger(__name__)

_ROOT_CANDIDATES = (
    "/httpapx/",
    "/httpapi/",
    "/webapi/",
)


@dataclass(frozen=True)
class ProbeResult:
    base_url: str          # e.g. https://ip:443 or http://ip:80
    root_path: str         # e.g. /httpapx/
    auth_scheme: str       # "none" | "digest" | "basic"
    flavor: str = "legacy"  # "legacy" | "security3" (best-effort)


def _normalize_root(root: str) -> str:
    root = (root or "").strip()
    if not root.startswith("/"):
        root = "/" + root
    if not root.endswith("/"):
        root += "/"
    return root


def _contains_digest(www: list[str]) -> bool:
    return any(h and "digest" in h.lower() for h in (www or []))


def _contains_basic(www: list[str]) -> bool:
    return any(h and "basic" in h.lower() for h in (www or []))


def _port_candidates(port: int) -> list[int]:
    """
    port == 0: AUTO
    """
    try:
        p = int(port)
    except Exception:
        p = 0

    if p <= 0:
        return [443, 80, 8443]

    out = [p]
    if p != 443:
        out.append(443)
    if p != 80:
        out.append(80)
    if p != 8443:
        out.append(8443)
    return out


def _base_candidates(ip: str, port: int) -> list[str]:
    out: list[str] = []
    for p in _port_candidates(port):
        if p in (443, 8443):
            out.append(f"https://{ip}:{p}")
            out.append(f"http://{ip}:{p}")
        else:
            out.append(f"http://{ip}:{p}")
            out.append(f"https://{ip}:{p}")

    uniq: list[str] = []
    for u in out:
        if u not in uniq:
            uniq.append(u)
    return uniq


def probe_camera(
    ip: str,
    port: int,
    timeout_sec: float = 2.5,
    verify_tls: bool = False,
) -> ProbeResult:
    """
    - root 후보(/httpapi/, /httpapx/, /webapi/) 탐색
    - auth scheme 판별 (none/basic/digest)
    - 일부 장비는 ETC_MIN_PASSWORD_LEN에서 400을 반환해 SYS_VERSION으로 1회 폴백
    - 보안3.0: SYS_PUBLIC_KEY=0 이 무인증 200이면 security3로 판단
    - port==0(AUTO) 지원
    """
    bases = _base_candidates(ip, port)

    root_candidates = (
        "/httpapi/",
        "/httpapx/",
        "/webapi/",
    )

    test_q_primary = "ETC_MIN_PASSWORD_LEN=0"
    test_q_fallback = "SYS_VERSION=0"
    test_q_security3 = "SYS_PUBLIC_KEY=0"

    last_err: Optional[ApiError] = None

    for base in bases:
        base_is_https = base.lower().startswith("https://")

        for root in root_candidates:
            root_norm = _normalize_root(root)

            def _try(q: str):
                url = f"{base}{root_norm}ReadParam?action=readparam&{q}"
                return http_get_with_retry(
                    url=url,
                    timeout_sec=timeout_sec,
                    verify_tls=verify_tls,
                )

            try:
                resp = _try(test_q_primary)
                sc = resp.status

                if sc == 400:
                    log.info(
                        "[PROBE] got 400 on primary key; fallback to SYS_VERSION base=%s root=%s",
                        base,
                        root_norm,
                    )
                    resp2 = _try(test_q_fallback)
                    sc2 = resp2.status

                    if sc2 in (400, 401, 403):
                        log.info("[PROBE] security3 candidate: %s", base)
                        resp3 = _try(test_q_security3)
                        if resp3.status == 200:
                            log.info("[PROBE] OK (security3 none) base=%s root=%s", base, root_norm)
                            return ProbeResult(base_url=base, root_path=root_norm, auth_scheme="none", flavor="security3")

                    resp = resp2
                    sc = sc2

                if sc == 200:
                    log.info("[PROBE] OK (none) base=%s root=%s", base, root_norm)
                    return ProbeResult(base_url=base, root_path=root_norm, auth_scheme="none", flavor="legacy")

                if sc in (401, 403):
                    www = resp.header_all("WWW-Authenticate") if hasattr(resp, "header_all") else []
                    if _contains_digest(www):
                        log.info("[PROBE] OK (digest) base=%s root=%s status=%s", base, root_norm, sc)
                        return ProbeResult(base_url=base, root_path=root_norm, auth_scheme="digest", flavor="legacy")
                    if _contains_basic(www):
                        log.info("[PROBE] OK (basic) base=%s root=%s status=%s", base, root_norm, sc)
                        return ProbeResult(base_url=base, root_path=root_norm, auth_scheme="basic", flavor="legacy")

                    detail = "; ".join([w for w in (www or []) if w])[:300]
                    raise ApiError(kind="compat", message="unsupported auth scheme", status_code=sc, detail=detail)

                if sc == 404:
                    continue

                raise ApiError(kind="http", message="probe failed", status_code=sc, detail=(resp.body or "")[:200])

            except ApiError as e:
                last_err = e
                log.warning(
                    "[PROBE] fail kind=%s base=%s root=%s msg=%s detail=%s",
                    e.kind,
                    base,
                    root_norm,
                    e.message,
                    (e.detail or "")[:200],
                )

                if base_is_https and e.kind == "ssl":
                    break

                continue

    raise last_err or ApiError(kind="network", message="probe failed", detail="no response")