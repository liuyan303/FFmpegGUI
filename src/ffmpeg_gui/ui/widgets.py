"""Small reusable widgets: the drag & drop area and collapsible section."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class DropArea(QFrame):
    """A drag & drop target that also acts as a browse button.

    Emits :attr:`fileDropped` with the first dropped local file and
    :attr:`clicked` when the user clicks anywhere on the area.
    """

    fileDropped = Signal(str)
    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dropArea")
        self.setAcceptDrops(True)
        self.setProperty("dragActive", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(92)

        self._title = QLabel(self)
        self._title.setObjectName("dropTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle = QLabel(self)
        self._subtitle.setObjectName("dropSubtitle")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        layout.addStretch(1)
        layout.addWidget(self._title)
        layout.addWidget(self._subtitle)
        layout.addStretch(1)

    # ------------------------------------------------------------------ i18n
    def setTexts(self, title: str, subtitle: str) -> None:
        self._title.setText(title)
        self._subtitle.setText(subtitle)

    # ---------------------------------------------------------- drag & drop
    @staticmethod
    def _local_files(event) -> list[str]:
        if not event.mimeData().hasUrls():
            return []
        files: list[str] = []
        for url in event.mimeData().urls():
            if url.isLocalFile():
                files.append(url.toLocalFile())
        return files

    def dragEnterEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._local_files(event):
            self._set_drag_active(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self._set_drag_active(False)

    def dropEvent(self, event) -> None:  # noqa: N802
        self._set_drag_active(False)
        files = self._local_files(event)
        if files:
            event.acceptProposedAction()
            self.fileDropped.emit(files[0])

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def _set_drag_active(self, active: bool) -> None:
        self.setProperty("dragActive", active)
        style = self.style()
        style.unpolish(self)
        style.polish(self)


class CollapsibleBox(QWidget):
    """A header button that shows or hides its content widget."""

    def __init__(
        self,
        title: str = "",
        expanded: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._button = QToolButton(self)
        self._button.setObjectName("collapsibleHeader")
        self._button.setCheckable(True)
        self._button.setChecked(expanded)
        self._button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self._button.setText(title)

        self._content = QWidget(self)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(10, 4, 10, 10)
        self._content.setVisible(expanded)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._button)
        outer.addWidget(self._content)

        self._button.toggled.connect(self._on_toggled)

    def _on_toggled(self, checked: bool) -> None:
        self._content.setVisible(checked)
        self._button.setArrowType(
            Qt.ArrowType.DownArrow if checked else Qt.ArrowType.RightArrow
        )

    def setTitle(self, title: str) -> None:  # noqa: N802 (Qt API)
        self._button.setText(title)

    def setExpanded(self, expanded: bool) -> None:  # noqa: N802
        self._button.setChecked(expanded)

    def isExpanded(self) -> bool:  # noqa: N802
        return self._button.isChecked()

    def contentLayout(self) -> QVBoxLayout:  # noqa: N802
        return self._content_layout
