"""Tests for the subprocess-based job runner.

These use the running interpreter as the child process so they need neither
FFmpeg nor a display server.
"""

from __future__ import annotations

import sys

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QTimer  # noqa: E402

from ffmpeg_gui.runner import FfmpegJob  # noqa: E402


@pytest.fixture(scope="module")
def qt_app():
    app = QCoreApplication.instance() or QCoreApplication(sys.argv[:1])
    yield app


def _run(argv: list[str], timeout_ms: int = 30_000) -> dict:
    """Drive one job to completion and collect what it reported."""
    app = QCoreApplication.instance()
    job = FfmpegJob(argv)
    seen = {"lines": [], "started": False, "finished": None}
    job.started.connect(lambda: seen.__setitem__("started", True))
    job.logLine.connect(seen["lines"].append)
    job.finished.connect(
        lambda ok, detail: (
            seen.__setitem__("finished", (ok, detail)),
            app.quit(),
        )
    )
    QTimer.singleShot(0, job.start)
    QTimer.singleShot(timeout_ms, app.quit)
    app.exec()
    assert seen["finished"] is not None, "job never emitted finished()"
    return seen


def test_successful_job_streams_output(qt_app):
    seen = _run([sys.executable, "-u", "-c", "print('alpha'); print('beta')"])
    ok, detail = seen["finished"]
    assert ok is True, detail
    assert seen["started"] is True
    assert "alpha" in seen["lines"] and "beta" in seen["lines"]


def test_failing_job_reports_tail(qt_app):
    seen = _run([sys.executable, "-u", "-c", "print('boom'); raise SystemExit(3)"])
    ok, detail = seen["finished"]
    assert ok is False
    assert "boom" in detail


def test_missing_executable_does_not_hang(qt_app):
    seen = _run(["/definitely/not/a/real/binary-xyz"])
    ok, detail = seen["finished"]
    assert ok is False
    assert detail  # a human readable reason is always provided
