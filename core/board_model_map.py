from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict

log = logging.getLogger(__name__)


def _read_text_with_fallback(path: Path) -> str:
    """
    board_model_map 파일은 인코딩이 혼재될 수 있어 순차적으로 시도한다.
    """
    errors = []

    for enc in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return path.read_text(encoding=enc)
        except Exception as e:
            errors.append(f"{enc}: {e}")

    raise RuntimeError(
        f"Failed to read board_model_map file: {path}\n" + "\n".join(errors)
    )


def load_board_model_map(path: str | Path) -> Dict[str, str]:
    """
    지원 형식:
      BOARDID=MODELNAME
      BOARDID , MODELNAME
      BOARDID MODELNAME

    - '#' 주석 및 빈 줄 무시
    - BOARDID는 문자열 그대로 key로 사용
    """
    p = Path(path)
    if not p.exists():
        log.warning("[BOARD_MAP] file not found: %s", p)
        return {}

    try:
        text = _read_text_with_fallback(p)
    except Exception:
        log.exception("[BOARD_MAP] failed to read file: %s", p)
        return {}

    out: Dict[str, str] = {}

    for lineno, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()

        if not line or line.startswith("#"):
            continue

        key: str | None = None
        val: str | None = None

        if "=" in line:
            key, val = line.split("=", 1)
        elif "," in line:
            key, val = line.split(",", 1)
        else:
            parts = line.split()
            if len(parts) >= 2:
                key = parts[0]
                val = " ".join(parts[1:])

        if key is None or val is None:
            log.warning("[BOARD_MAP] skip invalid line %d: %r", lineno, raw)
            continue

        key = key.strip()
        val = val.strip()

        if not key or not val:
            log.warning("[BOARD_MAP] skip empty key/value at line %d: %r", lineno, raw)
            continue

        out[key.upper().lstrip("0X")] = val

    log.info("[BOARD_MAP] loaded %d entries from %s", len(out), p)
    return out