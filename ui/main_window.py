from __future__ import annotations

import math
from pathlib import Path

from PyQt5.QtCore import Qt, QElapsedTimer, QSettings, QTimer
from PyQt5.QtGui import QTextCursor, QIcon
from PyQt5.QtWidgets import (
    QAction,
    QAbstractItemView,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from config.settings import AppSettings
from core.board_model_map import load_board_model_map
from core.display_names import display_name
from data.video_input_profiles import (
    boardid_to_hex,
    get_board_input_formats,
    get_label_for_inputformat,
    get_max_resolution_for_inputformat,
    resolve_board_input_group,
)
from ui.aspect_ratio_container import AspectRatioContainer
from ui.widgets.joystick import JoystickWidget
from workers.device_info_worker import DeviceInfoWorker
from workers.phase1_worker import Phase1Worker
from workers.request_hub_worker import HubConfig, RequestHubWorker


def normalize_board_hex(value: object | None) -> str:
    if value is None:
        return "-"
    s = str(value).strip().upper()
    if not s:
        return "-"
    if s.startswith("0X"):
        s = s[2:]
    return s or "-"


def as_bool_01(value: object | None) -> bool:
    if value is None:
        return False
    s = str(value).strip()
    if not s:
        return False
    try:
        return int(s) == 1
    except Exception:
        return s.upper() in ("ON", "TRUE", "YES", "1")


class LedIndicator(QFrame):
    """Simple LED-like indicator used for sensor/alarm state."""

    def __init__(self) -> None:
        super().__init__()
        self.setFixedSize(16, 16)
        self.setFrameShape(QFrame.StyledPanel)
        self.set_on(False)

    def set_on(self, on: bool) -> None:
        bg = "#3CB371" if on else "#4A4A4A"
        bd = "#202020"
        self.setStyleSheet(
            f"background-color:{bg}; border:1px solid {bd}; border-radius:3px;"
        )


class MainWindow(QWidget):
    """Main application window.

    Design principle:
    - worker/core layers collect data asynchronously
    - MainWindow only renders data and dispatches UI actions
    - summary sections are built once and then shown/hidden
    """

    TARGET_PASSWORD = "!camera1108"
    DEFAULT_PASSWORD = "1234"
    DEFAULT_IP = "192.168.10.100"

    BOARD_MODEL_MAP_PATH = Path(__file__).resolve().parents[1] / "data" / "board_model_map.txt"

    POLL_INTERVAL_MS = 1000
    PTZ_CONTINUE_INTERVAL_MS = 300
    PTZ_TIMEOUT_MS = 20000
    PTZ_CHANNEL_DEFAULT = 1

    JOY_DEADZONE = 0.15
    JOY_SEND_INTERVAL_MS = 80

    FIXED_SIDE_COL_W = 280

    def __init__(self) -> None:
        super().__init__()
        self._init_settings_and_state()
        self._init_connection_widgets()
        self._init_summary_models()
        self._init_preview_widgets()
        self._init_ptz_widgets()
        self._init_phase3_widgets()
        self._init_video_input_widgets()
        self._init_layout()
        self._connect_signals()
        self._restore_window_geometry()
        self.showMaximized()

    # ---------------------------------------------------------------------
    # initialization
    # ---------------------------------------------------------------------
    def _init_settings_and_state(self) -> None:
        self._settings = QSettings("Truen", "AS_test_tool_v6")

        self.setWindowTitle("AS_test_tool_v6")

        from pathlib import Path
        from PyQt5.QtGui import QIcon

        icon_path = Path(__file__).resolve().parents[1] / "TEST.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.settings = AppSettings.load()

        self._board_model_map: dict[str, str] = load_board_model_map(self.BOARD_MODEL_MAP_PATH)

        self._phase1: Phase1Worker | None = None
        self._info: DeviceInfoWorker | None = None
        self._hub: RequestHubWorker | None = None

        self._conn: dict | None = None
        self._used_password: str | None = None
        self._last_device_info: dict = {}

        self._audio_playing = False
        self._preview_include_audio = False
        self._audio_caps_supported: dict[str, bool] = {}
        self._audio_caps_values: dict[str, str] = {}

        self._joy_last_dir = "stop"
        self._joy_last_speed = 0
        self._joy_gate = QElapsedTimer()
        self._joy_gate.start()

    def _init_connection_widgets(self) -> None:
        self.ip = QLineEdit(self.DEFAULT_IP)
        self.port = QSpinBox()
        self.port.setRange(0, 65535)
        self.port.setValue(self.settings.default_port)

        self.user = QLineEdit(self.settings.default_username)
        self.pw = QLineEdit(self.DEFAULT_PASSWORD)
        self.pw.setEchoMode(QLineEdit.Password)

        self.btn_connect = QPushButton("Connect")
        self.btn_disconnect = QPushButton("Disconnect")
        self.btn_disconnect.setEnabled(False)

        self.lbl_conn_state = QLabel("Not connected.")
        self.lbl_conn_state.setAlignment(Qt.AlignLeft)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)

        self.cam_log_box = QPlainTextEdit()
        self.cam_log_box.setReadOnly(True)
        self.cam_log_box.setPlaceholderText("Camera system log will appear here...")

        self.btn_load_cam_log = QPushButton("Load Log from Camera")
        self.btn_save_cam_log = QPushButton("Save Log to File")
        self.btn_reload_info = QPushButton("Reload Device Info")
        self.btn_reload_info.setEnabled(False)

    def _init_summary_models(self) -> None:
        self._info_summary_specs: list[tuple[str, str, bool]] = [
            ("net_mac", "MAC address", True),
            ("sys_modelname", "Model", True),
            ("sys_version", "Firmware", True),
            ("sys_mode", "Type", True),
            ("module_version", "Module version", True),
            ("meca_version", "PTZ F/W", True),
            ("extra_id", "Extra ID", True),
            ("linkdown_num", "LD", True),
            ("local_ip_mode", "Local IP mode", True),
            ("power_type", "Power Type", True),
            ("startup_time", "Start up time", True),
            ("disk", "Disk", True),
            ("ai_version", "AI version", True),
            ("rcv_version", "RCV version", True),
        ]

        self._status_summary_specs: list[tuple[str, str, bool]] = [
            ("cds", display_name("CDS"), True),
            ("current", display_name("CURRENT_Y"), True),
            ("bitrate_fps", display_name("RATE1"), True),
            ("rate2", display_name("RATE2"), False),
            ("rate3", display_name("RATE3"), False),
            ("rate4", display_name("RATE4"), False),
            ("rtc", display_name("RTC"), True),
            ("eth", display_name("ETHERNET"), True),
            ("temp", display_name("TEMP"), True),
            ("fan", display_name("FAN"), False),
            ("audio_enc_bitrate", display_name("GRS_AENCBITRATE1"), False),
            ("audio_dec_bitrate", display_name("GRS_ADECBITRATE1"), False),
            ("audio_dec_algorithm", display_name("GRS_ADECALGORITHM1"), False),
            ("audio_dec_samplerate", display_name("GRS_ADECSAMPLERATE1"), False),
            ("sensor1", display_name("GIS_SENSOR1"), False),
            ("sensor2", display_name("GIS_SENSOR2"), False),
            ("sensor3", display_name("GIS_SENSOR3"), False),
            ("sensor4", display_name("GIS_SENSOR4"), False),
            ("sensor5", display_name("GIS_SENSOR5"), False),
            ("motion1", display_name("GIS_MOTION1"), False),
            ("motion2", display_name("GIS_MOTION2"), False),
            ("motion3", display_name("GIS_MOTION3"), False),
            ("motion4", display_name("GIS_MOTION4"), False),
            ("videoloss1", display_name("GIS_VIDEOLOSS1"), False),
            ("videoloss2", display_name("GIS_VIDEOLOSS2"), False),
            ("videoloss3", display_name("GIS_VIDEOLOSS3"), False),
            ("videoloss4", display_name("GIS_VIDEOLOSS4"), False),
            ("alarm1", display_name("GIS_ALARM1"), False),
            ("alarm2", display_name("GIS_ALARM2"), False),
            ("alarm3", display_name("GIS_ALARM3"), False),
            ("alarm4", display_name("GIS_ALARM4"), False),
            ("record1", display_name("GIS_RECORD1"), False),
            ("airwiper", display_name("GIS_AIRWIPER"), False),
            ("ethtool_raw", display_name("ETHTOOL"), False),
        ]

        self._info_summary_widgets: dict[str, tuple[str, QLabel]] = {
            key: (title, QLabel("-")) for key, title, _ in self._info_summary_specs
        }
        self._status_summary_widgets: dict[str, tuple[str, QLabel]] = {
            key: (title, QLabel("-")) for key, title, _ in self._status_summary_specs
        }

        self._info_summary_row_index: dict[str, int] = {}
        self._status_summary_row_index: dict[str, int] = {}

        self._info_summary_visible = {key: default for key, _title, default in self._info_summary_specs}
        self._status_summary_visible = {key: default for key, _title, default in self._status_summary_specs}
        self._load_summary_visibility()

        self.sensor_leds = [LedIndicator() for _ in range(4)]
        self.alarm_leds = [LedIndicator() for _ in range(4)]

    def _init_preview_widgets(self) -> None:
        self.vlc_widget = None  # type: ignore[assignment]
        self._vlc_inited = False

        self.vlc_placeholder = QLabel("Preview not started.")
        self.vlc_placeholder.setAlignment(Qt.AlignCenter)

        self.vlc_container = AspectRatioContainer(self.vlc_placeholder, aspect_w=16, aspect_h=9)
        self.vlc_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.vlc_container.setMinimumWidth(820)
        self.vlc_container.setMinimumHeight(460)

        self.btn_preview_start = QPushButton("Preview Start")
        self.btn_preview_stop = QPushButton("Preview Stop")
        self.btn_preview_start.setEnabled(False)
        self.btn_preview_stop.setEnabled(False)
        self.lbl_preview_state = QLabel("-")

    def _init_ptz_widgets(self) -> None:
        self.joystick = JoystickWidget()
        self.joystick.setFixedSize(140, 140)

        self.btn_zoom_in = QPushButton("Zoom In")
        self.btn_zoom_out = QPushButton("Zoom Out")
        self.btn_zoom_1x = QPushButton("1x")

        self.btn_focus_near = QPushButton("Focus Near")
        self.btn_focus_far = QPushButton("Focus Far")
        self.btn_focus_auto = QPushButton("Auto")

        self.btn_tdn_day = QPushButton("Day")
        self.btn_tdn_night = QPushButton("Night")
        self.btn_tdn_auto = QPushButton("Auto")

        self.btn_icr_on = QPushButton("ICR On")
        self.btn_icr_off = QPushButton("ICR Off")
        self.btn_icr_auto = QPushButton("Auto")

        self.btn_lens_offset_lens = QPushButton("Lens Offset (Lens)")
        self.btn_lens_offset_zoomlens = QPushButton("Lens Offset (Zoom Lens)")

    def _init_phase3_widgets(self) -> None:
        self.btn_factory_reset = QPushButton("Factory Reset")
        self.btn_reboot = QPushButton("Reboot")

        self.ed_modelname = QLineEdit()
        self.ed_modelname.setPlaceholderText("SYS_MODELNAME2")
        self.btn_set_modelname = QPushButton("Apply Model Name")

        self.btn_set_rtc_now = QPushButton("Set RTC (Now)")

        self.ed_extra_value = QLineEdit()
        self.ed_extra_value.setPlaceholderText("NET_EXTRA_ID")
        self.btn_set_extra_id = QPushButton("Apply Extra ID")

        self.ed_product_model = QLineEdit("업체명12_V1.0")
        self.ed_product_model.setPlaceholderText("SYS_PRODUCT_MODEL")
        self.btn_set_product_model = QPushButton("Apply Product Model")

        self.txt_product_model_result = QPlainTextEdit()
        self.txt_product_model_result.setReadOnly(True)
        self.txt_product_model_result.setPlaceholderText("ReadParam result will appear here...")
        self.txt_product_model_result.setMaximumHeight(90)

        self.ed_fw_path = QLineEdit()
        self.ed_fw_path.setPlaceholderText("Local firmware file path")
        self.btn_fw_browse = QPushButton("Browse")
        self.btn_fw_upload = QPushButton("Upload Firmware")

        self.btn_aud_play = QPushButton("Play")
        self.btn_aud_codec_aac = QPushButton("AAC")
        self.btn_aud_codec_g711 = QPushButton("G.711")
        self.btn_aud_analog = QPushButton("Analog Stereo")
        self.btn_aud_embedded = QPushButton("Embedded Audio")
        self.btn_aud_decoded = QPushButton("Decoded audio")
        self.btn_aud_loopback = QPushButton("Loopback")
        self.btn_aud_max_volume = QPushButton("Set max volume")

        self.lbl_audio_caps = QLabel("Audio caps: (not scanned)")
        self.lbl_audio_caps.hide()
        self.lbl_audio_caps.setWordWrap(True)

    def _init_video_input_widgets(self) -> None:
        self.lbl_vid_in_group = QLabel("-")
        self.lbl_vid_in_target = QLabel("Target: (not selected)")
        self.lbl_vid_in_current = QLabel("Current: (not read)")
        self.cmb_vid_in_format = QComboBox()
        self.btn_vid_in_scan = QPushButton("Scan formats")
        self.btn_vid_in_apply = QPushButton("Apply")

        self.cmb_vid_in_auto = QComboBox()
        self.btn_vid_in_auto_scan = QPushButton("Auto Detect")
        self.btn_vid_in_auto_apply = QPushButton("Apply Auto")
        self.lbl_vid_in_auto = QLabel("Auto: (not scanned)")

    def _init_layout(self) -> None:
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._build_col1())
        splitter.addWidget(self._build_col2())
        splitter.addWidget(self._build_col3())
        splitter.addWidget(self._build_col4())

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 10)
        splitter.setStretchFactor(2, 0)
        splitter.setStretchFactor(3, 0)

        root = QVBoxLayout()
        root.addWidget(splitter)
        self.setLayout(root)
        self.setMinimumSize(1200, 900)

    def _connect_signals(self) -> None:
        self.btn_connect.clicked.connect(self.on_connect_clicked)
        self.btn_disconnect.clicked.connect(self.on_disconnect_clicked)
        self.btn_reload_info.clicked.connect(self.on_reload_info_clicked)
        self.btn_load_cam_log.clicked.connect(self.on_load_cam_log_clicked)
        self.btn_save_cam_log.clicked.connect(self.on_save_cam_log_clicked)
        self.btn_preview_start.clicked.connect(self.on_preview_start)
        self.btn_preview_stop.clicked.connect(self.on_preview_stop)

        self._wire_ptz_ui()
        self._wire_phase3_ui()
        self._set_all_controls_enabled(False)

    def _restore_window_geometry(self) -> None:
        geo = self._settings.value("window/geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            self.resize(1200, 900)

    def _load_summary_visibility(self) -> None:
        saved_info = self._settings.value("summary/info_visible", None)
        if isinstance(saved_info, dict):
            for k, v in saved_info.items():
                self._info_summary_visible[str(k)] = str(v).strip().lower() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                )

        saved_status = self._settings.value("summary/status_visible", None)
        if isinstance(saved_status, dict):
            for k, v in saved_status.items():
                self._status_summary_visible[str(k)] = str(v).strip().lower() in (
                    "1",
                    "true",
                    "yes",
                    "on",
                )

    # ---------------------------------------------------------------------
    # layout builders
    # ---------------------------------------------------------------------
    def _build_col1(self) -> QWidget:
        w = QWidget()
        w.setMaximumWidth(self.FIXED_SIDE_COL_W)

        lay = QVBoxLayout()

        # ---------------------------
        # Device Info (table directly)
        # ---------------------------
        box_info = QGroupBox("Device Info")
        info_l = QVBoxLayout()

        self.tbl_info_summary = QTableWidget()
        self._init_summary_table(self.tbl_info_summary)

        # 우클릭 메뉴는 table에 직접 연결
        self.tbl_info_summary.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl_info_summary.customContextMenuRequested.connect(
            self._show_info_summary_context_menu
        )

        info_l.addWidget(self.tbl_info_summary)
        box_info.setLayout(info_l)

        # ---------------------------
        # Actions
        # ---------------------------
        box_actions = QGroupBox("Actions")
        act_l = QHBoxLayout()
        act_l.addWidget(self.btn_reload_info)
        act_l.addStretch(1)
        box_actions.setLayout(act_l)

        # ---------------------------
        # Status (table directly)
        # ---------------------------
        box_status = QGroupBox("Status")
        st_l = QVBoxLayout()

        self.tbl_status_summary = QTableWidget()
        self._init_summary_table(self.tbl_status_summary)

        self.tbl_status_summary.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tbl_status_summary.customContextMenuRequested.connect(
            self._show_status_summary_context_menu
        )

        st_l.addWidget(self.tbl_status_summary)
        box_status.setLayout(st_l)

        # ---------------------------
        # Layout
        # ---------------------------
        lay.addWidget(box_info, stretch=3)
        lay.addWidget(box_actions)
        lay.addWidget(box_status, stretch=2)
        lay.addWidget(self._build_sensor_alarm_led_box())

        w.setLayout(lay)

        # 테이블 row 초기화
        self._build_summary_table_rows_once()
        self._rebuild_info_summary_form()
        self._rebuild_status_summary_form()

        return w

    def _build_col2(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout()

        box_preview = QGroupBox("RTSP Preview (VLC)")
        pv = QVBoxLayout()
        pv.addWidget(self.vlc_container, stretch=1)
        row = QHBoxLayout()
        row.addWidget(self.btn_preview_start)
        row.addWidget(self.btn_preview_stop)
        pv.addLayout(row)
        pv.addWidget(self.lbl_preview_state)
        box_preview.setLayout(pv)

        lay.addWidget(box_preview, stretch=7)
        lay.addWidget(self._build_ptz_compact_box(), stretch=3)
        w.setLayout(lay)
        return w

    def _build_col3(self) -> QWidget:
        container = QWidget()
        container.setMaximumWidth(self.FIXED_SIDE_COL_W)

        lay = QVBoxLayout()
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(8)

        box_sys = QGroupBox("System")
        sys_l = QVBoxLayout()
        sys_l.setSpacing(6)
        sys_l.addWidget(self.btn_reboot)
        sys_l.addWidget(self.btn_factory_reset)
        box_sys.setLayout(sys_l)

        box_model = QGroupBox("Model Name (SYS_MODELNAME2)")
        model_l = QVBoxLayout()
        model_l.setSpacing(6)
        model_l.addWidget(self.ed_modelname)
        model_l.addWidget(self.btn_set_modelname)
        box_model.setLayout(model_l)

        box_extra = QGroupBox("Extra ID (NET_EXTRA_ID)")
        ex_l = QVBoxLayout()
        ex_l.setSpacing(6)
        ex_l.addWidget(self.ed_extra_value)
        ex_l.addWidget(self.btn_set_extra_id)
        box_extra.setLayout(ex_l)

        box_fw = QGroupBox("Firmware (Local Upload)")
        fw_l = QVBoxLayout()
        fw_l.setSpacing(6)
        fw_row = QHBoxLayout()
        fw_row.addWidget(self.ed_fw_path, stretch=1)
        fw_row.addWidget(self.btn_fw_browse)
        fw_l.addLayout(fw_row)
        fw_l.addWidget(self.btn_fw_upload)
        box_fw.setLayout(fw_l)

        box_rtc = QGroupBox("RTC Time")
        rtc_l = QVBoxLayout()
        rtc_l.setSpacing(6)
        rtc_l.addWidget(self.btn_set_rtc_now)
        box_rtc.setLayout(rtc_l)

        lay.addWidget(box_sys)
        lay.addWidget(box_model)
        lay.addWidget(box_rtc)
        lay.addWidget(box_extra)
        lay.addWidget(self._build_product_model_box())
        lay.addWidget(box_fw)
        lay.addWidget(self._build_audio_test_box())
        lay.addWidget(self._build_vid_inputformat_box())
        lay.addStretch(1)
        container.setLayout(lay)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        scroll.setMaximumHeight(900)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("QScrollArea { border: 0px; background: transparent; }")
        return scroll

    def _build_col4(self) -> QWidget:
        w = QWidget()
        w.setMaximumWidth(self.FIXED_SIDE_COL_W)

        lay = QVBoxLayout()

        box_conn = QGroupBox("Connect")
        form = QFormLayout()
        form.addRow("IP", self.ip)
        form.addRow("User", self.user)
        form.addRow("Pass", self.pw)

        btn_col = QVBoxLayout()
        btn_col.addWidget(self.btn_connect)
        btn_col.addWidget(self.btn_disconnect)

        box_conn_l = QVBoxLayout()
        box_conn_l.addLayout(form)
        box_conn_l.addLayout(btn_col)
        box_conn_l.addWidget(self.lbl_conn_state)
        box_conn.setLayout(box_conn_l)

        box_log = QGroupBox("System Log (REQ/RESP)")
        log_l = QVBoxLayout()
        log_l.addWidget(self.log_box)
        box_log.setLayout(log_l)

        box_cam = self._build_camera_log_viewer_box()
        log_split = QSplitter(Qt.Vertical)
        log_split.addWidget(box_cam)
        log_split.addWidget(box_log)
        log_split.setStretchFactor(0, 1)
        log_split.setStretchFactor(1, 1)
        log_split.setSizes([300, 300])

        lay.addWidget(box_conn)
        lay.addWidget(log_split, stretch=1)
        w.setLayout(lay)
        return w

    def _build_sensor_alarm_led_box(self) -> QGroupBox:
        box = QGroupBox("Sensor / Alarm")
        g = QGridLayout()
        g.addWidget(QLabel(""), 0, 0)

        for i in range(4):
            lab = QLabel(str(i + 1))
            lab.setAlignment(Qt.AlignCenter)
            g.addWidget(lab, 0, i + 1)

        g.addWidget(QLabel("Sensor"), 1, 0)
        for i, led in enumerate(self.sensor_leds):
            g.addWidget(led, 1, i + 1, alignment=Qt.AlignCenter)

        g.addWidget(QLabel("Alarm"), 2, 0)
        for i, led in enumerate(self.alarm_leds):
            g.addWidget(led, 2, i + 1, alignment=Qt.AlignCenter)

        box.setLayout(g)
        return box

    def _build_ptz_compact_box(self) -> QGroupBox:
        box = QGroupBox("PTZ Control")
        g = QGridLayout()
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(6)
        g.setContentsMargins(10, 10, 10, 10)

        left = QVBoxLayout()
        left.addWidget(self.joystick, alignment=Qt.AlignCenter)
        left.addStretch(1)
        left_w = QWidget()
        left_w.setLayout(left)
        g.addWidget(left_w, 0, 0, 6, 1)

        def add_row(row: int, title: str, buttons: list[QPushButton]) -> None:
            row_l = QHBoxLayout()
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.setSpacing(8)

            lab = QLabel(title)
            lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            lab.setFixedWidth(80)

            row_l.addWidget(lab)
            for b in buttons:
                row_l.addWidget(b)

            row_w = QWidget()
            row_w.setLayout(row_l)
            g.addWidget(row_w, row, 1, 1, 2, alignment=Qt.AlignHCenter | Qt.AlignVCenter)

        add_row(0, "Zoom", [self.btn_zoom_in, self.btn_zoom_out, self.btn_zoom_1x])
        add_row(1, "Focus", [self.btn_focus_near, self.btn_focus_far, self.btn_focus_auto])
        add_row(2, "TDN", [self.btn_tdn_day, self.btn_tdn_night, self.btn_tdn_auto])
        add_row(3, "ICR", [self.btn_icr_on, self.btn_icr_off, self.btn_icr_auto])
        add_row(4, "Lens Offset", [self.btn_lens_offset_lens, self.btn_lens_offset_zoomlens])

        box.setLayout(g)
        return box

    def _build_audio_test_box(self) -> QGroupBox:
        box = QGroupBox("Audio Test")
        g = QGridLayout()
        g.setColumnStretch(0, 1)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(2, 1)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(6)
        g.setContentsMargins(10, 10, 10, 10)

        g.addWidget(self.btn_aud_play, 0, 0)
        g.addWidget(self.btn_aud_codec_aac, 0, 1)
        g.addWidget(self.btn_aud_codec_g711, 0, 2)

        row1 = QHBoxLayout()
        row1.addWidget(self.btn_aud_analog)
        row1.addWidget(self.btn_aud_embedded)
        row1_w = QWidget()
        row1_w.setLayout(row1)
        g.addWidget(row1_w, 1, 0, 1, 3)

        row2 = QHBoxLayout()
        row2.addWidget(self.btn_aud_decoded)
        row2.addWidget(self.btn_aud_loopback)
        row2_w = QWidget()
        row2_w.setLayout(row2)
        g.addWidget(row2_w, 2, 0, 1, 3)

        g.addWidget(self.btn_aud_max_volume, 3, 0, 1, 3)

        for b in (
            self.btn_aud_play,
            self.btn_aud_codec_aac,
            self.btn_aud_codec_g711,
            self.btn_aud_analog,
            self.btn_aud_embedded,
            self.btn_aud_decoded,
            self.btn_aud_loopback,
            self.btn_aud_max_volume,
        ):
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        box.setLayout(g)
        return box

    def _build_vid_inputformat_box(self) -> QGroupBox:
        box = QGroupBox("Video Input Format")
        root = QVBoxLayout()
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        info_box = QGroupBox("Info")
        info_form = QFormLayout()
        info_form.addRow("Board Group", self.lbl_vid_in_group)
        info_form.addRow("Current", self.lbl_vid_in_current)
        info_form.addRow("Target", self.lbl_vid_in_target)
        info_box.setLayout(info_form)

        auto_box = QGroupBox("Auto")
        auto_l = QVBoxLayout()
        auto_l.addWidget(self.lbl_vid_in_auto)
        auto_l.addWidget(self.cmb_vid_in_auto)
        auto_btn_row = QHBoxLayout()
        auto_btn_row.addWidget(self.btn_vid_in_auto_scan)
        auto_btn_row.addWidget(self.btn_vid_in_auto_apply)
        auto_l.addLayout(auto_btn_row)
        auto_box.setLayout(auto_l)

        sel_box = QGroupBox("Detected Formats")
        sel_l = QVBoxLayout()
        sel_l.addWidget(self.cmb_vid_in_format)
        sel_btn_row = QHBoxLayout()
        sel_btn_row.addWidget(self.btn_vid_in_scan)
        sel_btn_row.addWidget(self.btn_vid_in_apply)
        sel_l.addLayout(sel_btn_row)
        sel_box.setLayout(sel_l)

        root.addWidget(info_box)
        root.addWidget(auto_box)
        root.addWidget(sel_box)

        for w in (
            self.cmb_vid_in_auto,
            self.btn_vid_in_auto_scan,
            self.btn_vid_in_auto_apply,
            self.cmb_vid_in_format,
            self.btn_vid_in_scan,
            self.btn_vid_in_apply,
        ):
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        box.setLayout(root)
        return box

    def _build_product_model_box(self) -> QGroupBox:
        box = QGroupBox("Product Model (SYS_PRODUCT_MODEL)")
        lay = QVBoxLayout()
        lay.setContentsMargins(10, 10, 10, 10)
        lay.setSpacing(8)
        lay.addWidget(QLabel("Sales product name"))
        lay.addWidget(self.ed_product_model)
        lay.addWidget(self.btn_set_product_model)
        lay.addWidget(self.txt_product_model_result)
        box.setLayout(lay)
        return box

    def _build_camera_log_viewer_box(self) -> QGroupBox:
        box = QGroupBox("Camera Log Viewer")
        l = QVBoxLayout()
        l.addWidget(self.cam_log_box, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_load_cam_log)
        btn_row.addWidget(self.btn_save_cam_log)
        l.addLayout(btn_row)
        box.setLayout(l)
        return box

    # ---------------------------------------------------------------------
    # summary rendering
    # ---------------------------------------------------------------------
    def _init_summary_table(self, table: QTableWidget) -> None:
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Key", "Value"])
        table.verticalHeader().setVisible(False)

        table.setAlternatingRowColors(True)
        table.setWordWrap(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setSelectionMode(QAbstractItemView.SingleSelection)
        table.setShowGrid(True)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        table.setColumnWidth(0, 110)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setStretchLastSection(True)

        table.verticalHeader().setDefaultSectionSize(26)

    def _build_summary_table_rows_once(self) -> None:
        if not self._info_summary_row_index:
            self.tbl_info_summary.setRowCount(0)
            for key, (title, value_widget) in self._info_summary_widgets.items():
                row = self.tbl_info_summary.rowCount()
                self.tbl_info_summary.insertRow(row)
                self.tbl_info_summary.setItem(row, 0, QTableWidgetItem(title))
                value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
                value_widget.setWordWrap(True)
                self.tbl_info_summary.setCellWidget(row, 1, value_widget)
                self._info_summary_row_index[key] = row

        if not self._status_summary_row_index:
            self.tbl_status_summary.setRowCount(0)
            for key, (title, value_widget) in self._status_summary_widgets.items():
                row = self.tbl_status_summary.rowCount()
                self.tbl_status_summary.insertRow(row)
                self.tbl_status_summary.setItem(row, 0, QTableWidgetItem(title))
                value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
                value_widget.setWordWrap(True)
                self.tbl_status_summary.setCellWidget(row, 1, value_widget)
                self._status_summary_row_index[key] = row

    def _set_info_summary_value(self, key: str, value: object) -> None:
        pair = self._info_summary_widgets.get(key)
        if not pair:
            return
        _, widget = pair
        widget.setText("-" if value in (None, "") else str(value))

    def _set_status_summary_value(self, key: str, value: object) -> None:
        pair = self._status_summary_widgets.get(key)
        if not pair:
            return
        _, widget = pair
        widget.setText("-" if value in (None, "") else str(value))

    def _sync_info_summary_table_visibility(self) -> None:
        for key, row in self._info_summary_row_index.items():
            self.tbl_info_summary.setRowHidden(
                row,
                not bool(self._info_summary_visible.get(key, False)),
            )

    def _sync_status_summary_table_visibility(self) -> None:
        for key, row in self._status_summary_row_index.items():
            self.tbl_status_summary.setRowHidden(
                row,
                not bool(self._status_summary_visible.get(key, False)),
            )

    def _rebuild_info_summary_form(self) -> None:
        self._sync_info_summary_table_visibility()
        self.tbl_info_summary.resizeRowsToContents()

    def _rebuild_status_summary_form(self) -> None:
        self._sync_status_summary_table_visibility()
        self.tbl_status_summary.resizeRowsToContents()

    def _save_summary_visibility(self) -> None:
        self._settings.setValue(
            "summary/info_visible",
            {k: bool(v) for k, v in self._info_summary_visible.items()},
        )
        self._settings.setValue(
            "summary/status_visible",
            {k: bool(v) for k, v in self._status_summary_visible.items()},
        )

    def _show_info_summary_context_menu(self, pos) -> None:
        menu = QMenu(self)
        for key, (title, _widget) in self._info_summary_widgets.items():
            action = QAction(title, menu)
            action.setCheckable(True)
            action.setChecked(bool(self._info_summary_visible.get(key, False)))
            action.toggled.connect(
                lambda checked, k=key: self._toggle_info_summary_item(k, checked)
            )
            menu.addAction(action)
        menu.exec_(self.tbl_info_summary.viewport().mapToGlobal(pos))

    def _show_status_summary_context_menu(self, pos) -> None:
        menu = QMenu(self)
        for key, (title, _widget) in self._status_summary_widgets.items():
            action = QAction(title, menu)
            action.setCheckable(True)
            action.setChecked(bool(self._status_summary_visible.get(key, False)))
            action.toggled.connect(
                lambda checked, k=key: self._toggle_status_summary_item(k, checked)
            )
            menu.addAction(action)
        menu.exec_(self.tbl_info_summary.viewport().mapToGlobal(pos))

    def _toggle_info_summary_item(self, key: str, checked: bool) -> None:
        self._info_summary_visible[key] = bool(checked)
        self._save_summary_visibility()
        self._rebuild_info_summary_form()

    def _toggle_status_summary_item(self, key: str, checked: bool) -> None:
        self._status_summary_visible[key] = bool(checked)
        self._save_summary_visibility()
        self._rebuild_status_summary_form()

    # ---------------------------------------------------------------------
    # data mapping helpers
    # ---------------------------------------------------------------------
    def _fmt_enum_value(self, key: str, value: object) -> str:
        s = "-" if value in (None, "") else str(value).strip()
        if s in ("", "-"):
            return "-"

        if key == "SYS_MODE":
            return {
                "0": "Encoder",
                "1": "Decoder",
                "2": "Duplex",
            }.get(s, s)

        if key == "NET_LOCALIPMODE":
            return {
                "0": "fixed IP",
                "1": "DHCP",
            }.get(s, s)

        return s

    def _build_disk_text(self, data: dict) -> str:
        disk_type = str(data.get("REC_DISKTYPE") or "-").strip()
        disk_size = str(data.get("REC_DISKSIZE") or "-").strip()
        disk_free = str(data.get("REC_DISKAVAILABLE") or "-").strip()

        if disk_type == "-" and disk_size == "-" and disk_free == "-":
            return "-"

        return f"{disk_type} <{disk_free} / {disk_size}>"

    def _extract_info_summary_map(self, data: dict) -> dict[str, str]:
        return {
            "net_mac": "-" if data.get("NET_MAC") in (None, "") else str(data.get("NET_MAC")).strip(),
            "sys_modelname": "-" if data.get("SYS_MODELNAME_ID") in (None, "") else str(data.get("SYS_MODELNAME_ID")).strip(),
            "sys_version": "-" if data.get("SYS_VERSION") in (None, "") else str(data.get("SYS_VERSION")).strip(),
            "sys_mode": self._fmt_enum_value("SYS_MODE", data.get("SYS_MODE")),
            "module_version": "-" if data.get("CAM_READMODULEVERSION") in (None, "") else str(
                data.get("CAM_READMODULEVERSION")).strip(),
            "meca_version": "-" if data.get("CAM_READMECAVERSION") in (None, "") else str(
                data.get("CAM_READMECAVERSION")).strip(),
            "linkdown_num": "-" if data.get("SYS_LINKDOWN_NUM") in (None, "") else str(
                data.get("SYS_LINKDOWN_NUM")).strip(),
            "local_ip_mode": self._fmt_enum_value("NET_LOCALIPMODE", data.get("NET_LOCALIPMODE")),
            "power_type": "-" if data.get("TEST_Power_CheckString") in (None, "") else str(
                data.get("TEST_Power_CheckString")).strip(),
            "startup_time": "-" if data.get("SYS_STARTTIME") in (None, "") else str(data.get("SYS_STARTTIME")).strip(),
            "disk": self._build_disk_text(data),
            "ai_version": "-" if data.get("SYS_AI_VERSION") in (None, "") else str(data.get("SYS_AI_VERSION")).strip(),
            "rcv_version": "-" if data.get("SYS_RCV_VERSION") in (None, "") else str(
                data.get("SYS_RCV_VERSION")).strip(),
        }

    def _rate_text_from_raw(self, raw: dict, idx: int) -> str:
        br = raw.get(f"GRS_VENCBITRATE{idx}") or "-"
        fp = raw.get(f"GRS_VENCFRAME{idx}") or "-"
        if br == "-" and fp == "-":
            return "-"
        return f"{br}kbps / {fp}fps"

    def _extract_status_summary_map(self, snap: dict) -> dict[str, str]:
        rate = snap.get("rate") or {}
        raw = snap.get("raw") or {}

        return {
            "cds": snap.get("cds", "-"),
            "current": snap.get("cds_current", "-"),
            "bitrate_fps": f"{rate.get('kbps') or '-'}kbps / {rate.get('fps') or '-'}fps",
            "rate2": self._rate_text_from_raw(raw, 2),
            "rate3": self._rate_text_from_raw(raw, 3),
            "rate4": self._rate_text_from_raw(raw, 4),
            "rtc": snap.get("rtc", "-"),
            "eth": snap.get("eth", "-"),
            "temp": snap.get("temp", "-"),
            "fan": snap.get("fan", "-"),
            "audio_enc_bitrate": raw.get("GRS_AENCBITRATE1", "-"),
            "audio_dec_bitrate": raw.get("GRS_ADECBITRATE1", "-"),
            "audio_dec_algorithm": raw.get("GRS_ADECALGORITHM1", "-"),
            "audio_dec_samplerate": raw.get("GRS_ADECSAMPLERATE1", "-"),
            "sensor1": raw.get("GIS_SENSOR1", "-"),
            "sensor2": raw.get("GIS_SENSOR2", "-"),
            "sensor3": raw.get("GIS_SENSOR3", "-"),
            "sensor4": raw.get("GIS_SENSOR4", "-"),
            "sensor5": raw.get("GIS_SENSOR5", "-"),
            "motion1": raw.get("GIS_MOTION1", "-"),
            "motion2": raw.get("GIS_MOTION2", "-"),
            "motion3": raw.get("GIS_MOTION3", "-"),
            "motion4": raw.get("GIS_MOTION4", "-"),
            "videoloss1": raw.get("GIS_VIDEOLOSS1", "-"),
            "videoloss2": raw.get("GIS_VIDEOLOSS2", "-"),
            "videoloss3": raw.get("GIS_VIDEOLOSS3", "-"),
            "videoloss4": raw.get("GIS_VIDEOLOSS4", "-"),
            "alarm1": raw.get("GIS_ALARM1", "-"),
            "alarm2": raw.get("GIS_ALARM2", "-"),
            "alarm3": raw.get("GIS_ALARM3", "-"),
            "alarm4": raw.get("GIS_ALARM4", "-"),
            "record1": raw.get("GIS_RECORD1", "-"),
            "airwiper": raw.get("GIS_AIRWIPER", "-"),
            "ethtool_raw": raw.get("ETHTOOL", "-"),
        }

    # ---------------------------------------------------------------------
    # preview / hub lifecycle
    # ---------------------------------------------------------------------
    def _build_rtsp_url(self, *, include_audio: bool) -> str:
        ip = (self.ip.text() or "").strip()
        if include_audio:
            return f"rtsp://{ip}:554/video1+audio1"
        return f"rtsp://{ip}:554/video1"

    def _ensure_vlc(self) -> bool:
        if self._vlc_inited:
            return True

        try:
            from ui.vlc_widget import VLCWidget

            self.vlc_widget = VLCWidget()
            self.vlc_widget.sig_state.connect(self.on_preview_state)
            self.vlc_container.set_child(self.vlc_widget)
            self._vlc_inited = True
            return True
        except Exception as e:
            self.lbl_preview_state.setText(f"VLC init failed: {e}")
            self._vlc_inited = False
            self.vlc_widget = None
            return False

    def on_preview_start(self) -> None:
        if not self._conn or not self._ensure_vlc():
            return

        try:
            url = self._build_rtsp_url(include_audio=self._preview_include_audio)
            username = (self.user.text() or "").strip() or "admin"
            password = (
                self._used_password
                or (self._conn.get("effective_password") or "").strip()
                or (self.pw.text() or "")
            )
            self.vlc_widget.play_rtsp(url, username=username, password=password)  # type: ignore[attr-defined]
        except Exception as e:
            self.lbl_preview_state.setText(f"Preview start failed: {e}")

    def on_preview_stop(self) -> None:
        try:
            if self.vlc_widget is not None:
                self.vlc_widget.stop()
        except Exception:
            pass

    def _restart_preview(self) -> None:
        if not self._conn or not self._ensure_vlc():
            return
        if self.btn_preview_stop.isEnabled():
            self.on_preview_stop()
        self.on_preview_start()

    def on_preview_state(self, state: str) -> None:
        self.lbl_preview_state.setText(state)

    def _start_hub(self) -> None:
        if not self._conn or not self._used_password or self._hub is not None:
            return

        base_url = self._conn.get("base_url")
        root_path = self._conn.get("root_path")
        auth_scheme = self._conn.get("auth_scheme")
        if not (base_url and root_path and auth_scheme):
            return

        cfg = HubConfig(
            base_url=base_url,
            root_path=root_path,
            auth_scheme=str(auth_scheme),
            username=self.user.text().strip() or "admin",
            password=self._used_password,
            verify_tls=bool(self.settings.verify_tls),
            poll_interval_ms=self.POLL_INTERVAL_MS,
            continue_interval_ms=self.PTZ_CONTINUE_INTERVAL_MS,
            ptz_timeout_ms=self.PTZ_TIMEOUT_MS,
            ptz_channel=self.PTZ_CHANNEL_DEFAULT,
        )

        self._hub = RequestHubWorker(cfg=cfg, settings=self.settings)
        self._hub.sig_readparam.connect(self.on_hub_readparam)
        self._hub.sig_poll.connect(self.on_hub_poll)
        self._hub.sig_error.connect(self.on_hub_error)
        self._hub.sig_log.connect(self._append_log)
        self._hub.sig_state.connect(lambda s: self.lbl_conn_state.setText(f"Connected. {s}"))
        self._hub.sig_task.connect(self.on_hub_task)
        self._hub.sig_cam_log.connect(self.on_cam_log_loaded)
        self._hub.sig_audio_caps.connect(self.on_audio_caps)
        self._hub.sig_video_auto.connect(self.on_video_auto_detect)
        self._hub.sig_product_model.connect(self.on_product_model_result)
        self._hub.start()

        self._preview_include_audio = False
        self._audio_playing = False
        self.btn_aud_play.setText("Play")
        self._hub.audio_caps_scan()
        QTimer.singleShot(300, lambda: self._hub and self._hub.readparam(key="VID_INPUTFORMAT"))

    def _stop_hub(self) -> None:
        hub = self._hub
        if not hub:
            return
        try:
            hub.request_cancel()
            hub.wait(1500)
        finally:
            self._hub = None
        self._audio_playing = False
        self.btn_aud_play.setText("Play")

    # ---------------------------------------------------------------------
    # logging / message helpers
    # ---------------------------------------------------------------------
    def _append_log(self, text: str) -> None:
        self.log_box.appendPlainText(text)
        self.log_box.moveCursor(QTextCursor.End)
        self.log_box.ensureCursorVisible()

    def _friendly_error_text(self, err: dict) -> str:
        code = (err.get("error_code") or "").upper()
        kind = err.get("kind")
        status = err.get("status_code")
        msg = err.get("message") or ""
        detail = (err.get("detail") or "").replace("\r", " ").replace("\n", " ")

        if code == "NO_DEVICE":
            return "해당 IP에 장비가 없습니다. IP 설정 및 네트워크 연결을 확인하세요."
        if code == "PORT_CLOSED":
            return "장비가 응답하지 않습니다. 포트(80/443) 또는 방화벽/네트워크 설정을 확인하세요."
        if code == "AUTH_FAILED":
            return "인증에 실패했습니다. 아이디/비밀번호를 확인하세요."
        if code == "PROBE_FAILED":
            return "장비 접속 정보를 확인할 수 없습니다. IP/포트/프로토콜(HTTP/HTTPS)을 확인하세요."

        if len(detail) > 140:
            detail = detail[-140:]
        if detail:
            return f"{msg} (kind={kind}, status={status}) - {detail}"
        return f"{msg} (kind={kind}, status={status})"

    # ---------------------------------------------------------------------
    # worker / connection flow
    # ---------------------------------------------------------------------
    def on_connect_clicked(self) -> None:
        ip = self.ip.text().strip()
        if not ip:
            QMessageBox.warning(self, "입력 오류", "IP는 필수입니다.")
            return

        self._stop_hub()
        self._conn = None
        self._used_password = None

        self.log_box.clear()
        self.cam_log_box.clear()
        self._clear_all_views()
        self._set_all_controls_enabled(False)
        self._set_fw_busy(False)

        self.lbl_conn_state.setText("Connecting...")
        self.btn_connect.setEnabled(False)

        pw_now = self.pw.text()
        self._phase1 = Phase1Worker(
            ip=ip,
            port=int(self.port.value()),
            username=self.user.text().strip() or "admin",
            password=pw_now,
            password_candidates=[pw_now],
            target_password=self.TARGET_PASSWORD,
            settings=self.settings,
            extra_keys=[],
        )
        self._phase1.sig_progress.connect(self.lbl_conn_state.setText)
        self._phase1.sig_success.connect(self.on_phase1_success)
        self._phase1.sig_failure.connect(self.on_failure)
        self._phase1.sig_finished.connect(self.on_phase1_finished)
        self._phase1.start()

    def on_phase1_success(self, payload: dict) -> None:
        self._conn = payload

        eff_user = (payload.get("effective_username") or "").strip() or None
        if eff_user and eff_user != self.user.text().strip():
            self.user.setText(eff_user)

        eff_pw = (payload.get("effective_password") or "").strip() or None
        if eff_pw:
            self._used_password = eff_pw
            self.pw.setText(eff_pw)
        else:
            self._used_password = (self.pw.text() or "").strip() or None

        self.lbl_conn_state.setText("Connected. Loading device info...")
        self.btn_reload_info.setEnabled(True)
        self.btn_disconnect.setEnabled(True)
        self.btn_preview_start.setEnabled(True)
        self.btn_preview_stop.setEnabled(True)
        self.lbl_preview_state.setText("Ready.")

        self._start_device_info_worker()

    def on_phase1_finished(self) -> None:
        self._phase1 = None
        self.btn_connect.setEnabled(True)

    def _build_password_candidates_for_reuse(self) -> list[str]:
        out: list[str] = []

        eff = None
        if self._conn:
            eff = (self._conn.get("effective_password") or "").strip() or None
        if eff:
            out.append(eff)

        if self._used_password and self._used_password not in out:
            out.append(self._used_password)

        pw_ui = (self.pw.text() or "").strip()
        if pw_ui and pw_ui not in out:
            out.append(pw_ui)

        return out[:3]

    def _start_device_info_worker(self) -> None:
        if not self._conn:
            return

        base_url = self._conn.get("base_url")
        root_path = self._conn.get("root_path")
        auth_scheme = self._conn.get("auth_scheme")
        if not (base_url and root_path and auth_scheme):
            self._append_log("[ERROR] missing connection info")
            return

        eff_pw = (self._conn.get("effective_password") or "").strip() or None
        if eff_pw:
            self._used_password = eff_pw

        eff_user = (self._conn.get("effective_username") or "").strip() or None
        username = eff_user or (self.user.text().strip() or "admin")

        self._info = DeviceInfoWorker(
            base_url=base_url,
            root_path=root_path,
            username=username,
            password_candidates=self._build_password_candidates_for_reuse(),
            auth_scheme=auth_scheme,
            settings=self.settings,
        )
        self._info.sig_progress.connect(self.lbl_conn_state.setText)
        self._info.sig_success.connect(self.on_device_info_success)
        self._info.sig_failure.connect(self.on_failure)
        self._info.sig_finished.connect(self.on_device_info_finished)
        self._info.start()

    def on_reload_info_clicked(self) -> None:
        if not self._conn:
            return
        self.lbl_conn_state.setText("Reloading device info...")
        self._start_device_info_worker()

    def on_device_info_success(self, payload: dict) -> None:
        data = payload.get("data") or {}
        self._last_device_info = dict(data)

        used_pw = payload.get("used_password")
        if used_pw:
            self._used_password = used_pw

        for key, value in self._extract_info_summary_map(data).items():
            self._set_info_summary_value(key, value)

        self._rebuild_info_summary_form()
        self._set_all_controls_enabled(True)
        self._start_hub()

        # 접속 완료 상태 반영
        self.lbl_conn_state.setText("Connected.")

        # 마지막 단계에서 자동 프리뷰 시작
        # 버튼 enable 상태도 이미 on_phase1_success()에서 켜져 있으므로 바로 호출 가능
        QTimer.singleShot(150, self.on_preview_start)

    def on_device_info_finished(self) -> None:
        self._info = None

    def on_failure(self, err: dict) -> None:
        detail = (err.get("detail") or "").replace("\r", " ").replace("\n", " ")
        if len(detail) > 200:
            detail = detail[-200:]
        friendly = self._friendly_error_text(err)
        self._append_log(f"[ERROR] {friendly}")
        self.lbl_conn_state.setText("Failed")

    def _force_disconnect_ui(self, reason: str = "") -> None:
        if reason:
            self._append_log(f"[INFO] {reason}")

        try:
            if self.vlc_widget is not None:
                self.vlc_widget.stop()
        except Exception:
            pass

        self._stop_hub()

        if self._phase1:
            try:
                self._phase1.request_cancel()
            except Exception:
                pass
        if self._info:
            try:
                self._info.request_cancel()
            except Exception:
                pass

        self._conn = None
        self._used_password = None
        self._set_fw_busy(False)

        self.btn_preview_start.setEnabled(False)
        self.btn_preview_stop.setEnabled(False)
        self.lbl_preview_state.setText("-")

        self.btn_reload_info.setEnabled(False)
        self.btn_disconnect.setEnabled(False)
        self.btn_connect.setEnabled(True)

        self._set_all_controls_enabled(False)
        self.lbl_conn_state.setText("Disconnected. reconnect after 30~120s.")

    def on_disconnect_clicked(self) -> None:
        self._force_disconnect_ui(reason="user disconnected")
        self.lbl_conn_state.setText("Disconnected.")

    # ---------------------------------------------------------------------
    # hub callbacks
    # ---------------------------------------------------------------------
    def on_hub_poll(self, snap: dict) -> None:
        raw = snap.get("raw") or {}

        for key, value in self._extract_status_summary_map(snap).items():
            self._set_status_summary_value(key, value)

        for i in range(4):
            self.sensor_leds[i].set_on(as_bool_01(raw.get(f"GIS_SENSOR{i + 1}")))
            self.alarm_leds[i].set_on(as_bool_01(raw.get(f"GIS_ALARM{i + 1}")))

        self._rebuild_status_summary_form()

    def on_hub_error(self, err: dict) -> None:
        kind = err.get("kind")
        msg = err.get("message") or ""
        detail = (err.get("detail") or "").replace("\r", " ").replace("\n", " ")
        if len(detail) > 200:
            detail = detail[-200:]

        if kind == "disconnect":
            reason = detail or msg or "disconnect required"
            self._append_log(f"[INFO] disconnect required | {reason}")
            self._force_disconnect_ui(reason=f"Disconnected required | {reason}")
            return

        friendly = self._friendly_error_text(err)
        self._append_log(f"[ERROR] {friendly}")

    def on_hub_readparam(self, key: str, value: str) -> None:
        k = (key or "").strip().upper()
        if k != "VID_INPUTFORMAT":
            return

        code = str(value or "").strip()
        label = "-"
        for dec_code, text in get_board_input_formats(
            (self._last_device_info or {}).get("SYS_BOARDID")
            or (self._last_device_info or {}).get("BOARDID_DEC")
            or (self._last_device_info or {}).get("BOARDID_HEX")
        ):
            if str(dec_code) == code:
                label = f"{text} [{code}]"
                break

        self.lbl_vid_in_current.setText(f"Current: {label}")

    def on_hub_task(self, kind: str, phase: str, ok: bool, message: str) -> None:
        if kind != "fw_upload":
            return

        if phase == "start":
            self._set_fw_busy(True)
            return

        self._set_fw_busy(False)
        if ok:
            self._append_log("[INFO] FW trigger done (device may reboot). reconnect after 30~120s.")
            self._force_disconnect_ui(reason="firmware upload requested (device may reboot)")
        else:
            self._append_log(f"[INFO] FW failed: {message}")

    def on_cam_log_loaded(self, ok: bool, text: str) -> None:
        self.btn_load_cam_log.setEnabled(True)
        if not ok:
            self.cam_log_box.setPlainText("No log / request failed")
            return
        self.cam_log_box.setPlainText(text or "No log")

    def on_audio_caps(self, caps: dict) -> None:
        self._audio_caps_supported = caps.get("supported") or {}
        self._audio_caps_values = caps.get("values") or {}
        supported = self._audio_caps_supported
        values = self._audio_caps_values

        def _s(k: str) -> bool:
            return bool(supported.get(k, False))

        parts = []
        for k in [
            "AUD_AUDIOMODE",
            "AUD_ENABLE",
            "AUD_CODEC",
            "AUD_ALGORITHM",
            "AUD_GAIN",
            "AUD_INPUTGAIN",
            "AUD_OUTPUTGAIN",
            "AUD_MUTE",
        ]:
            ok = _s(k)
            v = values.get(k, "")
            parts.append(f"{k}: {'OK' if ok else 'NO'}" + (f" (v={v})" if (ok and v != "") else ""))

        self.lbl_audio_caps.setText("Audio caps: " + " | ".join(parts))

        codec_ok = _s("AUD_CODEC") or _s("AUD_ALGORITHM")
        self.btn_aud_codec_aac.setEnabled(codec_ok)
        self.btn_aud_codec_g711.setEnabled(codec_ok)

        vol_ok = _s("AUD_GAIN") or _s("AUD_INPUTGAIN") or _s("AUD_OUTPUTGAIN")
        self.btn_aud_max_volume.setEnabled(vol_ok)

        cur_codec = self._aud_value("AUD_CODEC")
        if self._aud_supported("AUD_CODEC") and cur_codec.isdigit():
            self.btn_aud_codec_aac.setText("AAC (1)")
            self.btn_aud_codec_g711.setText("G.711 (0)")
        else:
            self.btn_aud_codec_aac.setText("AAC")
            self.btn_aud_codec_g711.setText("G.711")

    def on_product_model_result(self, ok: bool, written_value: str, read_value: str) -> None:
        if ok:
            same = written_value.strip() == (read_value or "").strip()
            if same:
                self.txt_product_model_result.setPlainText(
                    f"WRITE: {written_value}\nREAD : {read_value}\nRESULT: OK"
                )
                self._append_log(f"[INFO] SYS_PRODUCT_MODEL applied OK -> {read_value}")
            else:
                self.txt_product_model_result.setPlainText(
                    f"WRITE: {written_value}\nREAD : {read_value}\nRESULT: MISMATCH"
                )
                self._append_log(
                    f"[WARN] SYS_PRODUCT_MODEL mismatch | write={written_value} read={read_value}"
                )
        else:
            self.txt_product_model_result.setPlainText(read_value or "failed")
            self._append_log(f"[ERROR] SYS_PRODUCT_MODEL failed | {read_value}")

    def on_video_auto_detect(self, data: dict) -> None:
        boardid_raw = (
            (self._last_device_info or {}).get("SYS_BOARDID")
            or (self._last_device_info or {}).get("BOARDID_DEC")
            or (self._last_device_info or {}).get("BOARDID_HEX")
        )

        self.cmb_vid_in_auto.blockSignals(True)
        self.cmb_vid_in_auto.clear()

        count = 0
        for key, title in (
            ("VID_IAD_COMPOSITE", "Composite"),
            ("VID_IAD_HDMI", "HDMI"),
            ("VID_IAD_SDI", "SDI"),
        ):
            code = str(data.get(key) or "").strip()
            if not code:
                continue

            try:
                if int(code) <= 0:
                    continue
            except Exception:
                continue

            label = get_label_for_inputformat(code, boardid_raw)
            max_res = get_max_resolution_for_inputformat(code) or "?"
            self.cmb_vid_in_auto.addItem(
                f"{title}: {label} [{code}] / max res {max_res}",
                code,
            )
            count += 1

        self.cmb_vid_in_auto.blockSignals(False)
        self.lbl_vid_in_auto.setText(
            f"Auto: {count} detected" if count > 0 else "Auto: no signal detected"
        )

    # ---------------------------------------------------------------------
    # external actions
    # ---------------------------------------------------------------------
    def on_load_cam_log_clicked(self) -> None:
        if not self._hub:
            QMessageBox.information(self, "Not connected", "먼저 Connect 하세요.")
            return
        self.cam_log_box.setPlainText("Loading...")
        self.btn_load_cam_log.setEnabled(False)
        self._hub.cam_log_load()

    def on_save_cam_log_clicked(self) -> None:
        text = (self.cam_log_box.toPlainText() or "").strip()
        if not text:
            QMessageBox.information(self, "No log", "No log to save")
            return

        out_path = Path("camera_system_log.txt")
        try:
            out_path.write_text(text, encoding="utf-8", errors="ignore")
            QMessageBox.information(self, "Saved", f"Saved to: {out_path.resolve()}")
        except Exception as e:
            QMessageBox.critical(self, "Save failed", str(e))

    def _set_fw_busy(self, busy: bool) -> None:
        self.ed_fw_path.setEnabled(not busy)
        self.btn_fw_browse.setEnabled(not busy)
        self.btn_fw_upload.setEnabled(not busy)
        self.btn_fw_upload.setText("Uploading..." if busy else "Upload Firmware")

    def _on_fw_upload_clicked(self) -> None:
        if not self._hub:
            return
        path = self.ed_fw_path.text().strip()
        if not path:
            QMessageBox.warning(self, "입력 오류", "펌웨어 파일 경로를 선택하세요.")
            return
        self._set_fw_busy(True)
        self._hub.fw_upload(path)

    # ---------------------------------------------------------------------
    # audio helpers
    # ---------------------------------------------------------------------
    def _aud_supported(self, key: str) -> bool:
        return bool((self._audio_caps_supported or {}).get(key, False))

    def _aud_value(self, key: str) -> str:
        return str((self._audio_caps_values or {}).get(key, "") or "")

    def _aud_write_codec(self, algo_value: str, codec_value_str: str, codec_value_num: str) -> None:
        if not self._hub:
            return

        if self._aud_supported("AUD_ALGORITHM"):
            self._hub.writeparam(key="AUD_ALGORITHM", value=algo_value)
            return

        if self._aud_supported("AUD_CODEC"):
            cur = self._aud_value("AUD_CODEC")
            if cur.isdigit():
                self._hub.writeparam(key="AUD_CODEC", value=codec_value_num)
            else:
                self._hub.writeparam(key="AUD_CODEC", value=codec_value_str)

    # ---------------------------------------------------------------------
    # UI wiring
    # ---------------------------------------------------------------------
    def _wire_ptz_ui(self) -> None:
        self.joystick.changed.connect(self._on_joystick_changed)

        self.btn_zoom_in.pressed.connect(lambda: self._hub and self._hub.zoom_press(mode="zoomin"))
        self.btn_zoom_in.released.connect(lambda: self._hub and self._hub.zoom_release())
        self.btn_zoom_out.pressed.connect(lambda: self._hub and self._hub.zoom_press(mode="zoomout"))
        self.btn_zoom_out.released.connect(lambda: self._hub and self._hub.zoom_release())
        self.btn_zoom_1x.clicked.connect(lambda: self._hub and self._hub.zoom_1x())

        self.btn_focus_near.pressed.connect(lambda: self._hub and self._hub.focus_press(mode="focusnear"))
        self.btn_focus_near.released.connect(lambda: self._hub and self._hub.focus_release())
        self.btn_focus_far.pressed.connect(lambda: self._hub and self._hub.focus_press(mode="focusfar"))
        self.btn_focus_far.released.connect(lambda: self._hub and self._hub.focus_release())
        self.btn_focus_auto.clicked.connect(lambda: self._hub and self._hub.focus_auto())

        self.btn_tdn_auto.clicked.connect(lambda: self._hub and self._hub.writeparam(key="CAM_HI_TDN_MODE", value="0"))
        self.btn_tdn_day.clicked.connect(lambda: self._hub and self._hub.writeparam(key="CAM_HI_TDN_MODE", value="2"))
        self.btn_tdn_night.clicked.connect(lambda: self._hub and self._hub.writeparam(key="CAM_HI_TDN_MODE", value="3"))

        self.btn_icr_on.clicked.connect(lambda: self._hub and self._hub.writeparam(key="CAM_HI_TDN_FILTER", value="1"))
        self.btn_icr_off.clicked.connect(lambda: self._hub and self._hub.writeparam(key="CAM_HI_TDN_FILTER", value="2"))
        self.btn_icr_auto.clicked.connect(lambda: self._hub and self._hub.writeparam(key="CAM_HI_TDN_FILTER", value="0"))

        self.btn_lens_offset_lens.clicked.connect(lambda: self._hub and self._hub.lens_offset_lens())
        self.btn_lens_offset_zoomlens.clicked.connect(lambda: self._hub and self._hub.lens_offset_zoomlens())

    def _wire_phase3_ui(self) -> None:
        def _vid_in_auto_scan() -> None:
            if not self._hub:
                QMessageBox.information(self, "Not connected", "먼저 Connect 하세요.")
                return
            self.lbl_vid_in_auto.setText("Auto: scanning...")
            self.cmb_vid_in_auto.clear()
            self._hub.video_auto_detect()

        def _vid_in_auto_apply() -> None:
            if not self._hub:
                QMessageBox.information(self, "Not connected", "먼저 Connect 하세요.")
                return

            code = self.cmb_vid_in_auto.currentData()
            label = self.cmb_vid_in_auto.currentText()
            if not code:
                self._append_log("[ERROR] no auto detected format selected")
                return

            max_res = get_max_resolution_for_inputformat(code)
            if not max_res:
                self._append_log(f"[ERROR] no max resolution mapping for auto detected input={code}")
                return

            self.lbl_vid_in_target.setText(f"{label}")
            self._hub.video_set_input_format(str(code), str(max_res))
            self._append_log(f"[INFO] Auto video input apply -> input={code}, max_res={max_res}")

        def _reboot() -> None:
            if not self._hub:
                return
            self._append_log("[INFO] reboot requested")
            self._set_all_controls_enabled(False)
            self.btn_disconnect.setEnabled(False)
            self.lbl_conn_state.setText("Reboot requested... (waiting for device to drop)")
            self._hub.reboot()

        def _factory_reset() -> None:
            if not self._hub:
                return
            self._append_log("[INFO] factory reset requested")
            self._set_all_controls_enabled(False)
            self.btn_disconnect.setEnabled(False)
            self.lbl_conn_state.setText("Factory reset requested... (waiting for device to drop)")
            self._hub.factory_reset()

        def _set_rtc_now() -> None:
            if not self._hub:
                return
            from datetime import datetime

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._hub.writeparam(key="SYS_CURRENTTIME", value=now)
            self._append_log(f"[INFO] RTC set to {now}")

        def _browse() -> None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Select Firmware File",
                "",
                "Firmware Files (*.tus *.bin *.img);;All Files (*.*)",
            )
            if path:
                self.ed_fw_path.setText(path)

        def _aud_play() -> None:
            if not self._hub:
                return

            if not self._audio_playing:
                self._preview_include_audio = True
                self._restart_preview()
                self._audio_playing = True
                self.btn_aud_play.setText("Stop")
                return

            self._preview_include_audio = False
            self._restart_preview()
            self._audio_playing = False
            self.btn_aud_play.setText("Play")

        def _aud_codec_aac() -> None:
            self._aud_write_codec(algo_value="1", codec_value_str="AAC", codec_value_num="1")

        def _aud_codec_g711() -> None:
            self._aud_write_codec(algo_value="0", codec_value_str="G711", codec_value_num="0")

        def _aud_set_max_volume() -> None:
            if not self._hub:
                return

            if self._aud_supported("AUD_GAIN"):
                self._hub.writeparam(key="AUD_GAIN", value="31")
                return

            wrote = False
            if self._aud_supported("AUD_INPUTGAIN"):
                self._hub.writeparam(key="AUD_INPUTGAIN", value="100")
                wrote = True
            if self._aud_supported("AUD_OUTPUTGAIN"):
                self._hub.writeparam(key="AUD_OUTPUTGAIN", value="100")
                wrote = True
            if not wrote:
                return

        def _vid_in_scan() -> None:
            boardid_raw = (
                (self._last_device_info or {}).get("SYS_BOARDID")
                or (self._last_device_info or {}).get("BOARDID_DEC")
                or (self._last_device_info or {}).get("BOARDID_HEX")
            )

            board_hex = boardid_to_hex(boardid_raw)
            group_name = resolve_board_input_group(boardid_raw)
            formats = get_board_input_formats(boardid_raw)

            self.cmb_vid_in_format.blockSignals(True)
            self.lbl_vid_in_group.setText(f"{group_name} ({board_hex})")
            self.cmb_vid_in_format.clear()
            for dec_code, label in formats:
                self.cmb_vid_in_format.addItem(f"{label} [{dec_code}]", dec_code)
            self.cmb_vid_in_format.blockSignals(False)
            _vid_in_on_format_changed()

            if formats:
                self._append_log(
                    f"[INFO] Video input list loaded | board={board_hex} group={group_name} count={len(formats)}"
                )
            else:
                self._append_log(
                    f"[WARN] No video input list for board={board_hex}, fallback group={group_name}"
                )

        def _vid_in_apply() -> None:
            if not self._hub:
                QMessageBox.information(self, "Not connected", "먼저 Connect 하세요.")
                return

            code = self.cmb_vid_in_format.currentData()
            label = self.cmb_vid_in_format.currentText()
            if not code:
                self._append_log("[ERROR] invalid input format")
                return

            max_res = get_max_resolution_for_inputformat(code)
            if not max_res:
                self._append_log(f"[ERROR] no max resolution mapping for input format={code}")
                return

            self.lbl_vid_in_target.setText(f"{label} / max res {max_res}")
            self._hub.video_set_input_format(str(code), str(max_res))
            self._append_log(f"[INFO] Video input apply -> input={code}, max_res={max_res}")

        def _vid_in_on_format_changed() -> None:
            code = self.cmb_vid_in_format.currentData()
            label = self.cmb_vid_in_format.currentText()
            if not code:
                self.lbl_vid_in_target.setText("Target: (not selected)")
                return

            max_res = get_max_resolution_for_inputformat(code)
            if not max_res:
                self.lbl_vid_in_target.setText(f"{label} / max res ?")
                return

            self.lbl_vid_in_target.setText(f"{label} / max res {max_res}")

        def _set_product_model() -> None:
            if not self._hub:
                QMessageBox.information(self, "Not connected", "먼저 Connect 하세요.")
                return

            value = self.ed_product_model.text().strip()
            if not value:
                QMessageBox.warning(self, "입력 오류", "제품명을 입력하세요.")
                return

            self.txt_product_model_result.setPlainText("Applying...")
            self._hub.set_product_model(value)

        self.btn_reboot.clicked.connect(_reboot)
        self.btn_factory_reset.clicked.connect(_factory_reset)
        self.btn_set_modelname.clicked.connect(
            lambda: self._hub and self._hub.set_model_name(self.ed_modelname.text().strip())
        )
        self.btn_set_extra_id.clicked.connect(
            lambda: self._hub and self._hub.set_extra_id(self.ed_extra_value.text().strip())
        )
        self.btn_set_rtc_now.clicked.connect(_set_rtc_now)

        self.btn_fw_browse.clicked.connect(_browse)
        self.btn_fw_upload.clicked.connect(self._on_fw_upload_clicked)

        self.btn_aud_play.clicked.connect(_aud_play)
        self.btn_aud_codec_aac.clicked.connect(_aud_codec_aac)
        self.btn_aud_codec_g711.clicked.connect(_aud_codec_g711)
        self.btn_aud_max_volume.clicked.connect(_aud_set_max_volume)
        self.btn_aud_loopback.clicked.connect(
            lambda: self._hub and self._hub.writeparam(key="AUD_LOOPBACK", value="1")
        )
        self.btn_aud_analog.clicked.connect(
            lambda: self._hub and self._hub.writeparam(key="AUD_INPUTMODE", value="ANALOG")
        )
        self.btn_aud_embedded.clicked.connect(
            lambda: self._hub and self._hub.writeparam(key="AUD_INPUTMODE", value="EMBEDDED")
        )
        self.btn_aud_decoded.clicked.connect(
            lambda: self._hub and self._hub.writeparam(key="AUD_DECODED", value="1")
        )

        self.btn_set_product_model.clicked.connect(_set_product_model)
        self.btn_vid_in_scan.clicked.connect(_vid_in_scan)
        self.btn_vid_in_apply.clicked.connect(_vid_in_apply)
        self.cmb_vid_in_format.currentIndexChanged.connect(_vid_in_on_format_changed)
        self.btn_vid_in_auto_scan.clicked.connect(_vid_in_auto_scan)
        self.btn_vid_in_auto_apply.clicked.connect(_vid_in_auto_apply)

        _vid_in_scan()

    # ---------------------------------------------------------------------
    # joystick / control state helpers
    # ---------------------------------------------------------------------
    def _set_all_controls_enabled(self, on: bool) -> None:
        for b in (
            self.btn_zoom_in,
            self.btn_zoom_out,
            self.btn_zoom_1x,
            self.btn_focus_near,
            self.btn_focus_far,
            self.btn_focus_auto,
            self.btn_tdn_day,
            self.btn_tdn_night,
            self.btn_tdn_auto,
            self.btn_icr_on,
            self.btn_icr_off,
            self.btn_icr_auto,
            self.btn_lens_offset_lens,
            self.btn_lens_offset_zoomlens,
            self.btn_reboot,
            self.btn_factory_reset,
            self.btn_set_modelname,
            self.btn_set_rtc_now,
            self.btn_set_extra_id,
            self.btn_fw_browse,
            self.btn_fw_upload,
            self.btn_load_cam_log,
            self.btn_save_cam_log,
            self.btn_aud_play,
            self.btn_aud_codec_aac,
            self.btn_aud_codec_g711,
            self.btn_aud_analog,
            self.btn_aud_embedded,
            self.btn_aud_decoded,
            self.btn_aud_loopback,
            self.btn_aud_max_volume,
            self.btn_vid_in_scan,
            self.btn_vid_in_apply,
            self.btn_vid_in_auto_scan,
            self.btn_vid_in_auto_apply,
            self.btn_set_product_model,
        ):
            b.setEnabled(on)

        self.joystick.setEnabled(on)
        self.ed_modelname.setEnabled(on)
        self.ed_extra_value.setEnabled(on)
        self.ed_fw_path.setEnabled(on)
        self.cam_log_box.setEnabled(on)
        self.cmb_vid_in_format.setEnabled(on)
        self.cmb_vid_in_auto.setEnabled(on)
        self.ed_product_model.setEnabled(on)
        self.txt_product_model_result.setEnabled(on)

    def _joy_direction_speed(self, dx: float, dy: float) -> tuple[str, int]:
        mag = (dx * dx + dy * dy) ** 0.5
        if mag < self.JOY_DEADZONE:
            return ("stop", 0)

        sp = int(round(mag * 8))
        sp = max(1, min(8, sp))

        ang = math.degrees(math.atan2(-dy, dx))
        if -22.5 <= ang < 22.5:
            return ("right", sp)
        if 22.5 <= ang < 67.5:
            return ("rightup", sp)
        if 67.5 <= ang < 112.5:
            return ("up", sp)
        if 112.5 <= ang < 157.5:
            return ("leftup", sp)
        if ang >= 157.5 or ang < -157.5:
            return ("left", sp)
        if -157.5 <= ang < -112.5:
            return ("leftdown", sp)
        if -112.5 <= ang < -67.5:
            return ("down", sp)
        return ("rightdown", sp)

    def _on_joystick_changed(self, dx: float, dy: float) -> None:
        if not self.joystick.isEnabled() or not self._hub:
            return

        direction, speed = self._joy_direction_speed(dx, dy)

        if direction == "stop":
            if self._joy_last_dir != "stop":
                self._hub.ptz_move_release()
                self._joy_last_dir, self._joy_last_speed = "stop", 0
            self._joy_gate.restart()
            return

        if self._joy_gate.elapsed() < self.JOY_SEND_INTERVAL_MS:
            return

        if direction != self._joy_last_dir or speed != self._joy_last_speed:
            self._hub.ptz_move_update(direction=direction, speed=speed)
            self._joy_last_dir, self._joy_last_speed = direction, speed

        self._joy_gate.restart()

    # ---------------------------------------------------------------------
    # reset / close
    # ---------------------------------------------------------------------
    def _clear_all_views(self) -> None:
        for _key, (_title, widget) in self._info_summary_widgets.items():
            widget.setText("-")
        for _key, (_title, widget) in self._status_summary_widgets.items():
            widget.setText("-")

        for led in self.sensor_leds:
            led.set_on(False)
        for led in self.alarm_leds:
            led.set_on(False)

        self.lbl_vid_in_group.setText("-")
        self.lbl_vid_in_target.setText("Target: (not selected)")
        self.lbl_vid_in_current.setText("Current: (not read)")
        self.cmb_vid_in_format.clear()

        self.lbl_vid_in_auto.setText("Auto: (not scanned)")
        self.cmb_vid_in_auto.clear()
        self.txt_product_model_result.clear()

    def closeEvent(self, event) -> None:
        try:
            self._settings.setValue("window/geometry", self.saveGeometry())
            self._save_summary_visibility()
        except Exception:
            pass

        try:
            self.on_preview_stop()
        except Exception:
            pass

        try:
            self._stop_hub()
        except Exception:
            pass

        try:
            if self._phase1:
                self._phase1.request_cancel()
            if self._info:
                self._info.request_cancel()
        except Exception:
            pass

        super().closeEvent(event)
