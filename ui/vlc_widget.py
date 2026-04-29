from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from urllib.parse import quote, urlsplit, urlunsplit

from PyQt5.QtCore import QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import QWidget

log = logging.getLogger(__name__)

try:
    import vlc  # python-vlc
except Exception:  # noqa
    vlc = None


@dataclass
class ReconnectPolicy:
    base_delay_ms: int = 500
    max_delay_ms: int = 10_000
    jitter_ms: int = 250


class VLCWidget(QWidget):
    sig_state = pyqtSignal(str)  # unavailable|stopped|connecting|playing|reconnecting|error

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setAttribute(Qt.WA_NativeWindow, True)
        self.setAttribute(Qt.WA_DontCreateNativeAncestors, True)
        self.setAutoFillBackground(False)

        self._policy = ReconnectPolicy()
        self._attempt = 0
        self._user_stopped = True

        self._rtsp_url: str | None = None
        self._rtsp_user: str | None = None
        self._rtsp_pwd: str | None = None

        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self._do_reconnect)

        self.instance = None
        self.mediaplayer = None
        self._ev = None

        if vlc is None:
            self.setEnabled(False)
            self.sig_state.emit("unavailable")
            return

        try:
            self.instance = vlc.Instance()
            self.mediaplayer = self.instance.media_player_new()
            self._attach_events()
            self.sig_state.emit("stopped")
        except Exception:
            log.exception("[RTSP] VLC init failed")
            self.setEnabled(False)
            self.sig_state.emit("unavailable")

    def play_rtsp(self, rtsp_url: str, username: str, password: str) -> None:
        self._user_stopped = False
        self._attempt = 0

        self._rtsp_url = (rtsp_url or "").strip() or None
        self._rtsp_user = (username or "").strip() or None
        self._rtsp_pwd = (password or "").strip() or None

        log.info("[RTSP] play request url=%s", self._rtsp_url)

        if not self._rtsp_url:
            self.sig_state.emit("error")
            return

        try:
            if self._reconnect_timer.isActive():
                self._reconnect_timer.stop()
        except Exception:
            pass

        try:
            if self.mediaplayer:
                self.mediaplayer.stop()
        except Exception:
            pass

        self.update()
        self.repaint()
        self.winId()

        try:
            QTimer.singleShot(150, self._play_once)
        except Exception:
            log.exception("[RTSP] play_rtsp failed")
            self._schedule_reconnect("play_rtsp_failed")

    def stop(self):
        self._user_stopped = True
        self._attempt = 0
        self._rtsp_url = None
        self._rtsp_user = None
        self._rtsp_pwd = None

        try:
            self._reconnect_timer.stop()
        except Exception:
            pass

        try:
            if self.mediaplayer:
                self.mediaplayer.stop()
        except Exception:
            pass

        self.sig_state.emit("stopped")

    def _attach_events(self):
        if not self.mediaplayer or vlc is None:
            return
        self._ev = self.mediaplayer.event_manager()
        self._ev.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_vlc_error)
        self._ev.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_vlc_end)
        self._ev.event_attach(vlc.EventType.MediaPlayerPlaying, self._on_vlc_playing)

    def _bind_hwnd(self):
        if not self.mediaplayer:
            return
        wid = int(self.winId())
        try:
            self.mediaplayer.set_hwnd(wid)
            return
        except Exception:
            pass
        try:
            self.mediaplayer.set_xwindow(wid)
            return
        except Exception:
            pass
        try:
            self.mediaplayer.set_nsobject(wid)
        except Exception:
            pass

    def _build_auth_url(self) -> str | None:
        if not self._rtsp_url:
            return None

        if not self._rtsp_user:
            return self._rtsp_url

        try:
            sp = urlsplit(self._rtsp_url)

            # 이미 계정정보가 URL에 있으면 원본 유지
            if sp.username:
                return self._rtsp_url

            user = quote(self._rtsp_user, safe="")
            pwd = quote(self._rtsp_pwd or "", safe="")

            host = sp.hostname or ""
            if not host:
                return self._rtsp_url

            netloc = f"{user}:{pwd}@{host}"
            if sp.port:
                netloc += f":{sp.port}"

            return urlunsplit((sp.scheme, netloc, sp.path, sp.query, sp.fragment))
        except Exception:
            log.exception("[RTSP] failed to build auth url")
            return self._rtsp_url

    def _play_once(self):
        if self._user_stopped or not self._rtsp_url or not self.instance or not self.mediaplayer:
            return

        try:
            self.sig_state.emit("connecting")

            play_url = self._build_auth_url() or self._rtsp_url
            safe_url = self._rtsp_url  # 로그에는 비밀번호 노출 금지

            log.info("[RTSP] connecting url=%s hwnd=%s", safe_url, int(self.winId()))

            self.winId()
            self._bind_hwnd()

            media = self.instance.media_new(
                play_url,
                ":rtsp-tcp",
                ":network-caching=300",
                ":live-caching=300",
                ":clock-jitter=0",
                ":clock-synchro=0",
            )
            self.mediaplayer.set_media(media)

            rc = self.mediaplayer.play()
            log.info("[RTSP] play() returned rc=%s url=%s", rc, safe_url)

        except Exception:
            log.exception("[RTSP] play failed")
            self._schedule_reconnect("play_failed")

    def _schedule_reconnect(self, reason: str):
        if self._user_stopped or not self._rtsp_url:
            return

        self._attempt += 1
        base = self._policy.base_delay_ms * (2 ** max(0, self._attempt - 1))
        delay = min(base, self._policy.max_delay_ms)
        delay += random.randint(0, self._policy.jitter_ms)

        log.warning(
            "[RTSP] reconnect scheduled: reason=%s delay=%dms attempt=%d url=%s",
            reason,
            delay,
            self._attempt,
            self._rtsp_url,
        )
        self.sig_state.emit("reconnecting")

        try:
            self._reconnect_timer.start(delay)
        except Exception:
            pass

    def _do_reconnect(self):
        if self._user_stopped or not self._rtsp_url:
            return
        self._play_once()

    def _on_vlc_playing(self, event):  # noqa
        self._attempt = 0
        log.info("[RTSP] playing url=%s", self._rtsp_url)
        self.sig_state.emit("playing")

    def _on_vlc_error(self, event):  # noqa
        log.warning("[RTSP] vlc encountered error url=%s", self._rtsp_url)
        self.sig_state.emit("error")
        self._schedule_reconnect("vlc_error")

    def _on_vlc_end(self, event):  # noqa
        log.warning("[RTSP] vlc end reached")
        self._schedule_reconnect("end_reached")