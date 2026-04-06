#!/usr/bin/env python3

import base64
import os
from collections import defaultdict, deque
from datetime import datetime, timezone
import json
import logging
import signal
import sys
import threading
import time
import uuid
from io import BytesIO
from typing import Dict, List, Optional
from functools import wraps

import numpy as np
import requests

# Rate limiting configuration
_RATE_LIMIT_WINDOW = 60.0  # 1 minute sliding window
_RATE_LIMIT_MAX_REQUESTS = 1000  # per window

# Seat reservation configuration
_RESERVATION_TTL = 900  # 15 minutes default
_RESERVATION_MAX_PER_USER = 2

# In-memory rate limiting storage
_rate_limit_storage: Dict[str, deque] = defaultdict(lambda: deque(maxlen=_RATE_LIMIT_MAX_REQUESTS))
_rate_limit_lock = threading.Lock()

# In-memory seat reservations: seat_id -> {user_id: expiry_time}
_reservations: Dict[str, Dict[str, float]] = defaultdict(dict)
_reservations_lock = threading.Lock()

# Multi-room correlation: room_id -> pattern analysis
_room_patterns: Dict[str, dict] = {}
_room_correlation_lock = threading.Lock()

# Multi-room occupancy storage: room_id -> {timestamp, seats}
_occupancy_storage: Dict[str, dict] = {}
_occupancy_lock = threading.Lock()

# Request ID tracking for distributed tracing
_request_ids: Dict[str, str] = {}  # trace_id -> request_id

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
    ZONE_TO_SEATS,
    SEAT_TO_ZONE,
    HTTP_FALLBACK_PORT,
    LOG_LEVEL,
    LOG_FORMAT,
    TOTAL_SEATS,
)

HTTP_DASHBOARD_URL = os.environ.get("HTTP_DASHBOARD_URL", "http://localhost:5000/api/seat_state")

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO), format=LOG_FORMAT)
logger = logging.getLogger("processor")

mqtt_client = None
influx_write_api = None

# Stats
_stats = {
    "occupancy_received": 0,
    "mqtt_publishes": 0,
    "influx_writes": 0,
    "heatmap_requests": 0,
}

def _init_mqtt() -> bool:
    global mqtt_client
    try:
        import paho.mqtt.client as paho_mqtt

        def on_connect(client, userdata, flags, reason_code, properties=None):
            if reason_code == 0 or str(reason_code) == "Success":
                logger.info("MQTT connected to %s:%s", MQTT_BROKER_HOST, MQTT_BROKER_PORT)
                client.subscribe(MQTT_TOPIC_SENSOR)
                logger.info("Subscribed to %s", MQTT_TOPIC_SENSOR)
            else:
                logger.warning("MQTT connection refused: %s", reason_code)

        def on_disconnect(client, userdata, flags, reason_code, properties=None):
            logger.warning("MQTT disconnected (rc=%s). Will retry.", reason_code)

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
        return True
    except ImportError:
        logger.warning("paho-mqtt not installed. MQTT disabled; using HTTP fallback only.")
        return False
    except Exception as exc:
        logger.warning("Cannot connect to MQTT broker at %s:%s (%s). Using HTTP fallback.",
                        MQTT_BROKER_HOST, MQTT_BROKER_PORT, exc)
        return False

def _init_influxdb() -> bool:
    global influx_write_api
    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS

        client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        health = client.health()
        if health.status != "pass":
            logger.warning("InfluxDB health check did not pass: %s", health.message)
        influx_write_api = client.write_api(write_options=SYNCHRONOUS)
        logger.info("InfluxDB connected at %s (org=%s, bucket=%s)",
                     INFLUXDB_URL, INFLUXDB_ORG, INFLUXDB_BUCKET)
        return True
    except ImportError:
        logger.warning("influxdb-client not installed. InfluxDB writes disabled.")
        return False
    except Exception as exc:
        logger.warning("Cannot connect to InfluxDB at %s (%s). Writes disabled.",
                        INFLUXDB_URL, exc)
        return False

def _handle_mqtt_message(topic: str, payload: bytes):
    """Handle incoming MQTT messages from RPi devices."""
    try:
        data = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.warning("Invalid MQTT payload on %s: %s", topic, exc)
        return

    # RPi sends pre-processed occupancy data
    if topic.endswith("/occupancy"):
        process_occupancy_from_rpi(data)
    elif topic.endswith("/telemetry"):
        # Legacy telemetry format - convert to occupancy
        _process_legacy_telemetry(data)
    elif topic.endswith("/camera"):
        # Legacy camera format - RPi should now send detections directly
        logger.debug("Legacy camera message received, ignoring (RPi should send occupancy)")
    else:
        logger.debug("Unhandled MQTT topic: %s", topic)

def process_occupancy_from_rpi(data: dict):
    """
    Process pre-processed occupancy data from RPi.

    RPi sends seat-level data with:
    - is_present, occupancy_score (from sensor fusion)
    - ghost_state (from ghost detection FSM)
    - dwell_time, time_since_motion (from motion tracker)
    """
    source = data.get("source", "unknown")
    room_id = data.get("room_id", "room_1")
    timestamp = data.get("timestamp", time.time())
    seats = data.get("seats", {})

    _stats["occupancy_received"] += 1

    logger.info(
        "Occupancy from %s [%s]: %d seats, %d occupied",
        source, room_id, len(seats),
        sum(1 for s in seats.values() if s.get("is_occupied")),
    )

    # Store for multi-room aggregation
    with _occupancy_lock:
        _occupancy_storage[room_id] = {
            "timestamp": timestamp,
            "seats": seats,
        }

    # Analyze room correlation
    seat_states = {seat_id: seat.get("ghost_state", "empty") for seat_id, seat in seats.items()}
    _analyze_room_correlation(room_id, seat_states)

    # Forward to dashboard via MQTT
    _publish_occupancy_to_dashboard(room_id, seats, timestamp)

    # Write to InfluxDB
    _write_occupancy_to_influxdb(room_id, seats, timestamp)

def _process_legacy_telemetry(data: dict):
    """Process legacy telemetry format (for backwards compatibility)."""
    # Convert legacy format to occupancy format
    zone_id = data.get("zone_id", "")
    sensor_name = data.get("sensor", "unknown")
    seats_data = data.get("seats", {})
    ts_epoch = data.get("timestamp", time.time())

    occupancy_data = {
        "source": "legacy_telemetry",
        "room_id": f"room_from_{sensor_name}",
        "timestamp": ts_epoch,
        "seats": {},
    }

    for seat_id, info in seats_data.items():
        occupancy_data["seats"][seat_id] = {
            "zone_id": SEAT_TO_ZONE.get(seat_id, zone_id),
            "is_occupied": info.get("presence", 0) > 0.5,
            "occupancy_score": info.get("presence", 0),
            "ghost_state": "empty",
            "dwell_time": 0,
            "object_type": info.get("object_type", "unknown"),
        }

    process_occupancy_from_rpi(occupancy_data)

def _publish_occupancy_to_dashboard(room_id: str, seats: dict, timestamp: float):
    """Forward occupancy data to dashboard via MQTT or HTTP."""
    for seat_id, seat_data in seats.items():
        # Map is_occupied boolean to state string for dashboard compatibility
        is_occupied = seat_data.get("is_occupied", False)
        ghost_state = seat_data.get("ghost_state", "empty")
        if ghost_state in ("suspected_ghost", "confirmed_ghost"):
            state_str = ghost_state
        elif is_occupied:
            state_str = "occupied"
        else:
            state_str = "empty"

        state_data = {
            "seat_id": seat_id,
            "room_id": room_id,
            "zone_id": seat_data.get("zone_id", SEAT_TO_ZONE.get(seat_id, "unknown")),
            "state": state_str,
            "is_occupied": is_occupied,
            "occupancy_score": seat_data.get("occupancy_score", 0.0),
            "ghost_state": ghost_state,
            "dwell_time": seat_data.get("dwell_time", 0.0),
            "object_type": seat_data.get("object_type", "empty"),
            "timestamp": timestamp,
        }

        topic = MQTT_TOPIC_STATE_SEAT.replace("{seat_id}", seat_id)
        payload = json.dumps(state_data)

        if mqtt_client is not None and mqtt_client.is_connected():
            try:
                mqtt_client.publish(topic, payload, qos=1)
                _stats["mqtt_publishes"] += 1
            except Exception as exc:
                logger.warning("MQTT publish failed for %s: %s", topic, exc)
                _http_fallback_seat(state_data)
        else:
            _http_fallback_seat(state_data)

def _http_fallback_seat(state_data: dict):
    """Fallback: POST processed seat state to dashboard via HTTP when MQTT is down."""
    try:
        resp = requests.post(HTTP_DASHBOARD_URL, json=state_data, timeout=2)
        if resp.status_code == 200:
            _stats["http_fallbacks"] = _stats.get("http_fallbacks", 0) + 1
        else:
            logger.warning("HTTP fallback failed for %s: status=%d", state_data.get("seat_id"), resp.status_code)
    except Exception as exc:
        logger.debug("HTTP fallback unavailable for %s: %s", state_data.get("seat_id"), exc)

def _http_fallback_alert(alert: dict):
    """Fallback: POST alert to dashboard via HTTP when MQTT is down."""
    try:
        payload = {
            "type": alert.get("alert_type", "unknown"),
            "message": alert.get("details", ""),
            "seat_id": alert.get("seat_id", ""),
            "zone": alert.get("zone_id", ""),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        resp = requests.post(
            HTTP_DASHBOARD_URL.replace("/seat_state", "/alert"),
            json=payload,
            timeout=2,
        )
        if resp.status_code == 200:
            _stats["http_fallbacks"] = _stats.get("http_fallbacks", 0) + 1
    except Exception:
        pass

def _is_rate_limited(client_id: str = "default") -> bool:
    """Check if client has exceeded rate limit. Returns True if rate limited."""
    now = time.time()
    with _rate_limit_lock:
        window = _rate_limit_storage[client_id]
        # Remove expired entries
        while window and window[0] < now - _RATE_LIMIT_WINDOW:
            window.popleft()
        if len(window) >= _RATE_LIMIT_MAX_REQUESTS:
            return True
        window.append(now)
        return False

def _get_request_id() -> str:
    """Generate a unique request ID for distributed tracing."""
    return str(uuid.uuid4())[:16]

def _analyze_room_correlation(room_id: str, seat_states: Dict[str, str]) -> dict:
    """Analyze seat patterns within a room for ghost detection correlation."""
    occupied = sum(1 for s in seat_states.values() if s == "occupied")
    suspected = sum(1 for s in seat_states.values() if s == "suspected_ghost")
    confirmed = sum(1 for s in seat_states.values() if s == "confirmed_ghost")
    empty = len(seat_states) - occupied - suspected - confirmed

    # Ghost correlation: multiple suspected/confirmed in same zone suggests real object
    zone_ghosts: Dict[str, int] = defaultdict(int)
    for seat_id, state in seat_states.items():
        if state in ("suspected_ghost", "confirmed_ghost"):
            zone = SEAT_TO_ZONE.get(seat_id, "unknown")
            zone_ghosts[zone] += 1

    correlated_zones = {z for z, c in zone_ghosts.items() if c >= 2}
    has_correlated_ghost = len(correlated_zones) > 0

    pattern = {
        "occupied": occupied,
        "suspected": suspected,
        "confirmed": confirmed,
        "empty": empty,
        "utilization": round(occupied / max(len(seat_states), 1), 3),
        "ghost_correlation": has_correlated_ghost,
        "correlated_zones": list(correlated_zones),
        "zone_ghost_counts": dict(zone_ghosts),
    }

    with _room_correlation_lock:
        _room_patterns[room_id] = pattern

    return pattern

def _create_reservation(seat_id: str, user_id: str) -> dict:
    """Create a seat reservation for a user."""
    with _reservations_lock:
        # Check user's existing reservations
        user_reservations = [
            sid for sid, users in _reservations.items()
            if user_id in users and users[user_id] > time.time()
        ]
        if len(user_reservations) >= _RESERVATION_MAX_PER_USER:
            return {"success": False, "error": f"Maximum {_RESERVATION_MAX_PER_USER} reservations per user"}

        # Check if seat is already reserved
        if seat_id in _reservations:
            active = {u: exp for u, exp in _reservations[seat_id].items() if exp > time.time()}
            if active:
                # Check if user already has this reservation
                if user_id in active:
                    return {"success": True, "seat_id": seat_id, "expires_at": active[user_id], "renewed": True}
                return {"success": False, "error": "Seat already reserved"}

        # Create new reservation
        expiry = time.time() + _RESERVATION_TTL
        _reservations[seat_id][user_id] = expiry
        return {"success": True, "seat_id": seat_id, "expires_at": expiry}

def _release_reservation(seat_id: str, user_id: str) -> dict:
    """Release a seat reservation."""
    with _reservations_lock:
        if seat_id in _reservations and user_id in _reservations[seat_id]:
            del _reservations[seat_id][user_id]
            if not _reservations[seat_id]:
                del _reservations[seat_id]
            return {"success": True}
        return {"success": False, "error": "Reservation not found"}

def _get_all_reservations() -> dict:
    """Get all active reservations."""
    now = time.time()
    result = {}
    with _reservations_lock:
        for seat_id, users in _reservations.items():
            active = {u: exp for u, exp in users.items() if exp > now}
            if active:
                result[seat_id] = {
                    "reservations": [
                        {"user_id": u, "expires_at": exp, "ttl_seconds": int(exp - now)}
                        for u, exp in active.items()
                    ]
                }
    return result

def _cleanup_expired_reservations():
    """Remove expired reservations. Called periodically."""
    now = time.time()
    with _reservations_lock:
        for seat_id in list(_reservations.keys()):
            _reservations[seat_id] = {
                u: exp for u, exp in _reservations[seat_id].items() if exp > now
            }
            if not _reservations[seat_id]:
                del _reservations[seat_id]

# Cleanup expired reservations every 5 minutes
def _reservation_cleanup_thread():
    while True:
        time.sleep(300)
        _cleanup_expired_reservations()

_cleanup_thread = threading.Thread(target=_reservation_cleanup_thread, daemon=True)
_cleanup_thread.start()

def _write_occupancy_to_influxdb(room_id: str, seats: dict, timestamp: float):
    """Write occupancy data to InfluxDB for time-series storage."""
    if influx_write_api is None:
        return

    try:
        from influxdb_client import Point

        points = []

        for seat_id, seat_data in seats.items():
            p = (
                Point("occupancy")
                .tag("room_id", room_id)
                .tag("seat_id", seat_id)
                .tag("zone_id", seat_data.get("zone_id", SEAT_TO_ZONE.get(seat_id, "")))
                .tag("ghost_state", seat_data.get("ghost_state", "empty"))
                .tag("object_type", seat_data.get("object_type", "empty"))
                .field("is_occupied", bool(seat_data.get("is_occupied", False)))
                .field("occupancy_score", float(seat_data.get("occupancy_score", 0)))
                .field("dwell_time", float(seat_data.get("dwell_time", 0)))
                .field("time_since_motion", float(seat_data.get("time_since_motion", 0)))
            )
            points.append(p)

        if points:
            influx_write_api.write(bucket=INFLUXDB_BUCKET, record=points)
            _stats["influx_writes"] += len(points)
            logger.debug("Wrote %d points to InfluxDB", len(points))

    except Exception as exc:
        logger.warning("InfluxDB write failed: %s", exc)

def _run_http_server():
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        logger.warning("Flask not installed. HTTP fallback server disabled.")
        return

    app = Flask("liberty_twin_edge")
    app.logger.setLevel(logging.WARNING)

    @app.route("/api/occupancy", methods=["POST"])
    def api_occupancy():
        """
        Receive pre-processed occupancy data from RPi.

        RPi sends:
        {
            "source": "rpi_simulator",
            "room_id": "room_1",
            "timestamp": 1234567890.123,
            "seats": {
                "S1": {
                    "zone_id": "Z1",
                    "is_occupied": true,
                    "object_type": "person",
                    "confidence": 0.9,
                    "ghost_state": "occupied",
                    "dwell_time": 120.5,
                    "time_since_motion": 3.2,
                    ...
                },
                ...
            }
        }
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "no JSON body"}), 400

        # Rate limit by source
        client_id = data.get("room_id", "unknown")
        if _is_rate_limited(client_id):
            return jsonify({"error": "rate limited"}), 429

        try:
            process_occupancy_from_rpi(data)
        except Exception as exc:
            logger.error("Error processing occupancy: %s", exc, exc_info=True)
            return jsonify({"error": str(exc)}), 500

        seat_count = len(data.get("seats", {}))
        occupied = sum(1 for s in data.get("seats", {}).values() if s.get("is_occupied"))
        return jsonify({"ok": True, "received": seat_count, "occupied": occupied})

    @app.route("/api/status", methods=["GET", "POST"])
    def api_status():
        if request.method == "POST":
            return jsonify({"ok": True})

        # Aggregate seat states from all rooms
        all_seats = {}
        with _occupancy_lock:
            for room_id, room_data in _occupancy_storage.items():
                all_seats.update(room_data.get("seats", {}))

        return jsonify({
            "stats": _stats,
            "seat_states": {sid: seat.get("ghost_state", "empty") for sid, seat in all_seats.items()},
            "rooms_active": len(_occupancy_storage),
            "total_seats": TOTAL_SEATS,
        })

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "mqtt_connected": mqtt_client is not None and mqtt_client.is_connected(),
            "influxdb_connected": influx_write_api is not None,
        })

    @app.route("/health/ready", methods=["GET"])
    def health_ready():
        """Kubernetes readiness probe - checks if the service can handle requests."""
        mqtt_ok = mqtt_client is not None and mqtt_client.is_connected()
        influx_ok = influx_write_api is not None
        # Service is ready if at least one data pipeline works
        ready = mqtt_ok or influx_ok
        return jsonify({
            "ready": ready,
            "mqtt_connected": mqtt_ok,
            "influxdb_connected": influx_ok,
        }), 200 if ready else 503

    @app.route("/health/live", methods=["GET"])
    def health_live():
        """Kubernetes liveness probe - checks if the service process is alive."""
        return jsonify({"alive": True})

    @app.route("/api/seats", methods=["GET"])
    def api_seats():
        """Get state for all seats with optional filtering."""
        room = request.args.get("room", None)  # Optional room filter
        state_filter = request.args.get("state", None)  # empty, occupied, suspected_ghost, confirmed_ghost

        # Collect seats from all rooms or selected room
        all_seats = {}
        with _occupancy_lock:
            if room:
                if room in _occupancy_storage:
                    all_seats = dict(_occupancy_storage[room].get("seats", {}))
            else:
                for room_data in _occupancy_storage.values():
                    all_seats.update(room_data.get("seats", {}))

        result = {"seats": {}}

        for seat_id in sorted(all_seats.keys()):
            seat_data = all_seats[seat_id]
            state = seat_data.get("ghost_state", "empty")

            if state_filter and state != state_filter:
                continue

            seat_info = {
                "seat_id": seat_id,
                "room_id": seat_data.get("room_id", "unknown"),
                "zone_id": seat_data.get("zone_id", SEAT_TO_ZONE.get(seat_id, "unknown")),
                "state": state,
                "is_occupied": seat_data.get("is_occupied", False),
                "occupancy_score": seat_data.get("occupancy_score", 0.0),
                "object_type": seat_data.get("object_type", "empty"),
                "dwell_time": seat_data.get("dwell_time", 0.0),
                "time_since_motion": seat_data.get("time_since_motion", 0.0),
                "last_update": seat_data.get("timestamp", 0),
            }

            # Add reservation info
            with _reservations_lock:
                if seat_id in _reservations:
                    active = {u: exp for u, exp in _reservations[seat_id].items() if exp > time.time()}
                    if active:
                        seat_info["reserved"] = True
                        seat_info["reserved_by"] = list(active.keys())

            result["seats"][seat_id] = seat_info

        result["summary"] = {
            "total": len(result["seats"]),
            "occupied": sum(1 for s in result["seats"].values() if s.get("is_occupied")),
            "empty": sum(1 for s in result["seats"].values() if not s.get("is_occupied")),
            "suspected_ghost": sum(1 for s in result["seats"].values() if s.get("state") == "suspected_ghost"),
            "confirmed_ghost": sum(1 for s in result["seats"].values() if s.get("state") == "confirmed_ghost"),
        }

        return jsonify(result)

    @app.route("/api/reservations", methods=["GET"])
    def api_reservations():
        """Get all active reservations."""
        return jsonify(_get_all_reservations())

    @app.route("/api/reservation/<seat_id>", methods=["POST", "DELETE"])
    def api_reservation(seat_id: str):
        """Create (POST) or release (DELETE) a reservation."""
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            user_id = data.get("user_id", "anonymous")
            result = _create_reservation(seat_id, user_id)
            return jsonify(result), 201 if result.get("success") else 409
        else:
            data = request.get_json(silent=True) or {}
            user_id = data.get("user_id", "anonymous")
            result = _release_reservation(seat_id, user_id)
            return jsonify(result), 200 if result.get("success") else 404

    @app.route("/api/analytics/rooms", methods=["GET"])
    def api_analytics_rooms():
        """Cross-room analytics for pattern correlation."""
        with _occupancy_lock:
            room_patterns = dict(_room_patterns)

        result = {}
        for room_id, pattern in room_patterns.items():
            result[room_id] = pattern

        return jsonify(result)

    @app.route("/api/analytics/utilization", methods=["GET"])
    def api_analytics_utilization():
        """Zone utilization analytics across all rooms."""
        with _occupancy_lock:
            all_seats = {}
            for room_data in _occupancy_storage.values():
                all_seats.update(room_data.get("seats", {}))

        zone_utilization = {}

        for zone, seats in ZONE_TO_SEATS.items():
            zone_seats = {s: all_seats.get(s, {}).get("ghost_state", "empty") for s in seats}
            occupied = sum(1 for s in zone_seats.values() if s == "occupied")
            zone_utilization[zone] = {
                "total": len(seats),
                "occupied": occupied,
                "utilization": round(occupied / len(seats), 3),
                "states": {
                    "occupied": sum(1 for s in zone_seats.values() if s == "occupied"),
                    "empty": sum(1 for s in zone_seats.values() if s == "empty"),
                    "suspected_ghost": sum(1 for s in zone_seats.values() if s == "suspected_ghost"),
                    "confirmed_ghost": sum(1 for s in zone_seats.values() if s == "confirmed_ghost"),
                }
            }

        total_occupied = sum(1 for s in all_seats.values() if s.get("ghost_state") == "occupied")

        return jsonify({
            "zones": zone_utilization,
            "overall": {
                "total_seats": TOTAL_SEATS,
                "occupied": total_occupied,
                "utilization": round(total_occupied / max(TOTAL_SEATS, 1), 3)
            }
        })

    @app.route("/api/heatmap/<room_id>", methods=["GET"])
    def api_heatmap(room_id: str):
        """
        Generate heatmap data for a room (zones as heat cells).

        Returns zone-level aggregated occupancy scores for visualization.
        """
        _stats["heatmap_requests"] += 1

        with _occupancy_lock:
            if room_id not in _occupancy_storage:
                return jsonify({"error": "room not found", "available_rooms": list(_occupancy_storage.keys())}), 404

            data = _occupancy_storage[room_id]
            seats = data.get("seats", {})

        # Build zone-level heatmap
        zone_scores = {}
        for seat_id, seat_data in seats.items():
            zone_id = seat_data.get("zone_id", SEAT_TO_ZONE.get(seat_id, "unknown"))
            score = seat_data.get("occupancy_score", 0.0)
            is_occupied = seat_data.get("is_occupied", False)

            if zone_id not in zone_scores:
                zone_scores[zone_id] = {"scores": [], "occupied_count": 0, "total_count": 0}

            zone_scores[zone_id]["scores"].append(score)
            zone_scores[zone_id]["total_count"] += 1
            if is_occupied:
                zone_scores[zone_id]["occupied_count"] += 1

        heatmap = {}
        for zone_id, zone_data in zone_scores.items():
            scores = zone_data["scores"]
            heatmap[zone_id] = {
                "avg_occupancy": round(sum(scores) / len(scores), 3) if scores else 0,
                "max_occupancy": round(max(scores), 3) if scores else 0,
                "min_occupancy": round(min(scores), 3) if scores else 0,
                "occupied_seats": zone_data["occupied_count"],
                "total_seats": zone_data["total_count"],
                "utilization": round(zone_data["occupied_count"] / max(zone_data["total_count"], 1), 3),
            }

        return jsonify({
            "room_id": room_id,
            "timestamp": data.get("timestamp"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "heatmap": heatmap,
        })

    @app.route("/api/rooms", methods=["GET"])
    def api_rooms():
        """Get list of active rooms and their status."""
        with _occupancy_lock:
            rooms = []
            for room_id, room_data in _occupancy_storage.items():
                seats = room_data.get("seats", {})
                rooms.append({
                    "room_id": room_id,
                    "last_update": room_data.get("timestamp"),
                    "seat_count": len(seats),
                    "occupied": sum(1 for s in seats.values() if s.get("is_occupied")),
                    "utilization": round(
                        sum(1 for s in seats.values() if s.get("is_occupied")) / max(len(seats), 1), 3
                    ),
                })

        return jsonify({"rooms": rooms})

    logger.info("HTTP fallback server starting on port %d", HTTP_FALLBACK_PORT)
    app.run(host="0.0.0.0", port=HTTP_FALLBACK_PORT, threaded=True, debug=False)

def _log_stats_periodically(interval: float = 30.0):
    while True:
        time.sleep(interval)

        with _occupancy_lock:
            room_count = len(_occupancy_storage)
            total_seats_known = sum(len(r.get("seats", {})) for r in _occupancy_storage.values())
            total_occupied = sum(
                sum(1 for s in r.get("seats", {}).values() if s.get("is_occupied"))
                for r in _occupancy_storage.values()
            )

        logger.info(
            "Stats | occupancy_received=%d mqtt_pub=%d influx=%d | "
            "rooms=%d seats=%d occupied=%d",
            _stats["occupancy_received"], _stats["mqtt_publishes"], _stats["influx_writes"],
            room_count, total_seats_known, total_occupied,
        )

def main():
    print("=" * 60)
    print("  LIBERTY TWIN - Edge Processor (Aggregator)")
    print("=" * 60)

    mqtt_ok = _init_mqtt()
    influx_ok = _init_influxdb()

    print()
    print(f"  MQTT:     {'CONNECTED' if mqtt_ok else 'UNAVAILABLE (using HTTP fallback)'}")
    print(f"  InfluxDB: {'CONNECTED' if influx_ok else 'UNAVAILABLE (writes disabled)'}")
    print(f"  HTTP API: http://0.0.0.0:{HTTP_FALLBACK_PORT}")
    print(f"  Seats:    {TOTAL_SEATS} across {len(ZONE_TO_SEATS)} zones")
    print(f"  Mode:     RPi receives pre-processed occupancy data")
    print("=" * 60)
    print()

    stats_thread = threading.Thread(target=_log_stats_periodically, daemon=True)
    stats_thread.start()

    def _shutdown(signum, frame):
        logger.info("Shutting down edge processor...")
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
