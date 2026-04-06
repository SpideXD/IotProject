"""
Configuration for YOLO training on synthetic Unity data.
"""
import os

# Paths
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYNTHETIC_DATA_ROOT = os.path.join(PROJECT_ROOT, "rpi_simulator", "synthetic_data")
SYNTHETIC_DATA_V2 = os.path.join(PROJECT_ROOT, "rpi_simulator", "synthetic_data_v2")
SYNTHETIC_DATA_MERGED = os.path.join(PROJECT_ROOT, "rpi_simulator", "synthetic_data_merged")
IMAGES_DIR = os.path.join(SYNTHETIC_DATA_ROOT, "images")
LABELS_DIR = os.path.join(SYNTHETIC_DATA_ROOT, "labels")
DATA_YAML = os.path.join(SYNTHETIC_DATA_MERGED, "dataset.yaml")
OUTPUT_DIR = os.path.join(SYNTHETIC_DATA_MERGED, "runs")
MODEL_PATH = os.path.join(SYNTHETIC_DATA_MERGED, "custom_yolo.pt")

# YOLO classes (must match Unity ground truth)
# These map to what Unity exports in labels
CLASS_NAMES = [
    "person",
    "bag",
    "chair",
    "book",
    "laptop",
    "cup",
    "phone",
    "backpack",
]

CLASS_TO_ID = {name: i for i, name in enumerate(CLASS_NAMES)}
NUM_CLASSES = len(CLASS_NAMES)

# Training settings
YOLO_MODEL = "yolov8n.pt"  # Base model to fine-tune
BATCH_SIZE = 8  # Small batch for 8GB RAM (M2 can handle this)
IMAGE_SIZE = 640  # YOLO input size
NUM_EPOCHS = 50  # Epochs per training run
PATIENCE = 15  # Early stopping patience (longer for larger datasets)

# Incremental training settings
MIN_NEW_IMAGES_TO_TRAIN = 20  # Wait until we have at least this many new images
TRAIN_EVERY_N_IMAGES = 50  # Retrain after every N new images accumulated
MAX_TRAINING_IMAGES = 500  # Max images in training set (oldest drop off)

# Monitoring
METRICS_LOG = os.path.join(OUTPUT_DIR, "metrics.log")
WATCH_INTERVAL = 5  # Seconds between checking for new images

# MQTT settings (for publishing detections when model is ready)
MQTT_BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_KEEPALIVE = 60

# YOLO confidence threshold
CONF_THRESHOLD = 0.35

# FSM (State Machine) Thresholds
# Number of consecutive scans needed to confirm a state
GHOST_SCAN_THRESHOLD = 3       # Scans of "bag" before confirmed ghost
OCCUPIED_SCAN_THRESHOLD = 2    # Scans of "person" before confirmed occupied
EMPTY_SCAN_THRESHOLD = 2       # Scans of "empty" before confirmed empty
SUSPECTED_GHOST_THRESHOLD = 2  # Additional scans before confirmed ghost

# Scan timing
SCAN_INTERVAL = 5.0           # Expected seconds between scans (for dwell time)

# Confidence Matrix (YOLO vs Ground Truth)
YOLO_AGREEMENT_BONUS = 0.15          # Bonus when YOLO matches GT
YOLO_DISAGREEMENT_PENALTY = 0.30     # Penalty when YOLO mismatches GT
YOLO_BASE_CONFIDENCE = 0.50          # Base confidence when no YOLO data
YOLO_MISS_CONFIDENCE = 0.20          # Confidence when YOLO missed detection
YOLO_FALSE_POSITIVE_CONFIDENCE = 0.15  # Confidence when YOLO false positive

# Zone/Seat layout (default - can be overridden by calibration)
DEFAULT_ZONE_SEATS = {
    "Z1": ["S1", "S2", "S3", "S4"],
    "Z2": ["S5", "S6", "S7", "S8"],
    "Z3": ["S9", "S10", "S11", "S12"],
    "Z4": ["S13", "S14", "S15", "S16"],
    "Z5": ["S17", "S18", "S19", "S20"],
    "Z6": ["S21", "S22", "S23", "S24"],
    "Z7": ["S25", "S26", "S27", "S28"],
}

# RPi edge forwarding
EDGE_PROCESSOR_URL = "http://localhost:5002"
RPI_DEFAULT_PORT = 5001

# Time-based FSM Parameters (for GhostDetector)
GHOST_GRACE_PERIOD = 30.0    # Seconds before suspected_ghost
GHOST_THRESHOLD = 120.0      # Seconds before confirmed_ghost
PRESENCE_THRESHOLD = 0.5     # Radar presence to consider occupied
MOTION_THRESHOLD = 0.3       # Motion to indicate active person
CAMERA_WEIGHT = 0.6          # Weight for camera in fusion
RADAR_WEIGHT = 0.4           # Weight for radar in fusion
AGREEMENT_BONUS = 0.1        # Bonus when camera and radar agree

# Build SEAT_TO_ZONE mapping
SEAT_TO_ZONE = {}
for zone, seats in DEFAULT_ZONE_SEATS.items():
    for seat in seats:
        SEAT_TO_ZONE[seat] = zone
