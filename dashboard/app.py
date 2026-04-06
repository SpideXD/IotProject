
import base64
import csv
import io
import json
import logging
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template, request, Response
from flask_cors import CORS
from flask_socketio import SocketIO

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("liberty-twin-dashboard")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET", "liberty-twin-secret-key")
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# Multi-room support
state = {
    "current_room": "room_1",
    "rooms": {},  # room_id -> {seats, zones, stats, alerts, history}
    "sensors": {},
    "zones": {},
    "seats": {},
    "alerts": [],
    "alert_acks": {},  # alert_id -> {user_id, timestamp, snoozed_until}
    "stats": {
        "occupied": 0,
        "empty": 0,
        "ghost": 0,
        "suspected": 0,
        "total_scans": 0,
        "utilization": 0.0,
    },
    "camera_frames": {},
    "history": [],
    "theme": "dark",  # dark or light
    "sound_enabled": True,
}
state_lock = threading.Lock()

HISTORY_MAX = 3600

_last_history_ts = 0

# Room definitions
ROOM_CONFIGS = {
    "room_1": {"name": "Main Library", "zones": 7},
    "room_2": {"name": "Study Hall", "zones": 4},
    "room_3": {"name": "Reference Section", "zones": 3},
}

def _maybe_record_history():
    global _last_history_ts
    now = time.time()
    if now - _last_history_ts < 5:
        return
    _last_history_ts = now
    point = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "room_id": state["current_room"],
        "occupied": state["stats"]["occupied"],
        "empty": state["stats"]["empty"],
        "ghost": state["stats"]["ghost"],
        "suspected": state["stats"]["suspected"],
        "total": state["stats"]["occupied"] + state["stats"]["empty"]
                 + state["stats"]["ghost"] + state["stats"]["suspected"],
    }
    state["history"].append(point)
    if len(state["history"]) > HISTORY_MAX:
        state["history"] = state["history"][-HISTORY_MAX:]


def _generate_alert_id() -> str:
    """Generate unique alert ID."""
    return str(uuid.uuid4())[:12]

def _recompute_stats():
    counts = {"occupied": 0, "empty": 0, "ghost": 0, "suspected": 0}
    for seat in state["seats"].values():
        s = seat.get("state", "empty")
        if s in counts:
            counts[s] += 1
    total = sum(counts.values()) or 1
    state["stats"].update(counts)
    state["stats"]["utilization"] = round(counts["occupied"] / total * 100, 1)
    _maybe_record_history()

mqtt_client = None
mqtt_connected = False
_mqtt_reconnect_delay = 1

def _start_mqtt():
    global mqtt_client, mqtt_connected
    try:
        import paho.mqtt.client as paho_mqtt

        broker_host = os.environ.get("MQTT_HOST", "localhost")
        broker_port = int(os.environ.get("MQTT_PORT", 1883))

        def on_connect(client, userdata, flags, reason_code, properties=None):
            global mqtt_connected, _mqtt_reconnect_delay
            mqtt_connected = True
            _mqtt_reconnect_delay = 1
            log.info("MQTT connected to %s:%s", broker_host, broker_port)
            client.subscribe("liberty_twin/state/#")
            client.subscribe("liberty_twin/alerts/#")
            client.subscribe("liberty_twin/sensor/+/camera")

        def on_disconnect(client, userdata, flags, reason_code, properties=None):
            global mqtt_connected, mqtt_client, _mqtt_reconnect_delay
            mqtt_connected = False
            delay = _mqtt_reconnect_delay
            _mqtt_reconnect_delay = min(_mqtt_reconnect_delay * 2, 30)
            log.warning("MQTT disconnected (rc=%s), reconnecting in %ds...", reason_code, delay)
            import threading
            def _reconnect():
                import time
                time.sleep(delay)
                try:
                    if mqtt_client:
                        mqtt_client.reconnect()
                except Exception as exc:
                    log.warning("Reconnect failed: %s", exc)
            threading.Thread(target=_reconnect, daemon=True).start()

        def on_message(client, userdata, msg):
            topic = msg.topic
            try:
                if topic.endswith("/camera"):
                    parts = topic.split("/")
                    sensor_id = parts[2] if len(parts) >= 4 else "unknown"
                    frame_b64 = base64.b64encode(msg.payload).decode("ascii")
                    with state_lock:
                        state["camera_frames"][sensor_id] = frame_b64
                    socketio.emit("camera_frame", {
                        "sensor_id": sensor_id,
                        "image": frame_b64,
                    })
                    return

                payload = json.loads(msg.payload.decode())

                if topic.startswith("liberty_twin/state/"):
                    _handle_state_message(topic, payload)
                elif topic.startswith("liberty_twin/alerts/"):
                    _handle_alert_message(topic, payload)

            except Exception as exc:
                log.error("Error processing MQTT message on %s: %s", topic, exc)

        client = paho_mqtt.Client(
            paho_mqtt.CallbackAPIVersion.VERSION2,
            client_id="liberty-twin-dashboard",
        )
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message

        client.connect_async(broker_host, broker_port, keepalive=60)
        client.loop_start()
        mqtt_client = client
        log.info("MQTT client started (connecting to %s:%s)", broker_host, broker_port)
    except Exception as exc:
        log.warning("MQTT not available, running in HTTP-only mode: %s", exc)

def _handle_state_message(topic, payload):
    with state_lock:
        # Handle individual seat state messages from MQTT
        # Topic: liberty_twin/state/seat/{seat_id}
        if "seat_id" in payload and topic.startswith("liberty_twin/state/seat/"):
            seat_id = payload["seat_id"]
            zone_name = payload.get("zone_id", payload.get("zone", ""))
            seat_info = {
                "seat_id": seat_id,
                "zone": zone_name,
                "state": payload.get("state", "empty"),
                "occupancy_score": payload.get("occupancy_score", 0.0),
                "object_type": payload.get("object_type", "empty"),
                "confidence": payload.get("confidence", 0.0),
                "is_present": payload.get("is_present", False),
                "has_motion": payload.get("has_motion", False),
                "radar_presence": payload.get("radar_presence", 0.0),
                "radar_motion": payload.get("radar_motion", 0.0),
                "timestamp": payload.get("timestamp", time.time()),
                "source_room": payload.get("source_room", state["current_room"]),
            }
            state["seats"][seat_id] = seat_info
            if zone_name and zone_name not in state["zones"]:
                state["zones"][zone_name] = {"name": zone_name, "occupied": 0, "total": 0, "seats": {}}
            if zone_name and zone_name in state["zones"]:
                state["zones"][zone_name]["seats"][seat_id] = seat_info
            _recompute_stats()
            socketio.emit("seat_state", {
                "seats": {sid: sdata for sid, sdata in state["seats"].items()},
            })
            socketio.emit("stats", state["stats"])
            return

        if "sensor_id" in payload:
            sid = payload["sensor_id"]
            state["sensors"][sid] = {
                "status": payload.get("status", "online"),
                "zone": payload.get("zone", ""),
                "last_seen": datetime.now(timezone.utc).isoformat(),
            }
            socketio.emit("sensor_status", {
                "sensor_id": sid,
                **state["sensors"][sid],
            })

        if "zone" in payload and "seats" in payload:
            zone_name = payload["zone"]
            seats_data = payload["seats"]
            state["zones"][zone_name] = {
                "name": zone_name,
                "occupied": sum(1 for s in seats_data if s.get("state") == "occupied"),
                "total": len(seats_data),
                "seats": {s["id"]: s for s in seats_data},
            }
            for s in seats_data:
                state["seats"][s["id"]] = {**s, "zone": zone_name}

            _recompute_stats()
            state["stats"]["total_scans"] = state["stats"].get("total_scans", 0) + 1

            socketio.emit("telemetry", {
                "zone": zone_name,
                "zone_data": state["zones"][zone_name],
                "stats": state["stats"],
            })
            socketio.emit("stats", state["stats"])
            socketio.emit("seat_state", {
                "seats": {sid: sdata for sid, sdata in state["seats"].items()},
            })

def _handle_alert_message(topic, payload):
    with state_lock:
        alert_id = _generate_alert_id()
        alert = {
            "id": alert_id,
            "type": payload.get("type", "ghost"),
            "message": payload.get("message", "Unknown alert"),
            "seat_id": payload.get("seat_id", ""),
            "zone": payload.get("zone", ""),
            "countdown": payload.get("countdown", 0),
            "timestamp": payload.get(
                "timestamp", datetime.now(timezone.utc).isoformat()
            ),
            "acknowledged": False,
            "snoozed_until": None,
            "source_room": payload.get("source_room", state["current_room"]),
        }
        state["alerts"].insert(0, alert)
        state["alerts"] = state["alerts"][:200]

    socketio.emit("ghost_alert", alert)

    # Emit sound notification if enabled
    if state["sound_enabled"]:
        socketio.emit("play_alert_sound", {"type": alert["type"], "alert_id": alert_id})

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/telemetry", methods=["POST"])
def api_telemetry():
    payload = request.get_json(force=True)
    _handle_state_message("liberty_twin/state/http", payload)
    return jsonify({"status": "ok"})

@app.route("/api/camera", methods=["POST"])
def api_camera():
    payload = request.get_json(force=True)
    sensor_id = payload.get("sensor_id") or payload.get("sensor", "unknown")
    image_b64 = payload.get("image") or payload.get("frame", "")
    with state_lock:
        state["camera_frames"][sensor_id] = image_b64
    socketio.emit("camera_frame", {"sensor_id": sensor_id, "image": image_b64})
    return jsonify({"status": "ok"})

@app.route("/api/status", methods=["POST"])
def api_status():
    payload = request.get_json(force=True)
    sid = payload.get("sensor_id", "unknown")
    with state_lock:
        state["sensors"][sid] = {
            "status": payload.get("status", "online"),
            "zone": payload.get("zone", ""),
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }
    socketio.emit("sensor_status", {"sensor_id": sid, **state["sensors"][sid]})
    return jsonify({"status": "ok"})

@app.route("/api/seat_state", methods=["POST"])
def api_seat_state():
    """Receive processed seat state from edge (fallback when MQTT is down)."""
    payload = request.get_json(force=True)
    _handle_state_message("liberty_twin/state/http", payload)
    return jsonify({"status": "ok"})

@app.route("/api/alert", methods=["POST"])
def api_alert():
    payload = request.get_json(force=True)
    _handle_alert_message("liberty_twin/alerts/http", payload)
    return jsonify({"status": "ok"})

@app.route("/api/history", methods=["GET"])
def api_history():
    minutes = int(request.args.get("minutes", 60))
    room_filter = request.args.get("room")
    with state_lock:
        history = state.get("history", [])
        if room_filter:
            history = [p for p in history if p.get("room_id") == room_filter]
        return jsonify(history)


@app.route("/api/state", methods=["GET"])
def api_state():
    with state_lock:
        return jsonify({
            "sensors": state["sensors"],
            "zones": state["zones"],
            "seats": state["seats"],
            "stats": state["stats"],
            "alerts": state["alerts"][:20],
            "current_room": state["current_room"],
            "rooms": ROOM_CONFIGS,
            "theme": state["theme"],
            "sound_enabled": state["sound_enabled"],
        })


# =============================================================================
# Alert Management
# =============================================================================

@app.route("/api/alerts", methods=["GET"])
def api_alerts():
    """Get all alerts with optional filtering."""
    include_acked = request.args.get("include_acked", "true").lower() == "true"
    alert_type = request.args.get("type")
    room_filter = request.args.get("room")

    with state_lock:
        alerts = state["alerts"]

        if not include_acked:
            alerts = [a for a in alerts if not _is_alert_acknowledged(a["id"])]

        if alert_type:
            alerts = [a for a in alerts if a.get("type") == alert_type]

        if room_filter:
            alerts = [a for a in alerts if a.get("source_room") == room_filter]

        return jsonify({
            "alerts": alerts[:50],
            "total": len(alerts),
            "acknowledged_count": sum(1 for a in state["alerts"] if _is_alert_acknowledged(a["id"])),
        })


@app.route("/api/alerts/<alert_id>/acknowledge", methods=["POST"])
def api_acknowledge_alert(alert_id):
    """Acknowledge an alert."""
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id", "unknown")

    with state_lock:
        if alert_id in state["alert_acks"]:
            return jsonify({"status": "already_acknowledged", "alert_id": alert_id})

        state["alert_acks"][alert_id] = {
            "user_id": user_id,
            "timestamp": time.time(),
            "snoozed_until": None,
        }

        # Mark alert as acknowledged
        for alert in state["alerts"]:
            if alert["id"] == alert_id:
                alert["acknowledged"] = True
                break

    socketio.emit("alert_acknowledged", {
        "alert_id": alert_id,
        "user_id": user_id,
    })

    return jsonify({"status": "acknowledged", "alert_id": alert_id})


@app.route("/api/alerts/<alert_id>/snooze", methods=["POST"])
def api_snooze_alert(alert_id):
    """Snooze an alert for a specified duration."""
    data = request.get_json(force=True) or {}
    duration = int(data.get("duration", 300))  # Default 5 minutes
    user_id = data.get("user_id", "unknown")

    snooze_until = time.time() + duration

    with state_lock:
        existing = state["alert_acks"].get(alert_id, {})
        state["alert_acks"][alert_id] = {
            "user_id": user_id,
            "timestamp": existing.get("timestamp", time.time()),
            "snoozed_until": snooze_until,
        }

        # Mark alert as snoozed
        for alert in state["alerts"]:
            if alert["id"] == alert_id:
                alert["snoozed_until"] = snooze_until
                break

    socketio.emit("alert_snoozed", {
        "alert_id": alert_id,
        "snoozed_until": snooze_until,
        "duration": duration,
    })

    return jsonify({
        "status": "snoozed",
        "alert_id": alert_id,
        "snoozed_until": snooze_until,
    })


@app.route("/api/alerts/<alert_id>/resolve", methods=["POST"])
def api_resolve_alert(alert_id):
    """Resolve/dismiss an alert."""
    data = request.get_json(force=True) or {}
    user_id = data.get("user_id", "unknown")

    with state_lock:
        # Remove the alert
        state["alerts"] = [a for a in state["alerts"] if a["id"] != alert_id]
        if alert_id in state["alert_acks"]:
            del state["alert_acks"][alert_id]

    socketio.emit("alert_resolved", {
        "alert_id": alert_id,
        "user_id": user_id,
    })

    return jsonify({"status": "resolved", "alert_id": alert_id})


def _is_alert_acknowledged(alert_id) -> bool:
    """Check if alert is currently acknowledged."""
    ack = state["alert_acks"].get(alert_id)
    if not ack:
        return False
    # Check if snoozed
    if ack.get("snoozed_until"):
        if time.time() < ack["snoozed_until"]:
            return True  # Snoozed counts as acknowledged
    return True


# =============================================================================
# Theme & Settings
# =============================================================================

@app.route("/api/settings/theme", methods=["POST"])
def api_set_theme():
    """Set dashboard theme."""
    data = request.get_json(force=True) or {}
    theme = data.get("theme", "dark")

    if theme not in ("dark", "light"):
        return jsonify({"error": "Invalid theme. Use 'dark' or 'light'."}), 400

    with state_lock:
        state["theme"] = theme

    socketio.emit("theme_changed", {"theme": theme})

    return jsonify({"status": "ok", "theme": theme})


@app.route("/api/settings/sound", methods=["POST"])
def api_set_sound():
    """Enable/disable alert sounds."""
    data = request.get_json(force=True) or {}
    enabled = bool(data.get("enabled", True))

    with state_lock:
        state["sound_enabled"] = enabled

    return jsonify({"status": "ok", "sound_enabled": enabled})


# =============================================================================
# Room Selection (Multi-Room Support)
# =============================================================================

@app.route("/api/rooms", methods=["GET"])
def api_rooms():
    """Get available rooms."""
    return jsonify({
        "rooms": ROOM_CONFIGS,
        "current_room": state["current_room"],
    })


@app.route("/api/rooms/<room_id>/select", methods=["POST"])
def api_select_room(room_id):
    """Switch to a different room."""
    if room_id not in ROOM_CONFIGS:
        return jsonify({"error": "Room not found"}), 404

    with state_lock:
        old_room = state["current_room"]
        state["current_room"] = room_id

        # Reset seat/zone state for new room
        state["seats"] = {}
        state["zones"] = {}
        state["stats"] = {
            "occupied": 0,
            "empty": 0,
            "ghost": 0,
            "suspected": 0,
            "total_scans": 0,
            "utilization": 0.0,
        }

    socketio.emit("room_changed", {
        "old_room": old_room,
        "new_room": room_id,
        "room_config": ROOM_CONFIGS[room_id],
    })

    return jsonify({
        "status": "ok",
        "current_room": room_id,
        "room_config": ROOM_CONFIGS[room_id],
    })


# =============================================================================
# Data Export
# =============================================================================

@app.route("/api/export/history", methods=["GET"])
def api_export_history():
    """Export history data as CSV."""
    minutes = int(request.args.get("minutes", 60))
    format_type = request.args.get("format", "csv")

    with state_lock:
        history = state.get("history", [])

    cutoff = time.time() - (minutes * 60)
    filtered = [
        p for p in history
        if datetime.fromisoformat(p["ts"]).timestamp() > cutoff
    ]

    if format_type == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["timestamp", "room_id", "occupied", "empty", "ghost", "suspected", "total"])
        writer.writeheader()
        for p in filtered:
            writer.writerow({
                "timestamp": p["ts"],
                "room_id": p.get("room_id", ""),
                "occupied": p.get("occupied", 0),
                "empty": p.get("empty", 0),
                "ghost": p.get("ghost", 0),
                "suspected": p.get("suspected", 0),
                "total": p.get("total", 0),
            })

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename=occupancy_history_{int(time.time())}.csv"},
        )

    elif format_type == "json":
        return jsonify({
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "minutes": minutes,
            "records": len(filtered),
            "data": filtered,
        })

    return jsonify({"error": "Unsupported format. Use 'csv' or 'json'."}), 400


@app.route("/api/export/seats", methods=["GET"])
def api_export_seats():
    """Export current seat states as CSV."""
    with state_lock:
        seats = state.get("seats", {})

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=["seat_id", "zone", "state", "occupancy_score", "object_type", "confidence", "radar_presence", "has_motion"])
    writer.writeheader()
    for seat_id, s in seats.items():
        writer.writerow({
            "seat_id": seat_id,
            "zone": s.get("zone", ""),
            "state": s.get("state", "empty"),
            "occupancy_score": s.get("occupancy_score", 0),
            "object_type": s.get("object_type", ""),
            "confidence": s.get("confidence", 0),
            "radar_presence": s.get("radar_presence", 0),
            "has_motion": s.get("has_motion", False),
        })

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename=seat_states_{int(time.time())}.csv"},
    )


# =============================================================================
# Analytics
# =============================================================================

@app.route("/api/analytics/summary", methods=["GET"])
def api_analytics_summary():
    """Get occupancy analytics summary."""
    with state_lock:
        history = state.get("history", [])
        seats = state.get("seats", {})

    # Calculate statistics from history
    if len(history) < 2:
        return jsonify({
            "error": "Not enough history data",
            "data_points": len(history),
        })

    occupied_values = [p.get("occupied", 0) for p in history]
    utilization_values = [
        (p.get("occupied", 0) / p.get("total", 1) * 100) if p.get("total", 0) > 0 else 0
        for p in history
    ]

    # Peak occupancy
    peak_occupied = max(occupied_values) if occupied_values else 0
    peak_time = None
    for p in history:
        if p.get("occupied", 0) == peak_occupied:
            peak_time = p.get("ts")
            break

    # Average utilization
    avg_utilization = sum(utilization_values) / len(utilization_values) if utilization_values else 0

    # Current state counts
    current_states = {"occupied": 0, "empty": 0, "ghost": 0, "suspected": 0}
    for s in seats.values():
        st = s.get("state", "empty")
        if st in current_states:
            current_states[st] += 1

    return jsonify({
        "current": current_states,
        "peak_occupancy": {
            "count": peak_occupied,
            "timestamp": peak_time,
        },
        "average_utilization_pct": round(avg_utilization, 1),
        "history_duration_minutes": len(history) * 5 // 60,  # Approximate
        "data_points": len(history),
    })

@socketio.on("connect")
def handle_connect():
    log.info("Browser client connected")
    with state_lock:
        socketio.emit("stats", state["stats"])
        socketio.emit("seat_state", {"seats": state["seats"]})
        for zone_name, zone_data in state["zones"].items():
            socketio.emit("telemetry", {
                "zone": zone_name,
                "zone_data": zone_data,
                "stats": state["stats"],
            })
        for sid, sdata in state["sensors"].items():
            socketio.emit("sensor_status", {"sensor_id": sid, **sdata})
        for alert in state["alerts"][:20]:
            socketio.emit("ghost_alert", alert)
        for sid, frame in state["camera_frames"].items():
            socketio.emit("camera_frame", {"sensor_id": sid, "image": frame})

@socketio.on("request_history")
def handle_history_request(data):
    minutes = data.get("minutes", 60) if data else 60
    room_filter = data.get("room") if data else None
    with state_lock:
        cutoff = time.time() - minutes * 60
        history = [
            p for p in state["history"]
            if datetime.fromisoformat(p["ts"]).timestamp() > cutoff
        ]
        if room_filter:
            history = [p for p in history if p.get("room_id") == room_filter]
    socketio.emit("history_data", history)

if __name__ == "__main__":
    _start_mqtt()
    port = int(os.environ.get("PORT", 5000))
    log.info("Starting Liberty Twin Dashboard on port %s", port)
    socketio.run(app, host="0.0.0.0", port=port, debug=False, allow_unsafe_werkzeug=True)
