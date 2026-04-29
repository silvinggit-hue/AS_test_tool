from __future__ import annotations

# ----------------------------------------------------------------------
# ReadParam request structure
# ----------------------------------------------------------------------
# Fixed pattern:
#   GET /httpapi/ReadParam?action=readparam&KEY=0
#   GET /httpapi/ReadParam?action=readparam&KEY1=0&KEY2=0&...
# ----------------------------------------------------------------------


# ----------------------------------------------------------------------
# Network
# ----------------------------------------------------------------------
READPARAM_NETWORK_KEYS: tuple[str, ...] = (
    "NET_RTSPPORT",
    "NET_MAC",
    "NET_LOCALIPMODE",
)


# ----------------------------------------------------------------------
# System / identity / runtime
# ----------------------------------------------------------------------
READPARAM_SYSTEM_KEYS: tuple[str, ...] = (
    "SYS_BOARDID",
    "SYS_MODE",
    "SYS_MODELNAME_ID",
    "SYS_VERSION",
    "SYS_MODULE_TYPE",
    "SYS_MODULE_DETAIL",
    "SYS_PTZ_TYPE",
    "SYS_LINKDOWN_NUM",
    "SYS_RCV_VERSION",
    "SYS_TIMEFORMAT",
    "SYS_STARTTIME",
    "SYS_FTCAMERA_CDS",
    "SYS_AI_VERSION",
    "SYS_ZOOMMODULE",
    "SYS_PRODUCT_MODEL",
    "SYS_ONVIFVERSION",
    "SYS_OPENSSLVERSION",
    "SYS_CURRENTTIME",
)


# ----------------------------------------------------------------------
# Camera / module / hardware version
# ----------------------------------------------------------------------
READPARAM_CAMERA_VERSION_KEYS: tuple[str, ...] = (
    "CAM_READMODULEVERSION",
    "CAM_READMECAVERSION",
    "CAM_READPTZHWVERSION",
)


# ----------------------------------------------------------------------
# Video
# ----------------------------------------------------------------------
READPARAM_VIDEO_KEYS: tuple[str, ...] = (
    "VID_PREVIEWENABLE",
    "VID_OUTPUTFORMAT",
    "VID_INPUTFORMAT",
    "VID_RESOLUTION",
    "VID_FRAMERATE",
    "VID_PREFERENCE",
    "VID_QUALITY",
    "VID_BANDWIDTH",
    "VID_IINTERVAL",
    "VID_USEDUAL",
    "VID_DUALALGORITHM",
    "VID_DUALRESOLUTION",
    "VID_DUALFRAMERATE",
    "VID_DUALPREFERENCE",
    "VID_DUALQUALITY",
    "VID_DUALBANDWIDTH",
    "VID_DUALIINTERVAL",
)


# ----------------------------------------------------------------------
# Audio
# ----------------------------------------------------------------------
READPARAM_AUDIO_KEYS: tuple[str, ...] = (
    "AUD_ALGORITHM",
    "AUD_AUDIOMODE",
    "AUD_GAIN",
    "AUD_BITRATE",
)


# ----------------------------------------------------------------------
# Audio capability / project-used extension keys
# ----------------------------------------------------------------------
READPARAM_AUDIO_CAPABILITY_KEYS: tuple[str, ...] = (
    "AUD_ENABLE",
    "AUD_CODEC",
    "AUD_INPUTGAIN",
    "AUD_OUTPUTGAIN",
    "AUD_SAMPLERATE",
    "AUD_MUTE",
)


# ----------------------------------------------------------------------
# Storage
# ----------------------------------------------------------------------
READPARAM_STORAGE_KEYS: tuple[str, ...] = (
    "REC_DISKTYPE",
    "REC_DISKSIZE",
    "REC_DISKAVAILABLE",
)


# ----------------------------------------------------------------------
# Misc / serial / project-used additions
# ----------------------------------------------------------------------
READPARAM_PROJECT_EXTRA_KEYS: tuple[str, ...] = (
    "SER_BITRATE_2",
)


# ----------------------------------------------------------------------
# Test
# ----------------------------------------------------------------------
READPARAM_TEST_KEYS: tuple[str, ...] = (
    "TEST_Power_CheckString",
)


# ----------------------------------------------------------------------
# Device info summary keys
# ----------------------------------------------------------------------
DEVICE_INFO_KEYS: tuple[str, ...] = (
    "NET_MAC",
    "SYS_MODELNAME_ID",
    "SYS_VERSION",
    "SYS_MODE",
    "CAM_READMODULEVERSION",
    "CAM_READMECAVERSION",
    "SYS_LINKDOWN_NUM",
    "NET_LOCALIPMODE",
    "TEST_Power_CheckString",
    "SYS_STARTTIME",
    "REC_DISKTYPE",
    "REC_DISKSIZE",
    "REC_DISKAVAILABLE",
    "SYS_AI_VERSION",
    "SYS_RCV_VERSION",
)


# ----------------------------------------------------------------------
# Fast / slow partition for CamInfoReader
# ----------------------------------------------------------------------
DEVICE_INFO_FAST_KEYS: tuple[str, ...] = (
    "NET_MAC",
    "NET_LOCALIPMODE",

    "SYS_MODELNAME_ID",
    "SYS_VERSION",
    "SYS_MODE",
    "SYS_LINKDOWN_NUM",
    "SYS_RCV_VERSION",
    "SYS_STARTTIME",
    "SYS_AI_VERSION",

    "REC_DISKTYPE",
    "REC_DISKSIZE",
    "REC_DISKAVAILABLE",

    "SYS_BOARDID",
    "SYS_MODULE_TYPE",
    "SYS_MODULE_DETAIL",
    "SYS_PTZ_TYPE",
    "SYS_ZOOMMODULE",
    "SYS_PRODUCT_MODEL",

    "SER_BITRATE_2",
    "TEST_Power_CheckString",
)

DEVICE_INFO_SLOW_KEYS: tuple[str, ...] = (
    "CAM_READMECAVERSION",
    "CAM_READMODULEVERSION",
    "CAM_READPTZHWVERSION",
    "SYS_ONVIFVERSION",
    "SYS_OPENSSLVERSION",
    "SYS_CURRENTTIME",
)


# ----------------------------------------------------------------------
# CamStatusReader keys
# ----------------------------------------------------------------------
STATUS_READPARAM_KEYS: tuple[str, ...] = (
    "SYS_BOARDTEMP",
    "SYS_BOARD_TEMP",
    "ETC_BOARDTEMP",
    "CAM_HI_CURRENT_Y",
    "GIS_CDS",
    "GIS_CDS_CUR",
    "GIS_CDS_CURRENT",
    "SYS_CURRENTTIME",
    "GIS_RTC",
    "RTC_TIME",
    "SYS_FANSTATUS",
    "SYS_FAN_STATUS",
    "FAN_STATUS",
)

STATUS_RATE_KEYS: tuple[str, ...] = (
    "GRS_VENCFRAME1",
    "GRS_VENCBITRATE1",
    "GRS_VENCFRAME2",
    "GRS_VENCBITRATE2",
    "GRS_VENCFRAME3",
    "GRS_VENCBITRATE3",
    "GRS_VENCFRAME4",
    "GRS_VENCBITRATE4",
    "GRS_AENCBITRATE1",
    "GRS_ADECBITRATE1",
    "GRS_ADECALGORITHM1",
    "GRS_ADECSAMPLERATE1",
)

STATUS_INPUT_KEYS: tuple[str, ...] = (
    "GIS_SENSOR1",
    "GIS_SENSOR2",
    "GIS_SENSOR3",
    "GIS_SENSOR4",
    "GIS_SENSOR5",
    "GIS_MOTION1",
    "GIS_MOTION2",
    "GIS_MOTION3",
    "GIS_MOTION4",
    "GIS_VIDEOLOSS1",
    "GIS_VIDEOLOSS2",
    "GIS_VIDEOLOSS3",
    "GIS_VIDEOLOSS4",
    "GIS_ALARM1",
    "GIS_ALARM2",
    "GIS_ALARM3",
    "GIS_ALARM4",
    "GIS_RECORD1",
    "GIS_AIRWIPER",
)

STATUS_ETHTOOL_KEYS: tuple[str, ...] = (
    "ETHTOOL",
)


# ----------------------------------------------------------------------
# Full dump
# ----------------------------------------------------------------------
READPARAM_FULL_DUMP_KEYS: tuple[str, ...] = (
    READPARAM_NETWORK_KEYS
    + READPARAM_SYSTEM_KEYS
    + READPARAM_CAMERA_VERSION_KEYS
    + READPARAM_VIDEO_KEYS
    + READPARAM_AUDIO_KEYS
    + READPARAM_AUDIO_CAPABILITY_KEYS
    + READPARAM_STORAGE_KEYS
    + READPARAM_PROJECT_EXTRA_KEYS
    + READPARAM_TEST_KEYS
)