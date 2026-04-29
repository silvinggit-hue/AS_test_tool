from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

from config.settings import AppSettings
from controller.connect_usecase import run_phase1, Phase1Request
from core.cam_api_client import CamApiClient
from models.dto import ApiError

log = logging.getLogger(__name__)


class Phase1Worker(QThread):
    sig_progress = pyqtSignal(str)
    sig_success = pyqtSignal(dict)
    sig_failure = pyqtSignal(dict)
    sig_finished = pyqtSignal()

    def __init__(
        self,
        *,
        ip: str,
        port: int,
        username: str,
        password: str,
        password_candidates: list[str],
        target_password: str,
        settings: AppSettings,
        extra_keys: Optional[list[str]] = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._cancel = False

        self.ip = ip
        self.port = int(port)
        self.username = (username or "").strip() or "admin"
        self.password = password or ""
        self.password_candidates = password_candidates or []
        self.target_password = target_password or ""
        self.settings = settings
        self.extra_keys = extra_keys or []

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            self.sig_progress.emit("Probing / Connecting.")

            req = Phase1Request(
                ip=self.ip,
                port=self.port,
                username=self.username,
                password=self.password,
                password_candidates=self.password_candidates,
                target_password=self.target_password,
                verify_tls=bool(self.settings.verify_tls),
            )

            resp = run_phase1(req, settings=self.settings)
            if self._cancel:
                return

            if not resp.ok:
                err = resp.error.to_dict() if resp.error else {
                    "kind": "unknown",
                    "message": "unknown error",
                    "status_code": None,
                    "detail": None,
                }
                self.sig_failure.emit(err)
                return

            eff_user = (getattr(resp, "effective_username", None) or "").strip() or self.username

            payload = {
                "ok": True,
                "base_url": resp.base_url,
                "root_path": resp.root_path,
                "auth_scheme": resp.auth_scheme,
                "recovered": resp.recovered,
                "effective_password": resp.effective_password,
                "effective_username": eff_user,
                "sys_version": resp.sys_version,
            }

            if self.extra_keys:
                self.sig_progress.emit("Reading extra params.")
                self._read_extras_into(payload, username=eff_user, password=(resp.effective_password or ""))

            if self._cancel:
                return

            self.sig_success.emit(payload)

        except ApiError as e:
            self.sig_failure.emit(e.to_dict())
        except Exception as e:
            log.exception("[PHASE1] unexpected error")
            self.sig_failure.emit(
                {"kind": "ui", "message": "unexpected error", "status_code": None, "detail": str(e)}
            )
        finally:
            self.sig_finished.emit()

    def _read_extras_into(self, payload: dict, *, username: str, password: str) -> None:
        cli = CamApiClient(
            base_url=payload["base_url"],
            root_path=payload["root_path"],
            username=username,
            password=password,
            auth_scheme=payload["auth_scheme"],
            timeout=self.settings.timeout,
            retry=self.settings.retry,
            verify_tls=bool(self.settings.verify_tls),
        )

        for k in self.extra_keys:
            if self._cancel:
                return
            try:
                payload[k] = cli.read_param_value(k)
            except ApiError:
                payload[k] = None