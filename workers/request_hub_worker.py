from __future__ import annotations

import os
import time
import threading
import logging
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import quote, parse_qsl

from PyQt5.QtCore import QThread, pyqtSignal

from config.settings import AppSettings, RetrySettings
from core.cam_api_client import CamApiClient
from core.cam_status_reader import CamStatusReader
from core.firmware_upload import upload_firmware_progress_html
from models.dto import ApiError
from core.readparam_keys import (
    READPARAM_AUDIO_CAPABILITY_KEYS,
    READPARAM_VIDEO_KEYS,
    READPARAM_NETWORK_KEYS,
    READPARAM_STORAGE_KEYS,
    READPARAM_SYSTEM_KEYS,
    READPARAM_CAMERA_VERSION_KEYS,
    READPARAM_AUDIO_KEYS,
    READPARAM_TEST_KEYS,
    READPARAM_FULL_DUMP_KEYS,
)


@dataclass(frozen=True)
class HubConfig:
    base_url: str
    root_path: str
    auth_scheme: str
    username: str
    password: str
    verify_tls: bool

    poll_interval_ms: int = 1000
    continue_interval_ms: int = 300
    ptz_timeout_ms: int = 20000
    ptz_channel: int = 1


@dataclass
class HubTask:
    kind: str
    payload: dict[str, Any]
    priority: int
    seq: int


class _LoggerSilencer:
    def __init__(self, names: list[str]) -> None:
        self._names = names
        self._prev: dict[str, bool] = {}

    def __enter__(self):
        for n in self._names:
            lg = logging.getLogger(n)
            self._prev[n] = bool(getattr(lg, "disabled", False))
            lg.disabled = True
        return self

    def __exit__(self, exc_type, exc, tb):
        for n, prev in self._prev.items():
            logging.getLogger(n).disabled = prev
        return False


class RequestHubWorker(QThread):
    sig_poll = pyqtSignal(dict)
    sig_log = pyqtSignal(str)
    sig_error = pyqtSignal(dict)
    sig_state = pyqtSignal(str)
    sig_task = pyqtSignal(str, str, bool, str)
    sig_cam_log = pyqtSignal(bool, str)
    sig_audio_caps = pyqtSignal(dict)  # {"supported":{key:bool}, "values":{key:str}, "raw":{key:str}}
    sig_readparam = pyqtSignal(str, str)  # (key, value)
    sig_video_auto = pyqtSignal(dict)
    sig_product_model = pyqtSignal(bool, str, str)


    def __init__(self, *, cfg: HubConfig, settings: AppSettings) -> None:
        super().__init__()
        self._cfg = cfg
        self._settings = settings

        self._cancel = False
        self._lock = threading.Condition()
        self._seq = 0
        self._queue: list[HubTask] = []

        self._latest_move: Optional[dict[str, Any]] = None
        self._hold_joy = False
        self._hold_zoom = False
        self._hold_focus = False

        now = time.monotonic()
        self._next_poll_t = now
        self._next_continue_t = now

        self._suspend_polling = False
        self._suppress_poll_errors = True

        self._client: CamApiClient | None = None
        self._reader: CamStatusReader | None = None
        self._client_alt: CamApiClient | None = None

        self._disconnect_requested = False
        self._disconnect_reason = ""
        self._disconnect_on_poll_fail = False

        self._mute_loggers = [
            "core.cam_api_client",
            "core.cam_status_reader",
            "core.cam_info_reader",
            "core.http_client",
            "core.probe",
        ]

    # =========================
    def request_cancel(self) -> None:
        with self._lock:
            self._cancel = True
            self._queue.clear()
            self._latest_move = None
            self._hold_joy = False
            self._hold_zoom = False
            self._hold_focus = False
            self._suspend_polling = True
            self._lock.notify_all()

    def enqueue(self, kind: str, *, payload: dict[str, Any] | None = None, priority: int = 50) -> None:
        payload = payload or {}
        with self._lock:
            if self._cancel:
                return
            self._seq += 1
            self._queue.append(HubTask(kind=kind, payload=payload, priority=priority, seq=self._seq))
            self._queue.sort(key=lambda t: (-t.priority, t.seq))
            self._lock.notify_all()

    # PTZ API
    def ptz_stop(self) -> None:
        self.enqueue("ptz_stop", priority=100)

    def ptz_move_update(self, *, direction: str, speed: int) -> None:
        with self._lock:
            if self._cancel:
                return
            self._latest_move = {"direction": direction, "speed": int(speed)}
            self._hold_joy = True
            self._lock.notify_all()

    def ptz_move_release(self) -> None:
        self.enqueue("ptz_release_joy", priority=95)

    def zoom_press(self, *, mode: str) -> None:
        self.enqueue("zoom_press", payload={"mode": mode}, priority=70)

    def zoom_release(self) -> None:
        self.enqueue("zoom_release", priority=95)

    def focus_press(self, *, mode: str) -> None:
        self.enqueue("focus_press", payload={"mode": mode}, priority=70)

    def focus_release(self) -> None:
        self.enqueue("focus_release", priority=95)

    def focus_auto(self) -> None:
        self.enqueue("focus_auto", priority=80)

    def ptz_home(self) -> None:
        self.enqueue("ptz_home", priority=80)

    def zoom_1x(self) -> None:
        self.enqueue("zoom_1x", priority=80)

    # params/system
    def writeparam(self, *, key: str, value: str) -> None:
        self.enqueue("writeparam", payload={"key": key, "value": value}, priority=80)

    def readparam(self, *, key: str) -> None:
        self.enqueue("readparam", payload={"key": key}, priority=80)

    # audio caps scan
    def audio_caps_scan(self) -> None:
        self.enqueue("audio_caps_scan", priority=85)

    def reboot(self) -> None:
        self.enqueue("reboot", priority=90)

    def factory_reset(self) -> None:
        self.enqueue("factory_reset", priority=90)

        # ===== Audio helpers (optional thin wrappers) =====

    def audio_enable(self, on: bool) -> None:
        self.writeparam(key="AUD_ENABLE", value="1" if on else "0")

    def audio_set_codec_aac(self) -> None:
        # User-requested key
        self.writeparam(key="AUD_CODEC", value="1")
        # Spec fallback key (Configuration Parameters Eng)
        self.writeparam(key="AUD_ALGORITHM", value="1")

    def audio_set_codec_g711(self) -> None:
        self.writeparam(key="AUD_CODEC", value="0")
        self.writeparam(key="AUD_ALGORITHM", value="0")

    def audio_set_max_volume(self) -> None:
        # User-requested keys
        self.writeparam(key="AUD_INPUTGAIN", value="100")
        self.writeparam(key="AUD_OUTPUTGAIN", value="100")
        # Spec fallback key (0~31)
        self.writeparam(key="AUD_GAIN", value="31")

    # ===== Video input format helpers =====

    def video_set_input_format(self, input_code: str, resolution_code: str) -> None:
        self.enqueue(
            "video_set_input_format",
            payload={
                "input_code": str(input_code).strip(),
                "resolution_code": str(resolution_code).strip(),
            },
            priority=85,
        )

    def lens_offset_lens(self) -> None:
        self.enqueue("lens_offset_lens", priority=85)

    def lens_offset_zoomlens(self) -> None:
        self.enqueue("lens_offset_zoomlens", priority=85)

    def set_model_name(self, model_name: str) -> None:
        self.enqueue("set_model_name", payload={"model_name": model_name}, priority=90)

    def set_extra_id(self, value: str) -> None:
        self.enqueue("set_extra_id", payload={"value": value}, priority=90)

    def set_product_model(self, value: str) -> None:
        self.enqueue("set_product_model", payload={"value": value}, priority=90)

    def fw_upload(self, filepath: str) -> None:
        self.enqueue("fw_upload", payload={"filepath": filepath}, priority=95)

    def cam_log_load(self) -> None:
        self.enqueue("cam_log_load", priority=90)

    # =========================
    def _check_cancel(self) -> None:
        if self._cancel:
            raise ApiError("ui", "cancelled")

    def _ensure_client(self) -> None:
        if self._client is None:
            self._client = CamApiClient(
                base_url=self._cfg.base_url,
                root_path=self._cfg.root_path,
                username=self._cfg.username,
                password=self._cfg.password,
                auth_scheme=self._cfg.auth_scheme,
                timeout=self._settings.timeout,
                retry=self._settings.retry,
                verify_tls=self._cfg.verify_tls,
            )
            self._reader = CamStatusReader(self._client)

        if self._client_alt is None:
            self._client_alt = CamApiClient(
                base_url=self._cfg.base_url,
                root_path="/httpapi/",
                username=self._cfg.username,
                password=self._cfg.password,
                auth_scheme=self._cfg.auth_scheme,
                timeout=self._settings.timeout,
                retry=self._settings.retry,
                verify_tls=self._cfg.verify_tls,
            )

    # =========================
    @staticmethod
    def _dir_abbrev(direction: str) -> str:
        m = {
            "up": "U", "down": "D", "left": "L", "right": "R",
            "leftup": "LU", "rightup": "RU", "leftdown": "LD", "rightdown": "RD",
        }
        return m.get(direction, direction[:2].upper())

    def _short_from_sendptz(self, qs: dict[str, str]) -> str:
        mv = qs.get("PTZ_MOVE")
        if mv:
            if mv == "stop":
                return "PT ST"
            if mv == "continue":
                return "CT"
            if mv.startswith("zoomin"):
                return "Z+"
            if mv.startswith("zoomout"):
                return "Z-"
            if mv.startswith("focusnear"):
                return "FN"
            if mv.startswith("focusfar"):
                return "FF"
            parts = mv.split(",")
            if parts and parts[0] in ("up", "down", "left", "right", "leftup", "rightup", "leftdown", "rightdown"):
                d = self._dir_abbrev(parts[0])
                sp = parts[1] if len(parts) > 1 else ""
                return f"PT {d}{sp}".strip()

        if "PTZ_FOCUSAUTO" in qs:
            return "AF"
        if "PTZ_ABSOLUTEPOSITION" in qs:
            return "1X"
        if "PTZ_LENSOFFSETADJUST" in qs:
            return "LO"

        return "PTZ"

    def _short_from_writeparam(self, qs: dict[str, str]) -> str:
        if "CAM_HI_TDN_MODE" in qs:
            v = qs.get("CAM_HI_TDN_MODE", "")
            return {"0": "TDN A", "2": "TDN D", "3": "TDN N"}.get(v, "TDN")
        if "CAM_HI_TDN_FILTER" in qs:
            v = qs.get("CAM_HI_TDN_FILTER", "")
            return {"0": "ICR A", "1": "ICR ON", "2": "ICR OFF"}.get(v, "ICR")

        if "SYS_REBOOT" in qs:
            return "RB"
        if "SYS_RESET_V2" in qs:
            return "FR"

        if "SYS_MODELNAME2" in qs:
            return "MD"
        if "NET_EXTRA_ID" in qs:
            return "EX"
        if "SYS_PRODUCT_MODEL" in qs:
            return "PM"

        if "SYS_REMOTEUPGRADEUSERINFO" in qs:
            return "FW TR"

        for k in qs.keys():
            if k == "action":
                continue
            return f"WP {k[:2].upper()}"
        return "WP"

    @staticmethod
    def _short_from_testsystem(qs: dict[str, str]) -> str:
        if qs.get("TEST_WRITE") == "9500030501019F":
            return "LZ"
        return "TS"

    @staticmethod
    def _emit_short(sig_log: pyqtSignal, short: str, ok: bool) -> None:
        sig_log.emit(f"{short} OK" if ok else f"{short} ER")

    def _parse_qs(self, query: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for k, v in parse_qsl(query, keep_blank_values=True):
            if k not in out:
                out[k] = v
        return out

    @staticmethod
    def _q(s: str, *, safe: str = "") -> str:
        return quote(str(s or ""), safe=safe)

    def _request_text(self, client: CamApiClient, tail: str, *, log_io: bool, short: str) -> str:
        self._check_cancel()

        with _LoggerSilencer(self._mute_loggers):
            resp = client._request(tail)  # pylint: disable=protected-access

        self._check_cancel()

        if not log_io:
            if resp.status == 200:
                return resp.body or ""
            body = resp.body or ""
            tail_txt = body.replace("\r", " ").replace("\n", " ")
            tail_txt = tail_txt[-200:] if len(tail_txt) > 200 else tail_txt
            if resp.status in (401, 403):
                raise ApiError("auth", "authentication failed", resp.status, detail=tail_txt)
            if resp.status == 404:
                raise ApiError("http", "not found", resp.status, detail=tail_txt)
            raise ApiError("http", "request failed", resp.status, detail=tail_txt)

        if resp.status == 200:
            self._emit_short(self.sig_log, short, ok=True)
            return resp.body or ""

        self._emit_short(self.sig_log, short, ok=False)

        body = resp.body or ""
        tail_txt = body.replace("\r", " ").replace("\n", " ")
        tail_txt = tail_txt[-200:] if len(tail_txt) > 200 else tail_txt

        if resp.status in (401, 403):
            raise ApiError("auth", "authentication failed", resp.status, detail=tail_txt)
        if resp.status == 404:
            raise ApiError("http", "not found", resp.status, detail=tail_txt)
        raise ApiError("http", "request failed", resp.status, detail=tail_txt)

    def _request_text_with_fallback(self, tail: str, *, log_io: bool, short: str) -> str:
        if not self._client or not self._client_alt:
            raise ApiError("ui", "client not ready")
        try:
            return self._request_text(self._client, tail, log_io=log_io, short=short)
        except ApiError as e:
            if e.status_code == 404:
                return self._request_text(self._client_alt, tail, log_io=log_io, short=short)
            raise

    def _sendptz(self, query: str, *, log_io: bool) -> None:
        is_continue = "PTZ_MOVE=continue" in query
        if is_continue:
            log_io = False

        qs = self._parse_qs(query)
        short = self._short_from_sendptz(qs)

        try:
            self._request_text_with_fallback(f"SendPTZ?{query.lstrip('?')}", log_io=log_io, short=short)
        except ApiError:
            if is_continue:
                self.sig_log.emit("CT ER")
                self._hold_joy = False
                self._hold_zoom = False
                self._hold_focus = False
                return
            raise

    def _writeparam_raw(self, query: str, *, allow_non200: bool, log_io: bool) -> None:
        qs = self._parse_qs(query)
        short = self._short_from_writeparam(qs)

        tail = f"WriteParam?{query.lstrip('?')}"

        if allow_non200:
            try:
                self._request_text_with_fallback(tail, log_io=False, short=short)
                if log_io:
                    self._emit_short(self.sig_log, short, ok=True)
                return
            except ApiError as e:
                if e.kind == "auth":
                    if log_io:
                        self._emit_short(self.sig_log, short, ok=True)
                    raise
                if log_io:
                    self._emit_short(self.sig_log, short, ok=True)
                return

        self._request_text_with_fallback(tail, log_io=log_io, short=short)

    def _readparam_text_with_fallback(self, key: str, *, log_io: bool = False) -> str:
        kq = self._q(key)
        tail = f"ReadParam?action=readparam&{kq}=0"
        # short 코드는 너무 많아지니 RP로 고정(로그 최소화)
        return self._request_text_with_fallback(tail, log_io=log_io, short="RP")

    @staticmethod
    def _extract_kv_value(text: str, key: str) -> str:
        prefix = key + "="
        for line in (text or "").splitlines():
            if line.startswith(prefix):
                return line.split("=", 1)[1].strip()
        return ""

    def _testsystem(self, query: str, *, log_io: bool) -> None:
        qs = self._parse_qs(query)
        short = self._short_from_testsystem(qs)
        self._request_text_with_fallback(f"TestSystem?{query.lstrip('?')}", log_io=log_io, short=short)

    def _op_readparam(self, key: str) -> None:
        self._check_cancel()
        self._ensure_client()
        assert self._client is not None
        text = self._readparam_text_with_fallback(key,
                                                  log_io=False)  # 내부 util 이미 존재 :contentReference[oaicite:5]{index=5}
        value = self._extract_kv_value(text, key)
        self.sig_readparam.emit(key, value)

    def video_auto_detect(self) -> None:
        self.enqueue("video_auto_detect", priority=84)

    def _op_poll(self) -> None:
        self._check_cancel()
        if not self._reader:
            raise ApiError("ui", "reader not ready")
        with _LoggerSilencer(self._mute_loggers):
            snap = self._reader.read_status_block()
        raw = snap.get("raw") or {}
        self.sig_poll.emit(snap)

    def _op_ptz_continue_if_needed(self) -> None:
        self._check_cancel()
        if not (self._hold_joy or self._hold_zoom or self._hold_focus):
            return
        ch = int(self._cfg.ptz_channel)
        self._sendptz(f"action=sendptz&PTZ_CHANNEL={ch}&PTZ_MOVE=continue", log_io=False)

    def _op_ptz_stop(self) -> None:
        self._check_cancel()
        self._hold_joy = False
        self._hold_zoom = False
        self._hold_focus = False
        self._latest_move = None
        ch = int(self._cfg.ptz_channel)
        self._sendptz(f"action=sendptz&PTZ_CHANNEL={ch}&PTZ_MOVE=stop", log_io=True)

    def _op_ptz_move_latest(self) -> None:
        self._check_cancel()
        if not self._latest_move:
            return
        direction = str(self._latest_move["direction"])
        speed = max(1, min(8, int(self._latest_move["speed"])))
        ch = int(self._cfg.ptz_channel)
        to = int(self._cfg.ptz_timeout_ms)

        self._sendptz(
            f"action=sendptz&PTZ_CHANNEL={ch}&PTZ_MOVE={direction},{speed},1&PTZ_TIMEOUT={to}",
            log_io=True,
        )

    def _op_zoom_press(self, mode: str) -> None:
        self._check_cancel()
        self._hold_zoom = True
        ch = int(self._cfg.ptz_channel)
        self._sendptz(f"action=sendptz&PTZ_CHANNEL={ch}&PTZ_MOVE={mode},-1", log_io=True)

    def _op_zoom_release(self) -> None:
        self._hold_zoom = False
        self._op_ptz_stop()

    def _op_focus_press(self, mode: str) -> None:
        self._check_cancel()
        self._hold_focus = True
        ch = int(self._cfg.ptz_channel)
        self._sendptz(f"action=sendptz&PTZ_CHANNEL={ch}&PTZ_MOVE={mode},-1", log_io=True)

    def _op_focus_release(self) -> None:
        self._hold_focus = False
        self._op_ptz_stop()

    def _op_focus_auto(self) -> None:
        self._check_cancel()
        ch = int(self._cfg.ptz_channel)
        self._sendptz(f"action=sendptz&PTZ_CHANNEL={ch}&PTZ_FOCUSAUTO=1", log_io=True)

    def _op_ptz_home(self) -> None:
        self._check_cancel()
        ch = int(self._cfg.ptz_channel)
        self._sendptz(f"action=sendptz&PTZ_CHANNEL={ch}&PTZ_ABSOLUTEPOSITION=-1,-1,0,-1", log_io=True)

    def _op_zoom_1x(self) -> None:
        self._op_ptz_home()

    def _op_writeparam(self, key: str, value: str) -> None:
        self._check_cancel()
        kq = self._q(key)
        vq = self._q(value)
        self._writeparam_raw(f"action=writeparam&{kq}={vq}", allow_non200=False, log_io=True)

    def _op_audio_caps_scan(self) -> None:
        self._check_cancel()

        # capability 키 + 실제 audio 키를 함께 읽는다.
        keys = list(READPARAM_AUDIO_CAPABILITY_KEYS) + list(READPARAM_AUDIO_KEYS)

        supported: dict[str, bool] = {}
        values: dict[str, str] = {}
        raw: dict[str, str] = {}

        for k in keys:
            self._check_cancel()
            try:
                txt = self._readparam_text_with_fallback(k, log_io=False)
                raw[k] = txt or ""
                v = self._extract_kv_value(txt, k)

                if v != "":
                    supported[k] = True
                    values[k] = v
                else:
                    supported[k] = False
                    values[k] = ""

            except ApiError as e:
                if e.kind == "auth":
                    raise
                supported[k] = False
                values[k] = ""
                raw[k] = ""

        self.sig_audio_caps.emit(
            {
                "supported": supported,
                "values": values,
                "raw": raw,
            }
        )

    def _op_video_set_input_format(self, *, input_code: str, resolution_code: str) -> None:
        self._check_cancel()

        if not input_code:
            raise ApiError("param", "empty VID_INPUTFORMAT")
        if not resolution_code:
            raise ApiError("param", "empty VID_RESOLUTION")

        # web UI는 video 그룹 파라미터를 묶어서 WriteParam 호출
        # 우선 필수값만 안전하게 적용
        query = (
            "action=writeparam"
            f"&VID_INPUTFORMAT={self._q(input_code)}"
            f"&VID_RESOLUTION={self._q(resolution_code)}"
        )

        self._writeparam_raw(query, allow_non200=False, log_io=True)
        self.sig_log.emit(
            f"[INFO] Video input applied | VID_INPUTFORMAT={input_code}, VID_RESOLUTION={resolution_code}")

    def _op_video_auto_detect(self) -> None:
        self._check_cancel()
        self._ensure_client()
        assert self._client is not None

        resp = self._client._request("ReadParam?action=readpage&page=video_iad")  # pylint: disable=protected-access
        body = (resp.body or "").strip()

        if resp.status != 200:
            if resp.status in (401, 403):
                raise ApiError("auth", "authentication failed", resp.status, detail=body[:200])
            raise ApiError("http", "video auto detect failed", resp.status, detail=body[:200])

        lines = {}
        for line in body.splitlines():
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            lines[k.strip()] = v.strip()

        out = {
            "VID_IAD_COMPOSITE": lines.get("VID_IAD_COMPOSITE", ""),
            "VID_IAD_HDMI": lines.get("VID_IAD_HDMI", ""),
            "VID_IAD_SDI": lines.get("VID_IAD_SDI", ""),
            "raw": body,
        }
        self.sig_video_auto.emit(out)

    def _op_reboot(self) -> None:
        self._check_cancel()
        self._disconnect_on_poll_fail = True
        try:
            self._writeparam_raw("action=writeparam&SYS_REBOOT=0", allow_non200=True, log_io=True)
        except ApiError as e:
            if e.kind not in ("auth", "network", "timeout", "disconnect", "ssl"):
                raise
        finally:
            self._trigger_disconnect("reboot requested")

    def _op_factory_reset(self) -> None:
        self._check_cancel()
        self._disconnect_on_poll_fail = True
        try:
            self._writeparam_raw("action=writeparam&SYS_RESET_V2=0", allow_non200=True, log_io=True)
        except ApiError as e:
            if e.kind not in ("auth", "network", "timeout", "disconnect", "ssl"):
                raise
        finally:
            self._trigger_disconnect("factory reset requested")

    def _op_lens_offset_lens(self) -> None:
        self._check_cancel()
        ch = int(self._cfg.ptz_channel)
        self._sendptz(f"action=sendptz&PTZ_CHANNEL={ch}&PTZ_LENSOFFSETADJUST=1", log_io=True)

    def _op_lens_offset_zoomlens(self) -> None:
        self._check_cancel()
        self._testsystem("TEST_WRITE=9500030501019F", log_io=True)

    def _op_set_model_name(self, model_name: str) -> None:
        self._check_cancel()
        self._op_writeparam("SYS_MODELNAME2", model_name or "")

    def _op_set_extra_id(self, value: str) -> None:
        self._check_cancel()
        self._op_writeparam("NET_EXTRA_ID", value or "")

    def _op_set_product_model(self, value: str) -> None:
        self._check_cancel()
        self._ensure_client()

        val = (value or "").strip()
        if not val:
            self.sig_product_model.emit(False, val, "SYS_PRODUCT_MODEL value empty")
            return

        try:
            # 1) WriteParam
            kq = self._q("SYS_PRODUCT_MODEL")
            vq = self._q(val)
            text = self._request_text_with_fallback(
                f"WriteParam?action=writeparam&{kq}={vq}",
                log_io=True,
                short="PM",
            )

            body = (text or "").strip()
            if body and not body.lower().startswith("ok"):
                raise ApiError("http", "SYS_PRODUCT_MODEL write rejected", detail=body[:200])

            # 2) ReadParam verify
            read_text = self._readparam_text_with_fallback("SYS_PRODUCT_MODEL", log_io=False)
            read_val = self._extract_kv_value(read_text, "SYS_PRODUCT_MODEL")

            self.sig_product_model.emit(True, val, read_val)

        except ApiError as e:
            msg = f"{e.kind}: {e.message}"
            if e.detail:
                msg += f" | {e.detail}"
            self.sig_product_model.emit(False, val, msg)
            raise

    def _op_fw_upload(self, filepath: str) -> None:
        self._check_cancel()
        path = (filepath or "").strip()
        if not path:
            raise ApiError("param", "firmware path empty")
        if not os.path.exists(path):
            raise ApiError("param", "firmware file not found", detail=path)

        basename = os.path.basename(path)

        # 파일명은 점/언더바/대시 정도는 그대로 두는 편이 안전(장비별 처리 차이)
        kq = self._q("SYS_REMOTEUPGRADEUSERINFO")
        vq = self._q(basename, safe="._-")
        self._writeparam_raw(f"action=writeparam&{kq}={vq}", allow_non200=False, log_io=True)

        self._check_cancel()

        self._disconnect_on_poll_fail = True

        try:
            with _LoggerSilencer(self._mute_loggers):
                res = upload_firmware_progress_html(
                    base_url=self._cfg.base_url,
                    root_path=self._cfg.root_path,
                    username=self._cfg.username,
                    password=self._cfg.password,
                    auth_scheme=self._cfg.auth_scheme,
                    verify_tls=self._cfg.verify_tls,
                    timeout_sec=float(max(self._settings.timeout.read_sec, 10.0)),
                    retry=self._settings.retry or RetrySettings(),
                    filepath=path,
                )
            if int(getattr(res, "status", 0)) in (200, 204, 302, 303):
                self.sig_log.emit("FW UP OK")
            else:
                self.sig_log.emit("FW UP ER")

        finally:
            self._trigger_disconnect("firmware upload requested (device may reboot)")

    def _getstate(self, query: str, *, log_io: bool, short: str) -> str:
        return self._request_text_with_fallback(f"GetState?{query.lstrip('?')}", log_io=log_io, short=short)

    def _pop_task(self) -> Optional[HubTask]:
        return self._queue.pop(0) if self._queue else None

    def _trigger_disconnect(self, reason: str) -> None:
        if self._disconnect_requested:
            return
        self._disconnect_requested = True
        self._disconnect_reason = reason or "disconnect"

        self._suspend_polling = True

        self.sig_error.emit({
            "kind": "disconnect",
            "message": "disconnect required",
            "status_code": None,
            "detail": self._disconnect_reason,
        })

        with self._lock:
            self._cancel = True
            self._queue.clear()
            self._latest_move = None
            self._hold_joy = False
            self._hold_zoom = False
            self._hold_focus = False
            self._lock.notify_all()

    def run(self) -> None:
        try:
            self._ensure_client()
            self.sig_state.emit("hub started")

            poll_interval = max(100, int(self._cfg.poll_interval_ms))
            cont_interval = max(100, int(self._cfg.continue_interval_ms))

            last_move_sent = {"direction": None, "speed": None}

            while True:
                with self._lock:
                    if self._cancel:
                        break

                    now = time.monotonic()
                    task = self._pop_task()
                    due_continue = (now >= self._next_continue_t)
                    due_poll = (now >= self._next_poll_t)

                    if task is None and not due_continue and not due_poll and self._latest_move is None:
                        wake_in = min(self._next_continue_t, self._next_poll_t) - now
                        wake_in = max(0.05, min(0.3, wake_in))
                        self._lock.wait(timeout=wake_in)
                        continue

                try:
                    self._check_cancel()
                    now2 = time.monotonic()

                    if task is not None:
                        if task.kind == "ptz_stop":
                            self._op_ptz_stop()

                        elif task.kind == "ptz_release_joy":
                            self._hold_joy = False
                            self._op_ptz_stop()

                        elif task.kind == "zoom_press":
                            mode = str(task.payload.get("mode") or "")
                            if mode in ("zoomin", "zoomout"):
                                self._op_zoom_press(mode)

                        elif task.kind == "zoom_release":
                            self._op_zoom_release()

                        elif task.kind == "focus_press":
                            mode = str(task.payload.get("mode") or "")
                            if mode in ("focusnear", "focusfar"):
                                self._op_focus_press(mode)

                        elif task.kind == "focus_release":
                            self._op_focus_release()

                        elif task.kind == "focus_auto":
                            self._op_focus_auto()

                        elif task.kind == "ptz_home":
                            self._op_ptz_home()

                        elif task.kind == "zoom_1x":
                            self._op_zoom_1x()

                        elif task.kind == "writeparam":
                            k = str(task.payload.get("key") or "")
                            v = str(task.payload.get("value") or "")
                            if k:
                                self._op_writeparam(k, v)

                        elif task.kind == "readparam":
                            k = str(task.payload.get("key") or "")
                            if k:
                                self._op_readparam(k)

                        elif task.kind == "audio_caps_scan":
                            self._op_audio_caps_scan()

                        elif task.kind == "video_set_input_format":
                            input_code = str(task.payload.get("input_code") or "").strip()
                            resolution_code = str(task.payload.get("resolution_code") or "").strip()
                            if input_code and resolution_code:
                                self._op_video_set_input_format(
                                    input_code=input_code,
                                    resolution_code=resolution_code,
                                )

                        elif task.kind == "video_auto_detect":
                            self._op_video_auto_detect()

                        elif task.kind == "reboot":
                            self._op_reboot()

                        elif task.kind == "factory_reset":
                            self._op_factory_reset()

                        elif task.kind == "lens_offset_lens":
                            self._op_lens_offset_lens()

                        elif task.kind == "lens_offset_zoomlens":
                            self._op_lens_offset_zoomlens()

                        elif task.kind == "set_model_name":
                            self._op_set_model_name(str(task.payload.get("model_name") or ""))

                        elif task.kind == "set_extra_id":
                            self._op_set_extra_id(str(task.payload.get("value") or ""))

                        elif task.kind == "set_product_model":
                            self._op_set_product_model(str(task.payload.get("value") or ""))

                        elif task.kind == "cam_log_load":
                            try:
                                short = "LG"
                                text = self._getstate("action=getnewlog&GNL_READ=65535", log_io=True, short=short)
                                self.sig_cam_log.emit(True, text or "")
                            except ApiError as e:
                                self.sig_cam_log.emit(False, "")
                                self.sig_error.emit(e.to_dict())

                        elif task.kind == "fw_upload":
                            path = str(task.payload.get("filepath") or "")
                            self.sig_task.emit("fw_upload", "start", True, path)

                            self._suspend_polling = True
                            try:
                                self._op_fw_upload(path)
                                self.sig_task.emit("fw_upload", "end", True, "upload done (device may reboot)")

                            except ApiError as e:
                                detail = (e.detail or "").lower()
                                msg = (e.message or "").lower()
                                maybe_reboot_disconnect = (
                                    e.kind in ("network", "timeout")
                                    and (
                                        "10061" in detail
                                        or "connection refused" in detail
                                        or "eof occurred" in detail
                                        or "timed out" in detail
                                        or "ssl" in msg
                                    )
                                )
                                if maybe_reboot_disconnect:
                                    self.sig_log.emit("FW UP OK")
                                    self.sig_task.emit("fw_upload", "end", True, "connection dropped (likely reboot)")
                                else:
                                    self.sig_task.emit("fw_upload", "end", False, f"{e.kind}: {e.message}")
                                    self.sig_error.emit(e.to_dict())

                            finally:
                                self._suspend_polling = False

                        if self._cancel or self._disconnect_requested:
                            break

                    if self._hold_joy and self._latest_move is not None:
                        d = self._latest_move.get("direction")
                        s = int(self._latest_move.get("speed", 0))
                        if d != last_move_sent["direction"] or s != last_move_sent["speed"]:
                            self._op_ptz_move_latest()
                            last_move_sent = {"direction": d, "speed": s}

                    if now2 >= self._next_continue_t:
                        if self._hold_joy or self._hold_zoom or self._hold_focus:
                            self._op_ptz_continue_if_needed()
                        self._next_continue_t = now2 + (cont_interval / 1000.0)

                    if now2 >= self._next_poll_t:
                        if not self._suspend_polling:
                            if not (self._hold_joy or self._hold_zoom or self._hold_focus):
                                try:
                                    self._op_poll()
                                except ApiError as e:
                                    if self._disconnect_on_poll_fail:
                                        self._trigger_disconnect(f"status unavailable after fw/reset: {e.kind}")
                                        break
                                    if not self._suppress_poll_errors:
                                        self.sig_error.emit(e.to_dict())
                                except Exception as e:
                                    if self._disconnect_on_poll_fail:
                                        self._trigger_disconnect(f"status unavailable after fw/reset: {e}")
                                        break
                        self._next_poll_t = now2 + (poll_interval / 1000.0)

                except ApiError as e:
                    if e.kind == "ui" and e.message == "cancelled":
                        break
                    self.sig_error.emit(e.to_dict())
                except Exception as e:
                    self.sig_error.emit(
                        {"kind": "ui", "message": "unexpected error", "status_code": None, "detail": str(e)}
                    )

        finally:
            self.sig_state.emit("hub stopped")