"""File logging and a crash dialog, so user bug reports are actionable.

A rotating log file is written to ``%LOCALAPPDATA%\\FFmpegGUI\\logs``.
Set the environment variable ``FFMPEG_GUI_DEBUG=1`` (or pass ``--debug``)
for verbose logging.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import traceback
from pathlib import Path

LOG_FILENAME = "ffmpeg-gui.log"
LOGGER_NAME = "ffmpeg_gui"

_log_path: Path | None = None


def log_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    directory = Path(base) / "FFmpegGUI" / "logs"
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError:
        directory = Path.cwd()
    return directory


def log_file_path() -> Path | None:
    return _log_path


def setup_logging(debug: bool = False) -> None:
    global _log_path
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    if root.handlers:
        return

    try:
        _log_path = log_dir() / LOG_FILENAME
        handler: logging.Handler = logging.handlers.RotatingFileHandler(
            _log_path, maxBytes=1_000_000, backupCount=2, encoding="utf-8"
        )
    except OSError:
        handler = logging.NullHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root.addHandler(handler)

    if not getattr(sys, "frozen", False):
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        root.addHandler(console)


def install_excepthook() -> None:
    """Log unhandled exceptions and show a friendly dialog when possible."""

    def _hook(exc_type, exc_value, tb) -> None:
        logging.getLogger(LOGGER_NAME).critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, tb)
        )
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is None:
                return
            from .i18n import t

            details = "".join(traceback.format_exception(exc_type, exc_value, tb))
            logging.getLogger(LOGGER_NAME).debug(details)
            box = QMessageBox()
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle(t("crash.title"))
            box.setText(t("crash.body"))
            box.setDetailedText(details)
            box.exec()
        except Exception:
            pass

    sys.excepthook = _hook
