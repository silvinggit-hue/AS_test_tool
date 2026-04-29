from __future__ import annotations

import logging
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

from config.settings import AppSettings
from core.cam_api_client import CamApiClient
from core.cam_info_reader import CamInfoReader
from models.dto import ApiError

log = logging.getLogger(__name__)


class DeviceInfoWorker(QThread):
    sig_progress = pyqtSignal(str)
    sig_success = pyqtSignal(dict)   # {"data": {...}, "used_password": "..."}
    sig_failure = pyqtSignal(dict)   # ApiError dict
    sig_finished = pyqtSignal()

    def __init__(
        self,
        *,
        base_url: str,
        root_path: str,
        username: str,
        password_candidates: list[str],
        auth_scheme: str,
        settings: AppSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._cancel = False

        self.base_url = base_url
        self.root_path = root_path
        self.username = username
        self.password_candidates = password_candidates
        self.auth_scheme = auth_scheme
        self.settings = settings

    def request_cancel(self) -> None:
        self._cancel = True

    def _iter_passwords(self) -> list[str]:
        out: list[str] = []
        for p in (self.password_candidates or []):
            s = (p or "").strip()
            if not s:
                continue
            if s not in out:
                out.append(s)
            if len(out) >= 3:
                break
        return out

    def run(self) -> None:
        try:
            self.sig_progress.emit("Reading device info...")

            last_err: Optional[ApiError] = None

            for pw in self._iter_passwords():
                if self._cancel:
                    return

                try:
                    cli = CamApiClient(
                        base_url=self.base_url,
                        root_path=self.root_path,
                        username=self.username,
                        password=pw,
                        auth_scheme=self.auth_scheme,
                        timeout=self.settings.timeout,
                        retry=self.settings.retry,
                        verify_tls=bool(self.settings.verify_tls),
                    )

                    data = CamInfoReader(cli).get_info_block()

                    if self._cancel:
                        return

                    self.sig_success.emit({"data": data, "used_password": pw})
                    return

                except ApiError as e:
                    last_err = e
                    continue

            raise last_err or ApiError(kind="auth", message="all password candidates failed", status_code=401)

        except ApiError as e:
            self.sig_failure.emit(e.to_dict())

        except Exception as e:
            log.exception("[DEVICE-INFO] unexpected error")
            self.sig_failure.emit(
                {"kind": "ui", "message": "unexpected error", "status_code": None, "detail": str(e)}
            )

        finally:
            self.sig_finished.emit()