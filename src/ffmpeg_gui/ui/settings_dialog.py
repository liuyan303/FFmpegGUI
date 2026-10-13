"""The FFmpeg location settings dialog."""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from .. import config
from ..ffmpeg import default_extra_dirs, ffmpeg_version, find_ffmpeg
from ..i18n import t
from .install_dialog import run_download_flow


class SettingsDialog(QDialog):
    """Configure where FFmpeg lives (or install a copy automatically)."""

    def __init__(self, ffmpeg_path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("settings.title"))
        self.setMinimumWidth(560)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self.path_edit = QLineEdit(ffmpeg_path, self)
        browse_button = QPushButton(t("common.browse"), self)
        browse_button.clicked.connect(self._browse)
        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_button)

        detect_button = QPushButton(t("settings.detect"), self)
        detect_button.clicked.connect(self._detect)
        install_button = QPushButton(t("settings.auto_install"), self)
        install_button.clicked.connect(self._auto_install)
        action_row = QHBoxLayout()
        action_row.addWidget(detect_button)
        action_row.addWidget(install_button)
        action_row.addStretch(1)

        self.status_label = QLabel(self)
        self.status_label.setWordWrap(True)
        note_label = QLabel(t("settings.note"), self)
        note_label.setWordWrap(True)
        note_label.setStyleSheet("color: gray;")

        form = QFormLayout()
        form.addRow(t("settings.ffmpeg_path"), path_row)
        form.addRow("", action_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
        cancel_button = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        save_button.setText(t("common.save"))
        cancel_button.setText(t("common.cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status_label)
        layout.addWidget(note_label)
        layout.addSpacing(6)
        layout.addWidget(buttons)

        self.path_edit.textChanged.connect(self._refresh_status)
        self._refresh_status()

    # ------------------------------------------------------------------ API
    def ffmpeg_path(self) -> str:
        return self.path_edit.text().strip()

    # ------------------------------------------------------------- internals
    def _refresh_status(self) -> None:
        path = self.ffmpeg_path()
        if not path:
            self.status_label.setText(t("settings.empty_ok"))
            self.status_label.setStyleSheet("color: gray;")
            return
        version = ffmpeg_version(path) if os.path.isfile(path) else None
        if version:
            self.status_label.setText(t("settings.found", version=version))
            self.status_label.setStyleSheet("color: #1a7f37;")
        else:
            self.status_label.setText(t("settings.not_found"))
            self.status_label.setStyleSheet("color: #c62828;")

    def _browse(self) -> None:
        start_dir = os.path.dirname(self.ffmpeg_path()) or config.get_str(
            "paths/last_dir"
        )
        path, _ = QFileDialog.getOpenFileName(
            self, t("install.locate.title"), start_dir, t("install.filter")
        )
        if path:
            self.path_edit.setText(path)

    def _detect(self) -> None:
        found = find_ffmpeg(None, default_extra_dirs())
        if found:
            self.path_edit.setText(found)
        else:
            self.status_label.setText(t("settings.not_found"))
            self.status_label.setStyleSheet("color: #c62828;")

    def _auto_install(self) -> None:
        installed = run_download_flow(self)
        if installed:
            self.path_edit.setText(installed)
