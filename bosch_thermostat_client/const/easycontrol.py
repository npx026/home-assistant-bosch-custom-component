from . import DHW, DHW_CIRCUITS, HEATING_CIRCUITS, ZONES, ZN, HC, SC, SOLAR_CIRCUITS

MAGIC_EASYCONTROL = bytearray.fromhex(
    "1d86b2631b02f2c7978b41e8a3ae609b0b2afbfd30ff386da60c586a827408e4"
)
EASYCONTROL = "EASYCONTROL"
PRODUCT_ID = "productID"
DEVICES = "devices"
DV = "dv"
CIRCUIT_TYPES = {DHW: DHW_CIRCUITS, ZN: ZONES, DV: DEVICES, HC: HEATING_CIRCUITS, SC: SOLAR_CIRCUITS}
TARGET_TEMP = "targettemp"
PROGRAM_LIST = "programList"
IDLE = "idle"
TRUE = "true"
FALSE = "false"
USED = "used"
BOOLEAN = "boolean"
ENERGY = "energy"
PAGINATION = "pagination"
STEP_SIZE = "stepSize"
LOW_BATTERY = "low battery"
