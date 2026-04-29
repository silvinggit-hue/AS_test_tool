from __future__ import annotations

import logging
import ssl
import time
from dataclasses import dataclass
from typing import Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from http.client import RemoteDisconnected

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context

from config.settings import RetrySettings
from models.dto import ApiError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: str
    headers: dict[str, str]

    def header_all(self, name: str) -> list[str]:
        k = name.lower()
        out: list[str] = []
        for hk, hv in (self.headers or {}).items():
            if hk.lower() == k and hv:
                out.append(hv)
        return out


def _build_ssl_context(verify_tls: bool) -> ssl.SSLContext:
    if verify_tls:
        ctx = ssl.create_default_context()
    else:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    # 구형 장비 TLS 호환(SECLEVEL 완화)
    try:
        ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
    except Exception:
        pass

    return ctx


def http_get(
    *,
    url: str,
    headers: Optional[dict[str, str]] = None,
    timeout_sec: float = 6.0,
    verify_tls: bool = False,
    read_body: bool = True,
) -> HttpResponse:
    hdrs = headers or {}

    if "User-Agent" not in hdrs:
        hdrs = dict(hdrs)
        hdrs["User-Agent"] = "AS_test_tool_v4/urllib"

    req = Request(url=url, method="GET", headers=hdrs)
    ctx = _build_ssl_context(bool(verify_tls))

    try:
        with urlopen(req, timeout=float(timeout_sec), context=ctx) as resp:
            status = int(getattr(resp, "status", 200))

            resp_headers: dict[str, str] = {}
            for k in resp.headers.keys():
                try:
                    v = resp.headers.get(k)
                    if v is not None:
                        resp_headers[str(k)] = str(v)
                except Exception:
                    pass

            body = ""
            if read_body:
                data = resp.read() if status == 200 else resp.read(8192)
                try:
                    body = data.decode("utf-8", errors="replace")
                except Exception:
                    body = str(data)

            return HttpResponse(status=status, body=body, headers=resp_headers)

    except HTTPError as e:
        status = int(getattr(e, "code", 0) or 0)
        resp_headers: dict[str, str] = {}
        try:
            for k in e.headers.keys():
                v = e.headers.get(k)
                if v is not None:
                    resp_headers[str(k)] = str(v)
        except Exception:
            pass

        body = ""
        if read_body:
            try:
                data = e.read(8192)
                body = data.decode("utf-8", errors="replace")
            except Exception:
                body = ""

        return HttpResponse(status=status, body=body, headers=resp_headers)

    except ssl.SSLError as e:
        raise ApiError(kind="ssl", message="ssl handshake error", detail=str(e))
    except RemoteDisconnected as e:
        raise ApiError(kind="network", message="remote disconnected", detail=str(e))
    except URLError as e:
        raise ApiError(kind="network", message="network error", detail=str(e))
    except TimeoutError as e:
        raise ApiError(kind="timeout", message="timeout", detail=str(e))
    except Exception as e:
        raise ApiError(kind="network", message="request failed", detail=str(e))


def http_get_with_retry(
    *,
    url: str,
    headers: Optional[dict[str, str]] = None,
    timeout_sec: float = 6.0,
    verify_tls: bool = False,
    read_body: bool = True,
    retry: Optional[RetrySettings] = None,
) -> HttpResponse:
    retry = retry or RetrySettings()
    attempts = max(1, int(getattr(retry, "max_attempts", 1) or 1))

    last: Optional[ApiError] = None

    for i in range(attempts):
        try:
            return http_get(
                url=url,
                headers=headers,
                timeout_sec=timeout_sec,
                verify_tls=verify_tls,
                read_body=read_body,
            )
        except ApiError as e:
            last = e

            if i < attempts - 1 and e.kind in ("network", "timeout"):
                backoff = float(retry.backoff_base_sec) * (2 ** i)
                time.sleep(max(0.0, backoff))

    raise last or ApiError(kind="network", message="request failed")


class _TlsCompatAdapter(HTTPAdapter):
    def __init__(self, verify_tls: bool, **kwargs):
        self._verify_tls = bool(verify_tls)
        super().__init__(**kwargs)

    def init_poolmanager(self, connections, maxsize, block=False, **pool_kwargs):
        ctx = create_urllib3_context()
        if not self._verify_tls:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        try:
            ctx.set_ciphers("DEFAULT:@SECLEVEL=1")
        except Exception:
            pass
        pool_kwargs["ssl_context"] = ctx
        return super().init_poolmanager(connections, maxsize, block=block, **pool_kwargs)


def _build_session(verify_tls: bool) -> requests.Session:
    sess = requests.Session()
    adapter = _TlsCompatAdapter(
        verify_tls=verify_tls,
        pool_connections=10,
        pool_maxsize=10,
        max_retries=0,
    )
    sess.mount("https://", adapter)
    sess.mount("http://", adapter)
    return sess