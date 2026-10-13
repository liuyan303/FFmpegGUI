"""Render README screenshots without a visible window.

Requirements: PySide6, and FFmpeg available via ``FFMPEG_PATH`` (a short
demo clip is generated with it). Usage:

    python scripts/screenshot.py en_US docs/screenshots/main_en.png
    python scripts/screenshot.py zh_CN docs/screenshots/main_zh.png

Note: the Qt ``offscreen`` platform plugin ships no font database, so text
would be rendered as empty boxes.  The native Windows plugin is used by
default - it can render a widget into a pixmap without ever showing a window.
Set ``QT_QPA_PLATFORM`` explicitly only if you know the plugin has fonts.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication, QScrollArea  # noqa: E402

from ffmpeg_gui import theme  # noqa: E402
from ffmpeg_gui.ffmpeg import CREATE_NO_WINDOW, find_ffmpeg  # noqa: E402
from ffmpeg_gui.i18n import set_language  # noqa: E402
from ffmpeg_gui.ui.main_window import MainWindow  # noqa: E402


def make_sample_clip(ffmpeg: str) -> str:
    """Generate a 10 s test clip so the screenshot shows real media info."""
    target = Path(tempfile.gettempdir()) / "ffmpeg_gui_demo.mp4"
    command = [
        ffmpeg,
        "-y", "-hide_banner", "-nostdin",
        "-f", "lavfi", "-i", "testsrc2=size=1280x720:rate=30:duration=10",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28",
        "-c:a", "aac", "-b:a", "128k",
        str(target),
    ]
    subprocess.run(
        command, capture_output=True, check=False, creationflags=CREATE_NO_WINDOW
    )
    return str(target)


def main() -> None:
    language = sys.argv[1] if len(sys.argv) > 1 else "en_US"
    output = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else ROOT / "docs" / "screenshots" / f"main_{language}.png"
    )

    app = QApplication(sys.argv[:1])
    app.setStyleSheet(theme.APP_QSS)
    set_language(language)
    theme.apply_theme(app, "light")

    window = MainWindow()
    window.resize(1020, 980)

    ffmpeg_path = find_ffmpeg(os.environ.get("FFMPEG_PATH"))
    if ffmpeg_path:
        sample = make_sample_clip(ffmpeg_path)
        if Path(sample).is_file():
            window.load_input(sample)

    window.show()
    for _ in range(12):
        app.processEvents()

    output.parent.mkdir(parents=True, exist_ok=True)

    # Grab the scrolled content rather than the window frame: on a small
    # screen the window is clamped to the work area and would clip the
    # lower half of the form.
    area = window.centralWidget()
    if isinstance(area, QScrollArea) and area.widget() is not None:
        inner = area.widget()
        inner.resize(area.viewport().width(), inner.sizeHint().height())
        for _ in range(8):
            app.processEvents()
        inner.grab().save(str(output))
    else:
        window.grab().save(str(output))

    window.close()
    print(f"saved {output}")


if __name__ == "__main__":
    main()
