"""Lightweight JSON-based internationalization (i18n).

Every language lives in its own file inside the top-level ``locales/``
folder, for example ``locales/en_US.json`` and ``locales/zh_CN.json``::

    {
      "_meta": {"code": "en_US", "name": "English", "name_en": "English"},
      "app.title": "FFmpeg GUI",
      ...
    }

UI code looks strings up with :func:`t` using flat dot-separated keys.
Missing keys fall back to the built-in English file and finally to the
key itself, so a partially translated language can never break the
application.

The system language is detected automatically on first start
(``"auto"``); the user can override it at any time from the Settings
menu. This module has no Qt dependency and is covered by unit tests.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .resources import find_dir

FALLBACK_LANG = "en_US"
AUTO_LANG = "auto"

#: Primarily used for the Windows UI language, which is the most reliable
#: source on Windows. Keys are the "primary language" part of a LANGID.
_WINDOWS_PRIMARY_LANGUAGES = {
    0x01: "ar", 0x04: "zh", 0x07: "de", 0x09: "en", 0x0A: "es",
    0x0C: "fr", 0x10: "it", 0x11: "ja", 0x12: "ko", 0x15: "pl",
    0x16: "pt", 0x19: "ru", 0x1F: "tr", 0x21: "vi", 0x22: "uk",
    0x24: "sl", 0x2D: "eu", 0x39: "hi", 0x3E: "hu", 0x45: "bn",
}


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _read_meta(path: Path) -> dict:
    meta = _read_json(path).get("_meta")
    return meta if isinstance(meta, dict) else {}


def _collect_strings(path: Path) -> dict[str, str]:
    data = _read_json(path)
    return {
        key: value
        for key, value in data.items()
        if isinstance(value, str) and not key.startswith("_")
    }


def detect_system_language(available_codes: list[str] | None = None) -> str:
    """Best-effort detection of the user's preferred language.

    Returns the best matching code from *available_codes* (or the
    fallback language). Pure Python, safe to call before Qt starts.
    """
    candidates: list[str] = []
    for var in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        value = os.environ.get(var)
        if value:
            candidates.append(value)

    if sys.platform == "win32":
        try:
            import ctypes

            langid = int(ctypes.windll.kernel32.GetUserDefaultUILanguage())
            primary = langid & 0x3FF
            windows_lang = _WINDOWS_PRIMARY_LANGUAGES.get(primary)
            if windows_lang:
                candidates.append(windows_lang)
        except Exception:  # pragma: no cover - non fatal
            pass

    candidates.append(FALLBACK_LANG)

    codes = list(available_codes or [])
    for candidate in candidates:
        normalized = candidate.split(".")[0].split("@")[0].replace("-", "_").lower()
        if not normalized:
            continue
        for code in codes:
            if code.lower() == normalized:
                return code
        prefix = normalized.split("_")[0]
        for code in codes:
            if code.lower().split("_")[0] == prefix:
                return code
    return FALLBACK_LANG


class Translator:
    """Loads locale files and resolves translation keys."""

    def __init__(self, locales_dir: Path | str | None = None) -> None:
        self._explicit_dir = Path(locales_dir) if locales_dir else None
        self._current = FALLBACK_LANG
        self._strings: dict[str, str] = {}
        self._fallback: dict[str, str] = {}
        self.reload()

    # ------------------------------------------------------------------
    @property
    def locales_dir(self) -> Path | None:
        if self._explicit_dir is not None and self._explicit_dir.is_dir():
            return self._explicit_dir
        return find_dir("locales")

    @property
    def language(self) -> str:
        return self._current

    def reload(self) -> None:
        """(Re-)read the on-disk locale files."""
        directory = self.locales_dir
        fallback_file = directory / f"{FALLBACK_LANG}.json" if directory else None
        self._fallback = (
            _collect_strings(fallback_file) if fallback_file is not None else {}
        )
        self.set_language(self._current)

    # ------------------------------------------------------------------
    def available_languages(self) -> list[dict[str, str]]:
        """List every locale file as ``{code, name, name_en}``.

        ``name`` is the label in the language itself (used in menus),
        ``name_en`` is the English label (used in docs and tooltips).
        """
        directory = self.locales_dir
        if directory is None:
            return []
        result: list[dict[str, str]] = []
        for path in sorted(directory.glob("*.json")):
            meta = _read_meta(path)
            code = str(meta.get("code") or path.stem)
            result.append(
                {
                    "code": code,
                    "name": str(meta.get("name") or code),
                    "name_en": str(meta.get("name_en") or meta.get("name") or code),
                }
            )
        result.sort(key=lambda item: (item["code"] != FALLBACK_LANG, item["code"]))
        return result

    def _match_language(self, code: str) -> str | None:
        normalized = code.replace("-", "_").lower()
        flat = normalized.split("_")[0]
        for language in self.available_languages():
            if language["code"].lower() == normalized:
                return language["code"]
        for language in self.available_languages():
            if language["code"].lower().split("_")[0] == flat:
                return language["code"]
        return None

    def set_language(self, code: str | None) -> str:
        """Activate a language. ``"auto"`` follows the system locale.

        Returns the language code actually activated.
        """
        directory = self.locales_dir
        if not code or code == AUTO_LANG:
            codes = [lang["code"] for lang in self.available_languages()]
            resolved = detect_system_language(codes)
        else:
            resolved = code

        strings: dict[str, str] = {}
        if directory is not None:
            resolved = self._match_language(resolved) or FALLBACK_LANG
            path = directory / f"{resolved}.json"
            if path.is_file():
                strings = _collect_strings(path)

        if strings:
            self._strings = strings
            self._current = resolved
        else:
            self._strings = dict(self._fallback)
            self._current = FALLBACK_LANG
        return self._current

    # ------------------------------------------------------------------
    def t(self, key: str, **kwargs) -> str:
        """Translate *key*; unknown keys are returned unchanged."""
        text = self._strings.get(key)
        if text is None:
            text = self._fallback.get(key)
        if text is None:
            return key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    def strings(self) -> dict[str, str]:
        """A copy of the currently active string table (for tests/tools)."""
        return dict(self._strings)


# ----------------------------------------------------------------------
# Module-level convenience API used by the UI code.
# ----------------------------------------------------------------------
_translator: Translator | None = None


def translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator


def t(key: str, **kwargs) -> str:
    """Translate *key* with the active language (module-level shortcut)."""
    return translator().t(key, **kwargs)


def set_language(code: str | None) -> str:
    return translator().set_language(code)


def current_language() -> str:
    return translator().language


def available_languages() -> list[dict[str, str]]:
    return translator().available_languages()
