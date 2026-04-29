from __future__ import annotations


# =========================================================
# Video Input Profiles
# - board group -> available VID_INPUTFORMAT list
# - input format -> max VID_RESOLUTION
# HTML(boardinfo / video setup page) 기반 정적 매핑
# =========================================================


# -------------------------------
# HTML의 formboard 목록 기반
# key = 보드 그룹 이름
# value = [(decimal_code, label), ...]
# -------------------------------
BOARD_INPUT_GROUPS: dict[str, list[tuple[str, str]]] = {
    "sub_none": [],

    "sub_3000": [
        ("256", "Composite PAL"),
        ("257", "Composite NTSC"),
        ("520", "SD-SDI PAL"),
        ("519", "SD-SDI NTSC"),
        ("512", "HD-SDI 720p30"),
        ("517", "HD-SDI 720p50"),
        ("616", "HD-SDI 720p59.94"),
        ("516", "HD-SDI 720p60"),
        ("518", "HD-SDI 1080p30"),
        ("515", "HD-SDI 1080i50"),
        ("521", "HD-SDI 1080i59.94"),
        ("514", "HD-SDI 1080i60"),
        ("529", "HD-SDI 1080p25"),
        ("612", "HD-SDI 1080p29.97"),
        ("609", "3G-SDI 1080p50"),
        ("608", "3G-SDI 1080p60"),
        ("611", "3G-SDI 1080p59.94"),
        ("814", "HDMI 640x480p60"),
        ("768", "HDMI 480p30"),
        ("769", "HDMI 480p60"),
        ("770", "HDMI 480i60"),
        ("771", "HDMI 576p50"),
        ("772", "HDMI 576i50"),
        ("773", "HDMI 720p25"),
        ("774", "HDMI 720p30"),
        ("782", "HDMI 720p50"),
        ("834", "HDMI 720p59.94"),
        ("775", "HDMI 720p60"),
        ("780", "HDMI 1080i50"),
        ("789", "HDMI 1080i59.94"),
        ("779", "HDMI 1080i60"),
        ("833", "HDMI 1080p24"),
        ("776", "HDMI 1080p25"),
        ("777", "HDMI 1080p30"),
        ("781", "HDMI 1080p50"),
        ("778", "HDMI 1080p60"),
        ("791", "HDMI 800x600p60"),
        ("788", "HDMI 1024x768p60"),
        ("804", "HDMI 1152x864p60"),
        ("803", "HDMI 1280x768p60"),
        ("784", "HDMI 1280x960p30"),
        ("787", "HDMI 1280x960p60"),
        ("783", "HDMI 1280x1024p30"),
        ("786", "HDMI 1280x1024p60"),
        ("807", "HDMI 1280x1024p75"),
        ("805", "HDMI 1360x768p60"),
        ("790", "HDMI 1440x900p60"),
        ("815", "HDMI 1680x1050p60"),
        ("817", "HDMI 1600x1200p60"),
        ("793", "HDMI 1920x1200p60"),
    ],

    "sub_3000_HDMIOnly": [
        ("814", "HDMI 640x480p60"),
        ("768", "HDMI 480p30"),
        ("769", "HDMI 480p60"),
        ("770", "HDMI 480i60"),
        ("771", "HDMI 576p50"),
        ("772", "HDMI 576i50"),
        ("773", "HDMI 720p25"),
        ("774", "HDMI 720p30"),
        ("782", "HDMI 720p50"),
        ("834", "HDMI 720p59.94"),
        ("775", "HDMI 720p60"),
        ("780", "HDMI 1080i50"),
        ("789", "HDMI 1080i59.94"),
        ("779", "HDMI 1080i60"),
        ("833", "HDMI 1080p24"),
        ("776", "HDMI 1080p25"),
        ("777", "HDMI 1080p30"),
        ("781", "HDMI 1080p50"),
        ("778", "HDMI 1080p60"),
        ("791", "HDMI 800x600p60"),
        ("788", "HDMI 1024x768p60"),
        ("804", "HDMI 1152x864p60"),
        ("803", "HDMI 1280x768p60"),
        ("784", "HDMI 1280x960p30"),
        ("787", "HDMI 1280x960p60"),
        ("783", "HDMI 1280x1024p30"),
        ("786", "HDMI 1280x1024p60"),
        ("807", "HDMI 1280x1024p75"),
        ("805", "HDMI 1360x768p60"),
        ("790", "HDMI 1440x900p60"),
        ("815", "HDMI 1680x1050p60"),
        ("817", "HDMI 1600x1200p60"),
        ("793", "HDMI 1920x1200p60"),
    ],

    "sub_3500": [
        ("256", "Composite PAL"),
        ("257", "Composite NTSC"),
        ("520", "SD-SDI PAL"),
        ("519", "SD-SDI NTSC"),
        ("512", "HD-SDI 720p30"),
        ("517", "HD-SDI 720p50"),
        ("616", "HD-SDI 720p59.94"),
        ("516", "HD-SDI 720p60"),
        ("615", "HD-SDI 1080p24"),
        ("529", "HD-SDI 1080p25"),
        ("518", "HD-SDI 1080p30"),
        ("613", "HD-SDI 1080PsF23.98"),
        ("614", "HD-SDI 1080PsF24"),
        ("515", "HD-SDI 1080i50"),
        ("521", "HD-SDI 1080i59.94"),
        ("514", "HD-SDI 1080i60"),
        ("609", "3G-SDI 1080p50"),
        ("608", "3G-SDI 1080p60"),
        ("611", "3G-SDI 1080p59.94"),
        ("612", "HD-SDI 1080p29.97"),
        ("768", "HDMI 480p30"),
        ("769", "HDMI 480p60"),
        ("771", "HDMI 576p50"),
        ("773", "HDMI 720p25"),
        ("774", "HDMI 720p30"),
        ("782", "HDMI 720p50"),
        ("834", "HDMI 720p59.94"),
        ("775", "HDMI 720p60"),
        ("833", "HDMI 1080p24"),
        ("776", "HDMI 1080p25"),
        ("777", "HDMI 1080p30"),
        ("780", "HDMI 1080i50"),
        ("789", "HDMI 1080i59.94"),
        ("779", "HDMI 1080i60"),
        ("781", "HDMI 1080p50"),
        ("778", "HDMI 1080p60"),
        ("791", "HDMI 800x600p60"),
        ("788", "HDMI 1024x768p60"),
        ("804", "HDMI 1152x864p60"),
        ("803", "HDMI 1280x768p60"),
        ("784", "HDMI 1280x960p30"),
        ("787", "HDMI 1280x960p60"),
        ("783", "HDMI 1280x1024p30"),
        ("786", "HDMI 1280x1024p60"),
        ("805", "HDMI 1360x768p60"),
        ("790", "HDMI 1440x900p60"),
        ("817", "HDMI 1600x1200p60"),
        ("815", "HDMI 1680x1050p60"),
        ("793", "HDMI 1920x1200p60"),
    ],

    "sub_3500huns": [
        ("256", "Composite PAL"),
        ("257", "Composite NTSC"),
        ("520", "SD-SDI PAL"),
        ("519", "SD-SDI NTSC"),
        ("512", "HD-SDI 720p30"),
        ("517", "HD-SDI 720p50"),
        ("616", "HD-SDI 720p59.94"),
        ("516", "HD-SDI 720p60"),
        ("615", "HD-SDI 1080p24"),
        ("529", "HD-SDI 1080p25"),
        ("518", "HD-SDI 1080p30"),
        ("613", "HD-SDI 1080PsF23.98"),
        ("614", "HD-SDI 1080PsF24"),
        ("515", "HD-SDI 1080i50"),
        ("521", "HD-SDI 1080i59.94"),
        ("514", "HD-SDI 1080i60"),
        ("609", "3G-SDI 1080p50"),
        ("608", "3G-SDI 1080p60"),
        ("611", "3G-SDI 1080p59.94"),
        ("612", "HD-SDI 1080p29.97"),
        ("768", "HDMI 480p30"),
        ("769", "HDMI 480p60"),
        ("771", "HDMI 576p50"),
        ("773", "HDMI 720p25"),
        ("774", "HDMI 720p30"),
        ("782", "HDMI 720p50"),
        ("834", "HDMI 720p59.94"),
        ("775", "HDMI 720p60"),
        ("833", "HDMI 1080p24"),
        ("776", "HDMI 1080p25"),
        ("777", "HDMI 1080p30"),
        ("780", "HDMI 1080i50"),
        ("789", "HDMI 1080i59.94"),
        ("779", "HDMI 1080i60"),
        ("781", "HDMI 1080p50"),
        ("778", "HDMI 1080p60"),
        ("791", "HDMI 800x600p60"),
        ("788", "HDMI 1024x768p60"),
        ("804", "HDMI 1152x864p60"),
        ("803", "HDMI 1280x768p60"),
        ("784", "HDMI 1280x960p30"),
        ("787", "HDMI 1280x960p60"),
        ("783", "HDMI 1280x1024p30"),
        ("786", "HDMI 1280x1024p60"),
        ("805", "HDMI 1360x768p60"),
        ("790", "HDMI 1440x900p60"),
        ("817", "HDMI 1600x1200p60"),
        ("815", "HDMI 1680x1050p60"),
        ("793", "HDMI 1920x1200p60"),
    ],

    "sub_8000": [
        ("512", "HD-SDI 720p30"),
        ("517", "HD-SDI 720p50"),
        ("516", "HD-SDI 720p60"),
        ("518", "HD-SDI 1080p30"),
        ("529", "HD-SDI 1080p25"),
        ("612", "HD-SDI 1080p29.97"),
        ("609", "3G-SDI 1080p50"),
        ("608", "3G-SDI 1080p60"),
        ("611", "3G-SDI 1080p59.94"),
        ("782", "HDMI 720p50"),
        ("775", "HDMI 720p60"),
        ("776", "HDMI 1080p25"),
        ("777", "HDMI 1080p30"),
        ("781", "HDMI 1080p50"),
        ("778", "HDMI 1080p60"),
        ("788", "HDMI 1024x768p60"),
        ("784", "HDMI 1280x960p30"),
        ("787", "HDMI 1280x960p60"),
        ("783", "HDMI 1280x1024p30"),
        ("786", "HDMI 1280x1024p60"),
        ("807", "HDMI 1280x1024p75"),
        ("794", "HDMI 1920x1200p50"),
        ("793", "HDMI 1920x1200p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
        ("797", "HDMI 4096x2160p25"),
        ("798", "HDMI 4096x2160p30"),
    ],

    "sub_8500": [
        ("814", "HDMI 640x480p60"),
        ("771", "HDMI 576p50"),
        ("769", "HDMI 480p60"),
        ("791", "HDMI 800x600p60"),
        ("788", "HDMI 1024x768p60"),
        ("782", "HDMI 720p50"),
        ("775", "HDMI 720p60"),
        ("786", "HDMI 1280x1024p60"),
        ("790", "HDMI 1440x900p60"),
        ("817", "HDMI 1600x1200p60"),
        ("833", "HDMI 1080p24"),
        ("776", "HDMI 1080p25"),
        ("777", "HDMI 1080p30"),
        ("781", "HDMI 1080p50"),
        ("778", "HDMI 1080p60"),
        ("864", "HDMI 2560x1440p30"),
        ("866", "HDMI 2560x1600p60"),
        ("869", "HDMI 3840x2160p24"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
        ("867", "HDMI 3840x2160p50"),
        ("868", "HDMI 3840x2160p60"),
    ],

    "sub_imx103": [
        ("775", "HDMI 720p60"),
        ("776", "HDMI 1080p25"),
        ("777", "HDMI 1080p30"),
        ("781", "HDMI 1080p50"),
        ("778", "HDMI 1080p60"),
    ],

    "sub_S7500": [
        ("775", "HDMI 720p60"),
        ("776", "HDMI 1080p25"),
        ("777", "HDMI 1080p30"),
        ("781", "HDMI 1080p50"),
        ("778", "HDMI 1080p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
    ],

    "sub_S7520": [
        ("775", "HDMI 720p60"),
        ("776", "HDMI 1080p25"),
        ("777", "HDMI 1080p30"),
        ("781", "HDMI 1080p50"),
        ("778", "HDMI 1080p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
        ("867", "HDMI 3840x2160p50"),
        ("868", "HDMI 3840x2160p60"),
    ],

    "sub_S172": [
        ("775", "HDMI 720p60"),
        ("776", "HDMI 1080p25"),
        ("777", "HDMI 1080p30"),
        ("781", "HDMI 1080p50"),
        ("778", "HDMI 1080p60"),
    ],

    "sub_HIS124": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
    ],

    "sub_HIS178": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
    ],

    "sub_HIS185": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
    ],

    "sub_HIS322": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
    ],

    "sub_HIS385": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
        ("867", "HDMI 3840x2160p50"),
        ("868", "HDMI 3840x2160p60"),
    ],

    "sub_HIS185_ST": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
    ],

    "sub_HIS290": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
    ],

    "sub_HIS290_ST": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
    ],

    "sub_HIS291": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
        ("867", "HDMI 3840x2160p50"),
        ("868", "HDMI 3840x2160p60"),
    ],

    "sub_S291": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
        ("867", "HDMI 3840x2160p50"),
        ("868", "HDMI 3840x2160p60"),
    ],

    "sub_HIS274": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
    ],

    "sub_S8300": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
        ("867", "HDMI 3840x2160p50"),
        ("868", "HDMI 3840x2160p60"),
    ],

    "sub_HIS334": [
        ("775", "HDMI 720p60"),
        ("777", "HDMI 1080p30"),
        ("778", "HDMI 1080p60"),
        ("795", "HDMI 3840x2160p25"),
        ("796", "HDMI 3840x2160p30"),
    ],
}


# -------------------------------
# HTML의 formRes sub_<inputformat> 최대 해상도
# "선택한 입력포맷에서 최고로 갈 수 있는 VID_RESOLUTION 코드"
# -------------------------------
INPUTFORMAT_MAX_RES: dict[str, str] = {
    # Composite / SD-SDI / HD-SDI
    "256": "4",    # 720x576
    "257": "0",    # 720x480
    "512": "16",   # 1280x720
    "514": "17",   # 1920x1080
    "515": "17",   # 1920x1080
    "516": "16",   # 1280x720
    "517": "16",   # 1280x720
    "518": "17",   # 1920x1080
    "519": "0",    # 720x480
    "520": "4",    # 720x576
    "521": "17",   # 1920x1080
    "529": "17",   # 1920x1080
    "608": "17",   # 1920x1080
    "609": "17",   # 1920x1080
    "611": "17",   # 1920x1080
    "612": "17",   # 1920x1080
    "613": "17",   # 1920x1080
    "614": "17",   # 1920x1080
    "615": "17",   # 1920x1080
    "616": "16",   # 1280x720

    # HDMI SD/HD
    "768": "0",    # 720x480
    "769": "0",    # 720x480
    "770": "0",    # 720x480
    "771": "4",    # 720x576
    "772": "4",    # 720x576
    "773": "16",   # 1280x720
    "774": "16",   # 1280x720
    "775": "16",   # 1280x720
    "776": "17",   # 1920x1080
    "777": "17",   # 1920x1080
    "778": "17",   # 1920x1080
    "779": "17",   # 1920x1080
    "780": "17",   # 1920x1080
    "781": "17",   # 1920x1080
    "782": "16",   # 1280x720

    # PC timings
    "783": "12",   # 1280x1024
    "784": "11",   # 1280x960
    "785": "10",   # 1024x768
    "786": "12",   # 1280x1024
    "787": "11",   # 1280x960
    "788": "10",   # 1024x768
    "789": "17",   # 1920x1080
    "790": "13",   # 1440x900
    "791": "9",    # 800x600
    "793": "48",   # 1920x1200
    "794": "48",   # 1920x1200
    "795": "50",   # 3840x2160
    "796": "50",   # 3840x2160
    "797": "51",   # 4096x2160
    "798": "51",   # 4096x2160
    "803": "53",   # 1280x768
    "804": "54",   # 1152x864
    "805": "55",   # 1360x768
    "807": "12",   # 1280x1024
    "814": "8",    # 640x480
    "815": "15",   # 1680x1050
    "816": "57",   # 2048x2048
    "817": "47",   # 1600x1200

    # extra HDMI timings
    "833": "17",   # 1920x1080
    "834": "16",   # 1280x720
    "835": "16",   # conservative
    "836": "17",   # conservative
    "837": "17",   # conservative

    # higher res PC / UHD
    "862": "14",   # 1440x1050
    "863": "73",   # 1920x1440
    "864": "74",   # 2560x1440
    "866": "75",   # 2560x1600
    "867": "50",   # 3840x2160
    "868": "50",   # 3840x2160
    "869": "50",   # 3840x2160
}


# -------------------------------
# known exact board -> group
# 필요 시 계속 확장
# -------------------------------
BOARDID_EXACT_GROUPS: dict[int, str] = {
    # placeholder for future exact board matches
    # 0x1234: "sub_S7500",
}


def _safe_int(v: str | int | None, default: int = 0) -> int:
    try:
        if v is None:
            return default
        if isinstance(v, int):
            return v
        s = str(v).strip().lower()
        if not s:
            return default
        if s.startswith("0x"):
            return int(s, 16)
        return int(s)
    except Exception:
        return default


def boardid_to_hex(boardid: str | int | None) -> str:
    n = _safe_int(boardid, 0)
    return f"0x{n:X}" if n else "-"


def resolve_board_input_group(boardid: str | int | None) -> str:
    """
    SYS_BOARDID -> HTML formboard group name
    우선순위:
    1) exact board match
    2) upper nibble family
    """
    n = _safe_int(boardid, 0)
    if n <= 0:
        return "sub_3000"

    if n in BOARDID_EXACT_GROUPS:
        return BOARDID_EXACT_GROUPS[n]

    high = n & 0xF000

    if high == 0x3000:
        return "sub_3000"
    if high == 0x5000:
        return "sub_3500"
    if high == 0x8000:
        return "sub_8000"
    if high == 0x9000:
        return "sub_3500"
    if high == 0xA000:
        return "sub_8500"
    if high == 0xB000:
        return "sub_8500"

    return "sub_3000"


def get_board_input_formats(boardid: str | int | None) -> list[tuple[str, str]]:
    group = resolve_board_input_group(boardid)
    return BOARD_INPUT_GROUPS.get(group, [])


def get_max_resolution_for_inputformat(input_code: str | int) -> str | None:
    dec = str(_safe_int(input_code, 0))
    return INPUTFORMAT_MAX_RES.get(dec)


def get_label_for_inputformat(input_code: str | int, boardid: str | int | None = None) -> str:
    """
    boardid가 있으면 해당 board group 안에서 먼저 찾고,
    없으면 전체 group에서 순차 탐색.
    """
    dec = str(_safe_int(input_code, 0))
    if not dec or dec == "0":
        return "-"

    if boardid is not None:
        for code, label in get_board_input_formats(boardid):
            if code == dec:
                return label

    for items in BOARD_INPUT_GROUPS.values():
        for code, label in items:
            if code == dec:
                return label

    return dec