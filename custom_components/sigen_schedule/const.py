"""Constants for the Sigenergy Schedule integration."""

DOMAIN = "sigen_schedule"

CONF_REGION = "region"
CONF_STATION_ID = "station_id"

# Australia/NZ is `aus` and is a SEPARATE shard from `apac`. Getting this wrong
# returns "authentication failed" rather than anything region-specific.
REGION_BASE_URLS = {
    "eu": "https://api-eu.sigencloud.com/",
    "aus": "https://api-aus.sigencloud.com/",
    "apac": "https://api-apac.sigencloud.com/",
    "us": "https://api-us.sigencloud.com/",
    "jp": "https://api-jp.sigencloud.com/",
    "cn": "https://api-cn.sigencloud.com/",
}

REGION_LABELS = {
    "aus": "Australia & New Zealand",
    "eu": "Europe",
    "apac": "Asia Pacific",
    "us": "United States",
    "jp": "Japan",
    "cn": "Chinese Mainland",
}

# The cloud API throttles aggressively (roughly 1 request per endpoint per
# 5 minutes). Poll well inside that.
UPDATE_INTERVAL_SECONDS = 300

# Endpoints
EP_STATION_HOME = "device/owner/station/home"
EP_SCHEDULE_GET = "device/dischargesetting/{station_id}"
EP_SCHEDULE_SAVE = "device/dischargesetting/batch/save"

# dischargeType -> what the window does
DISCHARGE_TYPES = {
    0: "Charging",
    1: "Discharging",
    3: "Self-consumption",
}

# Every field the app sends per period. Anything omitted or null means
# "system default".
PERIOD_FIELDS = (
    "currType",
    "dischargeType",
    "startTime",
    "endTime",
    "stationId",
    "whichDay",
    "maxBuyPower",
    "maxSellPower",
    "maxChargePower",
    "maxDischargePower",
    "maxPackChargePower",
    "maxPackDischargePower",
    "gridChargeCutOffSoc",
    "gridDischargeCutOffSoc",
)

UNIT_KW = "kW"
UNIT_PCT = "%"

# Editable numeric fields, and which window types they are offered for.
#
# `maxChargePower` is the only mapping confirmed against the UI (it is the
# "Maximum Charging Power from Grid to BAT" box - captured as 10 with the UI
# showing 10 kW). The others are named from the API field, since the UI labels
# could not be matched one-to-one with certainty.
NUMBER_FIELDS = {
    "maxChargePower": {
        "name": "Max charge power (grid to battery)",
        "unit": UNIT_KW,
        "min": 0.0,
        "max": 100.0,
        "step": 0.1,
        "types": (0,),
    },
    "maxPackChargePower": {
        "name": "Max battery charge power",
        "unit": UNIT_KW,
        "min": 0.0,
        "max": 100.0,
        "step": 0.1,
        "types": (0, 3),
    },
    "maxBuyPower": {
        "name": "Max grid import power",
        "unit": UNIT_KW,
        "min": 0.0,
        "max": 100.0,
        "step": 0.1,
        "types": (0, 3),
    },
    "gridChargeCutOffSoc": {
        "name": "Grid charging cut-off SOC",
        "unit": UNIT_PCT,
        "min": 0.0,
        "max": 100.0,
        "step": 1.0,
        "types": (0,),
    },
    "maxDischargePower": {
        "name": "Max discharge power (battery to grid)",
        "unit": UNIT_KW,
        "min": 0.0,
        "max": 100.0,
        "step": 0.1,
        "types": (1,),
    },
    "maxPackDischargePower": {
        "name": "Max battery discharge power",
        "unit": UNIT_KW,
        "min": 0.0,
        "max": 100.0,
        "step": 0.1,
        "types": (1, 3),
    },
    "maxSellPower": {
        "name": "Max grid export power",
        "unit": UNIT_KW,
        "min": 0.0,
        "max": 100.0,
        "step": 0.1,
        "types": (1, 3),
    },
    "gridDischargeCutOffSoc": {
        "name": "Grid discharging cut-off SOC",
        "unit": UNIT_PCT,
        "min": 0.0,
        "max": 100.0,
        "step": 1.0,
        "types": (1,),
    },
}
