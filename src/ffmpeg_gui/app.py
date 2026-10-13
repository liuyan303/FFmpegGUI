"""Application entry point."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from . import __app_name__, __version__, config, logging_setup, theme
from .ffmpeg import find_ffmpeg
from .i18n import AUTO_LANG, available_languages, current_language, set_language
from .resources import find_file
from .runner import configure_no_console

log = logging.getLogger(__name__)

APP_USER_MODEL_ID = "FFmpegGUI.FFmpegGUI"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ffmpeg-gui",
        description=f"{__app_name__} {__version__}",
    )
    parser.add_argument(
        "--version", action="store_true", help="print the version and exit"
    )
    parser.add_argument(
        "--lang",
        metavar="CODE",
        help="force a UI language (e.g. zh_CN / en_US); overrides the settings",
    )
    parser.add_argument(
        "--debug", action="store_true", help="enable debug logging"
    )
    parser.add_argument(
        "--selftest",
        metavar="PATH",
        help="run a headless smoke test and write a JSON report, then exit",
    )
    return parser.parse_args(argv)


def _set_windows_app_id() -> None:
    """Group the taskbar icon properly on Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            APP_USER_MODEL_ID
        )
    except Exception:  # pragma: no cover - never fatal
        pass


def _create_application(argv: list[str]) -> QApplication:
    app = QApplication(argv)
    app.setApplicationName("FFmpegGUI")
    app.setApplicationDisplayName(__app_name__)
    app.setApplicationVersion(__version__)
    app.setOrganizationName("FFmpegGUI")
    app.setDesktopFileName("FFmpegGUI")
    app.setStyleSheet(theme.APP_QSS)

    icon_path = find_file("assets", "icon.ico") or find_file("assets", "icon.png")
    if icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))
    return app


def _run_selftest(app: QApplication, window, report_path: str) -> int:
    """Headless smoke test used by CI and packaging scripts."""
    report = {
        "ok": True,
        "app": __app_name__,
        "version": __version__,
        "language": current_language(),
        "languages": [entry["code"] for entry in available_languages()],
        "ffmpeg": find_ffmpeg(config.get_str("ffmpeg/path")) or "",
    }
    try:
        window.show()
        app.processEvents()
    except Exception as exc:  # noqa: BLE001 - reported in the JSON
        report["ok"] = False
        report["error"] = repr(exc)
    try:
        Path(report_path).write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    except OSError as exc:
        log.warning("could not write selftest report: %s", exc)
        return 1
    return 0 if report["ok"] else 1


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    if args.version:
        print(f"{__app_name__} {__version__}")
        return 0

    logging_setup.setup_logging(debug=args.debug)
    logging_setup.install_excepthook()
    _set_windows_app_id()

    app = _create_application(sys.argv[:1])

    # Language: CLI flag > saved setting > system detection ("auto").
    language = args.lang or config.get_str("ui/language", AUTO_LANG)
    set_language(language)
    log.info("UI language: %s", current_language())

    theme.apply_theme(app, config.get_str("ui/theme", theme.THEME_SYSTEM))
    configure_no_console()

    # Imported late so the QApplication exists before widgets are touched.
    from .ui.main_window import MainWindow

    window = MainWindow()

    if args.selftest:
        return _run_selftest(app, window, args.selftest)

    window.show()
    if not window.has_ffmpeg():
        # Give the window a moment to paint, then offer the auto-setup.
        QTimer.singleShot(400, window.maybe_prompt_ffmpeg_install)
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
