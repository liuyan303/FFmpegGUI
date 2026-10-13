"""Running FFmpeg as a child process with live progress reporting.

The job is executed with :mod:`subprocess` on a dedicated ``QThread`` rather
than with ``QProcess``.  The reasons:

* ``subprocess`` gives predictable UTF-8 decoding of ffmpeg's output on every
  Windows configuration (``QProcess`` inherits the console code page).
* The ``CREATE_NO_WINDOW`` flag is applied directly, so no console window
  flashes up on Windows.
* Process creation is not affected by Qt's ``CreateProcess`` handling, which
  some locked-down / instrumented environments block.

The public signal API (``started`` / ``logLine`` / ``progress`` / ``stats`` /
``finished``) is identical to the ``QProcess`` implementation, so the UI code
does not need to care which backend runs the job.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, QThread, Signal

from . import ffmpeg

log = logging.getLogger(__name__)

#: Windows flag that stops a console window from flashing up for child procs.
_CREATE_NO_WINDOW = 0x08000000
_LINE_SPLIT = re.compile(r"[\r\n]")
_TAIL_LINES = 40


def configure_no_console() -> None:
    """Kept for API compatibility - the subprocess backend needs no setup.

    ``CREATE_NO_WINDOW`` is passed directly to :func:`subprocess.Popen`, so
    there is nothing to configure globally.
    """
    if sys.platform == "win32":
        log.debug("child processes will be created with CREATE_NO_WINDOW")


class _JobWorker(QObject):
    """Blocking worker: runs ffmpeg and streams its merged output."""

    started = Signal()
    logLine = Signal(str)
    progress = Signal(float)
    stats = Signal(dict)
    done = Signal(bool, str)

    def __init__(self, argv: list[str], total_duration: float | None) -> None:
        super().__init__()
        self._argv = list(argv)
        self._duration = (
            float(total_duration) if (total_duration or 0) > 0 else None
        )
        self._process: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._cancel_requested = False

    # ------------------------------------------------------------- controls
    def cancel(self) -> None:
        with self._lock:
            self._cancel_requested = True
            process = self._process
        if process is not None and process.poll() is None:
            try:
                process.kill()
            except OSError:  # pragma: no cover - already gone
                pass

    @property
    def cancel_requested(self) -> bool:
        with self._lock:
            return self._cancel_requested

    # ------------------------------------------------------------------ run
    def run(self) -> None:  # noqa: D102 - plain method called by the thread
        creationflags = _CREATE_NO_WINDOW if sys.platform == "win32" else 0
        tail: list[str] = []
        buffer = ""

        try:
            process = subprocess.Popen(
                self._argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                creationflags=creationflags,
            )
        except (OSError, ValueError) as exc:
            log.error("could not start ffmpeg: %s", exc)
            self.done.emit(False, f"Could not start FFmpeg: {exc}")
            return

        with self._lock:
            self._process = process
            already_cancelled = self._cancel_requested
        if already_cancelled:  # cancelled between start() and exec
            try:
                process.kill()
            except OSError:
                pass

        self.started.emit()

        stream = process.stdout
        if stream is not None:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="replace")
                while True:
                    match = _LINE_SPLIT.search(buffer)
                    if match is None:
                        break
                    line = buffer[: match.start()]
                    buffer = buffer[match.end():]
                    if line.strip():
                        tail.append(line)
                        if len(tail) > _TAIL_LINES:
                            del tail[: len(tail) - _TAIL_LINES]
                        self.logLine.emit(line)
                        info = ffmpeg.parse_progress_line(line)
                        if info:
                            self.stats.emit(info)
                            self._emit_progress(info.get("time"))

        if buffer.strip():
            self.logLine.emit(buffer)

        return_code = process.wait()
        success = return_code == 0 and not self.cancel_requested
        detail = "" if success else "\n".join(tail[-15:])
        self.done.emit(success, detail)
        # Leave the worker thread's event loop so the QThread can finish.
        QThread.currentThread().quit()

    def _emit_progress(self, seconds) -> None:
        if seconds is not None and self._duration:
            percent = max(0.0, min(100.0, seconds / self._duration * 100.0))
            self.progress.emit(percent)
        else:
            self.progress.emit(-1.0)


class FfmpegJob(QObject):
    """Runs one ffmpeg invocation and reports progress / log lines.

    Signals
    -------
    started           - the process has been launched
    logLine(str)      - one line of merged stdout/stderr output
    progress(float)   - 0..100 percent, or -1 when the duration is unknown
    stats(dict)       - {"time": seconds, "speed": float, "fps": float,
                         "frame": int} whenever ffmpeg reports progress
    finished(bool,str)- success flag plus the tail of the output on failure
    """

    started = Signal()
    logLine = Signal(str)
    progress = Signal(float)
    stats = Signal(dict)
    finished = Signal(bool, str)

    def __init__(
        self,
        argv: list[str],
        total_duration: float | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._argv = list(argv)
        self._duration = (
            float(total_duration) if (total_duration or 0) > 0 else None
        )
        self._thread: QThread | None = None
        self._worker: _JobWorker | None = None
        self._finished = False
        self.user_canceled = False

    # ------------------------------------------------------------------ API
    @property
    def argv(self) -> list[str]:
        return list(self._argv)

    @property
    def total_duration(self) -> float | None:
        return self._duration

    def is_running(self) -> bool:
        return (
            self._thread is not None
            and not self._finished
            and self._thread.isRunning()
        )

    def start(self) -> None:
        if self._thread is not None:
            return
        thread = QThread(self)
        worker = _JobWorker(self._argv, self._duration)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.started.connect(self.started)
        worker.logLine.connect(self.logLine)
        worker.progress.connect(self.progress)
        worker.stats.connect(self.stats)
        worker.done.connect(self._on_worker_done)
        self._thread = thread
        self._worker = worker
        thread.start()

    def cancel(self) -> None:
        if self._worker is not None and not self._finished:
            self.user_canceled = True
            self._worker.cancel()

    def wait(self, timeout_ms: int = 3000) -> bool:
        """Block until the job thread exits (used while closing the window)."""
        if self._thread is None:
            return True
        return self._thread.wait(timeout_ms)

    # ------------------------------------------------------------- internals
    def _on_worker_done(self, success: bool, detail: str) -> None:
        self._finished = True
        self.finished.emit(success, detail)

        # Stop the worker thread *before* dropping the last reference to the
        # worker object.  Releasing it while the thread is still alive lets
        # Python destroy the C++ QObject underneath Qt, which aborts the
        # process; waiting first makes the teardown deterministic.
        thread = self._thread
        if thread is not None and thread.isRunning():
            thread.quit()
            thread.wait(3000)
        self._worker = None
