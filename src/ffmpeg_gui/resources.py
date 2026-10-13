"""Locating data files (locales, icons) in source and frozen layouts.

Search order (first hit wins):

1. ``$FFMPEG_GUI_HOME``          - explicit override, handy for testing
2. the folder of the executable  - portable mode, lets users drop in
                                   custom ``locales/`` next to the exe
3. ``sys._MEIPASS``              - data embedded in the single-file exe
4. the project root              - running from a source checkout
5. the package folder itself     - running from a pip installation

Having the portable folder *before* the bundled copy means a translation
can be added or fixed without rebuilding the application.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _candidates() -> list[Path]:
    candidates: list[Path] = []

    env_home = os.environ.get("FFMPEG_GUI_HOME")
    if env_home:
        candidates.append(Path(env_home).expanduser())

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.append(Path(meipass))

    package_dir = Path(__file__).resolve().parent
    # source checkout: .../<project>/src/ffmpeg_gui -> .../<project>
    candidates.append(package_dir.parents[1])
    # pip installation: data files live in <prefix>/share/ffmpeg-gui
    try:
        import sysconfig

        candidates.append(
            Path(sysconfig.get_path("data")) / "share" / "ffmpeg-gui"
        )
    except (KeyError, TypeError):  # pragma: no cover - exotic environments
        pass
    # pip installation: data lives inside the package
    candidates.append(package_dir)

    return candidates


def find_dir(name: str) -> Path | None:
    """Return the first existing directory called *name*."""
    for base in _candidates():
        candidate = base / name
        if candidate.is_dir():
            return candidate
    return None


def find_file(*parts: str) -> Path | None:
    """Return the first existing file located at ``base / *parts``."""
    for base in _candidates():
        candidate = base.joinpath(*parts)
        if candidate.is_file():
            return candidate
    return None
