"""The main application window."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QDesktopServices,
    QFontDatabase,
    QIcon,
    QKeySequence,
    QTextCursor,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .. import __app_name__, __license__, __url__, __version__, config
from .. import theme as theme_module
from ..ffmpeg import (
    DEFAULT_PRESET_ID,
    PRESETS,
    JobConfig,
    MediaInfo,
    build_args,
    default_extra_dirs,
    ffmpeg_version,
    find_ffmpeg,
    find_ffprobe,
    format_command_line,
    format_seconds,
    get_preset,
    human_bitrate,
    human_size,
    parse_time_to_seconds,
    probe,
    suggest_output_path,
)
from ..i18n import AUTO_LANG, available_languages, set_language, t
from ..logging_setup import log_dir
from ..resources import find_file
from ..runner import FfmpegJob
from .install_dialog import FFMPEG_WEB_URL, choose_setup_action, run_download_flow
from .settings_dialog import SettingsDialog
from .widgets import CollapsibleBox, DropArea

log = logging.getLogger(__name__)

_INFO_FIELDS = [
    "duration", "resolution", "frame_rate", "video_codec",
    "audio_codec", "size", "bitrate", "format",
]


class MainWindow(QMainWindow):
    """Main window: input, options, command preview, progress and log."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._input_path = ""
        self._info = MediaInfo()
        self._ffmpeg_path: str | None = None
        self._ffprobe_path: str | None = None
        self._ffmpeg_version: str | None = None
        self._job: FfmpegJob | None = None
        self._current_total: float | None = None
        self._output_user_edited = False

        self._build_ui()
        self._build_menus()
        self._populate_options()
        self._connect()
        self._load_settings()
        self._locate_ffmpeg()
        self.retranslate()
        self._restore_geometry()
        self._update_command_preview()

    # ==================================================================
    # UI construction
    # ==================================================================
    def _build_ui(self) -> None:
        self.setMinimumSize(780, 640)
        icon = find_file("assets", "icon.ico") or find_file("assets", "icon.png")
        if icon:
            self.setWindowIcon(QIcon(str(icon)))

        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(8)

        # ---- drop area -------------------------------------------------
        self.drop = DropArea(central)
        root.addWidget(self.drop)

        # ---- media information ----------------------------------------
        self.info_box = QGroupBox(central)
        info_layout = QVBoxLayout(self.info_box)
        info_layout.setSpacing(6)
        self.info_name_labels: dict[str, QLabel] = {}
        self.info_labels: dict[str, QLabel] = {}

        file_row = QHBoxLayout()
        file_name = QLabel(self.info_box)
        file_value = QLabel(self.info_box)
        file_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.info_name_labels["file"] = file_name
        self.info_labels["file"] = file_value
        file_row.addWidget(file_name)
        file_row.addWidget(file_value, 1)
        info_layout.addLayout(file_row)

        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(18)
        info_grid.setVerticalSpacing(4)
        for index, field in enumerate(_INFO_FIELDS):
            row = index % 4
            column = (index // 4) * 2
            name = QLabel(self.info_box)
            value = QLabel(self.info_box)
            value.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self.info_name_labels[field] = name
            self.info_labels[field] = value
            info_grid.addWidget(name, row, column)
            info_grid.addWidget(value, row, column + 1)
        info_grid.setColumnStretch(1, 1)
        info_grid.setColumnStretch(3, 1)
        info_layout.addLayout(info_grid)
        root.addWidget(self.info_box)

        # ---- output ----------------------------------------------------
        self.output_box = QGroupBox(central)
        output_row = QHBoxLayout(self.output_box)
        self.output_edit = QLineEdit(self.output_box)
        self.output_edit.setClearButtonEnabled(True)
        self.browse_output_btn = QPushButton(self.output_box)
        self.open_folder_btn = QPushButton(self.output_box)
        output_row.addWidget(self.output_edit, 1)
        output_row.addWidget(self.browse_output_btn)
        output_row.addWidget(self.open_folder_btn)
        root.addWidget(self.output_box)

        # ---- preset ----------------------------------------------------
        self.preset_box = QGroupBox(central)
        preset_row = QHBoxLayout(self.preset_box)
        self.preset_combo = QComboBox(self.preset_box)
        preset_row.addWidget(self.preset_combo, 1)
        root.addWidget(self.preset_box)

        # ---- advanced options -----------------------------------------
        self.advanced = CollapsibleBox("", expanded=True, parent=central)
        content = self.advanced.contentLayout()

        self.video_group = QGroupBox(central)
        video_grid = QGridLayout(self.video_group)
        video_grid.setHorizontalSpacing(10)
        self.lbl_vcodec = QLabel(self.video_group)
        self.cmb_vcodec = QComboBox(self.video_group)
        video_grid.addWidget(self.lbl_vcodec, 0, 0)
        video_grid.addWidget(self.cmb_vcodec, 0, 1, 1, 2)

        self.lbl_quality = QLabel(self.video_group)
        self.crf_slider = QSlider(Qt.Orientation.Horizontal, self.video_group)
        self.crf_slider.setRange(0, 51)
        self.crf_slider.setValue(23)
        self.crf_spin = QSpinBox(self.video_group)
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(23)
        quality_row = QHBoxLayout()
        quality_row.addWidget(self.crf_slider, 1)
        quality_row.addWidget(self.crf_spin)
        video_grid.addWidget(self.lbl_quality, 1, 0)
        video_grid.addLayout(quality_row, 1, 1, 1, 2)

        self.lbl_encoder = QLabel(self.video_group)
        self.cmb_epreset = QComboBox(self.video_group)
        video_grid.addWidget(self.lbl_encoder, 2, 0)
        video_grid.addWidget(self.cmb_epreset, 2, 1, 1, 2)

        self.lbl_resolution = QLabel(self.video_group)
        self.cmb_resolution = QComboBox(self.video_group)
        video_grid.addWidget(self.lbl_resolution, 3, 0)
        video_grid.addWidget(self.cmb_resolution, 3, 1, 1, 2)

        self.lbl_fps = QLabel(self.video_group)
        self.cmb_fps = QComboBox(self.video_group)
        video_grid.addWidget(self.lbl_fps, 4, 0)
        video_grid.addWidget(self.cmb_fps, 4, 1, 1, 2)
        video_grid.setColumnStretch(1, 1)

        self.audio_group = QGroupBox(central)
        audio_grid = QGridLayout(self.audio_group)
        audio_grid.setHorizontalSpacing(10)
        self.lbl_acodec = QLabel(self.audio_group)
        self.cmb_acodec = QComboBox(self.audio_group)
        self.lbl_bitrate = QLabel(self.audio_group)
        self.cmb_bitrate = QComboBox(self.audio_group)
        audio_grid.addWidget(self.lbl_acodec, 0, 0)
        audio_grid.addWidget(self.cmb_acodec, 0, 1)
        audio_grid.addWidget(self.lbl_bitrate, 1, 0)
        audio_grid.addWidget(self.cmb_bitrate, 1, 1)
        audio_grid.setColumnStretch(1, 1)

        self.trim_group = QGroupBox(central)
        trim_grid = QGridLayout(self.trim_group)
        trim_grid.setHorizontalSpacing(10)
        self.lbl_trim_start = QLabel(self.trim_group)
        self.trim_start_edit = QLineEdit(self.trim_group)
        self.lbl_trim_end = QLabel(self.trim_group)
        self.trim_end_edit = QLineEdit(self.trim_group)
        trim_grid.addWidget(self.lbl_trim_start, 0, 0)
        trim_grid.addWidget(self.trim_start_edit, 0, 1)
        trim_grid.addWidget(self.lbl_trim_end, 1, 0)
        trim_grid.addWidget(self.trim_end_edit, 1, 1)
        trim_grid.setColumnStretch(1, 1)

        self.gif_group = QGroupBox(central)
        gif_grid = QGridLayout(self.gif_group)
        gif_grid.setHorizontalSpacing(10)
        self.lbl_gif_fps = QLabel(self.gif_group)
        self.gif_fps_spin = QSpinBox(self.gif_group)
        self.gif_fps_spin.setRange(1, 60)
        self.gif_fps_spin.setValue(12)
        self.lbl_gif_width = QLabel(self.gif_group)
        self.gif_width_spin = QSpinBox(self.gif_group)
        self.gif_width_spin.setRange(0, 7680)
        self.gif_width_spin.setValue(480)
        self.gif_width_spin.setSpecialValueText("auto")
        gif_grid.addWidget(self.lbl_gif_fps, 0, 0)
        gif_grid.addWidget(self.gif_fps_spin, 0, 1)
        gif_grid.addWidget(self.lbl_gif_width, 1, 0)
        gif_grid.addWidget(self.gif_width_spin, 1, 1)
        gif_grid.setColumnStretch(1, 1)

        groups_row = QHBoxLayout()
        groups_row.addWidget(self.video_group, 3)
        side_column = QVBoxLayout()
        side_column.addWidget(self.audio_group)
        side_column.addWidget(self.trim_group)
        side_column.addWidget(self.gif_group)
        side_column.addStretch(1)
        groups_row.addLayout(side_column, 2)
        content.addLayout(groups_row)

        extra_row = QHBoxLayout()
        self.lbl_extra = QLabel(central)
        self.extra_edit = QLineEdit(central)
        extra_row.addWidget(self.lbl_extra)
        extra_row.addWidget(self.extra_edit, 1)
        content.addLayout(extra_row)

        root.addWidget(self.advanced)

        # ---- command preview ------------------------------------------
        self.command_box = CollapsibleBox("", expanded=True, parent=central)
        self.command_view = QPlainTextEdit(self.command_box)
        self.command_view.setReadOnly(True)
        self.command_view.setMaximumHeight(80)
        self.command_view.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.command_box.contentLayout().addWidget(self.command_view)
        root.addWidget(self.command_box)

        # ---- progress ---------------------------------------------------
        progress_row = QHBoxLayout()
        self.progress_bar = QProgressBar(central)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.stats_label = QLabel(central)
        self.stats_label.setMinimumWidth(240)
        self.stats_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        progress_row.addWidget(self.progress_bar, 1)
        progress_row.addWidget(self.stats_label)
        root.addLayout(progress_row)

        # ---- buttons ----------------------------------------------------
        buttons_row = QHBoxLayout()
        self.start_btn = QPushButton(central)
        self.start_btn.setObjectName("startButton")
        self.cancel_btn = QPushButton(central)
        self.cancel_btn.setEnabled(False)
        self.overwrite_check = QCheckBox(central)
        self.overwrite_check.setChecked(True)
        self.open_after_check = QCheckBox(central)
        self.open_after_check.setChecked(True)
        buttons_row.addWidget(self.start_btn)
        buttons_row.addWidget(self.cancel_btn)
        buttons_row.addSpacing(16)
        buttons_row.addWidget(self.overwrite_check)
        buttons_row.addWidget(self.open_after_check)
        buttons_row.addStretch(1)
        root.addLayout(buttons_row)

        # ---- log --------------------------------------------------------
        self.log_box = CollapsibleBox("", expanded=False, parent=central)
        self.log_view = QPlainTextEdit(self.log_box)
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(190)
        self.log_view.setFont(
            QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        )
        self.log_box.contentLayout().addWidget(self.log_view)
        root.addWidget(self.log_box)

        # Everything scrolls, so shrinking the window never squeezes the
        # controls below a usable height.
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(central)
        self.setCentralWidget(scroll)

        # ---- status bar -------------------------------------------------
        self.ffmpeg_label = QLabel(self)
        self.ffmpeg_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
        )
        self.ffmpeg_label.setOpenExternalLinks(False)
        self.ffmpeg_label.linkActivated.connect(self._on_statusbar_link)
        self.statusBar().addPermanentWidget(self.ffmpeg_label)

    # ==================================================================
    # Menus
    # ==================================================================
    def _build_menus(self) -> None:
        menu_bar = self.menuBar()

        # File -----------------------------------------------------------
        self.menu_file = menu_bar.addMenu("")
        self.act_open = QAction(self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self._open_input)
        self.act_open_folder = QAction(self)
        self.act_open_folder.setShortcut("Ctrl+E")
        self.act_open_folder.triggered.connect(self._open_output_folder)
        self.act_exit = QAction(self)
        self.act_exit.setShortcut("Ctrl+Q")
        self.act_exit.triggered.connect(self.close)
        self.menu_file.addAction(self.act_open)
        self.menu_file.addAction(self.act_open_folder)
        self.menu_file.addSeparator()
        self.menu_file.addAction(self.act_exit)

        # Settings -------------------------------------------------------
        self.menu_settings = menu_bar.addMenu("")
        self.act_ffmpeg_settings = QAction(self)
        self.act_ffmpeg_settings.triggered.connect(self._open_settings)
        self.menu_settings.addAction(self.act_ffmpeg_settings)
        self.menu_settings.addSeparator()

        self.menu_language = self.menu_settings.addMenu("")
        self._language_group = QActionGroup(self)
        self._language_group.setExclusive(True)
        self.act_lang_auto = QAction(self)
        self.act_lang_auto.setCheckable(True)
        self.act_lang_auto.triggered.connect(
            lambda: self._set_language(AUTO_LANG)
        )
        self._language_group.addAction(self.act_lang_auto)
        self.menu_language.addAction(self.act_lang_auto)
        self.menu_language.addSeparator()
        self._language_actions: dict[str, QAction] = {}
        for language in available_languages():
            action = QAction(language["name"], self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, code=language["code"]: self._set_language(code)
            )
            self._language_group.addAction(action)
            self.menu_language.addAction(action)
            self._language_actions[language["code"]] = action

        self.menu_theme = self.menu_settings.addMenu("")
        self._theme_group = QActionGroup(self)
        self._theme_group.setExclusive(True)
        self._theme_actions: dict[str, QAction] = {}
        for theme_name in theme_module.THEMES:
            action = QAction(self)
            action.setCheckable(True)
            action.triggered.connect(
                lambda _checked=False, name=theme_name: self._set_theme(name)
            )
            self._theme_group.addAction(action)
            self.menu_theme.addAction(action)
            self._theme_actions[theme_name] = action

        # Help -----------------------------------------------------------
        self.menu_help = menu_bar.addMenu("")
        self.act_install_ffmpeg = QAction(self)
        self.act_install_ffmpeg.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(FFMPEG_WEB_URL))
        )
        self.act_log_folder = QAction(self)
        self.act_log_folder.triggered.connect(
            lambda: QDesktopServices.openUrl(
                QUrl.fromLocalFile(str(log_dir()))
            )
        )
        self.act_github = QAction(self)
        self.act_github.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl(__url__))
        )
        self.act_about = QAction(self)
        self.act_about.triggered.connect(self._show_about)
        self.menu_help.addAction(self.act_install_ffmpeg)
        self.menu_help.addAction(self.act_log_folder)
        self.menu_help.addSeparator()
        self.menu_help.addAction(self.act_github)
        self.menu_help.addAction(self.act_about)

        # Hidden shortcut: Ctrl+Return starts the conversion.
        self.act_start = QAction(self)
        self.act_start.setShortcut("Ctrl+Return")
        self.act_start.triggered.connect(self._start)
        self.addAction(self.act_start)

    # ==================================================================
    # Options (combos)
    # ==================================================================
    def _video_codec_items(self) -> list[tuple[str, str]]:
        return [
            (t("codec.auto"), "auto"),
            (t("codec.copy"), "copy"),
            (t("codec.none"), "none"),
            ("H.264 (libx264)", "libx264"),
            ("H.265 / HEVC (libx265)", "libx265"),
            ("VP9 (libvpx-vp9)", "libvpx-vp9"),
            ("AV1 (libaom-av1)", "libaom-av1"),
            ("MPEG-4", "mpeg4"),
            ("H.264 (NVIDIA NVENC)", "h264_nvenc"),
            ("H.265 (NVIDIA NVENC)", "hevc_nvenc"),
            ("H.264 (Intel QSV)", "h264_qsv"),
            ("H.265 (Intel QSV)", "hevc_qsv"),
            ("H.264 (AMD AMF)", "h264_amf"),
            ("H.265 (AMD AMF)", "hevc_amf"),
        ]

    def _audio_codec_items(self) -> list[tuple[str, str]]:
        return [
            (t("codec.auto"), "auto"),
            (t("codec.copy"), "copy"),
            (t("codec.none"), "none"),
            ("AAC", "aac"),
            ("MP3 (libmp3lame)", "libmp3lame"),
            ("Opus (libopus)", "libopus"),
            ("FLAC", "flac"),
            ("ALAC", "alac"),
            (t("codec.pcm_wav"), "pcm_s16le"),
            ("AC-3", "ac3"),
        ]

    @staticmethod
    def _encoder_preset_items() -> list[tuple[str, str]]:
        return [(t("codec.auto"), "auto")] + [
            (name, name)
            for name in (
                "ultrafast", "superfast", "veryfast", "faster", "fast",
                "medium", "slow", "slower", "veryslow",
            )
        ]

    def _resolution_items(self) -> list[tuple[str, object]]:
        return [
            (t("value.keep"), None),
            ("2160p (4K)", 2160),
            ("1440p (2K)", 1440),
            ("1080p", 1080),
            ("720p", 720),
            ("480p", 480),
            ("360p", 360),
            ("240p", 240),
        ]

    def _fps_items(self) -> list[tuple[str, object]]:
        return [
            (t("value.keep"), None),
            ("60", 60),
            ("50", 50),
            ("30", 30),
            ("25", 25),
            ("24", 24),
            ("15", 15),
        ]

    @staticmethod
    def _bitrate_items() -> list[tuple[str, str]]:
        return [(value, value) for value in
                ("320k", "256k", "192k", "160k", "128k", "96k", "64k")]

    @staticmethod
    def _fill_combo(combo: QComboBox, items, current=None) -> None:
        combo.blockSignals(True)
        combo.clear()
        for text, data in items:
            combo.addItem(text, data)
        combo.blockSignals(False)
        if current is not None:
            MainWindow._select_data(combo, current)

    @staticmethod
    def _select_data(combo: QComboBox, data) -> bool:
        index = combo.findData(data)
        if index >= 0:
            combo.setCurrentIndex(index)
            return True
        return False

    def _populate_options(self) -> None:
        self._fill_combo(
            self.preset_combo,
            [(t(preset.label_key), preset.id) for preset in PRESETS],
        )
        self._repopulate_combos()

        preset_id = config.get_str("ui/last_preset", DEFAULT_PRESET_ID)
        if not self._select_data(self.preset_combo, preset_id):
            self._select_data(self.preset_combo, DEFAULT_PRESET_ID)
        self._apply_preset(self.current_preset_id())

    def _repopulate_combos(self) -> None:
        """(Re-)fill the option combos, keeping the current selection."""
        self._fill_combo(
            self.preset_combo,
            [(t(preset.label_key), preset.id) for preset in PRESETS],
            self.preset_combo.currentData(),
        )
        self._fill_combo(
            self.cmb_vcodec, self._video_codec_items(),
            self.cmb_vcodec.currentData(),
        )
        self._fill_combo(
            self.cmb_acodec, self._audio_codec_items(),
            self.cmb_acodec.currentData(),
        )
        self._fill_combo(
            self.cmb_epreset, self._encoder_preset_items(),
            self.cmb_epreset.currentData(),
        )
        self._fill_combo(
            self.cmb_resolution, self._resolution_items(),
            self.cmb_resolution.currentData(),
        )
        self._fill_combo(self.cmb_fps, self._fps_items(), self.cmb_fps.currentData())
        self._fill_combo(
            self.cmb_bitrate, self._bitrate_items(),
            self.cmb_bitrate.currentData(),
        )

    # ==================================================================
    # Signals
    # ==================================================================
    def _connect(self) -> None:
        self.drop.fileDropped.connect(self.load_input)
        self.drop.clicked.connect(self._open_input)
        self.browse_output_btn.clicked.connect(self._browse_output)
        self.open_folder_btn.clicked.connect(self._open_output_folder)
        self.output_edit.textChanged.connect(self._update_command_preview)
        self.output_edit.textEdited.connect(self._on_output_edited)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        for combo in (
            self.cmb_vcodec, self.cmb_acodec, self.cmb_epreset,
            self.cmb_resolution, self.cmb_fps, self.cmb_bitrate,
        ):
            combo.currentIndexChanged.connect(self._update_command_preview)
        self.crf_slider.valueChanged.connect(self.crf_spin.setValue)
        self.crf_spin.valueChanged.connect(self.crf_slider.setValue)
        self.crf_spin.valueChanged.connect(self._update_command_preview)
        self.gif_fps_spin.valueChanged.connect(self._update_command_preview)
        self.gif_width_spin.valueChanged.connect(self._update_command_preview)
        self.trim_start_edit.textChanged.connect(self._update_command_preview)
        self.trim_end_edit.textChanged.connect(self._update_command_preview)
        self.extra_edit.textChanged.connect(self._update_command_preview)
        self.overwrite_check.toggled.connect(self._update_command_preview)
        self.start_btn.clicked.connect(self._start)
        self.cancel_btn.clicked.connect(self._cancel)

    def _load_settings(self) -> None:
        self.overwrite_check.setChecked(config.get_bool("behavior/overwrite", True))
        self.open_after_check.setChecked(
            config.get_bool("behavior/open_after", True)
        )

    # ==================================================================
    # Translation
    # ==================================================================
    def retranslate(self) -> None:
        """Re-apply every user visible string (called on language change)."""
        self.setWindowTitle(__app_name__)

        self.menu_file.setTitle(t("menu.file"))
        self.act_open.setText(t("menu.file.open"))
        self.act_open_folder.setText(t("menu.file.open_output_folder"))
        self.act_exit.setText(t("menu.file.exit"))

        self.menu_settings.setTitle(t("menu.settings"))
        self.act_ffmpeg_settings.setText(t("menu.settings.ffmpeg"))
        self.menu_language.setTitle(t("menu.settings.language"))
        self.act_lang_auto.setText(t("language.auto"))
        self.menu_theme.setTitle(t("menu.settings.theme"))
        self._theme_actions["system"].setText(t("menu.settings.theme.system"))
        self._theme_actions["light"].setText(t("menu.settings.theme.light"))
        self._theme_actions["dark"].setText(t("menu.settings.theme.dark"))

        self.menu_help.setTitle(t("menu.help"))
        self.act_install_ffmpeg.setText(t("menu.help.install_ffmpeg"))
        self.act_log_folder.setText(t("menu.help.open_log_folder"))
        self.act_github.setText(t("menu.help.github"))
        self.act_about.setText(t("menu.help.about"))

        if self._input_path:
            self.drop.setTexts(Path(self._input_path).name, t("drop.change_hint"))
        else:
            self.drop.setTexts(t("drop.title"), t("drop.subtitle"))

        self.info_box.setTitle(t("info.title"))
        for field, label in self.info_name_labels.items():
            label.setText(t(f"info.{field}"))
        self._update_info_panel()

        self.output_box.setTitle(t("main.output"))
        self.browse_output_btn.setText(t("common.browse"))
        self.open_folder_btn.setText(t("main.open_folder"))
        self.preset_box.setTitle(t("main.preset"))

        self.advanced.setTitle(t("main.advanced"))
        self.video_group.setTitle(t("adv.video.title"))
        self.audio_group.setTitle(t("adv.audio.title"))
        self.trim_group.setTitle(t("adv.trim.title"))
        self.gif_group.setTitle(t("adv.gif.title"))
        self.lbl_vcodec.setText(t("adv.video_codec"))
        self.lbl_quality.setText(t("adv.quality"))
        self.lbl_encoder.setText(t("adv.encoder_preset"))
        self.lbl_resolution.setText(t("adv.resolution"))
        self.lbl_fps.setText(t("adv.frame_rate"))
        self.lbl_acodec.setText(t("adv.audio_codec"))
        self.lbl_bitrate.setText(t("adv.audio_bitrate"))
        self.lbl_trim_start.setText(t("adv.trim_start"))
        self.lbl_trim_end.setText(t("adv.trim_end"))
        self.trim_start_edit.setPlaceholderText(t("adv.trim_placeholder"))
        self.trim_end_edit.setPlaceholderText(t("adv.trim_placeholder"))
        self.lbl_gif_fps.setText(t("adv.gif_fps"))
        self.lbl_gif_width.setText(t("adv.gif_width"))
        self.gif_width_spin.setSpecialValueText(t("value.auto"))
        self.lbl_extra.setText(t("adv.extra_args"))
        self.extra_edit.setPlaceholderText(t("adv.extra_placeholder"))
        self.crf_spin.setToolTip(t("tooltip.crf"))
        self.crf_slider.setToolTip(t("tooltip.crf"))
        self.cmb_epreset.setToolTip(t("tooltip.encoder_preset"))
        self.trim_group.setToolTip(t("tooltip.trim"))
        self.extra_edit.setToolTip(t("tooltip.extra_args"))
        self.preset_combo.setToolTip(t("tooltip.preset"))

        self.command_box.setTitle(t("main.command"))
        self.log_box.setTitle(t("main.log"))

        self.start_btn.setText(t("main.start"))
        self.cancel_btn.setText(t("common.cancel"))
        self.overwrite_check.setText(t("main.overwrite"))
        self.open_after_check.setText(t("main.open_when_done"))

        self._repopulate_combos()
        self._sync_language_menu()
        self._sync_theme_menu()
        self._update_ffmpeg_label()

    def _sync_language_menu(self) -> None:
        current = config.get_str("ui/language", AUTO_LANG)
        self.act_lang_auto.setChecked(current == AUTO_LANG)
        for code, action in self._language_actions.items():
            action.setChecked(code == current)

    def _sync_theme_menu(self) -> None:
        current = config.get_str("ui/theme", theme_module.THEME_SYSTEM)
        for name, action in self._theme_actions.items():
            action.setChecked(name == current)

    def _set_language(self, code: str) -> None:
        config.set_str("ui/language", code)
        set_language(code)
        log.info("UI language switched to %s", code)
        self.retranslate()

    def _set_theme(self, name: str) -> None:
        config.set_str("ui/theme", name)
        app = QApplication.instance()
        if app is not None:
            theme_module.apply_theme(app, name)
        self._sync_theme_menu()

    # ==================================================================
    # FFmpeg discovery / setup
    # ==================================================================
    def has_ffmpeg(self) -> bool:
        return bool(self._ffmpeg_path)

    def _locate_ffmpeg(self) -> bool:
        previous = self._ffmpeg_path
        self._ffmpeg_path = find_ffmpeg(
            config.get_str("ffmpeg/path"), default_extra_dirs()
        )
        self._ffprobe_path = find_ffprobe(self._ffmpeg_path)
        self._ffmpeg_version = (
            ffmpeg_version(self._ffmpeg_path) if self._ffmpeg_path else None
        )
        if self._ffmpeg_path and self._ffmpeg_path != previous:
            log.info("Using ffmpeg: %s (%s)", self._ffmpeg_path, self._ffmpeg_version)
        self._update_ffmpeg_label()
        return bool(self._ffmpeg_path)

    def _update_ffmpeg_label(self) -> None:
        if self._ffmpeg_path:
            self.ffmpeg_label.setText(
                t("statusbar.ffmpeg_ok", version=self._ffmpeg_version or "?")
            )
            self.ffmpeg_label.setToolTip(self._ffmpeg_path)
        else:
            self.ffmpeg_label.setText(t("statusbar.ffmpeg_missing"))
            self.ffmpeg_label.setToolTip("")

    def _on_statusbar_link(self, link: str) -> None:
        if link == "#setup":
            self.maybe_prompt_ffmpeg_install()

    def maybe_prompt_ffmpeg_install(self) -> None:
        """Offer to set up FFmpeg (called at startup and from the status bar)."""
        if self._ffmpeg_path:
            self._open_settings()
            return
        action = choose_setup_action(self)
        if action == "download":
            self._download_and_install()
        elif action == "locate":
            self._locate_manually()
        elif action == "web":
            QDesktopServices.openUrl(QUrl(FFMPEG_WEB_URL))
        else:
            self.statusBar().showMessage(t("install.canceled.status"), 8000)

    def _download_and_install(self) -> None:
        installed = run_download_flow(self)
        if installed:
            self._locate_ffmpeg()
            self._set_status(
                t("install.ok.status", version=self._ffmpeg_version or "?")
            )
            self._append_log(f"ffmpeg installed: {installed}")

    def _locate_manually(self) -> None:
        start_dir = config.get_str("paths/last_dir") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, t("install.locate.title"), start_dir, t("install.filter")
        )
        if not path:
            return
        config.set_str("ffmpeg/path", path)
        if self._locate_ffmpeg():
            self._set_status(
                t("install.ok.status", version=self._ffmpeg_version or "?")
            )
        else:
            QMessageBox.warning(self, t("settings.title"), t("settings.not_found"))

    def _ensure_ffmpeg(self) -> bool:
        if self._ffmpeg_path:
            return True
        self.maybe_prompt_ffmpeg_install()
        return bool(self._ffmpeg_path)

    def _open_settings(self) -> None:
        dialog = SettingsDialog(config.get_str("ffmpeg/path"), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config.set_str("ffmpeg/path", dialog.ffmpeg_path())
            self._locate_ffmpeg()
            self._update_command_preview()

    # ==================================================================
    # Input / output
    # ==================================================================
    def _open_input(self) -> None:
        start_dir = config.get_str("paths/last_dir") or os.path.expanduser("~")
        filters = f"{t('file_dialog.media_filter')};;{t('file_dialog.all_filter')}"
        path, _ = QFileDialog.getOpenFileName(
            self, t("file_dialog.open_title"), start_dir, filters
        )
        if path:
            self.load_input(path)

    def load_input(self, path: str) -> None:
        """Load a media file (also used by the screenshot tooling)."""
        file_path = Path(path)
        if not file_path.is_file():
            QMessageBox.warning(
                self,
                t("msg.file_missing.title"),
                t("msg.file_missing.body", path=str(path)),
            )
            return

        self._input_path = str(file_path)
        self._output_user_edited = False
        config.set_str("paths/last_dir", str(file_path.parent))

        self._info = probe(self._ffprobe_path, str(file_path))
        self.drop.setTexts(file_path.name, t("drop.change_hint"))
        self._update_info_panel()
        if not self._output_user_edited:
            self._suggest_output()

        if self._info.ok:
            self._apply_media_constraints()
        else:
            self._set_status(t("status.probe_failed"))

        self._update_command_preview()

    def _apply_media_constraints(self) -> None:
        """Adapt safe defaults to what the file actually contains."""
        if not self._info.ok:
            return
        if not self._info.has_audio:
            current = self.cmb_acodec.currentData()
            if current not in ("none", "auto", "copy"):
                self._select_data(self.cmb_acodec, "none")
                self._set_status(t("status.no_audio"))
        if not self._info.has_video and not self._input_path.lower().endswith(".gif"):
            preset_kind = get_preset(self.current_preset_id()).kind
            if preset_kind in ("video", "remux"):
                self._set_status(t("status.no_video"))

    def _suggest_output(self) -> None:
        if not self._input_path:
            return
        self.output_edit.setText(
            suggest_output_path(self._input_path, self.current_preset_id())
        )

    def _browse_output(self) -> None:
        current = self.output_edit.text().strip()
        start_dir = (
            os.path.dirname(current)
            if current
            else config.get_str("paths/last_dir") or os.path.expanduser("~")
        )
        preset = get_preset(self.current_preset_id())
        suffix = f" (*{preset.ext})" if preset.ext else ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("file_dialog.output_title"),
            current or start_dir,
            f"{t('file_dialog.all_filter')}{suffix}",
        )
        if path:
            self.output_edit.setText(path)
            self._output_user_edited = True

    def _on_output_edited(self) -> None:
        self._output_user_edited = True

    def _open_output_folder(self) -> None:
        output = self.output_edit.text().strip()
        if output:
            folder = os.path.dirname(os.path.abspath(output))
        elif self._input_path:
            folder = os.path.dirname(os.path.abspath(self._input_path))
        else:
            folder = config.get_str("paths/last_dir")
        if folder and os.path.isdir(folder):
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    # ==================================================================
    # Presets / options
    # ==================================================================
    def current_preset_id(self) -> str:
        return self.preset_combo.currentData() or DEFAULT_PRESET_ID

    def _on_preset_changed(self, _index: int) -> None:
        preset_id = self.current_preset_id()
        config.set_str("ui/last_preset", preset_id)
        self._apply_preset(preset_id)
        if self._info.ok:
            self._apply_media_constraints()
        if get_preset(preset_id).kind == "audio":
            self.statusBar().showMessage(t("preset.audio_only_note"), 5000)

    def _apply_preset(self, preset_id: str) -> None:
        preset = get_preset(preset_id)
        defaults = preset.defaults

        def _apply() -> None:
            if "video_codec" in defaults:
                self._select_data(self.cmb_vcodec, defaults["video_codec"])
            if "audio_codec" in defaults:
                self._select_data(self.cmb_acodec, defaults["audio_codec"])
            if defaults.get("crf") is not None:
                self.crf_spin.setValue(int(defaults["crf"]))
            if "encoder_preset" in defaults:
                self._select_data(self.cmb_epreset, defaults["encoder_preset"])
            if "audio_bitrate" in defaults:
                self._select_data(self.cmb_bitrate, defaults["audio_bitrate"])
            if "gif_fps" in defaults:
                self.gif_fps_spin.setValue(int(defaults["gif_fps"]))
            if "gif_width" in defaults:
                self.gif_width_spin.setValue(int(defaults["gif_width"]))

        _apply()

        if preset.kind == "audio":
            self._select_data(self.cmb_vcodec, "none")
        elif preset.kind == "remux":
            self._select_data(self.cmb_vcodec, "copy")
            self._select_data(self.cmb_acodec, "copy")

        self._update_enabled_state()
        if self._input_path and not self._output_user_edited:
            self._suggest_output()
        self._update_command_preview()

    def _update_enabled_state(self) -> None:
        kind = get_preset(self.current_preset_id()).kind
        is_video = kind in ("video", "custom")
        for widget in (
            self.cmb_vcodec, self.crf_slider, self.crf_spin, self.cmb_epreset,
            self.cmb_resolution, self.cmb_fps,
        ):
            widget.setEnabled(is_video)
        for widget in (self.cmb_acodec, self.cmb_bitrate):
            widget.setEnabled(kind in ("video", "custom", "audio"))
        self.gif_group.setVisible(kind == "gif")

    # ==================================================================
    # Command preview
    # ==================================================================
    def _collect_job(self) -> JobConfig:
        return JobConfig(
            input_path=self._input_path,
            output_path=self.output_edit.text().strip(),
            preset_id=self.current_preset_id(),
            video_codec=self.cmb_vcodec.currentData() or "auto",
            audio_codec=self.cmb_acodec.currentData() or "auto",
            crf=self.crf_spin.value(),
            encoder_preset=self.cmb_epreset.currentData() or "auto",
            scale_height=self.cmb_resolution.currentData(),
            fps=self.cmb_fps.currentData(),
            audio_bitrate=self.cmb_bitrate.currentData() or "192k",
            trim_start=parse_time_to_seconds(self.trim_start_edit.text()),
            trim_end=parse_time_to_seconds(self.trim_end_edit.text()),
            gif_fps=self.gif_fps_spin.value(),
            gif_width=self.gif_width_spin.value(),
            extra_args=self.extra_edit.text(),
            overwrite=self.overwrite_check.isChecked(),
        )

    def _update_command_preview(self) -> None:
        if self._job is not None and self._job.is_running():
            return
        argv = build_args(self._collect_job(), self._ffmpeg_path or "ffmpeg")
        self.command_view.setPlainText(format_command_line(argv))

    # ==================================================================
    # Running a conversion
    # ==================================================================
    def _duration_for_progress(self, job: JobConfig) -> float | None:
        duration = self._info.duration if self._info.ok else None
        if duration is None:
            return None
        start = job.trim_start or 0.0
        if job.trim_end is not None:
            return max(0.0, job.trim_end - start)
        return max(0.0, duration - start)

    def _start(self) -> None:
        if self._job is not None and self._job.is_running():
            return
        job = self._collect_job()

        if not job.input_path:
            QMessageBox.information(
                self, t("msg.no_input.title"), t("msg.no_input.body")
            )
            return
        if not job.output_path:
            QMessageBox.information(
                self, t("msg.no_output.title"), t("msg.no_output.body")
            )
            return
        if os.path.abspath(job.input_path) == os.path.abspath(job.output_path):
            QMessageBox.warning(
                self, t("msg.same_path.title"), t("msg.same_path.body")
            )
            return
        if not self._ensure_ffmpeg():
            return

        if os.path.exists(job.output_path) and not job.overwrite:
            answer = QMessageBox.question(
                self,
                t("msg.output_exists.title"),
                t("msg.output_exists.body", name=os.path.basename(job.output_path)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            job.overwrite = True
            self.overwrite_check.setChecked(True)

        argv = build_args(job, self._ffmpeg_path or "ffmpeg")
        self._current_total = self._duration_for_progress(job)

        self.log_view.clear()
        self._append_log(f"$ {format_command_line(argv)}")
        self._append_log(f"input : {job.input_path}")
        self._append_log(f"output: {job.output_path}")

        self.progress_bar.setRange(0, 100 if self._current_total else 0)
        self.progress_bar.setValue(0)
        self.stats_label.setText("")

        # Release the previous run's threads before starting a new one.
        if self._job is not None:
            self._job.deleteLater()

        self._job = FfmpegJob(argv, self._current_total, self)
        self._job.logLine.connect(self._append_log)
        self._job.progress.connect(self._on_progress)
        self._job.stats.connect(self._on_stats)
        self._job.finished.connect(self._on_job_finished)
        self._job.start()

        self._set_running(True)
        self._set_status(t("status.converting"))

    def _cancel(self) -> None:
        if self._job is not None and self._job.is_running():
            self._job.cancel()
            self._set_status(t("status.canceling"))

    def _set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.output_edit.setEnabled(not running)
        self.preset_combo.setEnabled(not running)

    def _on_progress(self, percent: float) -> None:
        if percent < 0:
            self.progress_bar.setRange(0, 0)
        else:
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(int(percent))

    def _on_stats(self, info: dict) -> None:
        time_text = format_seconds(info.get("time")) or "—"
        total_text = format_seconds(self._current_total) or "—"
        speed_text = f"{info['speed']:.2f}x" if info.get("speed") else "—"
        fps_text = f"{info['fps']:.0f} fps" if info.get("fps") else "—"
        self.stats_label.setText(
            t("progress.stats", time=time_text, total=total_text,
              speed=speed_text, fps=fps_text)
        )

    def _on_job_finished(self, success: bool, detail: str) -> None:
        job = self._job
        self._set_running(False)
        self.progress_bar.setRange(0, 100)

        if success:
            self.progress_bar.setValue(100)
            self._set_status(t("status.done"))
            self._append_log("conversion finished")
            if self.open_after_check.isChecked():
                self._open_output_folder()
            return

        self.progress_bar.setValue(0)
        if job is not None and job.user_canceled:
            self._set_status(t("status.canceled"))
            self._append_log("conversion canceled by user")
            return

        self._set_status(t("status.failed"))
        self.log_box.setExpanded(True)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(t("msg.error.title"))
        box.setText(t("msg.error.body"))
        if detail:
            box.setDetailedText(detail)
        box.exec()

    # ==================================================================
    # Helpers
    # ==================================================================
    def _set_status(self, text: str) -> None:
        self.statusBar().showMessage(text)

    def _append_log(self, line: str) -> None:
        self.log_view.appendPlainText(line)
        if self.log_view.document().blockCount() > 800:
            cursor = self.log_view.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()

    def _update_info_panel(self) -> None:
        info = self._info

        def _value(text) -> str:
            return text if text else t("info.unknown")

        if self._input_path:
            self.info_labels["file"].setText(os.path.basename(self._input_path))
        else:
            self.info_labels["file"].setText(t("info.no_file"))
        self.info_labels["duration"].setText(_value(format_seconds(info.duration)))
        self.info_labels["resolution"].setText(
            _value(f"{info.width} × {info.height}" if info.width and info.height else "")
        )
        fps = info.fps
        fps_text = ""
        if fps:
            fps_text = f"{fps:.3f}".rstrip("0").rstrip(".")
        self.info_labels["frame_rate"].setText(_value(fps_text))
        self.info_labels["video_codec"].setText(_value(info.video_codec))
        self.info_labels["audio_codec"].setText(_value(info.audio_codec))
        self.info_labels["size"].setText(_value(human_size(info.size)))
        self.info_labels["bitrate"].setText(_value(human_bitrate(info.bitrate)))
        self.info_labels["format"].setText(
            _value((info.format_name or "").split(",")[0])
        )

    def _show_about(self) -> None:
        html = t(
            "about.body",
            version=__version__,
            description=t("about.description"),
            ffmpeg_note=t("about.ffmpeg_note"),
            license=__license__,
            url=__url__,
        )
        QMessageBox.about(self, t("about.title"), html)

    # ==================================================================
    # Geometry persistence
    # ==================================================================
    def _restore_geometry(self) -> None:
        geometry = config.get_value("window/geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt API)
        if self._job is not None and self._job.is_running():
            answer = QMessageBox.question(
                self,
                t("msg.quit_running.title"),
                t("msg.quit_running.body"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self._job.cancel()
            self._job.wait(3000)

        config.set_value("window/geometry", self.saveGeometry())
        config.sync()
        super().closeEvent(event)
