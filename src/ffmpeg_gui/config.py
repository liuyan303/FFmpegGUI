"""Persistent user settings backed by QSettings.

Settings keys
-------------
``ui/language``        ``"auto"`` or a locale code such as ``"zh_CN"``
``ui/theme``           ``"system"`` | ``"light"`` | ``"dark"``
``ffmpeg/path``        explicit ffmpeg executable (empty = auto-detect)
``behavior/overwrite`` overwrite existing output files by default
``behavior/open_after``open the output folder when a conversion finishes
``paths/last_dir``     last used folder (file dialogs start here)
``window/geometry``    saved window geometry
``window/state``       saved dock/toolbar state

Portable mode: if a file called ``config.ini`` sits next to the
executable, settings are stored there instead of the registry.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSettings

_ORG = "FFmpegGUI"
_APP = "FFmpegGUI"

_settings: QSettings | None = None


def _portable_ini() -> Path | None:
    if getattr(sys, "frozen", False):
        candidate = Path(sys.executable).resolve().parent / "config.ini"
        if candidate.is_file():
            return candidate
    return None


def settings() -> QSettings:
    global _settings
    if _settings is None:
        ini = _portable_ini()
        if ini is not None:
            _settings = QSettings(str(ini), QSettings.Format.IniFormat)
        else:
            _settings = QSettings(_ORG, _APP)
    return _settings


def get_value(key: str, default=None):
    return settings().value(key, default)


def set_value(key: str, value) -> None:
    settings().setValue(key, value)


def get_str(key: str, default: str = "") -> str:
    value = settings().value(key, default)
    return str(value) if value is not None else default


def set_str(key: str, value: str) -> None:
    settings().setValue(key, value)


def get_bool(key: str, default: bool = False) -> bool:
    value = settings().value(key, default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def set_bool(key: str, value: bool) -> None:
    settings().setValue(key, bool(value))


def get_int(key: str, default: int = 0) -> int:
    try:
        return int(settings().value(key, default))
    except (TypeError, ValueError):
        return default


def sync() -> None:
    settings().sync()
