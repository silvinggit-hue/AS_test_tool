from __future__ import annotations

import re
from dataclasses import dataclass

from core.cam_api_client import CamApiClient
from core.kv_utils import parse_kv_lines, pick
from core.readparam_keys import (
    STATUS_ETHTOOL_KEYS,
    STATUS_INPUT_KEYS,
    STATUS_RATE_KEYS,
    STATUS_READPARAM_KEYS,
)
from models.dto import ApiError


@dataclass(frozen=True)
class CamStatusReader:
    client: CamApiClient

    READPARAM_KEYS: tuple[str, ...] = STATUS_READPARAM_KEYS
    RATE_KEYS: tuple[str, ...] = STATUS_RATE_KEYS
    INPUT_KEYS: tuple[str, ...] = STATUS_INPUT_KEYS
    ETHTOOL_KEYS: tuple[str, ...] = STATUS_ETHTOOL_KEYS

    @staticmethod
    def _extract_ints(text: str | None) -> list[str]:
        if not text:
            return []
        return re.findall(r"(-?\d+)", text)

    @staticmethod
    def _parse_cds_current_pair(text: str | None) -> tuple[str | None, str | None]:
        if not text:
            return (None, None)

        t = " ".join(str(text).split())
        m_cur = re.search(r"\bCurrent\s+Value\s+(-?\d+)\b", t, flags=re.IGNORECASE)
        m_cds = re.search(r"\bCDS\s+Value\s+(-?\d+)\b", t, flags=re.IGNORECASE)
        cds = m_cds.group(1) if m_cds else None
        cur = m_cur.group(1) if m_cur else None
        return (cds, cur)

    def _getstate_text(self, action: str, keys: tuple[str, ...], *, optional: bool = False) -> str:
        if not keys:
            return ""

        parts = "&".join([f"{k}=0" for k in keys])
        tail = f"GetState?action={action}&{parts}"

        try:
            resp = self.client._request(tail)  # pylint: disable=protected-access
        except ApiError:
            if optional:
                return ""
            raise

        if resp.status == 200:
            return resp.body or ""

        if optional:
            return ""

        if resp.status in (401, 403):
            raise ApiError(
                kind="auth",
                message="authentication failed",
                status_code=resp.status,
                detail=(resp.body or "")[:200],
            )

        raise ApiError(
            kind="http",
            message="getstate failed",
            status_code=resp.status,
            detail=(resp.body or "")[:200],
        )

    @staticmethod
    def _format_link_speed_from_ethtool(code: str | None) -> str | None:
        if code is None:
            return None
        v = str(code).strip()
        if v == "":
            return None

        # 당신이 확인한 매핑: 24=1G, 22=100M
        if v == "24":
            return "1G"
        if v == "22":
            return "100M"

        # 혹시 다른 코드가 나오면 raw 표기
        return f"ETHTOOL({v})"

    def read_status_block(self) -> dict:
        rp_text = self.client.read_params_text(list(self.READPARAM_KEYS))
        rp_kv = parse_kv_lines(rp_text)

        rate_text = self._getstate_text("getrate", self.RATE_KEYS, optional=False)
        rate_kv = parse_kv_lines(rate_text)

        in_text = self._getstate_text("getinput", self.INPUT_KEYS, optional=True)
        in_kv = parse_kv_lines(in_text) if in_text else {}

        cds_raw = pick(rp_kv, "CAM_HI_CURRENT_Y", "GIS_CDS", "GIS_CDS_CUR", "GIS_CDS_CURRENT")

        cds, cds_current = self._parse_cds_current_pair(cds_raw)
        if cds is None and cds_current is None:
            ints = self._extract_ints(cds_raw)
            cds = ints[0] if len(ints) >= 1 else (cds_raw.strip() if cds_raw else None)
            cds_current = ints[1] if len(ints) >= 2 else None

        rtc = pick(rp_kv, "SYS_CURRENTTIME", "GIS_RTC", "RTC_TIME")
        temp = pick(rp_kv, "SYS_BOARDTEMP", "SYS_BOARD_TEMP", "ETC_BOARDTEMP")
        fan = pick(rp_kv, "SYS_FANSTATUS", "SYS_FAN_STATUS", "FAN_STATUS")

        link_state = pick(rp_kv, "NET_LINKSTATE", "NET_LINK_STATE")
        link_speed = pick(rp_kv, "NET_LINKSPEED", "NET_LINK_SPEED")
        eth = (
            f"{link_state or 'None'} / {link_speed or 'None'}"
            if (link_state or link_speed)
            else pick(rp_kv, "SYS_ETHERNET")
        )

        ethtool_kv: dict[str, str] = {}
        if not eth or str(eth).strip() in ("", "None", "None / None"):
            ethtool_text = self._getstate_text("ethtool", self.ETHTOOL_KEYS, optional=True)
            if ethtool_text:
                ethtool_kv = parse_kv_lines(ethtool_text)
                sp = self._format_link_speed_from_ethtool(ethtool_kv.get("ETHTOOL"))
                if sp:
                    # link_state는 못 얻을 수도 있으니 speed만이라도 표시
                    eth = f"link / {sp}"

        fps1 = pick(rate_kv, "GRS_VENCFRAME1")
        br1 = pick(rate_kv, "GRS_VENCBITRATE1")

        raw_all = dict(rp_kv)
        raw_all.update(rate_kv)
        raw_all.update(in_kv)
        raw_all.update(ethtool_kv)

        return {
            "temp": temp,
            "cds": cds,
            "cds_current": cds_current,
            "rtc": rtc,
            "fan": fan,
            "eth": eth,
            "rate": {"kbps": br1, "fps": fps1},
            "raw": raw_all,
        }