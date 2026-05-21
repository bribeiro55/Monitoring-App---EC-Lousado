import os


APP_ROOT = os.path.dirname(os.path.abspath(__file__))
#PROJECT_ROOT = r"Z:\prstruh\ctend_pt"
PROJECT_ROOT = os.path.join(APP_ROOT, "logs")  


MACHINES = ["Machine 7900", "Machine 7950", "Machine 7960"]
POSITION_LABELS = {1: "Position 1", 2: "Position 2"}

MACHINE_BADGE = {"Machine 7900": "7900", "Machine 7950": "7950", "Machine 7960": "7960"}

DISPLAY_TO_MACHINE_ID = {
    "Machine 7900": "M7900",
    "Machine 7950": "M7950",
    "Machine 7960": "M7960",
}
MACHINE_ID_TO_LABEL = {v: k for k, v in DISPLAY_TO_MACHINE_ID.items()}

OTHER_PLACEMENT_LINE_COLOR = "#8B93A8"

POS_COLORS = {
    1: "#F0BA20",
    2: "#E8721A",
}

VARIABLE_CONFIG = {
    "temperature": {"col": "cpc_temp_c", "label": "Temperature", "unit": "°C"},
    "load": {"col": "load_kg", "label": "Load", "unit": "kg"},
    "inflation_pressure": {"col": "inflation_pressure_kpa", "label": "Inflation Pressure", "unit": "kPa"},
    "room_temperature": {"col": "room_temp_c", "label": "Room Temperature", "unit": "°C"},
    "speed": {"col": "speed", "label": "Speed", "unit": "km/h"},
    "torque": {"col": "torque_nm", "label": "Torque", "unit": "Nm"},
}

STORE_COLUMNS = [
    "timestamp",
    "machine_id",
    "position",
    "step",
    "speed",
    "torque_nm",
    "machine_running",
    "cpc_temp_c",
    "load_kg",
    "inflation_pressure_kpa",
    "room_temp_c",
    "thermo_cam_1",
    "thermo_cam_2",
    "thermo_cam_3",
    "thermo_cam_4",
    "thermo_cam_5",
]

STEP_COLORS = {
    1: "rgba(240,186,32,0.08)",
    2: "rgba(232,114,26,0.08)",
    3: "rgba(80,160,220,0.08)",
    4: "rgba(100,200,140,0.08)",
    5: "rgba(200,100,180,0.08)",
    6: "rgba(160,120,80,0.08)",
    7: "rgba(120,180,60,0.08)",
    8: "rgba(220,80,80,0.08)",
    9: "rgba(80,200,200,0.08)",
}

STEP_BORDER_COLORS = {
    1: "rgba(240,186,32,0.45)",
    2: "rgba(232,114,26,0.45)",
    3: "rgba(80,160,220,0.45)",
    4: "rgba(100,200,140,0.45)",
    5: "rgba(200,100,180,0.45)",
    6: "rgba(160,120,80,0.45)",
    7: "rgba(120,180,60,0.45)",
    8: "rgba(220,80,80,0.45)",
    9: "rgba(80,200,200,0.45)",
}
