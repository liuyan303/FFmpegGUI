# Changelog

All notable changes to this project are documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-13

### Added

- Drag & drop and file-picker input, automatic output path suggestion.
- One-click presets: MP4 (H.264/H.265), MKV, WebM (VP9+Opus), MOV, AVI, GIF,
  MP3, M4A, WAV, FLAC, remux (stream copy) and a fully custom mode.
- Advanced options: codec, CRF quality, encoder preset, resolution, frame
  rate, audio bitrate, trimming, GIF options and extra FFmpeg arguments.
- Live FFmpeg command preview, progress reporting (percent, speed, FPS,
  elapsed time), cancel support and a collapsible log panel.
- Automatic FFmpeg detection with a built-in per-user installer
  (downloads a static build from gyan.dev, no administrator rights).
- Media information panel powered by ffprobe.
- Full i18n system: JSON locale files, runtime language switching,
  system-language detection. Languages: English, Simplified Chinese.
- Light / dark / follow-system themes.
- Portable mode: `config.ini` and external `locales/` next to the executable.
- PyInstaller packaging (single-file exe) with CI workflow, tests and a
  build script that produces the release zip.
- Rotating log file and crash dialog for actionable bug reports.

[1.0.0]: https://github.com/liuyan303/FFmpegGUI/releases/tag/v1.0.0
