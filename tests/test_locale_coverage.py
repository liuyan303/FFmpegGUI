"""Every translation key used in the source must exist in every locale.

This guards against forgetting to translate a new UI string: if a
``t("some.key")`` call has no matching entry in ``locales/*.json`` the
test fails and names the missing keys.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ffmpeg_gui.ffmpeg import PRESETS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
LOCALES = ROOT / "locales"

#: Matches ``t("some.key")`` and ``t('some.key', ...)`` including
#: multi-line calls, but only when ``t`` is not part of a longer name
#: (so ``.get("x")`` style calls are ignored).
_KEY_RE = re.compile(r"""(?<![A-Za-z0-9_.])t\(\s*(["'])([a-z0-9_.]+)\1""")

#: Keys that are built dynamically and therefore invisible to the regex.
_DYNAMIC_KEYS = [
    "info.file",
    "info.duration",
    "info.resolution",
    "info.frame_rate",
    "info.video_codec",
    "info.audio_codec",
    "info.size",
    "info.bitrate",
    "info.format",
    "install.dl.stage_extract",
    "install.dl.stage_verify",
    *[preset.label_key for preset in PRESETS],
]


def _source_keys() -> set[str]:
    keys: set[str] = set()
    for path in SRC.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        keys.update(match.group(2) for match in _KEY_RE.finditer(text))
    keys.update(_DYNAMIC_KEYS)
    return keys


def _locale_keys(code: str) -> set[str]:
    data = json.loads((LOCALES / f"{code}.json").read_text(encoding="utf-8"))
    return {key for key in data if not key.startswith("_")}


def test_source_keys_have_english_translations():
    missing = sorted(_source_keys() - _locale_keys("en_US"))
    assert not missing, f"en_US.json is missing keys: {missing}"


def test_source_keys_have_chinese_translations():
    missing = sorted(_source_keys() - _locale_keys("zh_CN"))
    assert not missing, f"zh_CN.json is missing keys: {missing}"


def test_no_unused_locale_entries():
    """Locales may not carry keys that no longer exist in the source."""
    unused = sorted(_locale_keys("en_US") - _source_keys())
    assert not unused, f"en_US.json has unused keys: {unused}"
