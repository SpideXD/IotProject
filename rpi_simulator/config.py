"""
Configuration for RPi Simulator (per-room processing node).
Raw camera images stay on this node; only seat occupancy is forwarded.
"""
import os

# HTTP server
RPI_HTTP_PORT = int(os.environ.get("RPI_HTTP_PORT", 5001))

# Central edge processor (receives occupancy data from all RPi simulators)
EDGE_PROCESSOR_URL = os.environ.get("EDGE_PROCESSOR_URL", "http://localhost:5002")

# Room identification
ROOM_ID = os.environ.get("ROOM_ID", "room_1")

# Delta compression - only send occupancy when it changes
SEND_DELTAS_ONLY = True

# Minimum confidence threshold for occupancy decisions
MIN_OCCUPANCY_CONFIDENCE = 0.35

# Zone to seat mapping (same as edge config)
ZONE_TO_SEATS = {
    "Z1": ["S1",  "S2",  "S3",  "S4"],
    "Z2": ["S5",  "S6",  "S7",  "S8"],
    "Z3": ["S9",  "S10", "S11", "S12"],
    "Z4": ["S13", "S14", "S15", "S16"],
    "Z5": ["S17", "S18", "S19", "S20"],
    "Z6": ["S21", "S22", "S23", "S24"],
    "Z7": ["S25", "S26", "S27", "S28"],
}

SEAT_TO_ZONE = {}
for _zone, _seats in ZONE_TO_SEATS.items():
    for _seat in _seats:
        SEAT_TO_ZONE[_seat] = _zone

TOTAL_SEATS = 28

# Camera sensor to zone mapping (rail sensors in Unity)
# Each rail sensor moves through multiple zones and reports detections per zone
# Rail_Back covers Z1-Z4, Rail_Front covers Z5-Z7
SENSOR_TO_ZONE = {
    "Rail_Back": "Z1",   # Back rail scans zones 1-4 sequentially
    "Rail_Front": "Z5",  # Front rail scans zones 5-7 sequentially
}

# YOLO model (local inference - not sent to edge)
# Trained model path - yolov8s fine-tuned on Unity synthetic data
YOLO_MODEL_PATH = os.environ.get(
    "YOLO_MODEL_PATH",
    "/Users/agentswarm/Desktop/IotProject/rpi_simulator/models/yolov8s_trained.pt"
)
YOLO_CONFIDENCE = 0.35
YOLO_IOU_THRESHOLD = 0.45
YOLO_IMAGE_SIZE = 640

# Frame skip - skip frames when no motion detected
FRAME_SKIP_THRESHOLD = 0.1

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
AUDIT_LOG_PATH = os.environ.get("AUDIT_LOG_PATH", "occupancy_audit.json")

# Bandwidth optimization - hash state before sending
USE_STATE_HASHING = True

# ============================================================
# Sensor Fusion (moved from edge processor)
# Camera weight: 60%, Radar weight: 40%
# ============================================================
CAMERA_WEIGHT = 0.6
RADAR_WEIGHT = 0.4
AGREEMENT_BONUS = 0.10
PRESENCE_THRESHOLD = 0.6
MOTION_THRESHOLD = 0.15

# ============================================================
# Ghost Detection FSM (runs locally on RPi)
# ============================================================
GHOST_GRACE_PERIOD = 120    # seconds before suspecting ghost
GHOST_THRESHOLD = 300       # seconds before confirming ghost
