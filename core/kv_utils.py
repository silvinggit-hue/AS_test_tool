from __future__ import annotations

from typing import Iterable


def parse_kv_lines(text: str) -> dict[str, str]:
    """
    KEY=VALUE 형식의 라인을 파싱한다.
    """
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        out[k] = v
    return out


def pick(kv: dict[str, str], *cands: str) -> str | None:
    """
    후보 키 중 첫 번째 유효 값을 반환한다.
    """
    for c in cands:
        v = kv.get(c)
        if v not in (None, ""):
            return v
    return None


def join_kv_dicts(*dicts: Iterable[dict[str, str]]) -> dict[str, str]:
    """
    여러 dict를 순차적으로 병합한다. (후행 dict 우선)
    """
    out: dict[str, str] = {}
    for d in dicts:
        for x in d:
            out.update(x)
    return out