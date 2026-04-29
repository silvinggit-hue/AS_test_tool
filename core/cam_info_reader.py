from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable

from core.cam_api_client import CamApiClient
from core.kv_utils import parse_kv_lines
from core.readparam_keys import (
    DEVICE_INFO_FAST_KEYS,
    DEVICE_INFO_KEYS,
    DEVICE_INFO_SLOW_KEYS,
)
from models.dto import ApiError

log = logging.getLogger(__name__)

PASSWORD_TEST_KEY = "ETC_MIN_PASSWORD_LEN"


@dataclass(frozen=True)
class CamInfoReader:
    client: CamApiClient

    FAST_KEYS: tuple[str, ...] = DEVICE_INFO_FAST_KEYS
    SLOW_KEYS: tuple[str, ...] = DEVICE_INFO_SLOW_KEYS

    @staticmethod
    def _chunks(items: list[str], n: int) -> Iterable[list[str]]:
        n = max(1, int(n))
        for i in range(0, len(items), n):
            yield items[i : i + n]

    def _read_multi_with_fallback(self, keys: list[str]) -> str:
        """
        ReadParam 멀티 요청이 불안정한 장비가 있어 단계적으로 분할하여 시도한다.
        """
        if not keys:
            return ""

        try:
            return (self.client.read_params_text(keys) or "").strip()
        except ApiError as e:
            if e.kind not in ("timeout", "network", "http", "auth"):
                raise

        out_lines: list[str] = []
        try:
            for ck in self._chunks(keys, 6):
                txt = self.client.read_params_text(ck)
                if txt:
                    out_lines.append(txt.rstrip("\r\n"))
            return "\n".join(out_lines).strip()
        except ApiError as e:
            if e.kind not in ("timeout", "network", "http", "auth"):
                raise

        out_lines = []
        try:
            for ck in self._chunks(keys, 3):
                txt = self.client.read_params_text(ck)
                if txt:
                    out_lines.append(txt.rstrip("\r\n"))
            return "\n".join(out_lines).strip()
        except ApiError as e:
            if e.kind not in ("timeout", "network", "http", "auth"):
                raise

        out_lines = []
        for k in keys:
            try:
                txt = self.client.read_param_text(k)
                if txt:
                    out_lines.append(txt.rstrip("\r\n"))
            except ApiError as e:
                log.warning(
                    "[INFO] ReadParam single fail key=%s kind=%s status=%s",
                    k,
                    e.kind,
                    e.status_code,
                )
                continue

        return "\n".join(out_lines).strip()

    def read_params_text(self, keys: list[str], *, include_slow: bool = False) -> str:
        if not keys:
            return ""

        scheme = (getattr(self.client, "auth_scheme", "") or "").lower().strip()

        if scheme == "basic":
            req_fast = [k for k in keys if k in self.FAST_KEYS]
            req_slow = [k for k in keys if k in self.SLOW_KEYS]
            req_rest = [k for k in keys if (k not in self.FAST_KEYS and k not in self.SLOW_KEYS)]

            out: list[str] = []

            if req_fast:
                out.append(self._read_multi_with_fallback(req_fast))

            if req_rest:
                out.append(self._read_multi_with_fallback(req_rest))

            if include_slow and req_slow:
                out.append(self._read_multi_with_fallback(req_slow))
            else:
                if req_slow:
                    log.info("[INFO] basic scheme: skip slow keys=%s", ",".join(req_slow))

            return "\n".join([t for t in out if t]).strip()

        return self._read_multi_with_fallback(keys)

    def get_info_block(self) -> dict[str, str]:
        text = self.read_params_text(list(DEVICE_INFO_KEYS), include_slow=False)
        data = parse_kv_lines(text)

        raw = data.get("SYS_BOARDID")
        if raw is not None:
            try:
                n = int(raw)
                data["BOARDID_DEC"] = str(n)
                data["BOARDID_HEX"] = hex(n)
            except Exception:
                pass

        return data