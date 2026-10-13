"""Light / dark / system theme handling."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

THEME_SYSTEM = "system"
THEME_LIGHT = "light"
THEME_DARK = "dark"
THEMES = (THEME_SYSTEM, THEME_LIGHT, THEME_DARK)

_default_style: str | None = None
_default_palette: QPalette | None = None


def _dark_palette() -> QPalette:
    palette = QPalette()
    window = QColor(53, 54, 58)
    base = QColor(42, 43, 47)
    text = QColor(232, 233, 236)
    disabled = QColor(130, 131, 136)

    palette.setColor(QPalette.ColorRole.Window, window)
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, base)
    palette.setColor(QPalette.ColorRole.AlternateBase, window)
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(25, 25, 25))
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, window)
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 90, 90))
    palette.setColor(QPalette.ColorRole.Link, QColor(90, 160, 255))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(61, 126, 255))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(140, 141, 146))
    palette.setColor(QPalette.ColorRole.Mid, QColor(90, 91, 96))

    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


def apply_theme(app: QApplication, theme: str) -> str:
    """Apply *theme*; returns the concrete theme used.

    ``"system"`` is resolved from the platform color scheme hint
    (Qt >= 6.5). Unknown values fall back to the light theme.
    """
    global _default_style, _default_palette
    if _default_style is None:
        _default_style = app.style().objectName()
    if _default_palette is None:
        _default_palette = QPalette(app.palette())

    resolved = theme
    if theme == THEME_SYSTEM:
        hints = app.styleHints()
        getter = getattr(hints, "colorScheme", None)
        try:
            scheme = getter() if getter else None
        except Exception:
            scheme = None
        resolved = THEME_DARK if scheme == Qt.ColorScheme.Dark else THEME_LIGHT

    if resolved == THEME_DARK:
        app.setStyle("Fusion")
        app.setPalette(_dark_palette())
    else:
        from PySide6.QtWidgets import QStyleFactory

        style = QStyleFactory.create(_default_style) if _default_style else None
        if style is not None:
            app.setStyle(style)
        if _default_palette is not None:
            app.setPalette(_default_palette)
    return resolved


#: Global stylesheet: uses palette() references so it adapts to both themes.
APP_QSS = """
QFrame#dropArea {
    border: 2px dashed palette(mid);
    border-radius: 10px;
    background: palette(base);
}
QFrame#dropArea[dragActive="true"] {
    border: 2px solid #3d7eff;
    background: rgba(61, 126, 255, 0.10);
}
QLabel#dropTitle { font-size: 15px; font-weight: 600; }
QLabel#dropSubtitle { color: palette(mid); }
QToolButton#collapsibleHeader {
    border: none;
    font-weight: 600;
    padding: 6px 2px;
    text-align: left;
}
QPushButton#startButton {
    background-color: #2563eb;
    color: #ffffff;
    border: none;
    border-radius: 6px;
    padding: 9px 28px;
    font-size: 14px;
    font-weight: 600;
}
QPushButton#startButton:hover { background-color: #1d4ed8; }
QPushButton#startButton:pressed { background-color: #1e40af; }
QPushButton#startButton:disabled { background-color: #93b0e8; }
"""
