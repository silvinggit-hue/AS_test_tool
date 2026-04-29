from __future__ import annotations

import sys
import logging
import os
import pathlib
import faulthandler

import PyQt5
import urllib3
from PyQt5.QtWidgets import QApplication

from utils.logging_config import setup_logging
from ui.main_window import MainWindow

if sys.stderr is not None:
    faulthandler.enable(file=sys.stderr)

# PyInstaller/배포 환경에서 Qt 플러그인 경로가 꼬이는 경우를 대비한 환경 변수 설정
_qt_root = pathlib.Path(PyQt5.__file__).parent / "Qt5"
_plugins = _qt_root / "plugins"
_platforms = _plugins / "platforms"

os.environ.setdefault("QT_PLUGIN_PATH", str(_plugins))
os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(_platforms))
os.environ.setdefault("QT_QPA_PLATFORM", "windows")

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def main() -> int:
    setup_logging(level=logging.INFO)

    app = QApplication(sys.argv)

    w = MainWindow()
    w.show()

    screen = QApplication.primaryScreen()
    if screen is not None:
        geo = screen.availableGeometry()
        w.move(
            geo.center().x() - (w.width() // 2),
            geo.center().y() - (w.height() // 2),
        )

    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())