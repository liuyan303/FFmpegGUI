# FFmpeg GUI

**English** | [简体中文](README.zh-CN.md)

A simple, bilingual (English / 简体中文) graphical front-end for **FFmpeg** on
Windows. Drag in a video, pick a preset, press **Start** — no command line
needed.

!\[Screenshot](docs/screenshots/main\_en.png)

## Features

* **Drag \& drop or file picker** for the input; output path is suggested
automatically.
* **One-click presets** — MP4 (H.264 / H.265), MKV, WebM (VP9 + Opus), MOV,
AVI, GIF, MP3 / M4A / WAV / FLAC audio, and *copy streams* (remux without
re-encoding).
* **Advanced options** — video/audio codec, CRF quality slider, encoder
preset, resolution, frame rate, audio bitrate, trimming (start/end), GIF
frame rate \& width, extra FFmpeg arguments.
* **Live command preview** — see exactly what will be executed.
* **Progress with speed / FPS / ETA**, cancel button and a full log panel.
* **FFmpeg auto-setup** — the app detects your FFmpeg installation; if it is
missing you are asked once and it can download a free static build for you
(per-user, no administrator rights, nothing installed system-wide).
* **Media info** via `ffprobe` (duration, resolution, codecs, bitrate…).
* **Full i18n** — English and Simplified Chinese included, switchable at
runtime from *Settings → Language*. Translations are plain JSON files in
[`locales/`](locales) — adding a language takes five minutes.
* **Themes** — light, dark or follow the system.
* **Portable mode** — drop a `config.ini` next to the exe to keep settings
in the folder; drop a `locales/` folder next to the exe to add or fix
translations without rebuilding.

## Download

Grab the latest single-file executable (or the zip with a portable folder)
from the [**Releases**](https://github.com/liuyan303/FFmpegGUI/releases)
page:

|File|Description|
|-|-|
|`FFmpegGUI-<version>-win64.zip`|Portable folder: exe + locales + docs|
|`FFmpegGUI.exe`|Single-file executable|

FFmpeg itself is **not bundled** (it is a separate project with its own
license). Install it in any of these ways:

1. Do nothing — on first start the app offers to download a static build
into `%LOCALAPPDATA%\\FFmpegGUI\\ffmpeg` (no admin rights needed).
2. Use your package manager: `winget install ffmpeg`, `choco install ffmpeg`
or `scoop install ffmpeg`.
3. Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html)
and add `ffmpeg.exe` to your `PATH`.

The app finds FFmpeg automatically (settings → *FFmpeg location* to set it
manually).

## Usage

1. **Drag \& drop** a media file onto the window (or click the drop area).
2. Choose a **preset** (default: MP4 · H.264 + AAC).
3. Optionally tweak the **advanced options** — the command preview updates
live.
4. Pick the **output file** (suggested automatically).
5. Press **Start conversion** (`Ctrl+Enter`).

Tips:

* *Copy streams (remux)* only changes the container — instant and lossless.
* *Custom* preset + codec *Copy* lets you combine stream copies with new
encodes (e.g. re-encode audio only).
* Hardware encoders (NVIDIA NVENC / Intel QSV / AMD AMF) are available in the
codec list if your GPU and driver support them.

## Requirements

* Windows 10 / 11 (64-bit) for the prebuilt executable.
* To run from source: Python 3.10+ and PySide6.
* FFmpeg: any recent version (the app downloads or detects one).

## Run from source

```bat
git clone https://github.com/liuyan303/FFmpegGUI.git
cd FFmpegGUI
python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements-dev.txt
pip install -e .
ffmpeg-gui
```

Run the tests (the command-building and i18n tests need neither Qt nor
FFmpeg; the runner tests use the current interpreter as the child process):

```bat
python -m pytest tests -q
```

Build the standalone executable and the release zip:

```bat
python scripts/build.py
```

The build script runs the tests, builds with PyInstaller (spec in
`packaging/ffmpeg\_gui.spec`), smoke-tests the frozen exe head-lessly and
assembles `release/FFmpegGUI-<version>-win64.zip`.

## Adding a translation

1. Copy `locales/en\_US.json` to `locales/<code>.json`
(e.g. `locales/ja\_JP.json`).
2. Update `\_meta` (`code`, `name` — the name in your language, `name\_en`).
3. Translate the values — keep the keys and any `{placeholders}` unchanged.
4. Run `python -m pytest tests -q` — a test verifies that all locale files
have exactly the same keys as the source.
5. Open a pull request.

No rebuild is required for portable installs: dropping the new file into the
`locales/` folder next to `FFmpegGUI.exe` is enough — it appears in the
language menu after a restart. See
[CONTRIBUTING.md](CONTRIBUTING.md#adding-a-new-language) for details.

## Project structure

```
src/ffmpeg\_gui/          application package (pure-logic modules + Qt UI)
  ffmpeg.py              locating ffmpeg, probing, building the command line
  installer.py           download/unpack a static FFmpeg build
  i18n.py                JSON translation loader (no Qt dependency)
  runner.py              subprocess job runner with live progress parsing
  ui/                    main window and dialogs
locales/                 one JSON file per language (en\_US, zh\_CN, …)
tests/                   pytest suite (Qt-free)
packaging/               PyInstaller spec + Windows version resource
scripts/                 icon generator, screenshot tool, build script
```

## FAQ

**Windows SmartScreen warns about the exe.** The builds are unsigned. Click
*More info → Run anyway*, or build from source yourself.

**Why is the exe \~50 MB?** It bundles the Qt (PySide6) runtime. The trade-off
is a modern, native-feeling GUI without requiring a Python installation.

**Where are settings and logs stored?**
Settings: `HKCU\\Software\\FFmpegGUI` (or `config.ini` next to the exe in
portable mode). Logs: `%LOCALAPPDATA%\\FFmpegGUI\\logs` — attach this file to
bug reports.

**Does this project include FFmpeg?** No. FFmpeg is an independent project
licensed under LGPL/GPL; this GUI only invokes the executable you provide.

**The exe does not start when I double-click it.** The single-file build
unpacks itself into `%TEMP%` at every launch. A few security products and
some managed, network or redirected folders block that. Move
`FFmpegGUI.exe` to an ordinary local folder (Desktop,
`C:\\Program Files\\FFmpegGUI`, a USB stick…) and try again. Running from
source (`pip install -e .` then `ffmpeg-gui`) avoids self-extraction
entirely if nothing else works, and the log in
`%LOCALAPPDATA%\\FFmpegGUI\\logs` will say why a start-up attempt failed.

## License

[MIT](LICENSE). FFmpeg is a trademark of Fabrice Bellard; this project is
not affiliated with the FFmpeg project.

