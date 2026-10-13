"""Tests for the pure ffmpeg helpers (no Qt required).

Run with:  python -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ffmpeg_gui.ffmpeg import (  # noqa: E402
    JobConfig,
    build_args,
    format_command_line,
    format_seconds,
    format_timestamp,
    human_bitrate,
    human_size,
    parse_progress_line,
    parse_time_to_seconds,
    suggest_output_path,
)


def _job(**overrides) -> JobConfig:
    values = dict(
        input_path="in.mp4",
        output_path="out.mp4",
        preset_id="mp4_h264",
        video_codec="libx264",
        audio_codec="aac",
        crf=23,
        encoder_preset="medium",
        audio_bitrate="192k",
    )
    values.update(overrides)
    return JobConfig(**values)


# ----------------------------------------------------------------------
# build_args
# ----------------------------------------------------------------------
def test_basic_mp4_job():
    args = build_args(_job())
    assert args[0] == "ffmpeg"
    assert "-hide_banner" in args
    assert "-nostdin" in args
    assert "-y" in args
    assert args[args.index("-i") + 1] == "in.mp4"
    assert args[args.index("-c:v") + 1] == "libx264"
    assert args[args.index("-crf") + 1] == "23"
    assert args[args.index("-preset") + 1] == "medium"
    assert args[args.index("-c:a") + 1] == "aac"
    assert args[args.index("-b:a") + 1] == "192k"
    assert args[args.index("-movflags") + 1] == "+faststart"
    assert args[-1] == "out.mp4"


def test_no_overwrite_uses_dash_n():
    args = build_args(_job(overwrite=False))
    assert "-n" in args
    assert "-y" not in args


def test_remux_copies_streams():
    args = build_args(
        JobConfig(input_path="a.mkv", output_path="b.mkv", preset_id="remux")
    )
    assert args[args.index("-c") + 1] == "copy"
    assert "-crf" not in args


def test_gif_palette_pipeline():
    args = build_args(
        JobConfig(
            input_path="a.mp4", output_path="a.gif", preset_id="gif",
            gif_fps=15, gif_width=320,
        )
    )
    vf = args[args.index("-vf") + 1]
    assert "fps=15" in vf
    assert "scale=320:-1" in vf
    assert "palettegen" in vf
    assert "paletteuse" in vf
    assert args[args.index("-loop") + 1] == "0"
    assert "-an" in args


def test_audio_only_preset_removes_video():
    args = build_args(
        JobConfig(
            input_path="a.mp4", output_path="a.mp3", preset_id="mp3",
            audio_codec="libmp3lame", audio_bitrate="192k",
        )
    )
    assert "-vn" in args
    assert args[args.index("-c:a") + 1] == "libmp3lame"


def test_trim_uses_input_seek_and_duration():
    args = build_args(_job(trim_start=10.0, trim_end=25.5))
    assert args.index("-ss") < args.index("-i")
    assert args[args.index("-ss") + 1] == "00:00:10.000"
    assert args[args.index("-t") + 1] == "15.500"


def test_trim_only_start():
    args = build_args(_job(trim_start=5.0))
    assert args[args.index("-ss") + 1] == "00:00:05.000"
    assert "-t" not in args


def test_scale_and_fps_filters_combine():
    args = build_args(_job(scale_height=720, fps=30))
    assert args[args.index("-vf") + 1] == "scale=-2:720,fps=30"


def test_extra_args_are_appended():
    args = build_args(_job(extra_args='-map 0:s:0 -tag:v hvc1'))
    assert "-map" in args
    assert "0:s:0" in args
    assert args[-1] == "out.mp4"


def test_vp9_constant_quality_needs_zero_bitrate():
    args = build_args(_job(video_codec="libvpx-vp9", crf=32))
    assert args[args.index("-crf") + 1] == "32"
    assert args[args.index("-b:v") + 1] == "0"


def test_nvenc_uses_cq_instead_of_crf():
    args = build_args(_job(video_codec="h264_nvenc", crf=28))
    assert "-cq" in args
    assert "-crf" not in args


def test_hevc_gets_hvc1_tag_for_mp4():
    args = build_args(_job(video_codec="libx265"))
    assert args[args.index("-tag:v") + 1] == "hvc1"


def test_copy_codecs():
    args = build_args(_job(video_codec="copy", audio_codec="copy"))
    assert args[args.index("-c:v") + 1] == "copy"
    assert args[args.index("-c:a") + 1] == "copy"


def test_format_command_line_quotes_spaces():
    rendered = format_command_line(["ffmpeg", "-i", "C:/my videos/a b.mp4"])
    assert '"C:/my videos/a b.mp4"' in rendered


# ----------------------------------------------------------------------
# Time helpers
# ----------------------------------------------------------------------
def test_parse_time_to_seconds():
    assert parse_time_to_seconds("12") == 12.0
    assert parse_time_to_seconds("12.5") == 12.5
    assert parse_time_to_seconds("1:23") == 83.0
    assert parse_time_to_seconds("01:02:03.5") == 3723.5
    assert parse_time_to_seconds("") is None
    assert parse_time_to_seconds(None) is None
    assert parse_time_to_seconds("abc") is None
    assert parse_time_to_seconds("1:2:3:4") is None


def test_format_seconds():
    assert format_seconds(0) == "00:00"
    assert format_seconds(83) == "01:23"
    assert format_seconds(3723) == "1:02:03"
    assert format_seconds(None) == ""


def test_format_timestamp():
    assert format_timestamp(0) == "00:00:00.000"
    assert format_timestamp(3723.5) == "01:02:03.500"


# ----------------------------------------------------------------------
# Progress parsing
# ----------------------------------------------------------------------
def test_progress_line_parsing():
    line = (
        "frame=  120 fps= 30 q=28.0 size=     512kB "
        "time=00:00:04.00 bitrate=1048.6kbits/s speed=1.98x"
    )
    info = parse_progress_line(line)
    assert info is not None
    assert info["time"] == 4.0
    assert info["fps"] == 30.0
    assert info["speed"] == 1.98
    assert info["frame"] == 120


def test_progress_line_ignores_banner():
    assert parse_progress_line("ffmpeg version 7.1 Copyright (c) 2000-2024") is None
    assert parse_progress_line("Stream #0:0: Video: h264") is None


# ----------------------------------------------------------------------
# Output helpers
# ----------------------------------------------------------------------
def test_suggest_output_path_uses_preset_extension():
    result = suggest_output_path("C:/videos/a.mp4", "mp4_h264")
    assert result.replace("\\", "/").endswith("a_out.mp4")
    result = suggest_output_path("/home/u/clip.mov", "gif")
    assert result.endswith("clip_out.gif")


def test_suggest_output_path_custom_keeps_extension():
    result = suggest_output_path("/home/u/clip.mov", "custom")
    assert result.endswith("clip_out.mov")


def test_human_size():
    assert human_size(0) == ""
    assert human_size(None) == ""
    assert human_size(512) == "512 B"
    assert human_size(1536) == "1.5 KB"
    assert human_size(5 * 1024 * 1024) == "5.0 MB"


def test_human_bitrate():
    assert human_bitrate(None) == ""
    assert human_bitrate(128_000) == "128 kb/s"
    assert human_bitrate(6_200_000) == "6.20 Mb/s"
