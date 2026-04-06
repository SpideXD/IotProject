#!/usr/bin/env python3
"""
Edge Processor - Central hub that receives occupancy data from RPi simulators.

Receives pre-computed seat occupancy from per-room RPi simulators.
Performs cross-room ghost detection, sensor fusion, and forwards to dashboard.
No raw camera images ever arrive here (privacy preserved).

Features:
- Ghost detection FSM with 4 states (empty → occupied → suspected_ghost → confirmed_ghost)
- Sensor fusion (camera + radar with 60/40 weighting + agreement bonus)
- Multi-room correlation for cross-room ghost detection
- MQTT publishing to dashboard with HTTP fallback
- InfluxDB batch writes for historical data
- Alert batching to reduce noise
- State deduplication via hash comparison
- API rate limiting for protection
- Request ID tracking for distributed tracing
- Seat reservation system
- Prometheus-style metrics with enhanced details
- Health/readiness endpoints for Kubernetes
"""
import hashlib
import os
import json
import logging
import signal
import sys
import threading
import time
import uuid
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from collections import defaultdict
from functools import wraps
import queue

import requests

from config import (
    MQTT_BROKER_HOST,
    MQTT_BROKER_PORT,
    MQTT_CLIENT_ID,
    MQTT_KEEPALIVE,
    MQTT_TOPIC_SENSOR,
    MQTT_TOPIC_STATE_SEAT,
    MQTT_TOPIC_ALERTS_GHOST,
    INFLUXDB_URL,
    INFLUXDB_TOKEN,
    INFLUXDB_ORG,
    INFLUXDB_BUCKET,
    SEAT_TO_ZONE,
    HTTP_FALLBACK_PORT,
    LOG_LEVEL,
    LOG_FORMAT,
    TOTAL_SEATS,
    ZONE_TO_SEATS,
)

from sensor_fusion import SensorFusion, CameraResult, RadarResult, FusedResult
from ghost_detector import GhostDetector, GhostAlert

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format=LOG_FORMAT)
logger = logging.getLogger("edge_processor")

# =============================================================================
# Global State
# =============================================================================

mqtt_client = None
influx_client = None
influx_write_api = None

# Track RPi sources
_rpi_sources: Dict[str, dict] = {}

# Ghost detector and sensor fusion
fusion = SensorFusion()
ghost_detector = GhostDetector()

# Dashboard HTTP URL
HTTP_DASHBOARD_URL = os.environ.get("HTTP_DASHBOARD_URL", "http://localhost:5000/api/seat_state")

# Stats - using list instead of set for JSON serialization
_stats = {
    "occupancy_count": 0,
    "telemetry_count": 0,
    "ghost_alerts": 0,
    "mqtt_publishes": 0,
    "influx_writes": 0,
    "http_fallbacks": 0,
    "rpi_sources": [],  # List, not set (JSON serializable)
    "alerts_batched": 0,
    "alerts_sent": 0,
    "duplicates_skipped": 0,
    "rate_limited": 0,
    "request_errors": 0,
}

# State deduplication
_last_state_hash: str = ""
_state_hash_lock = threading.Lock()

# Alert batching
_alert_batch: List[GhostAlert] = []
_alert_batch_lock = threading.Lock()
_ALERT_BATCH_SIZE = 5
_ALERT_BATCH_TIMEOUT = 2.0  # seconds

# InfluxDB batch buffer
_influx_batch: List = []
_influx_batch_lock = threading.Lock()
_INFLUX_BATCH_SIZE = 20
_INFLUX_BATCH_TIMEOUT = 5.0  # seconds

# Last flush times
_last_alert_flush = time.time()
_last_influx_flush = time.time()

# =============================================================================
# Rate Limiting
# =============================================================================

_RATE_LIMIT_WINDOW = 60.0  # 1 minute window
_RATE_LIMIT_MAX_REQUESTS = 1000  # per window
_rate_limit_storage: Dict[str, List[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()


def check_rate_limit(client_id: str = "default") -> bool:
    """Check if request is within rate limit. Returns True if allowed."""
    now = time.time()
    with _rate_limit_lock:
        # Clean old entries
        _rate_limit_storage[client_id] = [
            t for t in _rate_limit_storage[client_id] if now - t < _RATE_LIMIT_WINDOW
        ]

        if len(_rate_limit_storage[client_id]) >= _RATE_LIMIT_MAX_REQUESTS:
            _stats["rate_limited"] += 1
            return False

        _rate_limit_storage[client_id].append(now)
        return True


def rate_limit(client_id: str = "default"):
    """Decorator for rate limiting endpoints."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not check_rate_limit(client_id):
                return {"error": "rate_limit_exceeded", "retry_after": _RATE_LIMIT_WINDOW}, 429
            return func(*args, **kwargs)
        return wrapper
    return decorator

# =============================================================================
# Request ID Tracking
# =============================================================================

_request_lock = threading.Lock()
_request_timestamps: Dict[str, float] = {}
_MAX_REQUEST_AGE = 300  # 5 minutes


def generate_request_id() -> str:
    """Generate a unique request ID for distributed tracing."""
    return str(uuid.uuid4())[:16]


def get_request_id(request) -> str:
    """Extract request ID from request headers or generate new one."""
    return request.headers.get("X-Request-ID", generate_request_id())


def log_with_request_id(request_id: str, message: str, level: int = logging.INFO):
    """Log with request ID for tracing."""
    logger.log(level, f"[{request_id}] {message}")


# =============================================================================
# Seat Reservation System
# =============================================================================

_reservations: Dict[str, dict] = {}  # seat_id -> {user_id, expires_at, created_at}
_reservation_lock = threading.Lock()
_RESERVATION_TTL = 900  # 15 minutes default
_RESERVATION_MAX_PER_USER = 2


def create_reservation(seat_id: str, user_id: str, ttl: int = None) -> dict:
    """Create a seat reservation."""
    global _reservations

    if ttl is None:
        ttl = _RESERVATION_TTL

    now = time.time()

    with _reservation_lock:
        # Check if seat already reserved
        if seat_id in _reservations:
            res = _reservations[seat_id]
            if res["expires_at"] > now:
                if res["user_id"] == user_id:
                    # Extend reservation
                    res["expires_at"] = now + ttl
                    return {"status": "extended", "seat_id": seat_id, "expires_at": res["expires_at"]}
                return {"status": "error", "message": "Seat already reserved by another user"}

        # Check user reservation limit
        user_reservations = [sid for sid, r in _reservations.items()
                           if r["user_id"] == user_id and r["expires_at"] > now]
        if len(user_reservations) >= _RESERVATION_MAX_PER_USER:
            return {"status": "error", "message": f"Maximum {_RESERVATION_MAX_PER_USER} reservations per user"}

        # Create reservation
        _reservations[seat_id] = {
            "user_id": user_id,
            "expires_at": now + ttl,
            "created_at": now,
        }

        return {"status": "created", "seat_id": seat_id, "expires_at": now + ttl}


def release_reservation(seat_id: str, user_id: str) -> dict:
    """Release a seat reservation."""
    with _reservation_lock:
        if seat_id not in _reservations:
            return {"status": "error", "message": "No reservation found"}

        res = _reservations[seat_id]
        if res["user_id"] != user_id:
            return {"status": "error", "message": "Reservation belongs to another user"}

        del _reservations[seat_id]
        return {"status": "released", "seat_id": seat_id}


def get_reservation(seat_id: str) -> Optional[dict]:
    """Get reservation if exists and valid."""
    with _reservation_lock:
        res = _reservations.get(seat_id)
        if res and res["expires_at"] > time.time():
            return res
        return None


def get_user_reservations(user_id: str) -> List[dict]:
    """Get all active reservations for a user."""
    now = time.time()
    with _reservation_lock:
        return [
            {"seat_id": sid, **r}
            for sid, r in _reservations.items()
            if r["user_id"] == user_id and r["expires_at"] > now
        ]


def cleanup_expired_reservations():
    """Remove expired reservations."""
    now = time.time()
    with _reservation_lock:
        expired = [sid for sid, r in _reservations.items() if r["expires_at"] <= now]
        for sid in expired:
            del _reservations[sid]
    return len(expired)


# =============================================================================
# Multi-Room Correlation
# =============================================================================

# Track patterns across rooms for cross-room ghost detection
_room_patterns: Dict[str, dict] = {}  # room_id -> {last_pattern, seat_patterns}
_room_correlation_lock = threading.Lock()


def update_room_pattern(room_id: str, seats_data: dict):
    """Update pattern tracking for cross-room correlation."""
    with _room_correlation_lock:
        # Count seat states in this room
        state_counts = {"empty": 0, "occupied": 0, "suspected_ghost": 0, "confirmed_ghost": 0}
        for seat_info in seats_data.values():
            state = seat_info.get("state", "empty")
            if state in state_counts:
                state_counts[state] += 1

        # Store pattern
        _room_patterns[room_id] = {
            "timestamp": time.time(),
            "state_counts": state_counts,
            "seats_data": seats_data,
        }


def detect_cross_room_ghosts(current_room_id: str, seat_id: str, current_state: str) -> Optional[dict]:
    """
    Detect if a ghost pattern exists across multiple rooms.
    If same seat in multiple rooms shows ghost state, it's likely a false positive.
    """
    with _room_correlation_lock:
        if len(_room_patterns) < 2:
            return None

        # Find same seat ID in other rooms
        cross_room_matches = []
        for room_id, pattern in _room_patterns.items():
            if room_id == current_room_id:
                continue
            seats_data = pattern.get("seats_data", {})
            if seat_id in seats_data:
                other_state = seats_data[seat_id].get("state", "empty")
                if other_state == current_state:
                    cross_room_matches.append({
                        "room_id": room_id,
                        "state": other_state,
                        "age": time.time() - pattern["timestamp"],
                    })

        if len(cross_room_matches) >= 2:  # Same pattern in 2+ rooms
            return {
                "type": "cross_room_correlation",
                "seat_id": seat_id,
                "current_room": current_room_id,
                "matching_rooms": len(cross_room_matches) + 1,
                "pattern": current_state,
            }

        return None


# =============================================================================
# HTTP Connection Pooling
# =============================================================================

_http_session = None
_http_pool_lock = threading.Lock()


def get_http_session() -> requests.Session:
    """Get or create HTTP session with connection pooling."""
    global _http_session
    if _http_session is None:
        with _http_pool_lock:
            if _http_session is None:
                _http_session = requests.Session()
                adapter = requests.adapters.HTTPAdapter(
                    pool_connections=10,
                    pool_maxsize=20,
                    max_retries=0,
                )
                _http_session.mount("http://", adapter)
                _http_session.mount("https://", adapter)
    return _http_session


# =============================================================================
# Enhanced Error Recovery
# =============================================================================

_mqtt_reconnect_delay = 1.0
_mqtt_max_reconnect_delay = 30.0


def _should_reconnect_mqtt() -> bool:
    """Check if MQTT should attempt reconnection."""
    if mqtt_client is None:
        return True
    if not hasattr(mqtt_client, 'is_connected'):
        return True
    return not mqtt_client.is_connected()


def _attempt_mqtt_reconnect():
    """Attempt MQTT reconnection with exponential backoff."""
    global _mqtt_reconnect_delay

    if not _should_reconnect_mqtt():
        return False

    try:
        if mqtt_client:
            mqtt_client.reconnect()
            _mqtt_reconnect_delay = 1.0  # Reset on success
            return True
    except Exception as exc:
        logger.warning("MQTT reconnect failed: %s", exc)
        _mqtt_reconnect_delay = min(_mqtt_reconnect_delay * 2, _mqtt_max_reconnect_delay)

    return False


# Schedule periodic MQTT reconnection attempts
def _mqtt_reconnect_worker():
    """Background worker for MQTT reconnection."""
    while True:
        time.sleep(_mqtt_reconnect_delay)
        if _should_reconnect_mqtt():
            _attempt_mqtt_reconnect()


_mqtt_reconnect_thread = None


def _start_mqtt_reconnect_worker():
    global _mqtt_reconnect_thread
    _mqtt_reconnect_thread = threading.Thread(target=_mqtt_reconnect_worker, daemon=True)
    _mqtt_reconnect_thread.start()

# =============================================================================
# Initialization
# =============================================================================

def _init_mqtt() -> bool:
    global mqtt_client
    try:
        import paho.mqtt.client as paho_mqtt

        def on_connect(client, userdata, flags, reason_code, properties=None):
            global _mqtt_reconnect_delay
            if reason_code == 0 or str(reason_code) == "Success":
                logger.info("MQTT connected to %s:%s", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
                # Subscribe to sensor topics AND occupancy topics
                client.subscribe(MQTT_TOPIC_SENSOR)  # liberty_twin/sensor/#
                client.subscribe("liberty_twin/sensor/+/occupancy")  # occupancy from RPis
                client.subscribe("liberty_twin/state/#")  # state updates
                logger.info("Subscribed to MQTT topics")
                _mqtt_reconnect_delay = 1.0  # Reset backoff on successful connection
            else:
                logger.warning("MQTT connection refused: %s", reason_code)

        def on_disconnect(client, userdata, flags, reason_code, properties=None):
            global _mqtt_reconnect_delay
            logger.warning("MQTT disconnected (rc=%s). Will retry with backoff.", reason_code)
            _mqtt_reconnect_delay = 1.0  # Reset on disconnect

        def on_message(client, userdata, msg):
            _handle_mqtt_message(msg.topic, msg.payload)

        client = paho_mqtt.Client(
            client_id=MQTT_CLIENT_ID,
            callback_api_version=paho_mqtt.CallbackAPIVersion.VERSION2,
        )
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message
        client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_KEEPALIVE)
        client.loop_start()
        mqtt_client = client
        _start_mqtt_reconnect_worker()  # Start background reconnection worker
        return True
    except ImportError:
        logger.warning("paho-mqtt not installed. MQTT disabled; using HTTP fallback only.")
        return False
    except Exception as exc:
        logger.warning("Cannot connect to MQTT broker at %s:%s (%s). Using HTTP fallback.",
                        MQTT_BROKER_HOST, MQTT_BROKER_PORT, exc)
        return False


def _init_influxdb() -> bool:
    global influx_client, influx_write_api
    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import BATCHING

        influx_client = InfluxDBClient(
            url=INFLUXDB_URL,
            token=INFLUXDB_TOKEN,
            org=INFLUXDB_ORG,
        )
        health = influx_client.health()
        if health.status != "pass":
            logger.warning("InfluxDB health check did not pass: %s", health.message)

        # Use batching writes instead of synchronous
        influx_write_api = influx_client.write_api(
            write_options=BATCHING,
            success_callback=_on_influx_write_success,
            error_callback=_on_influx_write_error,
        )
        logger.info("InfluxDB connected at %s (org=%s, bucket=%s, batching enabled)",
                     INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET)
        return True
    except ImportError:
        logger.warning("influxdb-client not installed. InfluxDB writes disabled.")
        return False
    except Exception as exc:
        logger.warning("Cannot connect to InfluxDB at %s (%s). Writes disabled.",
                        INFLUXDB_URL, exc)
        return False


def _on_influx_write_success(self, bucket: str, success: list):
    logger.debug("InfluxDB wrote %d points to %s", len(success), bucket)


def _on_influx_write_error(self, bucket: str, failure: list):
    for point in failure:
        logger.warning("InfluxDB write failed for point: %s", point)


# =============================================================================
# Core Processing
# =============================================================================

def process_occupancy(data: dict, request_id: str = None):
    """
    Process pre-computed seat occupancy from an RPi simulator.

    Expected data format:
    {
        "source": "rpi_simulator",
        "room_id": "room_1",
        "timestamp": 1743187200.123,
        "seats": {
            "S1": {"zone_id": "Z1", "is_occupied": true, "object_type": "person",
                   "confidence": 0.95, "has_motion": true, "radar_presence": 0.8, ...},
            ...
        }
    }
    """
    global _last_state_hash

    _stats["occupancy_count"] += 1

    source = data.get("source", "unknown")
    room_id = data.get("room_id", "unknown")
    timestamp = data.get("timestamp", time.time())
    seats_data = data.get("seats", {})

    rid = request_id or generate_request_id()

    # Track RPi source
    if room_id not in _stats["rpi_sources"]:
        _stats["rpi_sources"].append(room_id)

    _rpi_sources[room_id] = {
        "last_seen": timestamp,
        "seats_reporting": len(seats_data),
    }

    logger.info(
        "[%s] Occupancy #%d from %s (%s), %d seats",
        rid,
        _stats["occupancy_count"],
        source,
        room_id,
        len(seats_data),
    )

    # Update room pattern for cross-room correlation
    update_room_pattern(room_id, seats_data)

    alerts: List[GhostAlert] = []
    state_updates: Dict[str, dict] = {}

    for seat_id, info in seats_data.items():
        # Build CameraResult from RPi's processed data
        obj_type = info.get("object_type", "empty")
        conf = float(info.get("confidence", 0.0))
        cam = CameraResult(
            object_type=obj_type if conf > 0 else "empty",
            confidence=conf,
        )

        # Build RadarResult from RPi's enriched data
        radar = RadarResult(
            presence=float(info.get("radar_presence", 0.0)),
            motion=float(info.get("radar_motion", 0.0)),
            micro_motion=bool(info.get("has_motion", False)),
        )

        # Fuse camera and radar
        fused = fusion.fuse(camera_result=cam, radar_result=radar)

        # Update ghost detector for cross-room ghost detection
        alert = ghost_detector.update(seat_id, fused)

        # Check for cross-room correlation
        seat_state = ghost_detector.get_state(seat_id).value
        if seat_state in ("suspected_ghost", "confirmed_ghost"):
            correlation = detect_cross_room_ghosts(room_id, seat_id, seat_state)
            if correlation:
                logger.info("[%s] Cross-room correlation detected: %s", rid, correlation)

        if alert is not None:
            alerts.append(alert)

        zone_id = info.get("zone_id", SEAT_TO_ZONE.get(seat_id, ""))

        state_updates[seat_id] = {
            "seat_id": seat_id,
            "zone_id": zone_id,
            "state": seat_state,
            "occupancy_score": fused.occupancy_score,
            "object_type": fused.object_type,
            "confidence": fused.confidence,
            "is_present": fused.is_present,
            "has_motion": fused.has_motion,
            "radar_presence": fused.radar_presence,
            "radar_motion": fused.radar_motion,
            "radar_micro_motion": fused.radar_micro_motion,
            "timestamp": timestamp,
            "source_room": room_id,
        }

    # Check for duplicates
    if _is_duplicate_state(state_updates):
        _stats["duplicates_skipped"] += 1
        logger.debug("[%s] Duplicate state update skipped", rid)
        return

    # Publish state updates
    _publish_state_updates(state_updates, rid)

    # Queue alerts for batching
    for alert in alerts:
        _queue_alert(alert)

    # Write to InfluxDB
    _write_to_influxdb(state_updates, alerts)


def process_telemetry(data: dict):
    """
    Process radar telemetry (legacy, from direct sensor connections).
    Note: Prefer receiving occupancy from RPi simulators.
    """
    global _last_state_hash

    _stats["telemetry_count"] += 1
    sensor_name = data.get("sensor", "unknown")
    seats_data = data.get("seats", {})
    ts_epoch = data.get("timestamp", time.time())

    logger.info(
        "Telemetry #%d from %s, %d seats",
        _stats["telemetry_count"],
        sensor_name,
        len(seats_data),
    )

    alerts: List[GhostAlert] = []
    state_updates: Dict[str, dict] = {}

    for seat_id, info in seats_data.items():
        radar = RadarResult(
            presence=float(info.get("presence", 0)),
            motion=float(info.get("motion", 0)),
            micro_motion=bool(info.get("micro_motion", False)),
        )

        obj_type = info.get("object_type", "empty")
        conf = float(info.get("confidence", 0))
        cam = CameraResult(object_type=obj_type, confidence=conf)

        fused = fusion.fuse(camera_result=cam, radar_result=radar)

        alert = ghost_detector.update(seat_id, fused)
        if alert is not None:
            alerts.append(alert)

        seat_state = ghost_detector.get_state(seat_id).value
        zone_id = SEAT_TO_ZONE.get(seat_id, "")

        state_updates[seat_id] = {
            "seat_id": seat_id,
            "zone_id": zone_id,
            "state": seat_state,
            "occupancy_score": fused.occupancy_score,
            "object_type": fused.object_type,
            "confidence": fused.confidence,
            "is_present": fused.is_present,
            "has_motion": fused.has_motion,
            "radar_presence": fused.radar_presence,
            "radar_motion": fused.radar_motion,
            "radar_micro_motion": fused.radar_micro_motion,
            "timestamp": ts_epoch,
        }

    if _is_duplicate_state(state_updates):
        _stats["duplicates_skipped"] += 1
        return

    _publish_state_updates(state_updates)

    for alert in alerts:
        _queue_alert(alert)

    _write_to_influxdb(state_updates, alerts)


def _is_duplicate_state(state_updates: Dict[str, dict]) -> bool:
    """Check if state is duplicate using hash."""
    global _last_state_hash

    # Create deterministic hash of state
    state_hash = _compute_state_hash(state_updates)

    with _state_hash_lock:
        if state_hash == _last_state_hash:
            return True
        _last_state_hash = state_hash
    return False


def _compute_state_hash(state_updates: Dict[str, dict]) -> str:
    """Compute hash of seat states for deduplication."""
    # Create deterministic representation
    state_repr = {}
    for seat_id in sorted(state_updates.keys()):
        s = state_updates[seat_id]
        state_repr[seat_id] = {
            "state": s.get("state", ""),
            "occ": s.get("occupancy_score", 0),
            "type": s.get("object_type", ""),
        }

    json_str = json.dumps(state_repr, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()[:16]


# =============================================================================
# State Publishing
# =============================================================================

def _publish_state_updates(updates: Dict[str, dict], request_id: str = None):
    rid = request_id or ""
    for seat_id, state_data in updates.items():
        topic = MQTT_TOPIC_STATE_SEAT.replace("{seat_id}", seat_id)
        payload = json.dumps(state_data)

        if mqtt_client is not None and mqtt_client.is_connected():
            try:
                mqtt_client.publish(topic, payload, qos=1)
                _stats["mqtt_publishes"] += 1
            except Exception as exc:
                logger.warning("[%s] MQTT publish failed for %s: %s", rid, topic, exc)
                _http_fallback_seat(state_data)
        else:
            _http_fallback_seat(state_data)


def _http_fallback_seat(state_data: dict):
    """Fallback: POST processed seat state to dashboard via HTTP when MQTT is down."""
    try:
        resp = requests.post(HTTP_DASHBOARD_URL, json=state_data, timeout=2)
        if resp.status_code == 200:
            _stats["http_fallbacks"] += 1
        else:
            logger.warning("HTTP fallback failed for %s: status=%d",
                           state_data.get("seat_id"), resp.status_code)
    except Exception as exc:
        logger.debug("HTTP fallback unavailable for %s: %s",
                     state_data.get("seat_id"), exc)


# =============================================================================
# Alert Batching
# =============================================================================

def _queue_alert(alert: GhostAlert):
    """Queue alert for batched publishing."""
    global _alert_batch, _last_alert_flush

    with _alert_batch_lock:
        _alert_batch.append(alert)
        _stats["alerts_batched"] += 1

        # Flush if batch is full or timeout
        should_flush = (
            len(_alert_batch) >= _ALERT_BATCH_SIZE or
            (time.time() - _last_alert_flush) > _ALERT_BATCH_TIMEOUT
        )

        if should_flush:
            _flush_alerts()


def _flush_alerts():
    """Send batched alerts."""
    global _alert_batch, _last_alert_flush

    with _alert_batch_lock:
        if not _alert_batch:
            return

        alerts_to_send = _alert_batch[:]
        _alert_batch.clear()
        _last_alert_flush = time.time()

    for alert in alerts_to_send:
        _publish_ghost_alert(alert)


def _publish_ghost_alert(alert: GhostAlert):
    """Publish a single ghost alert."""
    _stats["ghost_alerts"] += 1
    _stats["alerts_sent"] += 1

    payload = json.dumps(alert.to_dict())

    logger.warning(
        "GHOST ALERT [%s] seat=%s zone=%s: %s",
        alert.alert_type, alert.seat_id, alert.zone_id, alert.details,
    )

    if mqtt_client is not None and mqtt_client.is_connected():
        try:
            mqtt_client.publish(MQTT_TOPIC_ALERTS_GHOST, payload, qos=1)
            _stats["mqtt_publishes"] += 1
        except Exception as exc:
            logger.warning("MQTT publish failed for ghost alert: %s", exc)
            _http_fallback_alert(alert)
    else:
        _http_fallback_alert(alert)


def _http_fallback_alert(alert: GhostAlert):
    """Fallback: POST ghost alert to dashboard via HTTP when MQTT is down."""
    try:
        payload = {
            "type": alert.alert_type,
            "message": alert.details,
            "seat_id": alert.seat_id,
            "zone": alert.zone_id,
            "countdown": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        resp = requests.post(
            HTTP_DASHBOARD_URL.replace("/seat_state", "/alert"),
            json=payload,
            timeout=2,
        )
        if resp.status_code == 200:
            _stats["http_fallbacks"] += 1
    except Exception:
        pass


# =============================================================================
# InfluxDB Writing
# =============================================================================

def _write_to_influxdb(updates: Dict[str, dict], alerts: List[GhostAlert]):
    """Buffer and write to InfluxDB."""
    global _influx_batch, _last_influx_flush

    if influx_write_api is None:
        return

    try:
        from influxdb_client import Point

        points = []

        for seat_id, state_data in updates.items():
            # Use provided timestamp or current time
            ts = state_data.get("timestamp")
            if ts is None:
                ts = time.time()

            p = (
                Point("seat_state")
                .tag("seat_id", seat_id)
                .tag("zone_id", state_data.get("zone_id", ""))
                .tag("state", state_data.get("state", ""))
                .tag("source_room", state_data.get("source_room", ""))
                .field("occupancy_score", float(state_data.get("occupancy_score", 0)))
                .field("confidence", float(state_data.get("confidence", 0)))
                .field("is_present", bool(state_data.get("is_present", False)))
                .field("has_motion", bool(state_data.get("has_motion", False)))
                .field("radar_presence", float(state_data.get("radar_presence", 0)))
                .field("radar_motion", float(state_data.get("radar_motion", 0)))
                .field("object_type", str(state_data.get("object_type", "empty")))
                .time(int(ts * 1_000_000_000))  # nanoseconds
            )
            points.append(p)

        for alert in alerts:
            p = (
                Point("ghost_alert")
                .tag("seat_id", alert.seat_id)
                .tag("zone_id", alert.zone_id)
                .tag("alert_type", alert.alert_type)
                .field("previous_state", alert.previous_state)
                .field("new_state", alert.new_state)
                .time(int(alert.timestamp * 1_000_000_000))
            )
            points.append(p)

        if points:
            influx_write_api.write(bucket=INFLUXDB_BUCKET, record=points)
            _stats["influx_writes"] += len(points)
            logger.debug("Queued %d points for InfluxDB", len(points))

    except Exception as exc:
        logger.warning("InfluxDB write failed: %s", exc)


# =============================================================================
# MQTT Handling
# =============================================================================

def _handle_mqtt_message(topic: str, payload: bytes):
    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Invalid MQTT payload on %s: %s", topic, exc)
        return

    if topic.endswith("/telemetry"):
        process_telemetry(data)
    elif topic.endswith("/occupancy"):
        process_occupancy(data)
    else:
        logger.debug("Unhandled MQTT topic: %s", topic)


# =============================================================================
# HTTP Server
# =============================================================================

def _run_http_server():
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        logger.warning("Flask not installed. HTTP server disabled.")
        return

    app = Flask("liberty_twin_edge")
    app.logger.setLevel(logging.WARNING)

    @app.before_request
    def before_request():
        """Add request ID to all requests for tracing."""
        request.request_id = get_request_id(request)

    @app.route("/api/occupancy", methods=["POST"])
    def api_occupancy():
        """Receive pre-computed seat occupancy from RPi simulators."""
        # Rate limiting
        client_id = request.headers.get("X-Forwarded-For", request.remote_addr)
        if not check_rate_limit(client_id):
            return jsonify({
                "error": "rate_limit_exceeded",
                "retry_after": _RATE_LIMIT_WINDOW,
            }), 429

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "no JSON body"}), 400
        try:
            process_occupancy(data, request_id=request.request_id)
        except Exception as exc:
            _stats["request_errors"] += 1
            logger.error("[%s] Error processing occupancy: %s", request.request_id, exc, exc_info=True)
            return jsonify({"error": str(exc), "request_id": request.request_id}), 500
        return jsonify({"ok": True, "request_id": request.request_id})

    @app.route("/api/telemetry", methods=["POST"])
    def api_telemetry():
        # Rate limiting
        client_id = request.headers.get("X-Forwarded-For", request.remote_addr)
        if not check_rate_limit(client_id):
            return jsonify({
                "error": "rate_limit_exceeded",
                "retry_after": _RATE_LIMIT_WINDOW,
            }), 429

        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "no JSON body"}), 400
        try:
            process_telemetry(data)
        except Exception as exc:
            _stats["request_errors"] += 1
            logger.error("[%s] Error processing telemetry: %s", request.request_id, exc, exc_info=True)
            return jsonify({"error": str(exc), "request_id": request.request_id}), 500
        return jsonify({"ok": True, "request_id": request.request_id})

    @app.route("/api/camera", methods=["POST"])
    def api_camera():
        """
        Legacy endpoint for direct camera frames.
        Raw frames should NOT arrive here - they stay on RPi simulators.
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "no JSON body"}), 400
        sensor_name = data.get("sensor", "unknown")
        logger.warning(
            "[%s] Received camera frame from %s - raw frames should stay on RPi!",
            request.request_id, sensor_name
        )
        return jsonify({
            "ok": True,
            "warning": "Camera frames should be processed by RPi simulator",
            "request_id": request.request_id,
        })

    @app.route("/api/status", methods=["GET", "POST"])
    def api_status():
        if request.method == "POST":
            return jsonify({"ok": True, "request_id": request.request_id})

        # Get current ghost states
        states = ghost_detector.get_all_states()

        # Count by state
        occupied = sum(1 for v in states.values() if v == "occupied")
        suspected = sum(1 for v in states.values() if v == "suspected_ghost")
        confirmed = sum(1 for v in states.values() if v == "confirmed_ghost")
        empty = TOTAL_SEATS - occupied - suspected - confirmed

        return jsonify({
            "stats": {
                **_stats,
                "state_counts": {
                    "occupied": occupied,
                    "empty": empty,
                    "suspected_ghost": suspected,
                    "confirmed_ghost": confirmed,
                }
            },
            "seat_states": states,
            "total_seats": TOTAL_SEATS,
            "uptime_seconds": time.time() - _start_time,
            "request_id": request.request_id,
        })

    @app.route("/api/state/<seat_id>", methods=["GET"])
    def api_seat_state(seat_id):
        """Get detailed state for a specific seat."""
        rec = ghost_detector.get_seat_record(seat_id)
        reservation = get_reservation(seat_id)
        return jsonify({
            "seat_id": seat_id,
            "state": rec.state.value,
            "last_motion_time": rec.last_motion_time,
            "state_entered_time": rec.state_entered_time,
            "last_update_time": rec.last_update_time,
            "last_object_type": rec.last_object_type,
            "last_occupancy_score": rec.last_occupancy_score,
            "reservation": reservation,
            "request_id": request.request_id,
        })

    @app.route("/api/seats", methods=["GET"])
    def api_all_seats():
        """Get state for all seats with optional filtering."""
        state_filter = request.args.get("filter")  # empty, occupied, suspected, confirmed
        states = ghost_detector.get_all_states()

        result = {}
        for seat_id, state in states.items():
            if state_filter and state != state_filter:
                continue
            rec = ghost_detector.get_seat_record(seat_id)
            result[seat_id] = {
                "state": state,
                "occupancy_score": rec.last_occupancy_score,
                "object_type": rec.last_object_type,
                "last_motion_time": rec.last_motion_time,
                "reservation": get_reservation(seat_id),
            }

        return jsonify({
            "seats": result,
            "total": len(result),
            "filter": state_filter,
            "request_id": request.request_id,
        })

    # -------------------------------------------------------------------------
    # Seat Reservation Endpoints
    # -------------------------------------------------------------------------

    @app.route("/api/reservations", methods=["GET"])
    def api_get_reservations():
        """Get all active reservations (admin view)."""
        user_id = request.args.get("user_id")
        if user_id:
            reservations = get_user_reservations(user_id)
        else:
            # Return all reservations
            now = time.time()
            with _reservation_lock:
                reservations = [
                    {"seat_id": sid, **r}
                    for sid, r in _reservations.items()
                    if r["expires_at"] > now
                ]
        return jsonify({
            "reservations": reservations,
            "total": len(reservations),
            "request_id": request.request_id,
        })

    @app.route("/api/reservation/<seat_id>", methods=["POST"])
    def api_create_reservation(seat_id):
        """Create a seat reservation."""
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id required", "request_id": request.request_id}), 400
        ttl = data.get("ttl", _RESERVATION_TTL)
        result = create_reservation(seat_id, user_id, ttl)
        status = 200 if result["status"] == "created" or result["status"] == "extended" else 400
        return jsonify({**result, "request_id": request.request_id}), status

    @app.route("/api/reservation/<seat_id>", methods=["DELETE"])
    def api_release_reservation(seat_id):
        """Release a seat reservation."""
        data = request.get_json(silent=True) or {}
        user_id = data.get("user_id")
        if not user_id:
            return jsonify({"error": "user_id required", "request_id": request.request_id}), 400
        result = release_reservation(seat_id, user_id)
        status = 200 if result["status"] == "released" else 400
        return jsonify({**result, "request_id": request.request_id}), status

    # -------------------------------------------------------------------------
    # Health & Readiness (Kubernetes-style)
    # -------------------------------------------------------------------------

    @app.route("/health", methods=["GET"])
    def health():
        """Basic health check."""
        return jsonify({
            "status": "ok",
            "uptime_seconds": round(time.time() - _start_time, 1),
        })

    @app.route("/health/ready", methods=["GET"])
    def health_ready():
        """Readiness probe - returns 200 if ready to serve traffic."""
        checks = {
            "mqtt": mqtt_client is not None and mqtt_client.is_connected(),
            "influxdb": influx_write_api is not None,
            "at_least_one_rpi": len(_stats["rpi_sources"]) > 0,
        }
        ready = all(checks.values())
        return jsonify({
            "ready": ready,
            "checks": checks,
            "rpi_sources": list(_stats["rpi_sources"]),
        }), 200 if ready else 503

    @app.route("/health/live", methods=["GET"])
    def health_live():
        """Liveness probe - returns 200 if process is alive."""
        return jsonify({
            "alive": True,
            "uptime_seconds": round(time.time() - _start_time, 1),
        })

    # -------------------------------------------------------------------------
    # Enhanced Metrics
    # -------------------------------------------------------------------------

    @app.route("/metrics", methods=["GET"])
    def metrics():
        """Prometheus-style metrics endpoint with enhanced details."""
        states = ghost_detector.get_all_states()
        occupied = sum(1 for v in states.values() if v == "occupied")
        suspected = sum(1 for v in states.values() if v == "suspected_ghost")
        confirmed = sum(1 for v in states.values() if v == "confirmed_ghost")

        # Zone-based metrics
        zone_metrics = {}
        for zone_id, seats in ZONE_TO_SEATS.items():
            zone_states = {sid: states.get(sid, "empty") for sid in seats}
            zone_occupied = sum(1 for s in zone_states.values() if s == "occupied")
            zone_metrics[zone_id] = {
                "occupied": zone_occupied,
                "total": len(seats),
                "utilization": round(zone_occupied / len(seats) * 100, 1) if seats else 0,
            }

        # Reservation stats
        now = time.time()
        with _reservation_lock:
            active_reservations = sum(1 for r in _reservations.values() if r["expires_at"] > now)

        metrics_lines = [
            "# HELP liberty_occupancy_count Total occupancy updates received",
            "# TYPE liberty_occupancy_count counter",
            f"liberty_occupancy_count {_stats['occupancy_count']}",
            "",
            "# HELP liberty_telemetry_count Total telemetry messages received",
            "# TYPE liberty_telemetry_count counter",
            f"liberty_telemetry_count {_stats['telemetry_count']}",
            "",
            "# HELP liberty_ghost_alerts Total ghost alerts generated",
            "# TYPE liberty_ghost_alerts counter",
            f"liberty_ghost_alerts {_stats['ghost_alerts']}",
            "",
            "# HELP liberty_mqtt_publishes Total MQTT messages published",
            "# TYPE liberty_mqtt_publishes counter",
            f"liberty_mqtt_publishes {_stats['mqtt_publishes']}",
            "",
            "# HELP liberty_influxdb_writes Total InfluxDB points written",
            "# TYPE liberty_influxdb_writes counter",
            f"liberty_influxdb_writes {_stats['influx_writes']}",
            "",
            "# HELP liberty_http_fallbacks Total HTTP fallback calls",
            "# TYPE liberty_http_fallbacks counter",
            f"liberty_http_fallbacks {_stats['http_fallbacks']}",
            "",
            "# HELP liberty_rate_limited Total rate-limited requests",
            "# TYPE liberty_rate_limited counter",
            f"liberty_rate_limited {_stats['rate_limited']}",
            "",
            "# HELP liberty_request_errors Total request processing errors",
            "# TYPE liberty_request_errors counter",
            f"liberty_request_errors {_stats['request_errors']}",
            "",
            "# HELP liberty_duplicates_skipped Total duplicate state updates skipped",
            "# TYPE liberty_duplicates_skipped counter",
            f"liberty_duplicates_skipped {_stats['duplicates_skipped']}",
            "",
            "# HELP liberty_seats_occupied Current number of occupied seats",
            "# TYPE liberty_seats_occupied gauge",
            f"liberty_seats_occupied {occupied}",
            "",
            "# HELP liberty_seats_suspected_ghost Current suspected ghost seats",
            "# TYPE liberty_seats_suspected_ghost gauge",
            f"liberty_seats_suspected_ghost {suspected}",
            "",
            "# HELP liberty_seats_confirmed_ghost Current confirmed ghost seats",
            "# TYPE liberty_seats_confirmed_ghost gauge",
            f"liberty_seats_confirmed_ghost {confirmed}",
            "",
            "# HELP liberty_seats_empty Current empty seats",
            "# TYPE liberty_seats_empty gauge",
            f"liberty_seats_empty {TOTAL_SEATS - occupied - suspected - confirmed}",
            "",
            "# HELP liberty_rpi_sources Number of connected RPi simulators",
            "# TYPE liberty_rpi_sources gauge",
            f"liberty_rpi_sources {len(_stats['rpi_sources'])}",
            "",
            "# HELP liberty_active_reservations Current active seat reservations",
            "# TYPE liberty_active_reservations gauge",
            f"liberty_active_reservations {active_reservations}",
            "",
            "# HELP liberty_uptime_seconds Process uptime in seconds",
            "# TYPE liberty_uptime_seconds gauge",
            f"liberty_uptime_seconds {round(time.time() - _start_time, 1)}",
            "",
            "# HELP liberty_zone_occupancy Zone-level occupancy percentage",
            "# TYPE liberty_zone_occupancy gauge",
        ]

        for zone_id, zdata in zone_metrics.items():
            metrics_lines.append(f'liberty_zone_occupancy{{zone="{zone_id}"}} {zdata["utilization"]}')

        metrics_text = "\n".join(metrics_lines) + "\n"
        return metrics_text, 200, {"Content-Type": "text/plain"}

    # -------------------------------------------------------------------------
    # Cross-Room Analytics
    # -------------------------------------------------------------------------

    @app.route("/api/analytics/rooms", methods=["GET"])
    def api_room_analytics():
        """Get analytics across all rooms."""
        with _room_correlation_lock:
            room_data = {}
            for room_id, pattern in _room_patterns.items():
                room_data[room_id] = {
                    "last_seen": pattern["timestamp"],
                    "age_seconds": round(time.time() - pattern["timestamp"], 1),
                    "state_counts": pattern["state_counts"],
                }

        return jsonify({
            "rooms": room_data,
            "total_rooms": len(room_data),
            "request_id": request.request_id,
        })

    @app.route("/api/analytics/utilization", methods=["GET"])
    def api_utilization():
        """Get zone utilization analytics."""
        states = ghost_detector.get_all_states()
        result = {}
        for zone_id, seats in ZONE_TO_SEATS.items():
            zone_states = [states.get(sid, "empty") for sid in seats]
            occupied = sum(1 for s in zone_states if s == "occupied")
            suspected = sum(1 for s in zone_states if s == "suspected_ghost")
            confirmed = sum(1 for s in zone_states if s == "confirmed_ghost")
            empty = len(seats) - occupied - suspected - confirmed

            result[zone_id] = {
                "total": len(seats),
                "occupied": occupied,
                "suspected": suspected,
                "confirmed": confirmed,
                "empty": empty,
                "utilization_pct": round(occupied / len(seats) * 100, 1) if seats else 0,
            }

        return jsonify({
            "zones": result,
            "overall": {
                "total_seats": TOTAL_SEATS,
                "occupied": sum(1 for s in states.values() if s == "occupied"),
                "utilization_pct": round(sum(1 for s in states.values() if s == "occupied") / TOTAL_SEATS * 100, 1),
            },
            "request_id": request.request_id,
        })

    logger.info("Edge HTTP server starting on port %d", HTTP_FALLBACK_PORT)
    app.run(host="0.0.0.0", port=HTTP_FALLBACK_PORT, threaded=True, debug=False)


# =============================================================================
# Stats Logging
# =============================================================================

_start_time = time.time()

def _log_stats_periodically(interval: float = 30.0):
    """Log statistics periodically."""
    _flush_alerts()  # Flush any pending alerts

    while True:
        time.sleep(interval)

        # Flush pending batches
        _flush_alerts()

        # Cleanup expired reservations
        expired_count = cleanup_expired_reservations()

        states = ghost_detector.get_all_states()
        occupied = sum(1 for v in states.values() if v == "occupied")
        suspected = sum(1 for v in states.values() if v == "suspected_ghost")
        confirmed = sum(1 for v in states.values() if v == "confirmed_ghost")
        empty = TOTAL_SEATS - occupied - suspected - confirmed

        logger.info(
            "Stats | occ=%d tel=%d alerts=%d pub=%d influx=%d dup=%d rate_limited=%d | "
            "occupied=%d empty=%d suspected=%d confirmed=%d | RPi: %s | Reservations: %d expired",
            _stats["occupancy_count"], _stats["telemetry_count"],
            _stats["ghost_alerts"], _stats["mqtt_publishes"], _stats["influx_writes"],
            _stats["duplicates_skipped"], _stats["rate_limited"],
            occupied, empty, suspected, confirmed,
            ", ".join(sorted(_stats["rpi_sources"])) or "none",
            expired_count,
        )


# =============================================================================
# Main
# =============================================================================

def main():
    global _start_time
    _start_time = time.time()

    print("=" * 60)
    print("  LIBERTY TWIN - Edge Processor (Central Hub)")
    print("=" * 60)

    mqtt_ok = _init_mqtt()
    influx_ok = _init_influxdb()

    print()
    print(f"  MQTT:     {'CONNECTED' if mqtt_ok else 'UNAVAILABLE (HTTP fallback)'}")
    print(f"  InfluxDB: {'CONNECTED (batching)' if influx_ok else 'UNAVAILABLE (writes disabled)'}")
    print(f"  HTTP API: http://0.0.0.0:{HTTP_FALLBACK_PORT}")
    print(f"  Seats:    {TOTAL_SEATS} across {len(set(SEAT_TO_ZONE.values()))} zones")
    print("=" * 60)
    print()
    print("  Ghost Detection: 4-state FSM")
    print("  - Empty → Occupied (motion detected)")
    print("  - Occupied → Suspected Ghost (2 min no motion)")
    print("  - Suspected Ghost → Confirmed Ghost (5 min no motion)")
    print("  - All states can return to Occupied (motion restored)")
    print()
    print("  Alert Batching: up to %d alerts or %ds timeout" % (_ALERT_BATCH_SIZE, _ALERT_BATCH_TIMEOUT))
    print("  State Deduplication: hash-based")
    print()
    print("  ENHANCED FEATURES:")
    print("  - Multi-Room Correlation: Track patterns across rooms")
    print("  - Rate Limiting: %d req/min per client" % _RATE_LIMIT_MAX_REQUESTS)
    print("  - Seat Reservations: API for seat booking (TTL: %ds)" % _RESERVATION_TTL)
    print("  - Request ID Tracking: Distributed tracing support")
    print("  - Health Endpoints: /health, /health/ready, /health/live")
    print("  - Zone Utilization Analytics: Per-zone metrics")
    print()
    print("  Note: RPi simulators handle camera processing locally.")
    print("        Only seat occupancy data is sent to this edge.")
    print()

    stats_thread = threading.Thread(target=_log_stats_periodically, daemon=True)
    stats_thread.start()

    def _shutdown(signum, frame):
        logger.info("Shutting down edge processor...")
        _flush_alerts()  # Flush pending alerts
        if influx_write_api is not None:
            try:
                influx_write_api.flush()
                influx_client.close()
            except Exception:
                pass
        if mqtt_client is not None:
            try:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()
            except Exception:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    _run_http_server()


if __name__ == "__main__":
    main()
