
MQTT_BROKER_HOST = "localhost"
MQTT_BROKER_PORT = 1883
MQTT_CLIENT_ID = "liberty_twin_edge"
MQTT_KEEPALIVE = 60

MQTT_TOPIC_SENSOR = "liberty_twin/sensor/#"
MQTT_TOPIC_STATE_SEAT = "liberty_twin/state/seat/{seat_id}"
MQTT_TOPIC_ALERTS_GHOST = "liberty_twin/alerts/ghost"

INFLUXDB_URL = "http://localhost:8086"
INFLUXDB_TOKEN = "liberty-twin-token"
INFLUXDB_ORG = "liberty-twin"
INFLUXDB_BUCKET = "iot_data"

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

HTTP_FALLBACK_PORT = 5002

LOG_LEVEL = "INFO"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

HEATMAP_UPDATE_INTERVAL = 5

GHOST_GRACE_PERIOD = 30.0
GHOST_THRESHOLD = 120.0
PRESENCE_THRESHOLD = 0.5
MOTION_THRESHOLD = 0.3
CAMERA_WEIGHT = 0.6
RADAR_WEIGHT = 0.4
AGREEMENT_BONUS = 0.1
