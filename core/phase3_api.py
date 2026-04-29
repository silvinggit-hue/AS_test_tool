from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from core.cam_api_client import CamApiClient
from core.kv_utils import parse_kv_lines
from models.dto import ApiError


@dataclass(frozen=True)
class Phase3Api:
    """
    Phase3(WriteParam/SetState/SendPTZ) wrapper.

    PTZ는 Web UI 규격(PTZ_CHANNEL, PTZ_MOVE, PTZ_TIMEOUT)을 사용한다.
    """
    client: CamApiClient

    def read_value(self, key: str) -> str:
        txt = self.client.read_param_text(key)
        kv = parse_kv_lines(txt)
        return kv.get(key, "")

    def write_param(self, key: str, value: str) -> None:
        kq = quote(key, safe="")
        vq = quote(value or "", safe="")
        tail = f"WriteParam?action=writeparam&{kq}={vq}"
        resp = self.client._request(tail)  # pylint: disable=protected-access

        if resp.status == 200:
            return
        if resp.status in (401, 403):
            raise ApiError(
                kind="auth",
                message="authentication failed",
                status_code=resp.status,
                detail=(resp.body or "")[:200],
            )
        raise ApiError(
            kind="http",
            message="write_param failed",
            status_code=resp.status,
            detail=(resp.body or "")[:200],
        )

    def set_state(self, key: str, value: str) -> None:
        kq = quote(key, safe="")
        vq = quote(value or "", safe="")
        tail = f"SetState?action=setstate&{kq}={vq}"
        resp = self.client._request(tail)  # pylint: disable=protected-access

        if resp.status == 200:
            return
        if resp.status in (401, 403):
            raise ApiError(
                kind="auth",
                message="authentication failed",
                status_code=resp.status,
                detail=(resp.body or "")[:200],
            )
        raise ApiError(
            kind="http",
            message="set_state failed",
            status_code=resp.status,
            detail=(resp.body or "")[:200],
        )

    def send_ptz_move(self, *, channel: int, move: str, timeout_ms: int | None = 5000) -> None:
        """
        SendPTZ?action=sendptz&PTZ_CHANNEL=1&PTZ_MOVE=right,9&PTZ_TIMEOUT=5000
        SendPTZ?action=sendptz&PTZ_CHANNEL=1&PTZ_MOVE=stop
        """
        params: list[str] = [
            "action=sendptz",
            f"PTZ_CHANNEL={int(channel)}",
            f"PTZ_MOVE={quote(move or '', safe=',')}",
        ]
        if timeout_ms is not None and (move or "").lower() != "stop":
            params.append(f"PTZ_TIMEOUT={int(timeout_ms)}")

        tail = "SendPTZ?" + "&".join(params)
        resp = self.client._request(tail)  # pylint: disable=protected-access

        if resp.status == 200:
            body = (resp.body or "").strip().lower()
            if body and any(x in body for x in ("ng", "error", "fail", "invalid")):
                raise ApiError(
                    kind="compat",
                    message="ptz rejected",
                    status_code=200,
                    detail=(resp.body or "")[:200],
                )
            return

        if resp.status in (401, 403):
            raise ApiError(
                kind="auth",
                message="authentication failed",
                status_code=resp.status,
                detail=(resp.body or "")[:200],
            )

        raise ApiError(
            kind="http",
            message="send_ptz_move failed",
            status_code=resp.status,
            detail=(resp.body or "")[:200],
        )

    def send_ptz(self, cmd_key: str, value: str, *, speed: int | None = None, ch: int | None = None) -> None:
        raise ApiError(
            kind="compat",
            message="legacy PTZ key/value mode is not supported on this firmware; use send_ptz_move(PTZ_MOVE...)",
            detail=f"cmd_key={cmd_key!r} value={value!r} speed={speed!r} ch={ch!r}",
        )