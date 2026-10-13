"""Tests for the JSON i18n system (no Qt required)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ffmpeg_gui.i18n import (  # noqa: E402
    AUTO_LANG,
    FALLBACK_LANG,
    Translator,
    detect_system_language,
)

LOCALES = Path(__file__).resolve().parents[1] / "locales"


def _load(code: str) -> dict:
    return json.loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))


def _keys(data: dict) -> set[str]:
    return {key for key in data if not key.startswith("_")}


# ----------------------------------------------------------------------
# Locale file consistency
# ----------------------------------------------------------------------
def test_locale_files_exist():
    assert (LOCALES / "en_US.json").is_file()
    assert (LOCALES / "zh_CN.json").is_file()


def test_locale_meta_present():
    for code in ("en_US", "zh_CN"):
        meta = _load(code).get("_meta", {})
        assert meta.get("code") == code
        assert meta.get("name")
        assert meta.get("name_en")


def test_locale_keys_are_identical():
    english = _keys(_load("en_US"))
    chinese = _keys(_load("zh_CN"))
    missing_in_chinese = sorted(english - chinese)
    missing_in_english = sorted(chinese - english)
    assert not missing_in_chinese, f"zh_CN is missing: {missing_in_chinese}"
    assert not missing_in_english, f"en_US is missing: {missing_in_english}"


# ----------------------------------------------------------------------
# Translator behaviour
# ----------------------------------------------------------------------
def test_translator_switches_language():
    translator = Translator(LOCALES)
    translator.set_language("zh_CN")
    assert translator.language == "zh_CN"
    assert translator.t("main.start") == "开始转换"

    translator.set_language("en_US")
    assert translator.t("main.start") == "Start conversion"


def test_translator_matches_language_prefix():
    translator = Translator(LOCALES)
    assert translator.set_language("zh") == "zh_CN"
    assert translator.set_language("zh-CN") == "zh_CN"
    assert translator.set_language("en-GB") == "en_US"


def test_unknown_key_returns_key():
    translator = Translator(LOCALES)
    translator.set_language("zh_CN")
    assert translator.t("does.not.exist") == "does.not.exist"


def test_missing_translation_falls_back_to_english(tmp_path: Path):
    (tmp_path / "en_US.json").write_text(
        json.dumps({"_meta": {"code": "en_US"}, "a.b": "English text"}),
        encoding="utf-8",
    )
    (tmp_path / "xx_XX.json").write_text(
        json.dumps({"_meta": {"code": "xx_XX"}}), encoding="utf-8"
    )
    translator = Translator(tmp_path)
    translator.set_language("xx_XX")
    assert translator.t("a.b") == "English text"


def test_format_placeholders():
    translator = Translator(LOCALES)
    translator.set_language("en_US")
    assert translator.t("statusbar.ffmpeg_ok", version="7.1") == "FFmpeg 7.1"


def test_broken_placeholder_does_not_crash():
    translator = Translator(LOCALES)
    translator.set_language("en_US")
    # The key contains {version} but we pass nothing.
    assert "{version}" in translator.t("install.ok.status")


def test_available_languages_lists_files():
    translator = Translator(LOCALES)
    codes = [entry["code"] for entry in translator.available_languages()]
    assert "en_US" in codes
    assert "zh_CN" in codes


def test_auto_language_resolves_to_available_code():
    translator = Translator(LOCALES)
    resolved = translator.set_language(AUTO_LANG)
    assert resolved in ("en_US", "zh_CN")


def test_detect_system_language_returns_available():
    codes = ["en_US", "zh_CN"]
    assert detect_system_language(codes) in codes
    assert FALLBACK_LANG == "en_US"
