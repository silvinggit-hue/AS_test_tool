from __future__ import annotations

import logging
import re
import time
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

from config.settings import AppSettings
from models.dto import ApiError, Phase1Response

from core.probe import probe_camera
from core.cam_api_client import CamApiClient
from core.password_change import try_recover_password, rsa_encrypt_with_pem, tencode_url_js

log = logging.getLogger(__name__)

PASSWORD_TEST_KEY = "ETC_MIN_PASSWORD_LEN"
ESSENTIAL_KEYS = ("SYS_VERSION", "SYS_MODELNAME", "SYS_BOARDID")
SEC3_PUBLIC_KEY = "SYS_PUBLIC_KEY"

_PEM_RE = re.compile(
    r"-----BEGIN PUBLIC KEY-----\s*(.*?)\s*-----END PUBLIC KEY-----",
    re.DOTALL,
)


@dataclass(frozen=True)
class Phase1Request:
    ip: str
    port: int = 80

    # legacy/basic/TTA
    username: str = "admin"
    password: str = "admin"
    password_candidates: Optional[list[str]] = None
    target_password: str = "Truen1309!"
    verify_tls: bool = False

    # security3 bootstrap
    sec3_username: str = "TruenAS"
    allowed_ip: str = "192.168.10.2"


def _detect_local_ip(target_host: str) -> str:
    """
    대상 장비와 통신에 사용되는 로컬 IP를 감지한다.
    """
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect((target_host, 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def _normalize_public_key_pem(readparam_text: str) -> str:
    """
    ReadParam(SYS_PUBLIC_KEY) 응답에서 PEM 블록을 정규화한다.

    - SYS_PUBLIC_KEY= prefix 제거
    - BEGIN/END 사이 base64만 추출
    - 64자 라인으로 재구성
    """
    if not readparam_text:
        return ""

    s = readparam_text.replace("\r", "").strip()
    if "SYS_PUBLIC_KEY=" in s:
        s = s.split("SYS_PUBLIC_KEY=", 1)[1].strip()

    m = _PEM_RE.search(s)
    if m:
        b64 = re.sub(r"\s+", "", m.group(1))
    else:
        b64 = re.sub(r"\s+", "", s)

    if not b64 or len(b64) < 80:
        return ""

    lines = [b64[i : i + 64] for i in range(0, len(b64), 64)]
    pem = "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----\n"
    return pem


@dataclass(frozen=True)
class _TmpTimeout:
    connect_sec: float
    read_sec: float | None = None

    def __post_init__(self):
        if self.read_sec is None:
            object.__setattr__(self, "read_sec", self.connect_sec)


@dataclass(frozen=True)
class _TmpRetry:
    max_attempts: int = 1
    backoff_base_sec: float = 0.1
    backoff_jitter_sec: float = 0.05
    retry_on_status: tuple[int, ...] = ()


def _sec3_usr_add_noauth(
    *,
    base_url: str,
    root_path: str,
    new_user: str,
    new_pass: str,
    verify_tls: bool,
    timeout_sec: float,
) -> CamApiClient:
    cli_none = CamApiClient(
        base_url=base_url,
        root_path=root_path,
        username="",
        password="",
        auth_scheme="none",
        timeout=_TmpTimeout(timeout_sec),
        retry=_TmpRetry(),
        verify_tls=verify_tls,
    )

    # 1) 공개키 읽기
    txt = cli_none.read_param_text(SEC3_PUBLIC_KEY)
    pem = _normalize_public_key_pem(txt)

    if not pem:
        raise ApiError(kind="compat", message="security3 public key missing/invalid")

    # 2) 비밀번호만 RSA 암호화
    cipher_b64 = rsa_encrypt_with_pem(pem, new_pass)

    # 3) base64를 1회 percent-encoding
    enc_cipher = quote(cipher_b64, safe="")

    tail = (
        f"WriteParam?action=writeparam&USR_ADD="
        f"{quote(new_user, safe='')}:{enc_cipher}:0"
    )

    resp = cli_none._request(tail)
    body = (resp.body or "").strip()

    if resp.status == 200 and body.lower().startswith("ok"):
        log.info("[SEC3] USR_ADD OK")
        return cli_none

    raise ApiError(
        kind="http",
        message="USR_ADD failed",
        status_code=resp.status,
        detail=body[:300],
    )

    # NOTE: 유지 목적의 도달 불가 코드(기존 구조 보존)
    # raise last_err or ApiError(kind="http", message="USR_ADD failed")


def _sec3_write_remoteaccess_first(
    *,
    base_url: str,
    root_path: str,
    shared_session_client: CamApiClient,
    username: str,
    password: str,
    allowed_ip: str,
    verify_tls: bool,
    timeout_sec: float,
) -> CamApiClient:
    """
    Security3 단계 2:
    - Digest로 "/"에 1회 접속하여 세션 안정화
    - REMOTEACCESS(IP 허용) WriteParam 수행
    """
    cli = CamApiClient(
        base_url=base_url,
        root_path=root_path,
        username=username,
        password=password,
        auth_scheme="digest",
        timeout=_TmpTimeout(timeout_sec),
        retry=_TmpRetry(),
        verify_tls=verify_tls,
    ).with_shared_session(shared_session_client._get_session())  # pylint: disable=protected-access

    # USR_ADD 직후 일시적으로 응답이 지연될 수 있음
    home_ok = False
    last_exc = None

    for _ in range(10):
        try:
            r_home = cli.get_abs("/")
            if r_home.status == 200:
                home_ok = True
                break
        except Exception as e:
            last_exc = e

        time.sleep(0.5)

    if not home_ok:
        raise ApiError(
            kind="auth",
            message="digest home failed after security3 bootstrap",
            detail=str(last_exc),
        )

    # REMOTEACCESS 설정 (00만 활성)
    ip0 = (allowed_ip or "").strip() or "192.168.10.2"
    kv: dict[str, str] = {}
    for i in range(20):
        kv[f"ETC_REMOTEACCESS_IP{i:02d}"] = ip0 if i == 0 else "0.0.0.0"
        kv[f"ETC_REMOTEACCESS_USE{i:02d}"] = "1" if i == 0 else "0"

    resp = cli.write_param_raw(kv)
    body = (resp.body or "").strip()

    if resp.status != 200 or (body and not body.lower().startswith("ok")):
        raise ApiError(
            kind="http",
            message="remoteaccess write failed",
            status_code=resp.status,
            detail=body[:300],
        )

    log.info("[SEC3] REMOTEACCESS OK (body=%s)", body or "Ok")
    return cli


def _read_essentials_best_effort(cli: CamApiClient) -> dict[str, str]:
    """
    Security3 정책 단계에서 일부 ReadParam이 400을 반환할 수 있으므로,
    가능한 키만 읽고 실패는 빈 값으로 둔다.
    """
    out: dict[str, str] = {}
    for k in ESSENTIAL_KEYS:
        try:
            out[k] = cli.read_param_value(k)
        except Exception:
            out[k] = ""
    return out


def _is_policy_block_for_default_state(e: ApiError) -> bool:
    if e.kind not in ("http", "auth", "compat"):
        return False

    sc = e.status_code
    if sc not in (400, 401, 403, None):
        return False

    d = (e.detail or "").lower()
    if any(x in d for x in ("bad request", "document error", "access error", "parse error")):
        return True
    if sc == 401:
        return True
    if sc == 403 and any(x in d for x in ("access", "forbidden", "policy")):
        return True

    return False


def run_phase1(req: Phase1Request, settings: Optional[AppSettings] = None) -> Phase1Response:
    """
    - probe로 base_url/root_path/auth_scheme/flavor 판별
    - security3:
        (no-auth) SYS_PUBLIC_KEY 읽기 -> (no-auth) USR_ADD ->
        (digest) "/" -> (digest) REMOTEACCESS -> (digest) essentials 확보
    - legacy/basic/TTA:
        root_path 후보를 순차 시도하여 유효 root 확정
    """
    settings = settings or AppSettings.load()

    try:
        pr = probe_camera(
            ip=req.ip,
            port=req.port,
            timeout_sec=float(settings.timeout.connect_sec),
            verify_tls=bool(req.verify_tls),
        )

        base_url = pr.base_url
        probed_root = pr.root_path
        auth_scheme = pr.auth_scheme
        flavor = getattr(pr, "flavor", "legacy")

        # ============================
        # Security 3.0
        # ============================
        if flavor == "security3":
            essentials: dict[str, str] = {}
            last_exc: Optional[Exception] = None

            # 1) USR_ADD (no-auth)
            cli_none = _sec3_usr_add_noauth(
                base_url=base_url,
                root_path=probed_root,
                new_user=req.sec3_username,
                new_pass=req.target_password,
                verify_tls=bool(req.verify_tls),
                timeout_sec=float(settings.timeout.read_sec),
            )

            # 2) Digest "/" + REMOTEACCESS
            allowed_ip = _detect_local_ip(req.ip)
            log.info("[SEC3] auto-detected local IP = %s", allowed_ip)
            cli_digest = _sec3_write_remoteaccess_first(
                base_url=base_url,
                root_path=probed_root,
                shared_session_client=cli_none,
                username=req.sec3_username,
                password=req.target_password,
                allowed_ip=allowed_ip,
                verify_tls=bool(req.verify_tls),
                timeout_sec=float(settings.timeout.read_sec),
            )

            # 3) essentials (최대 3회 시도)
            for _ in range(3):
                try:
                    essentials = _read_essentials_best_effort(cli_digest)
                    if any((essentials.get(k) or "").strip() for k in ESSENTIAL_KEYS):
                        break
                except Exception as e:
                    last_exc = e
                time.sleep(0.3)

            return Phase1Response(
                ok=True,
                sys_version=(essentials.get("SYS_VERSION") or "").strip() or None,
                base_url=base_url,
                root_path=probed_root,
                auth_scheme="digest",
                recovered=True,
                effective_password=req.target_password,
                effective_username=req.sec3_username,
                error=None,
            )

        # ============================
        # legacy/basic/TTA
        # ============================
        candidates: list[str] = []
        if req.password_candidates:
            candidates.extend([p for p in req.password_candidates if p])
        if req.password and req.password not in candidates:
            candidates.append(req.password)

        recovered = False
        last_err: Optional[ApiError] = None

        # root 후보 (TTA/기본 펌웨어는 /httpapi/ 가능성이 높음)
        def _normalize_root_local(r: str) -> str:
            r = (r or "").strip()
            if not r.startswith("/"):
                r = "/" + r
            if not r.endswith("/"):
                r += "/"
            return r

        def _uniq_roots(*items: str) -> list[str]:
            out: list[str] = []
            for x in items:
                if not x:
                    continue
                rn = _normalize_root_local(x)
                if rn not in out:
                    out.append(rn)
            return out

        roots_to_try = _uniq_roots("/httpapx/", probed_root, "/httpapi/", "/webapi/")

        def _build_cli(pw: str, root_path: str) -> CamApiClient:
            return CamApiClient(
                base_url=base_url,
                root_path=root_path,
                username=req.username,
                password=pw,
                auth_scheme=auth_scheme,
                timeout=settings.timeout,
                retry=settings.retry,
                verify_tls=bool(req.verify_tls),
            )

        def _read_essentials(cli: CamApiClient) -> dict[str, str]:
            out: dict[str, str] = {}
            for k in ESSENTIAL_KEYS:
                out[k] = cli.read_param_value(k)
            return out

        for pw in candidates:
            for root_path in roots_to_try:
                try:
                    cli = _build_cli(pw, root_path)
                    _ = cli.read_param_text(PASSWORD_TEST_KEY)

                    try:
                        essentials = _read_essentials(cli)
                        return Phase1Response(
                            ok=True,
                            sys_version=essentials.get("SYS_VERSION"),
                            base_url=base_url,
                            root_path=root_path,
                            auth_scheme=auth_scheme,
                            recovered=recovered,
                            effective_password=pw,
                            effective_username=req.username,
                            error=None,
                        )

                    except ApiError as e:
                        last_err = e

                        if (not recovered) and (pw == req.password) and _is_policy_block_for_default_state(e):
                            log.info("[PHASE1] default password state suspected; try auto password change once")

                            try_recover_password(
                                base_url=base_url,
                                root_path=root_path,
                                username=req.username,
                                password_candidates=[pw],
                                target_password=req.target_password,
                                timeout_sec=float(settings.timeout.read_sec),
                                verify_tls=bool(req.verify_tls),
                                auth_scheme=auth_scheme,
                            )

                            recovered = True

                            cli2 = _build_cli(req.target_password, root_path)
                            _ = cli2.read_param_text(PASSWORD_TEST_KEY)
                            essentials2 = _read_essentials(cli2)

                            return Phase1Response(
                                ok=True,
                                sys_version=essentials2.get("SYS_VERSION"),
                                base_url=base_url,
                                root_path=root_path,
                                auth_scheme=auth_scheme,
                                recovered=True,
                                effective_password=req.target_password,
                                effective_username=req.username,
                                error=None,
                            )

                        # 이 root에서는 실패했으므로 다음 root로 진행
                        continue

                except ApiError as e:
                    last_err = e
                    # 이 root에서는 실패했으므로 다음 root로 진행
                    continue
                except Exception as e:
                    last_err = ApiError(kind="network", message="request failed", detail=str(e))
                    continue

            # 현재 비밀번호 후보에서 root 후보를 모두 소진한 경우 다음 후보로 진행
            continue

        return Phase1Response(
            ok=False,
            base_url=base_url,
            root_path=probed_root,
            auth_scheme=auth_scheme,
            recovered=recovered,
            effective_password=None,
            effective_username=req.username,
            error=last_err or ApiError(kind="auth", message="all password candidates failed", status_code=401),
        )

    except ApiError as e:
        return Phase1Response(ok=False, effective_password=None, effective_username=req.username, error=e)

    except Exception as e:
        log.exception("[PHASE1] crashed")
        return Phase1Response(
            ok=False,
            effective_password=None,
            effective_username=req.username,
            error=ApiError(kind="phase1", message="phase1 crashed", detail=str(e)),
        )