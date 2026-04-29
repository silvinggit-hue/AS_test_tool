from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TimeoutSettings:
    connect_sec: float = 3.0
    read_sec: float = 6.0


@dataclass(frozen=True)
class RetrySettings:
    # Phase1은 단발 실행 기준의 최소 재시도 설정
    max_attempts: int = 2  # 1회 실행 + 1회 재시도
    backoff_base_sec: float = 0.25
    backoff_jitter_sec: float = 0.15
    retry_on_status: tuple[int, ...] = (502, 503, 504)


@dataclass
class AppSettings:
    default_port: int = 0  # 0: auto
    default_username: str = "admin"
    default_password: str = "1234"

    target_password: str = "Truen1309!"

    # Security 3.0 초기 프로비저닝(USR_ADD 이후)에서 설정할 REMOTEACCESS 허용 IP
    allowed_ip: str = "192.168.10.2"

    timeout: TimeoutSettings = field(default_factory=TimeoutSettings)
    retry: RetrySettings = field(default_factory=RetrySettings)

    # 현장 장비 특성상 self-signed 인증서가 많아 기본값은 False
    verify_tls: bool = False

    @classmethod
    def load(cls) -> "AppSettings":
        return cls()