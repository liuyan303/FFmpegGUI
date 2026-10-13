"""Dialogs for the "FFmpeg was not found" auto-setup flow."""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from ..ffmpeg import human_size
from ..i18n import t
from ..installer import FfmpegInstallWorker

log = logging.getLogger(__name__)

#: Official FFmpeg download page (used when the user prefers manual setup).
FFMPEG_WEB_URL = "https://ffmpeg.org/download.html"


def choose_setup_action(parent=None) -> str:
    """Ask how to proceed when FFmpeg is missing.

    Returns one of ``"download"``, ``"locate"``, ``"web"`` or ``"later"``.
    """
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(t("install.ask.title"))
    box.setText(t("install.ask.body"))
    download_button = box.addButton(
        t("install.ask.download"), QMessageBox.ButtonRole.AcceptRole
    )
    locate_button = box.addButton(
        t("install.ask.locate"), QMessageBox.ButtonRole.ActionRole
    )
    web_button = box.addButton(
        t("install.ask.web"), QMessageBox.ButtonRole.ActionRole
    )
    box.addButton(t("install.ask.later"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(download_button)
    box.exec()

    clicked = box.clickedButton()
    if clicked is download_button:
        return "download"
    if clicked is locate_button:
        return "locate"
    if clicked is web_button:
        return "web"
    return "later"


class FfmpegDownloadDialog(QDialog):
    """Downloads FFmpeg with a progress bar.

    On success :attr:`ffmpeg_path` holds the installed executable and the
    dialog is accepted.
    """

    def __init__(self, parent=None, url: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("install.dl.title"))
        self.setModal(True)
        self.setMinimumWidth(480)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self.ffmpeg_path = ""
        self._url = url
        self._worker: FfmpegInstallWorker | None = None

        self.status_label = QLabel(self)
        self.detail_label = QLabel("", self)
        self.detail_label.setStyleSheet("color: gray;")
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.cancel_button = QPushButton(t("common.cancel"), self)
        self.cancel_button.clicked.connect(self._on_cancel_clicked)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.addWidget(self.status_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.detail_label)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)

        self._set_stage("download")
        self._start_worker()

    # ------------------------------------------------------------- internals
    def _start_worker(self) -> None:
        self._worker = FfmpegInstallWorker(url=self._url, parent=self)
        self._worker.stageChanged.connect(self._set_stage)
        self._worker.progressChanged.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._worker.start()

    def _set_stage(self, stage: str) -> None:
        keys = {
            "download": "install.dl.stage_download",
            "extract": "install.dl.stage_extract",
            "verify": "install.dl.stage_verify",
        }
        self.status_label.setText(t(keys.get(stage, "install.dl.stage_download")))
        if stage != "download":
            self.progress_bar.setRange(0, 0)

    def _on_progress(self, received: int, total: int) -> None:
        if total > 0:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(received * 100 / total))
            self.detail_label.setText(
                f"{human_size(received)} / {human_size(total)}"
            )
        else:
            self.progress_bar.setRange(0, 0)
            self.detail_label.setText(human_size(received))

    def _on_succeeded(self, path: str, version: str) -> None:
        log.info("FFmpeg installed: %s (%s)", path, version)
        self.ffmpeg_path = path
        self.accept()

    def _on_failed(self, error: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(t("install.dl.error_title"))
        box.setText(t("install.dl.error_body", error=error))
        retry_button = box.addButton(
            t("install.dl.retry"), QMessageBox.ButtonRole.AcceptRole
        )
        web_button = box.addButton(
            t("install.ask.web"), QMessageBox.ButtonRole.ActionRole
        )
        box.addButton(t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.exec()

        clicked = box.clickedButton()
        if clicked is retry_button:
            self.status_label.setText(t("install.dl.stage_download"))
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(0)
            self.detail_label.setText("")
            self.cancel_button.setEnabled(True)
            self._start_worker()
        elif clicked is web_button:
            QDesktopServices.openUrl(QUrl(FFMPEG_WEB_URL))
            self.reject()
        else:
            self.reject()

    def _on_cancelled(self) -> None:
        self.reject()

    def _on_cancel_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self.status_label.setText(t("install.dl.canceling"))
            self.cancel_button.setEnabled(False)
            self._worker.cancel()
        else:
            self.reject()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait(5000)
        super().closeEvent(event)


def run_download_flow(parent=None, url: str | None = None) -> str | None:
    """Show the download dialog; returns the installed ffmpeg path."""
    dialog = FfmpegDownloadDialog(parent=parent, url=url)
    if dialog.exec() == QDialog.DialogCode.Accepted and dialog.ffmpeg_path:
        return dialog.ffmpeg_path
    return None
