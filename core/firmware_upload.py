from __future__ import annotations

import base64
import logging
import os
import random
import time
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import requests

from config.settings import RetrySettings
from core.digest import parse_www_authenticate_digest, build_digest_authorization
from core.http_client import _build_session
from models.dto import ApiError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadResult:
    status: int
    body_tail: str


def _flip_scheme(base_url: str) -> str:
    if base_url.startswith("https://"):
        return "http://" + base_url[len("https://") :]
    if base_url.startswith("http://"):
        return "https://" + base_url[len("http://") :]
    return base_url


def _is_remote_closed(detail: str) -> bool:
    d = (detail or "").lower()
    return (
        "remote end closed connection without response" in d
        or "remote disconnected" in d
        or "remotedisconnected" in d
        or "connection was closed" in d
        or "connection reset by peer" in d
        or "broken pipe" in d
        or "eof occurred in violation of protocol" in d
        or "read timed out" in d
    )


def _sleep_backoff(attempt: int, retry: RetrySettings) -> None:
    sleep_s = float(retry.backoff_base_sec) * (2 ** (attempt - 1)) + random.random() * float(retry.backoff_jitter_sec)
    time.sleep(max(0.0, sleep_s))


def _as_api_error(e: Exception) -> ApiError:
    if isinstance(e, requests.exceptions.SSLError):
        return ApiError(kind="ssl", message="ssl error", detail=str(e))
    if isinstance(e, requests.Timeout):
        return ApiError(kind="timeout", message="timeout", detail=str(e))
    if isinstance(e, requests.RequestException):
        return ApiError(kind="network", message="network error", detail=str(e))
    return ApiError(kind="network", message="unexpected network error", detail=str(e))


def _normalize_root_path(root_path: str) -> str:
    rp = (root_path or "").strip()
    if not rp:
        return ""
    if not rp.startswith("/"):
        rp = "/" + rp
    if not rp.endswith("/"):
        rp += "/"
    return rp


def upload_firmware_progress_html(
    *,
    base_url: str,
    username: str,
    password: str,
    auth_scheme: str,  # "digest" | "basic" | "none"
    verify_tls: bool,
    timeout_sec: float,
    retry: Optional[RetrySettings],
    filepath: str,
    root_path: str = "",
    **_ignored,
) -> UploadResult:
    retry = retry or RetrySettings()

    path = (filepath or "").strip()
    if not path:
        raise ApiError(kind="param", message="firmware path empty")
    if not os.path.exists(path):
        raise ApiError(kind="param", message="firmware file not found", detail=path)

    filename = os.path.basename(path)

    base_candidates = [base_url]
    flipped = _flip_scheme(base_url)
    if flipped != base_url:
        base_candidates.append(flipped)

    rp = _normalize_root_path(root_path)
    upload_paths = ["progress.html"]
    if rp:
        upload_paths.append(rp + "progress.html")

    sess = _build_session(bool(verify_tls))

    last_err: Optional[ApiError] = None

    for base in base_candidates:
        for upath in upload_paths:
            upload_url = urllib.parse.urljoin(base.rstrip("/") + "/", upath.lstrip("/"))
            log.info("[FW] upload try url=%s", upload_url)

            for attempt in range(1, max(1, int(retry.max_attempts)) + 1):
                try:
                    scheme = (auth_scheme or "").lower().strip()

                    common_headers: dict[str, str] = {
                        "User-Agent": "TTA-AUTO/FW-UPLOAD",
                        "Connection": "close",
                    }

                    authz: Optional[str] = None

                    if scheme == "basic":
                        token = base64.b64encode(f"{username}:{password}".encode()).decode()
                        authz = f"Basic {token}"

                    elif scheme == "digest":
                        try:
                            r0 = sess.get(
                                upload_url,
                                headers=common_headers,
                                timeout=float(timeout_sec),
                                allow_redirects=False,
                                verify=bool(verify_tls),
                            )
                        except Exception as e:
                            raise _as_api_error(e)

                        st0 = int(r0.status_code)

                        if st0 not in (200, 401):
                            raise ApiError(
                                kind="http",
                                message="unexpected progress.html status",
                                status_code=st0,
                            )

                        if st0 == 401:
                            www = (r0.headers.get("WWW-Authenticate") or "").strip()
                            if not www:
                                raise ApiError(kind="auth", message="digest challenge missing", status_code=401)

                            chall = parse_www_authenticate_digest(www)
                            authz = build_digest_authorization(
                                method="POST",
                                url=upload_url,
                                username=username,
                                password=password,
                                challenge=chall,
                            )

                    elif scheme == "none":
                        authz = None
                    else:
                        raise ApiError(kind="param", message="invalid auth_scheme", detail=str(auth_scheme))

                    headers = dict(common_headers)
                    if authz:
                        headers["Authorization"] = authz

                    post_timeout = max(float(timeout_sec), 120.0)

                    with open(path, "rb") as f:
                        files = {"upgrade": (filename, f, "application/octet-stream")}
                        data = {"MAX_FILE_SIZE": "30000000"}

                        try:
                            r = sess.post(
                                upload_url,
                                headers=headers,
                                data=data,
                                files=files,
                                timeout=post_timeout,
                                allow_redirects=False,
                                verify=bool(verify_tls),
                            )
                        except Exception as e:
                            ae = _as_api_error(e)
                            if ae.kind in ("network", "ssl", "timeout") and _is_remote_closed(ae.detail or ""):
                                log.warning(
                                    "[FW] remote closed connection after upload (assume reboot) url=%s",
                                    upload_url,
                                )
                                return UploadResult(
                                    status=204,
                                    body_tail="remote closed connection (assumed reboot)",
                                )
                            raise ae

                    st = int(r.status_code)
                    text = r.text or ""

                    if st in (200, 204, 302, 303):
                        return UploadResult(status=st, body_tail=text[-300:])

                    if st in (401, 403):
                        raise ApiError(
                            kind="auth",
                            message="authentication failed",
                            status_code=st,
                            detail=text[:200],
                        )

                    raise ApiError(kind="http", message="upload failed", status_code=st, detail=text[:200])

                except ApiError as e:
                    last_err = e

                    if attempt < int(retry.max_attempts) and e.kind in ("network", "timeout"):
                        log.warning("[FW] retry kind=%s attempt=%s url=%s", e.kind, attempt, upload_url)
                        _sleep_backoff(attempt, retry)
                        continue

                    break

    raise last_err or ApiError(kind="network", message="upload failed")