from __future__ import annotations

from PyQt5.QtCore import QRect
from PyQt5.QtWidgets import QWidget


class AspectRatioContainer(QWidget):
    """
    자식 위젯을 지정한 종횡비로 유지하면서 중앙에 배치한다.
    """

    def __init__(self, child: QWidget, aspect_w: int = 16, aspect_h: int = 9, parent=None) -> None:
        super().__init__(parent)
        self._child: QWidget | None = None
        self._aw = max(1, int(aspect_w))
        self._ah = max(1, int(aspect_h))
        self.set_child(child)

    def set_aspect(self, w: int, h: int) -> None:
        self._aw = max(1, int(w))
        self._ah = max(1, int(h))
        self._relayout()

    def set_child(self, child: QWidget) -> None:
        if self._child is child:
            return

        if self._child is not None:
            try:
                self._child.setParent(None)
                self._child.hide()
            except Exception:
                pass

        self._child = child
        self._child.setParent(self)
        self._child.show()
        self._relayout()

    def resizeEvent(self, e) -> None:  # noqa
        super().resizeEvent(e)
        self._relayout()

    def _relayout(self) -> None:
        if self._child is None:
            return

        cw = self.width()
        ch = self.height()
        if cw <= 0 or ch <= 0:
            return

        target_ratio = self._aw / self._ah
        container_ratio = cw / ch

        if container_ratio >= target_ratio:
            h = ch
            w = int(h * target_ratio)
        else:
            w = cw
            h = int(w / target_ratio)

        x = (cw - w) // 2
        y = (ch - h) // 2
        self._child.setGeometry(QRect(x, y, w, h))