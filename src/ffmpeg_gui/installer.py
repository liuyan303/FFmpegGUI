"""Download and install a static FFmpeg build (auto-setup flow).

The built-in installer puts a per-user copy of FFmpeg under
``%LOCALAPPDATA%\\FFmpegGUI\\ffmpeg\\bin``, which
:func:`ffmpeg_gui.ffmpeg.find_ffmpeg` picks up automatically.

* No administrator rights are required.
* Nothing is installed system-wide; everything stays inside that folder.
* The download source is the static build recommended on ffmpeg.org
  (gyan.dev). Override with the ``FFMPEG_GUI_FFMPEG_URL`` environment
  variable if you prefer another mirror (e.g. BtbN builds).
"""

from __future__ import annotations

import logging
import os
import shutil
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from . import __version__
from .ffmpeg import FFMPEG_DOWNLOAD_URL, ffmpeg_version, managed_install_dir

log = logging.getLogger(__name__)

_USER_AGENT = f"FFmpegGUI/{__version__}"
_CHUNK_SIZE = 256 * 1024


class DownloadCancelled(Exception):
    """Raised internally when the user cancels the installation."""


def download_url() -> str:
    """The URL used for the download (env override for tests/mirrors)."""
    return os.environ.get("FFMPEG_GUI_FFMPEG_URL") or FFMPEG_DOWNLOAD_URL


def install_ffmpeg(
    target_root: str | os.PathLike | None = None,
    url: str | None = None,
    on_stage=None,
    on_progress=None,
    should_cancel=None,
) -> str:
    """Download and unpack FFmpeg. Blocking - call from a worker thread.

    Parameters
    ----------
    target_root:
        Installation folder. Defaults to the per-user managed folder.
    url:
        Download URL. Defaults to :func:`download_url`.
    on_stage:
        ``callable(stage: str)`` with stage in ``"download"``,
        ``"extract"``, ``"verify"``.
    on_progress:
        ``callable(received: int, total: int)`` during the download.
    should_cancel:
        ``callable() -> bool`` polled during download and extraction.

    Returns the path of the installed ``ffmpeg`` executable.
    """
    target = Path(target_root) if target_root else _default_target()
    target.mkdir(parents=True, exist_ok=True)
    source_url = url or download_url()
    archive = target / "ffmpeg-download.zip"

    if on_stage:
        on_stage("download")
    _download(source_url, archive, on_progress, should_cancel)

    if on_stage:
        on_stage("extract")
    _extract(archive, target, should_cancel)

    if on_stage:
        on_stage("verify")
    executable = _find_installed(target)
    if executable is None:
        raise RuntimeError("ffmpeg executable not found after extraction")
    if ffmpeg_version(str(executable)) is None:
        raise RuntimeError("the downloaded ffmpeg executable could not be started")
    log.info("FFmpeg installed at %s", executable)
    return str(executable)


def _default_target() -> Path:
    managed = managed_install_dir()
    if managed:
        return Path(managed)
    return Path.home() / ".ffmpeg-gui" / "ffmpeg"


def _download(url, archive: Path, on_progress, should_cancel) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, open(
            archive, "wb"
        ) as handle:
            total = int(response.headers.get("Content-Length") or 0)
            received = 0
            while True:
                if should_cancel and should_cancel():
                    raise DownloadCancelled()
                chunk = response.read(_CHUNK_SIZE)
                if not chunk:
                    break
                handle.write(chunk)
                received += len(chunk)
                if on_progress:
                    on_progress(received, total)
    except DownloadCancelled:
        archive.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError, ValueError) as exc:
        archive.unlink(missing_ok=True)
        raise RuntimeError(str(exc)) from exc


def _extract(archive: Path, target: Path, should_cancel) -> None:
    work = target / "_extract_tmp"
    shutil.rmtree(work, ignore_errors=True)
    try:
        with zipfile.ZipFile(archive) as zip_file:
            try:
                zip_file.extractall(work, filter="data")
            except TypeError:  # Python < 3.12 has no filter parameter
                zip_file.extractall(work)
        if should_cancel and should_cancel():
            raise DownloadCancelled()

        executable = next(
            iter(work.rglob("ffmpeg.exe" if os.name == "nt" else "ffmpeg")), None
        )
        if executable is None:
            raise RuntimeError("ffmpeg executable not found inside the archive")

        destination = target / "bin"
        shutil.rmtree(destination, ignore_errors=True)
        shutil.move(str(executable.parent), str(destination))
    finally:
        shutil.rmtree(work, ignore_errors=True)
        archive.unlink(missing_ok=True)


def _find_installed(target: Path) -> Path | None:
    bin_dir = target / "bin"
    for name in ("ffmpeg.exe", "ffmpeg"):
        candidate = bin_dir / name
        if candidate.is_file():
            return candidate
    return None


class FfmpegInstallWorker(QThread):
    """Background worker running :func:`install_ffmpeg`."""

    #: stage in {"download", "extract", "verify"}
    stageChanged = Signal(str)
    #: bytes received, total bytes (0 when unknown)
    progressChanged = Signal(int, int)
    #: ffmpeg path, version
    succeeded = Signal(str, str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, url: str | None = None, target_root=None, parent=None) -> None:
        super().__init__(parent)
        self._url = url
        self._target_root = target_root
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def run(self) -> None:  # noqa: D102 (QThread API)
        try:
            path = install_ffmpeg(
                target_root=self._target_root,
                url=self._url,
                on_stage=self.stageChanged.emit,
                on_progress=self.progressChanged.emit,
                should_cancel=lambda: self._cancel_requested,
            )
        except DownloadCancelled:
            self.cancelled.emit()
            return
        except Exception as exc:  # noqa: BLE001 - every failure goes to the UI
            log.warning("FFmpeg installation failed: %s", exc, exc_info=True)
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(path, ffmpeg_version(path) or "")
