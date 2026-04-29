from __future__ import annotations


DISPLAY_NAME_MAP: dict[str, str] = {
    # ------------------------------------------------------------------
    # Network
    # ------------------------------------------------------------------
    "NET_RTSPPORT": "RTSP Port",
    "NET_MAC": "MAC Address",
    "NET_LOCALIPMODE": "Local IP Mode",
    "NET_LINKSTATE": "Link State",
    "NET_LINK_STATE": "Link State",
    "NET_LINKSPEED": "Link Speed",
    "NET_LINK_SPEED": "Link Speed",
    "NET_EXTRA_ID": "Extra ID",

    # ------------------------------------------------------------------
    # System
    # ------------------------------------------------------------------
    "SYS_BOARDID": "Board ID",
    "SYS_MODE": "Type",
    "SYS_MODELNAME": "Model",
    "SYS_MODELNAME2": "Model",
    "SYS_VERSION": "Firmware",
    "SYS_MODULE_TYPE": "Module Type",
    "SYS_MODULE_DETAIL": "Module Detail",
    "SYS_PRODUCT_MODEL": "Product Model",
    "SYS_LINKDOWN_NUM": "LD",
    "SYS_RCV_VERSION": "RCV Version",
    "SYS_TIMEFORMAT": "Time Display Format",
    "SYS_STARTTIME": "System Booting Time",
    "SYS_FTCAMERA_CDS": "CDS",
    "SYS_AI_VERSION": "AI Version",
    "SYS_ZOOMMODULE": "Zoom Module",
    "SYS_ONVIFVERSION": "ONVIF Version",
    "SYS_OPENSSLVERSION": "OpenSSL Version",
    "SYS_CURRENTTIME": "Current Time",
    "SYS_REBOOT": "Reboot",
    "SYS_RESET_V2": "Reset",
    "SYS_BOARDTEMP": "Board Temp",
    "SYS_BOARD_TEMP": "Board Temp",
    "SYS_ETHERNET": "Ethernet",
    "SYS_FANSTATUS": "Fan Status",
    "SYS_FAN_STATUS": "Fan Status",

    # ------------------------------------------------------------------
    # Camera / PTZ
    # ------------------------------------------------------------------
    "CAM_READMODULEVERSION": "Module Version",
    "CAM_READMECAVERSION": "PTZ F/W",
    "CAM_READPTZHWVERSION": "PTZ H/W Version",
    "CAM_HI_CURRENT_Y": "CDS / Current Y",
    "CAM_HI_TDN_MODE": "TDN",
    "CAM_HI_TDN_FILTER": "ICR",

    # ------------------------------------------------------------------
    # Video
    # ------------------------------------------------------------------
    "VID_PREVIEWENABLE": "Preview Enable",
    "VID_OUTPUTFORMAT": "Output Format",
    "VID_INPUTFORMAT": "Input Format",
    "VID_RESOLUTION": "Resolution",
    "VID_FRAMERATE": "Frame Rate",
    "VID_PREFERENCE": "Video Preference",
    "VID_QUALITY": "Video Quality",
    "VID_BANDWIDTH": "Bandwidth",
    "VID_IINTERVAL": "I-Frame Interval",
    "VID_USEDUAL": "Dual Stream Use",
    "VID_DUALALGORITHM": "Dual Stream Algorithm",
    "VID_DUALRESOLUTION": "Dual Stream Resolution",
    "VID_DUALFRAMERATE": "Dual Stream Frame Rate",
    "VID_DUALPREFERENCE": "Dual Stream Preference",
    "VID_DUALQUALITY": "Dual Stream Quality",
    "VID_DUALBANDWIDTH": "Dual Stream Bandwidth",
    "VID_DUALIINTERVAL": "Dual Stream I-Frame Interval",

    # ------------------------------------------------------------------
    # Audio
    # ------------------------------------------------------------------
    "AUD_ENABLE": "Audio Enable",
    "AUD_CODEC": "Audio Codec",
    "AUD_ALGORITHM": "Audio Algorithm",
    "AUD_AUDIOMODE": "Audio Mode",
    "AUD_GAIN": "Audio Gain",
    "AUD_INPUTGAIN": "Audio Input Gain",
    "AUD_OUTPUTGAIN": "Audio Output Gain",
    "AUD_SAMPLERATE": "Audio Sample Rate",
    "AUD_BITRATE": "Audio Bit Rate",
    "AUD_MUTE": "Audio Mute",

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------
    "REC_DISKTYPE": "SD / USB",
    "REC_DISKSIZE": "Disk Size",
    "REC_DISKAVAILABLE": "Disk Available",

    # ------------------------------------------------------------------
    # Serial / Test
    # ------------------------------------------------------------------
    "SER_PROTOCOL_1": "Serial Protocol 1",
    "SER_BITRATE_2": "Serial Bitrate 2",
    "TEST_Power_CheckString": "Power Type",
    "TEST_WRITE": "Test Write",
    "ETC_MIN_PASSWORD_LEN": "Minimum Password Length",

    # ------------------------------------------------------------------
    # Status / CDS / RTC / Fan / Temp
    # ------------------------------------------------------------------
    "ETC_BOARDTEMP": "Board Temp",
    "GIS_CDS": "CDS",
    "GIS_CDS_CUR": "CDS Current",
    "GIS_CDS_CURRENT": "CDS Current",
    "GIS_RTC": "RTC Time",
    "RTC_TIME": "RTC Time",
    "FAN_STATUS": "Fan Status",
    "ETHTOOL": "Ethernet Speed Raw",

    # ------------------------------------------------------------------
    # Rate
    # ------------------------------------------------------------------
    "GRS_VENCFRAME1": "Video1 FPS",
    "GRS_VENCBITRATE1": "Video1 Bitrate",
    "GRS_VENCFRAME2": "Video2 FPS",
    "GRS_VENCBITRATE2": "Video2 Bitrate",
    "GRS_VENCFRAME3": "Video3 FPS",
    "GRS_VENCBITRATE3": "Video3 Bitrate",
    "GRS_VENCFRAME4": "Video4 FPS",
    "GRS_VENCBITRATE4": "Video4 Bitrate",
    "GRS_AENCBITRATE1": "Audio Encode Bitrate",
    "GRS_ADECBITRATE1": "Audio Decode Bitrate",
    "GRS_ADECALGORITHM1": "Audio Decode Algorithm",
    "GRS_ADECSAMPLERATE1": "Audio Decode Sample Rate",

    # ------------------------------------------------------------------
    # Input / Alarm
    # ------------------------------------------------------------------
    "GIS_SENSOR1": "Sensor 1",
    "GIS_SENSOR2": "Sensor 2",
    "GIS_SENSOR3": "Sensor 3",
    "GIS_SENSOR4": "Sensor 4",
    "GIS_SENSOR5": "Sensor 5",
    "GIS_MOTION1": "Motion 1",
    "GIS_MOTION2": "Motion 2",
    "GIS_MOTION3": "Motion 3",
    "GIS_MOTION4": "Motion 4",
    "GIS_VIDEOLOSS1": "Video Loss 1",
    "GIS_VIDEOLOSS2": "Video Loss 2",
    "GIS_VIDEOLOSS3": "Video Loss 3",
    "GIS_VIDEOLOSS4": "Video Loss 4",
    "GIS_ALARM1": "Alarm 1",
    "GIS_ALARM2": "Alarm 2",
    "GIS_ALARM3": "Alarm 3",
    "GIS_ALARM4": "Alarm 4",
    "GIS_RECORD1": "Record 1",
    "GIS_AIRWIPER": "Air Wiper",

    # ------------------------------------------------------------------
    # UI-only synthesized labels
    # ------------------------------------------------------------------
    "BOARDID_HEX": "Board ID",
    "CDS": "CDS",
    "CURRENT_Y": "Current Y",
    "RATE1": "Primary",
    "RATE2": "Secondary",
    "RATE3": "Video3 Rate",
    "RATE4": "Video4 Rate",
    "RTC": "RTC Time",
    "ETHERNET": "Ethernet",
    "TEMP": "Board Temp",
    "FAN": "Fan Status",
}


def display_name(key: str) -> str:
    return DISPLAY_NAME_MAP.get(str(key), str(key))