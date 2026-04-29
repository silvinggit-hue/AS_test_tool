from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


class ApiError(Exception):
    """
    공통 예외 타입.
    kind 예:
      - network, timeout, http, auth, param, compat, probe, ssl, disconnect
    """

    def __init__(
        self,
        kind: str,
        message: str,
        status_code: int | None = None,
        detail: str | None = None,
        phase: str | None = None,
        error_code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.status_code = status_code
        self.detail = detail
        self.phase = phase
        self.error_code = error_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "message": self.message,
            "status_code": self.status_code,
            "detail": self.detail,
            "phase": self.phase,
            "error_code": self.error_code,
        }

    def __str__(self) -> str:
        base = f"{self.kind}: {self.message}"
        if self.status_code is not None:
            base += f" (status={self.status_code})"
        if self.phase:
            base += f" (phase={self.phase})"
        if self.error_code:
            base += f" (code={self.error_code})"
        if self.detail:
            base += f" | {self.detail}"
        return base


@dataclass(frozen=True)
class ProbeResult:
    base_url: str          # e.g. "https://1.2.3.4:443"
    root_path: str         # e.g. "/httpapi/"
    auth_scheme: str       # "none" | "digest" | "basic"


@dataclass(frozen=True)
class Phase1Response:
    ok: bool
    base_url: Optional[str] = None
    root_path: Optional[str] = None
    auth_scheme: Optional[str] = None

    sys_version: Optional[str] = None
    recovered: bool = False

    effective_password: Optional[str] = None
    effective_username: Optional[str] = None

    error: Optional[ApiError] = None