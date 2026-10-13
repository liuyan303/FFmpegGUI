# Contributing

Thanks for your interest in improving FFmpeg GUI! This document covers the
basics; for anything unclear, open an issue and ask.

## Development setup

```bat
git clone https://github.com/liuyan303/FFmpegGUI.git
cd FFmpegGUI
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
pip install -e .
ffmpeg-gui
```

Tests are Qt-free (they never touch PySide6) so they run anywhere:

```bat
python -m pytest tests -q
```

## Project conventions

- Pure logic (command building, i18n, probing, downloading) lives in modules
  **without Qt imports** (`ffmpeg.py`, `i18n.py`, `installer.py`) so it stays
  testable. Qt code lives in `ui/` and `runner.py` / `config.py` / `theme.py`.
- Every user-visible string must go through `t("some.key")`; the
  `tests/test_locale_coverage.py` suite fails if a key is missing from any
  locale file, so you cannot accidentally hard-code English text.
- Keep the code Python 3.10 compatible, formatted with standard 4-space
  indentation (ruff/black defaults are fine).
- Commit messages: short imperative subject line
  (`Add AV1 preset`, `Fix trimming with start only`).

## Adding a new language

1. Copy `locales/en_US.json` to `locales/<code>.json` using the usual
   language code (`de_DE`, `ja_JP`, `pt_BR`, …).
2. Edit `_meta`:

   ```json
   "_meta": { "code": "ja_JP", "name": "日本語", "name_en": "Japanese" }
   ```

   `name` is what appears in the language menu (write it in your language).

3. Translate the values. Keep the keys exactly as they are, and keep
   placeholders like `{version}` or `{path}` untouched.
4. Run `python -m pytest tests -q` — `test_locale_coverage.py` and
   `test_i18n.py` verify structural consistency.
5. Add your language to the README feature list if you like, and open a PR.

For **portable builds**, users do not need to wait for a new release: the app
loads locale files from the `locales/` folder next to `FFmpegGUI.exe` first,
falling back to the bundled copies. A translation can therefore be shipped as
a single JSON file.

## Reporting bugs

Please include:

- Windows version, app version (Help → About),
- the log file from `%LOCALAPPDATA%\FFmpegGUI\logs\ffmpeg-gui.log`,
- the FFmpeg command shown in the "FFmpeg command" panel and its output if
  the conversion itself failed.

## Pull requests

- Keep PRs focused; one feature or fix per PR.
- Run the test suite before pushing.
- Screenshots for UI changes are very welcome.
