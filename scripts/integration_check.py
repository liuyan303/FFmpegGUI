"""End-to-end integration check (not part of the unit test suite).

Generates a small test clip with FFmpeg, runs real transcodes through the
same code path the GUI uses (``build_args`` + ``FfmpegJob``) and validates
the produced files with ``ffprobe``.

Usage::

    PYTHONPATH=src python scripts/integration_check.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from ffmpeg_gui.ffmpeg import (  # noqa: E402
    JobConfig,
    build_args,
    find_ffmpeg,
    find_ffprobe,
    format_command_line,
    probe,
)
from ffmpeg_gui.runner import FfmpegJob  # noqa: E402


def run_job(argv: list[str], duration: float | None) -> tuple[bool, str]:
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)
    job = FfmpegJob(argv, duration)
    result = {"ok": False, "detail": "", "done": False}

    def finished(success: bool, detail: str) -> None:
        result["ok"], result["detail"], result["done"] = success, detail, True
        app.quit()

    job.finished.connect(finished)
    QTimer.singleShot(0, job.start)
    QTimer.singleShot(180_000, app.quit)  # safety net for the test harness
    app.exec()
    assert result["done"], "job never reported completion"
    return result["ok"], result["detail"]


def main() -> int:
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe(ffmpeg)
    print("ffmpeg :", ffmpeg)
    print("ffprobe:", ffprobe)
    assert ffmpeg, "ffmpeg not found - run the app's installer first"

    with tempfile.TemporaryDirectory(prefix="ffmpeg-gui-check-") as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / "source.mp4"
        output = tmp_path / "output.mp4"
        gif = tmp_path / "output.gif"

        # 1) create a 3s 320x240 test clip with audio
        subprocess.run(
            [
                ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
                "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=3",
                "-f", "lavfi", "-i", "sine=frequency=440:duration=3",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                "-shortest", str(source),
            ],
            check=True,
        )
        print("source :", source.stat().st_size, "bytes")

        # 2) probe it through the app's own probe wrapper
        info = probe(ffprobe, str(source))
        print("probe  :", info)
        assert info.ok, "ffprobe failed on the generated clip"
        assert info.video_codec == "h264" and info.has_audio

        # 3) transcode mp4 -> mp4 (scale to 480p, crf 28) via the GUI code path
        args = build_args(
            JobConfig(
                input_path=str(source),
                output_path=str(output),
                preset_id="mp4_h264",
                video_codec="libx264",
                audio_codec="aac",
                crf=28,
                encoder_preset="ultrafast",
                audio_bitrate="128k",
                scale_height=480,
                overwrite=True,
            ),
            ffmpeg,
        )
        print("command:", format_command_line(args))
        ok, detail = run_job(args, info.duration)
        print("transcode:", ok, "|", detail.strip())
        assert ok, f"transcode failed: {detail}"
        assert output.is_file() and output.stat().st_size > 0

        out = probe(ffprobe, str(output))
        print("result :", out)
        assert out.ok and out.height == 480, f"unexpected output: {out}"

        # 4) GIF preset (palettegen/paletteuse filter chain in one command)
        gif_args = build_args(
            JobConfig(
                input_path=str(source),
                output_path=str(gif),
                preset_id="gif",
                gif_fps=12,
                gif_width=240,
                overwrite=True,
            ),
            ffmpeg,
        )
        print("gif cmd:", format_command_line(gif_args))
        ok, detail = run_job(gif_args, info.duration)
        print("gif     :", ok, "|", detail.strip())
        assert ok, f"gif failed: {detail}"
        assert gif.is_file() and gif.stat().st_size > 0

        # 5) audio extraction preset
        mp3 = tmp_path / "output.mp3"
        mp3_args = build_args(
            JobConfig(
                input_path=str(source),
                output_path=str(mp3),
                preset_id="mp3",
                audio_bitrate="192k",
                overwrite=True,
            ),
            ffmpeg,
        )
        ok, detail = run_job(mp3_args, info.duration)
        print("mp3     :", ok, "|", detail.strip())
        assert ok and mp3.stat().st_size > 0, f"mp3 failed: {detail}"

    print("INTEGRATION-CHECK-PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
