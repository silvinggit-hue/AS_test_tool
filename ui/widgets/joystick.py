from __future__ import annotations

from PyQt5.QtCore import pyqtSignal, QPointF, Qt, QTimer
from PyQt5.QtGui import QPainter, QBrush, QColor
from PyQt5.QtWidgets import QWidget


class JoystickWidget(QWidget):
    """
    dx, dy: [-1..1]

    - 입력은 원형으로 clamp한다.
    - 드래그 중에는 주기적으로 changed를 emit한다(이벤트 누락 대비).
    """
    changed = pyqtSignal(float, float)  # dx, dy in [-1..1]

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)

        self.dragging = False
        self.pos = QPointF(0.0, 0.0)

        self._tick = QTimer(self)
        self._tick.setInterval(40)
        self._tick.timeout.connect(self._emit_current)

    def _center(self) -> tuple[float, float]:
        return (self.width() / 2.0, self.height() / 2.0)

    def _normalize_circle(self, x: float, y: float) -> tuple[float, float]:
        r2 = x * x + y * y
        if r2 <= 1.0:
            return (x, y)
        r = r2**0.5
        if r <= 0.0:
            return (0.0, 0.0)
        return (x / r, y / r)

    def _update_pos_from_event(self, ev) -> None:
        w = max(1.0, float(self.width()))
        h = max(1.0, float(self.height()))
        cx, cy = self._center()

        nx = (ev.pos().x() - cx) / (w / 2.0)
        ny = (ev.pos().y() - cy) / (h / 2.0)

        nx, ny = self._normalize_circle(float(nx), float(ny))

        self.pos = QPointF(nx, ny)
        self.changed.emit(nx, ny)
        self.update()

    def _emit_current(self) -> None:
        if self.dragging:
            self.changed.emit(float(self.pos.x()), float(self.pos.y()))

    def _reset_to_center(self) -> None:
        self.pos = QPointF(0.0, 0.0)
        self.changed.emit(0.0, 0.0)
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() != Qt.LeftButton:
            return

        try:
            self.grabMouse()
        except Exception:
            pass

        self.dragging = True
        self._tick.start()
        self._update_pos_from_event(ev)

    def mouseMoveEvent(self, ev):
        if not self.dragging:
            return
        self._update_pos_from_event(ev)

    def mouseReleaseEvent(self, ev):
        self.dragging = False
        self._tick.stop()
        try:
            self.releaseMouse()
        except Exception:
            pass
        self._reset_to_center()

    def leaveEvent(self, ev):
        super().leaveEvent(ev)

    def focusOutEvent(self, ev):
        if self.dragging:
            self.dragging = False
            self._tick.stop()
            try:
                self.releaseMouse()
            except Exception:
                pass
            self._reset_to_center()
        super().focusOutEvent(ev)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        p.setBrush(QBrush(QColor("#111")))
        p.setPen(Qt.NoPen)
        p.drawEllipse(0, 0, self.width(), self.height())

        cx, cy = self._center()
        r = min(self.width(), self.height()) * 0.18

        max_r = (min(self.width(), self.height()) / 2.0) - r - 2.0
        kx = cx + float(self.pos.x()) * max_r
        ky = cy + float(self.pos.y()) * max_r

        p.setBrush(QBrush(QColor("#ccc")))
        p.drawEllipse(int(kx - r), int(ky - r), int(r * 2), int(r * 2))