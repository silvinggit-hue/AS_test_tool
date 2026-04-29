from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass
from urllib.parse import quote

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from core.cam_api_client import CamApiClient
from models.dto import ApiError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PasswordChangeResult:
    ok: bool
    used_password: str
    changed_to: str
    detail: str | None = None


def tencryption_js(s: str) -> str:
    if not s:
        s = ""
    return base64.b64encode(s.encode("utf-8")).decode("ascii")


def tencode_url_js(b64_str: str) -> str:
    if not b64_str:
        return ""
    converted = b64_str.replace("+", "-").replace("/", "_").rstrip("=")
    if len(converted) == 0:
        return ""
    first = b64_str[len(converted) - 1]
    second = b64_str[len(converted) // 2]
    return first + second + converted


def rsa_encrypt_with_pem(public_key_pem: str, msg: str) -> str:
    key = serialization.load_pem_public_key(public_key_pem.encode())
    encrypted = key.encrypt(msg.encode(), padding.PKCS1v15())
    return base64.b64encode(encrypted).decode()


def _encode_component(s: str) -> str:
    return quote(s, safe="")


def _write_usr_modpass(cli: CamApiClient, username: str, enc_old: str, enc_new: str) -> str | None:
    msg = (
        "USR_MODPASS="
        + quote(username, safe="")
        + ":"
        + _encode_component(enc_old)
        + ":"
        + _encode_component(enc_new)
    )

    tail = f"WriteParam?action=writeparam&{msg}"
    resp = cli._request(tail)  # pylint: disable=protected-access

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
        message="password change rejected",
        status_code=resp.status,
        detail=(resp.body or "")[:300],
    )


def _verify_new_password(
    *,
    base_url: str,
    root_path: str,
    username: str,
    new_password: str,
    auth_scheme: str,
    timeout_sec: float,
    verify_tls: bool,
) -> None:
    cli_new = CamApiClient(
        base_url=base_url,
        root_path=root_path,
        username=username,
        password=new_password,
        auth_scheme=auth_scheme,
        timeout=_SimpleTimeout(connect_sec=timeout_sec, read_sec=timeout_sec),
        retry=_SimpleRetry(max_attempts=1),
        verify_tls=verify_tls,
    )

    last_err: Exception | None = None
    for _ in range(8):
        try:
            _ = cli_new.read_param_text("SYS_VERSION")
            return
        except Exception as e:
            last_err = e
            try:
                _ = cli_new.read_param_text("ETC_MIN_PASSWORD_LEN")
                return
            except Exception as e2:
                last_err = e2
                time.sleep(0.6)

    raise ApiError(
        kind="auth",
        message="verify failed after password change",
        status_code=401,
        detail=str(last_err)[:300] if last_err else None,
    )


def change_password_if_needed(
    *,
    base_url: str,
    root_path: str,
    username: str,
    old_password: str,
    new_password: str,
    timeout_sec: float = 6.0,
    verify_tls: bool = False,
    auth_scheme: str = "digest",
) -> None:
    cli_old = CamApiClient(
        base_url=base_url,
        root_path=root_path,
        username=username,
        password=old_password,
        auth_scheme=auth_scheme,
        timeout=_SimpleTimeout(connect_sec=timeout_sec, read_sec=timeout_sec),
        retry=_SimpleRetry(max_attempts=1),
        verify_tls=verify_tls,
    )

    crypto_type = 0
    public_key_pem = ""

    try:
        txt = cli_old.read_param_text("SYS_PUBLIC_KEY_CRYPTO")
        crypto_type = 1 if "SYS_PUBLIC_KEY_CRYPTO=1" in (txt or "") else 0
    except Exception:
        crypto_type = 0

    if crypto_type == 1:
        try:
            txt2 = cli_old.read_param_text("SYS_PUBLIC_KEY")
            if "SYS_PUBLIC_KEY=" in (txt2 or ""):
                raw = txt2.split("SYS_PUBLIC_KEY=", 1)[1].strip()
                if "BEGIN PUBLIC KEY" in raw:
                    public_key_pem = raw
                else:
                    public_key_pem = "-----BEGIN PUBLIC KEY-----\n" + raw + "\n-----END PUBLIC KEY-----"
        except Exception:
            public_key_pem = ""

    if crypto_type == 1 and public_key_pem:
        try:
            enc_old = rsa_encrypt_with_pem(public_key_pem, old_password)
            enc_new = rsa_encrypt_with_pem(public_key_pem, new_password)

            log.info("[MODPASS] RSA call")
            body = _write_usr_modpass(cli_old, username, enc_old, enc_new)

            if body is None or (body or "").lstrip().lower().startswith("ok"):
                _verify_new_password(
                    base_url=base_url,
                    root_path=root_path,
                    username=username,
                    new_password=new_password,
                    auth_scheme=auth_scheme,
                    timeout_sec=timeout_sec,
                    verify_tls=verify_tls,
                )
                return

            log.info("[MODPASS] RSA rejected; fallback to TENC")

        except Exception as e:
            log.info("[MODPASS] RSA failed (%s); fallback to TENC", e)

    b64_old = tencryption_js(old_password)
    b64_new = tencryption_js(new_password)
    enc_old = tencode_url_js(b64_old)
    enc_new = tencode_url_js(b64_new)

    log.info("[MODPASS] TENC call")
    body = _write_usr_modpass(cli_old, username, enc_old, enc_new)

    if body is not None and not (body or "").lstrip().lower().startswith("ok"):
        raise ApiError(kind="http", message="password change rejected", detail=(body or "")[:300])

    _verify_new_password(
        base_url=base_url,
        root_path=root_path,
        username=username,
        new_password=new_password,
        auth_scheme=auth_scheme,
        timeout_sec=timeout_sec,
        verify_tls=verify_tls,
    )


def try_recover_password(
    *,
    base_url: str,
    root_path: str,
    username: str,
    password_candidates: list[str],
    target_password: str,
    timeout_sec: float = 6.0,
    verify_tls: bool = False,
    auth_scheme: str = "digest",
) -> PasswordChangeResult:
    if not password_candidates:
        raise ApiError(kind="param", message="password_candidates empty")
    if not target_password:
        raise ApiError(kind="param", message="target_password empty")

    last_err: ApiError | None = None

    for old_pw in password_candidates:
        try:
            change_password_if_needed(
                base_url=base_url,
                root_path=root_path,
                username=username,
                old_password=old_pw,
                new_password=target_password,
                timeout_sec=timeout_sec,
                verify_tls=verify_tls,
                auth_scheme=auth_scheme,
            )
            return PasswordChangeResult(ok=True, used_password=old_pw, changed_to=target_password)

        except ApiError as e:
            last_err = e
            log.warning(
                "[PW] recover fail old=%s kind=%s status=%s msg=%s",
                "*" * len(old_pw),
                e.kind,
                e.status_code,
                e.message,
            )
            continue
        except Exception as e:
            last_err = ApiError(kind="network", message="password recover failed", detail=str(e))
            continue

    raise last_err or ApiError(kind="auth", message="password recover failed")


@dataclass(frozen=True)
class _SimpleTimeout:
    connect_sec: float = 6.0
    read_sec: float = 6.0


@dataclass(frozen=True)
class _SimpleRetry:
    max_attempts: int = 1
    retry_on_status: tuple[int, ...] = ()
    backoff_base_sec: float = 0.1
    backoff_jitter_sec: float = 0.05