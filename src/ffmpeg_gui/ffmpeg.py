"""Pure-Python helpers around the FFmpeg / FFprobe command line tools.

This module deliberately has **no Qt dependency** (installer excepted,
see ``installer.py``) so it can be unit tested head-lessly and reused.

It covers three jobs:

* locating ``ffmpeg.exe`` / ``ffprobe.exe`` on the system,
* inspecting media files with ``ffprobe`` and formatting the results,
* translating a :class:`JobConfig` into a full FFmpeg command line.
"""

from __future__ import annotations

import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Windows flag that prevents console windows flashing up for child processes.
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

EXE_SUFFIX = ".exe" if sys.platform == "win32" else ""

#: Official recommended Windows build source (linked from ffmpeg.org).
FFMPEG_DOWNLOAD_URL = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)


# ----------------------------------------------------------------------
# Running helper processes
# ----------------------------------------------------------------------
def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
        creationflags=CREATE_NO_WINDOW,
    )


def _to_float(value) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _to_int(value) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _executable_in(directory: str, stem: str = "ffmpeg") -> str | None:
    if not directory:
        return None
    for name in (stem + EXE_SUFFIX, stem):
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


# ----------------------------------------------------------------------
# Locating FFmpeg
# ----------------------------------------------------------------------
def managed_install_dir() -> str | None:
    """Folder used by the built-in installer (per-user, no admin rights).

    Resolves to ``%LOCALAPPDATA%\\FFmpegGUI\\ffmpeg`` on Windows.
    """
    if sys.platform != "win32":
        return None
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return os.path.join(base, "FFmpegGUI", "ffmpeg")


def _well_known_dirs() -> list[str]:
    dirs: list[str] = []
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA", "")
        profile = os.environ.get("USERPROFILE", "")
        dirs += [
            r"C:\ffmpeg\bin",
            r"C:\ProgramData\chocolatey\bin",
            os.path.join(local, r"Microsoft\WinGet\Links"),
            os.path.join(local, r"Programs\ffmpeg\bin"),
            os.path.join(profile, "scoop", "shims"),
        ]
    else:
        dirs += ["/usr/local/bin", "/usr/bin", "/opt/homebrew/bin"]
    return [d for d in dirs if d]


def find_ffmpeg(
    configured: str | None = None,
    extra_dirs: list[str] | None = None,
) -> str | None:
    """Locate the ffmpeg executable.

    Search order:

    1. explicit path from the user settings (file or folder),
    2. the ``FFMPEG_PATH`` environment variable,
    3. *extra_dirs* (e.g. a portable ``ffmpeg`` folder next to the app),
    4. the folder managed by the built-in installer,
    5. the system ``PATH``,
    6. well-known installation locations.
    """
    if configured:
        candidate = configured.strip().strip('"')
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
        if os.path.isdir(candidate):
            hit = _executable_in(candidate)
            if hit:
                return hit

    env_path = os.environ.get("FFMPEG_PATH")
    if env_path:
        if os.path.isfile(env_path):
            return os.path.abspath(env_path)
        hit = _executable_in(env_path)
        if hit:
            return hit

    for directory in extra_dirs or []:
        for sub in ("", "bin", "ffmpeg", os.path.join("ffmpeg", "bin")):
            hit = _executable_in(os.path.join(directory, sub))
            if hit:
                return hit

    managed = managed_install_dir()
    if managed:
        hit = _executable_in(os.path.join(managed, "bin"))
        if hit:
            return hit

    which = shutil.which("ffmpeg")
    if which:
        return which

    for directory in _well_known_dirs():
        hit = _executable_in(directory)
        if hit:
            return hit
    return None


def find_ffprobe(ffmpeg_path: str | None) -> str | None:
    """Locate ``ffprobe``, preferring the folder of *ffmpeg_path*."""
    if ffmpeg_path:
        directory = os.path.dirname(os.path.abspath(ffmpeg_path))
        hit = _executable_in(directory, "ffprobe")
        if hit:
            return hit
    which = shutil.which("ffprobe")
    if which:
        return which
    return None


def ffmpeg_version(ffmpeg_path: str) -> str | None:
    """Return the version string of *ffmpeg_path* (e.g. ``"7.1.1"``)."""
    try:
        completed = _run([ffmpeg_path, "-version"], timeout=15)
    except (OSError, subprocess.SubprocessError):
        return None
    first_line = (completed.stdout or "").splitlines()[:1]
    if not first_line:
        return None
    match = re.search(r"ffmpeg version (\S+)", first_line[0])
    return match.group(1) if match else first_line[0].strip()


# ----------------------------------------------------------------------
# Probing media files
# ----------------------------------------------------------------------
@dataclass
class MediaInfo:
    """Result of an ffprobe inspection. ``ok`` is False when probing failed."""

    path: str = ""
    ok: bool = False
    duration: float | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    size: int | None = None
    bitrate: int | None = None
    format_name: str | None = None
    has_video: bool = False
    has_audio: bool = False


def _parse_fps(value: str | None) -> float | None:
    if not value:
        return None
    try:
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            denominator_value = float(denominator)
            if denominator_value == 0:
                return None
            return float(numerator) / denominator_value
        return float(value)
    except (TypeError, ValueError):
        return None


def probe(ffprobe_path: str | None, media_path: str, timeout: int = 30) -> MediaInfo:
    """Run ffprobe on *media_path*; never raises, returns ``ok=False``."""
    info = MediaInfo(path=media_path)
    if not ffprobe_path:
        return info
    cmd = [
        ffprobe_path,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        media_path,
    ]
    try:
        completed = _run(cmd, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return info
    if completed.returncode != 0 or not completed.stdout:
        return info
    try:
        data = json.loads(completed.stdout)
    except ValueError:
        return info

    fmt = data.get("format") or {}
    info.format_name = fmt.get("format_name")
    info.duration = _to_float(fmt.get("duration"))
    info.size = _to_int(fmt.get("size"))
    info.bitrate = _to_int(fmt.get("bit_rate"))

    for stream in data.get("streams") or []:
        kind = stream.get("codec_type")
        if kind == "video" and not info.has_video:
            # Skip embedded cover art (e.g. MP3 thumbnails).
            if (stream.get("disposition") or {}).get("attached_pic"):
                continue
            info.has_video = True
            info.video_codec = stream.get("codec_name")
            info.width = _to_int(stream.get("width"))
            info.height = _to_int(stream.get("height"))
            info.fps = _parse_fps(stream.get("avg_frame_rate")) or _parse_fps(
                stream.get("r_frame_rate")
            )
        elif kind == "audio" and not info.has_audio:
            info.has_audio = True
            info.audio_codec = stream.get("codec_name")
            if info.duration is None:
                info.duration = _to_float(stream.get("duration"))

    info.ok = bool(info.has_video or info.has_audio)
    return info


# ----------------------------------------------------------------------
# Time / number formatting
# ----------------------------------------------------------------------
def parse_time_to_seconds(text: str | None) -> float | None:
    """Parse ``"12"``, ``"12.5"``, ``"1:23"`` or ``"01:02:03.4"``."""
    if not text:
        return None
    text = text.strip()
    if not text:
        return None
    try:
        parts = text.split(":")
        if len(parts) > 3:
            return None
        total = 0.0
        for part in parts:
            if not part.strip():
                return None
            total = total * 60.0 + float(part)
    except ValueError:
        return None
    return total if total >= 0 else None


def format_seconds(seconds: float | None) -> str:
    """``01:23:45`` / ``23:45``; empty string when unknown."""
    if seconds is None or seconds < 0:
        return ""
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_timestamp(seconds: float) -> str:
    """``HH:MM:SS.mmm`` as accepted by ffmpeg's -ss / -t options."""
    hours = int(seconds // 3600)
    minutes = int(seconds % 3600 // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:g}"


def human_size(num_bytes: int | None) -> str:
    """``123.4 MB`` - empty string when unknown."""
    if not num_bytes or num_bytes <= 0:
        return ""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return ""


def human_bitrate(bits_per_second: int | None) -> str:
    """``6.2 Mb/s`` - empty string when unknown."""
    if not bits_per_second or bits_per_second <= 0:
        return ""
    if bits_per_second >= 1_000_000:
        return f"{bits_per_second / 1_000_000:.2f} Mb/s"
    return f"{bits_per_second / 1000:.0f} kb/s"


def format_command_line(argv: list[str]) -> str:
    """Render an argv list the way it would be typed on Windows."""
    return subprocess.list2cmdline(argv)


# ----------------------------------------------------------------------
# Progress parsing
# ----------------------------------------------------------------------
_RE_TIME = re.compile(r"time=\s*(\d+:\d{2}:\d{2}(?:\.\d+)?)")
_RE_SPEED = re.compile(r"speed=\s*([\d.]+|N/A)")
_RE_FPS = re.compile(r"fps=\s*([\d.]+|N/A)")
_RE_FRAME = re.compile(r"frame=\s*(\d+)")


def parse_progress_line(line: str) -> dict | None:
    """Extract progress fields from one line of ffmpeg console output.

    Returns a dict with any of ``time`` (seconds), ``speed`` (float,
    x-realtime), ``fps`` and ``frame``; ``None`` when nothing was found.
    """
    result: dict = {}
    match = _RE_TIME.search(line)
    if match:
        seconds = parse_time_to_seconds(match.group(1))
        if seconds is not None:
            result["time"] = seconds
    match = _RE_SPEED.search(line)
    if match and match.group(1) != "N/A":
        result["speed"] = _to_float(match.group(1))
    match = _RE_FPS.search(line)
    if match and match.group(1) != "N/A":
        result["fps"] = _to_float(match.group(1))
    match = _RE_FRAME.search(line)
    if match:
        result["frame"] = _to_int(match.group(1))
    return result or None


# ----------------------------------------------------------------------
# Presets and command building
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class Preset:
    """A one-click conversion profile shown in the preset combo box."""

    id: str
    label_key: str  # i18n key
    ext: str  # default output extension ("" = keep input extension)
    kind: str  # "video" | "audio" | "gif" | "remux" | "custom"
    defaults: dict = field(default_factory=dict)


PRESETS: list[Preset] = [
    Preset(
        "mp4_h264", "preset.mp4_h264", ".mp4", "video",
        {
            "video_codec": "libx264", "audio_codec": "aac", "crf": 23,
            "encoder_preset": "medium", "audio_bitrate": "192k",
        },
    ),
    Preset(
        "mp4_h265", "preset.mp4_h265", ".mp4", "video",
        {
            "video_codec": "libx265", "audio_codec": "aac", "crf": 28,
            "encoder_preset": "medium", "audio_bitrate": "192k",
        },
    ),
    Preset(
        "mkv_h264", "preset.mkv_h264", ".mkv", "video",
        {
            "video_codec": "libx264", "audio_codec": "aac", "crf": 23,
            "encoder_preset": "medium", "audio_bitrate": "192k",
        },
    ),
    Preset(
        "webm_vp9", "preset.webm_vp9", ".webm", "video",
        {
            "video_codec": "libvpx-vp9", "audio_codec": "libopus", "crf": 32,
            "encoder_preset": "auto", "audio_bitrate": "128k",
        },
    ),
    Preset(
        "mov_h264", "preset.mov_h264", ".mov", "video",
        {
            "video_codec": "libx264", "audio_codec": "aac", "crf": 23,
            "encoder_preset": "medium", "audio_bitrate": "192k",
        },
    ),
    Preset(
        "avi", "preset.avi", ".avi", "video",
        {"video_codec": "mpeg4", "audio_codec": "libmp3lame", "audio_bitrate": "192k"},
    ),
    Preset("gif", "preset.gif", ".gif", "gif", {"gif_fps": 12, "gif_width": 480}),
    Preset(
        "mp3", "preset.mp3", ".mp3", "audio",
        {"audio_codec": "libmp3lame", "audio_bitrate": "192k"},
    ),
    Preset(
        "m4a", "preset.m4a", ".m4a", "audio",
        {"audio_codec": "aac", "audio_bitrate": "192k"},
    ),
    Preset("wav", "preset.wav", ".wav", "audio", {"audio_codec": "pcm_s16le"}),
    Preset("flac", "preset.flac", ".flac", "audio", {"audio_codec": "flac"}),
    Preset("remux", "preset.remux", ".mkv", "remux", {}),
    Preset("custom", "preset.custom", "", "custom", {}),
]

DEFAULT_PRESET_ID = "mp4_h264"


def get_preset(preset_id: str) -> Preset:
    for preset in PRESETS:
        if preset.id == preset_id:
            return preset
    return PRESETS[-1]


@dataclass
class JobConfig:
    """Everything needed to build one ffmpeg invocation."""

    input_path: str = ""
    output_path: str = ""
    preset_id: str = DEFAULT_PRESET_ID

    # Video ("auto" = let the preset / ffmpeg decide)
    video_codec: str = "auto"  # "auto" | "copy" | "none" | codec name
    crf: int | None = None
    encoder_preset: str = "auto"
    scale_height: int | None = None
    fps: float | None = None

    # Audio
    audio_codec: str = "auto"  # "auto" | "copy" | "none" | codec name
    audio_bitrate: str = "192k"

    # Trimming (seconds, None = untouched)
    trim_start: float | None = None
    trim_end: float | None = None

    # GIF
    gif_fps: int = 12
    gif_width: int = 480

    extra_args: str = ""
    overwrite: bool = True


#: Software encoders that understand -crf.
_CRF_CODECS = ("libx264", "libx265", "libvpx-vp9", "libaom-av1")
#: Hardware encoders that use -cq instead of -crf.
_CQ_CODECS = ("h264_nvenc", "hevc_nvenc", "av1_nvenc")
#: Encoders that understand -preset.
_PRESET_CODECS = ("libx264", "libx265")
#: Audio codecs that take -b:a.
_BITRATE_CODECS = ("aac", "libmp3lame", "mp3", "libopus", "libvorbis", "alac", "ac3")
#: Containers where +faststart makes sense.
_FASTSTART_EXTS = (".mp4", ".mov", ".m4v")


def build_args(job: JobConfig, ffmpeg_exe: str = "ffmpeg") -> list[str]:
    """Translate a :class:`JobConfig` into a full ffmpeg argv list."""
    preset = get_preset(job.preset_id)
    args: list[str] = [ffmpeg_exe, "-hide_banner", "-nostdin"]
    args.append("-y" if job.overwrite else "-n")

    if job.trim_start is not None:
        args += ["-ss", format_timestamp(job.trim_start)]
    args += ["-i", job.input_path]
    if job.trim_end is not None and job.trim_end > (job.trim_start or 0.0):
        args += ["-t", f"{job.trim_end - (job.trim_start or 0.0):.3f}"]

    filters: list[str] = []

    if preset.kind == "gif":
        chain = f"fps={max(1, int(job.gif_fps))}"
        if job.gif_width and job.gif_width > 0:
            chain += f",scale={int(job.gif_width)}:-1:flags=lanczos"
        args += [
            "-vf",
            chain + ",split[s0][s1];[s0]palettegen=max_colors=256[p];"
                    "[s1][p]paletteuse=dither=bayer:bayer_scale=3",
            "-loop", "0",
            "-an",
        ]
    elif preset.kind == "remux":
        # No re-encoding: just repackage the streams into the new container.
        args += ["-c", "copy"]
    else:
        # ---- video --------------------------------------------------
        if preset.kind == "audio":
            args += ["-vn"]
        else:
            video_codec = job.video_codec
            if video_codec == "copy":
                args += ["-c:v", "copy"]
            elif video_codec == "none":
                args += ["-vn"]
            elif video_codec and video_codec != "auto":
                args += ["-c:v", video_codec]
                if job.crf is not None:
                    if video_codec in _CQ_CODECS:
                        args += ["-cq", str(int(job.crf))]
                    elif video_codec in _CRF_CODECS:
                        args += ["-crf", str(int(job.crf))]
                        if video_codec == "libvpx-vp9":
                            args += ["-b:v", "0"]  # true constant quality
                if (
                    job.encoder_preset
                    and job.encoder_preset != "auto"
                    and video_codec in _PRESET_CODECS
                ):
                    args += ["-preset", job.encoder_preset]
                output_ext = os.path.splitext(job.output_path)[1].lower()
                if video_codec == "libx265" and output_ext in (".mp4", ".mov"):
                    args += ["-tag:v", "hvc1"]  # Apple compatibility

            if job.scale_height:
                filters.append(f"scale=-2:{int(job.scale_height)}")
            if job.fps:
                filters.append(f"fps={_format_number(job.fps)}")
            if filters:
                args += ["-vf", ",".join(filters)]

        # ---- audio --------------------------------------------------
        audio_codec = job.audio_codec
        if audio_codec == "copy":
            args += ["-c:a", "copy"]
        elif audio_codec == "none":
            args += ["-an"]
        elif audio_codec and audio_codec != "auto":
            args += ["-c:a", audio_codec]
            if job.audio_bitrate and audio_codec in _BITRATE_CODECS:
                args += ["-b:a", str(job.audio_bitrate)]

        # ---- container tweaks --------------------------------------
        output_ext = os.path.splitext(job.output_path)[1].lower()
        if preset.kind in ("video", "custom") and output_ext in _FASTSTART_EXTS:
            args += ["-movflags", "+faststart"]

    if job.extra_args and job.extra_args.strip():
        args += shlex.split(job.extra_args.strip())

    args.append(job.output_path)
    return args


def suggest_output_path(input_path: str, preset: Preset | str) -> str:
    """``video.mp4`` -> ``video_out.mkv`` (same folder as the input)."""
    if isinstance(preset, str):
        preset = get_preset(preset)
    path = Path(input_path)
    extension = preset.ext or path.suffix
    if extension and not extension.startswith("."):
        extension = "." + extension
    return str(path.with_name(f"{path.stem}_out{extension}"))


def default_extra_dirs() -> list[str]:
    """Folders searched for a portable FFmpeg next to the application."""
    dirs: list[str] = []
    if getattr(sys, "frozen", False):
        dirs.append(os.path.dirname(os.path.abspath(sys.executable)))
    dirs.append(os.getcwd())
    return dirs
