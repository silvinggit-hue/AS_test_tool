from __future__ import annotations

import logging
from PyQt5.QtCore import QThread, pyqtSignal

from config.settings import AppSettings
from core.cam_api_client import CamApiClient
from core.cam_status_reader import CamStatusReader
from models.dto import ApiError

log = logging.getLogger(__name__)


def _normalize_root(root_path: str) -> str:
    rp = (root_path or "").strip()
    if not rp:
        return ""
    if not rp.startswith("/"):
        rp = "/" + rp
    if not rp.endswith("/"):
        rp += "/"
    return rp


class StatusPollWorker(QThread):
    sig_success = pyqtSignal(dict)   # snapshot dict
    sig_failure = pyqtSignal(dict)   # ApiError dict
    sig_finished = pyqtSignal()

    def __init__(
        self,
        *,
        base_url: str,
        root_path: str,
        username: str,
        password: str,
        auth_scheme: str,
        settings: AppSettings,
    ) -> None:
        super().__init__()
        self._cancel = False

        self.base_url = base_url
        self.root_path = _normalize_root(root_path)
        self.username = username
        self.password = password
        self.auth_scheme = auth_scheme
        self.settings = settings

    def request_cancel(self) -> None:
        self._cancel = True

    def _make_client(self, root_path: str) -> CamApiClient:
        return CamApiClient(
            base_url=self.base_url,
            root_path=_normalize_root(root_path),
            username=self.username,
            password=self.password,
            auth_scheme=self.auth_scheme,
            timeout=self.settings.timeout,
            retry=self.settings.retry,
            verify_tls=bool(self.settings.verify_tls),
        )

    @staticmethod
    def _is_httpapi_root(root_path: str) -> bool:
        # "/httpapi/" "/httpapi" 모두 True 처리
        rp = (root_path or "").strip().rstrip("/")
        return rp == "/httpapi"

    def run(self) -> None:
        try:
            if self._cancel:
                return

            # 1) primary root_path
            cli = self._make_client(self.root_path)

            if self._cancel:
                return

            try:
                snap = CamStatusReader(cli).read_status_block()

            except ApiError as e:
                # 404면 /httpapi/로 1회 폴백
                # (ReadParam OK, GetState 404 같은 혼종 장비 대응)
                if (
                    e.kind == "http"
                    and e.status_code == 404
                    and not self._is_httpapi_root(self.root_path)
                ):
                    if self._cancel:
                        return
                    cli2 = self._make_client("/httpapi/")
                    snap = CamStatusReader(cli2).read_status_block()
                else:
                    raise

            if self._cancel:
                return

            self.sig_success.emit(snap)

        except ApiError as e:
            if not self._cancel:
                self.sig_failure.emit(e.to_dict())

        except Exception as e:
            log.exception("[POLL] unexpected error")
            if not self._cancel:
                self.sig_failure.emit(
                    {"kind": "ui", "message": "unexpected error", "status_code": None, "detail": str(e)}
                )

        finally:
            self.sig_finished.emit()