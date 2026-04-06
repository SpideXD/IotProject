"""
Flask HTTP server for RPi Simulator (per-room node).

Receives data from Unity (camera frames + detections, radar telemetry),
processes locally with RoomProcessor (sensor fusion, ghost detection, motion tracking),
and sends only seat occupancy to the central edge processor.

Endpoints:
- POST /api/camera - Receive camera frame + detections
- POST /api/telemetry - Receive radar telemetry
- GET  /api/status - Processing status
- GET  /api/occupancy - Current seat occupancy state
- GET  /api/alerts - Ghost detection alerts
- GET  /api/motion - Motion/dwell analytics
- GET  /api/heatmap - Zone heatmap data
- POST /api/reset - Reset seat state
- GET  /health - Health check
"""
import logging
import os
import signal
import sys
import threading
from typing import Any

from flask import Flask, jsonify, request
from flask_cors import CORS

from .config import LOG_FORMAT, LOG_LEVEL, RPI_HTTP_PORT, ROOM_ID
from .room_processor import RoomProcessor

# Configure logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
_log = logging.getLogger("rpi_simulator.http_server")

# Create Flask app
app = Flask(__name__)
CORS(app)

# Global room processor instance
_processor: RoomProcessor = None
_shutdown_event = threading.Event()


def init_app(room_id: str = None, edge_url: str = None) -> Flask:
    """Initialize the Flask app with RoomProcessor."""
    global _processor

    room_id = room_id or ROOM_ID
    edge_url = edge_url or os.environ.get(
        "EDGE_PROCESSOR_URL", "http://localhost:5002"
    )

    _processor = RoomProcessor(
        room_id=room_id,
        edge_url=edge_url,
        send_deltas=True,
    )

    _log.info(
        "RPi HTTP Server initialized for room '%s', edge: %s",
        room_id,
        edge_url,
    )

    return app


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "room_id": _processor.room_id if _processor else "uninitialized",
    })


@app.route("/api/status", methods=["GET"])
def status():
    """Return processing status."""
    if _processor is None:
        return jsonify({"error": "not initialized"}), 500

    return jsonify(_processor.status)


@app.route("/api/occupancy", methods=["GET"])
def occupancy():
    """Return current seat occupancy state."""
    if _processor is None:
        return jsonify({"error": "not initialized"}), 500

    return jsonify({
        "room_id": _processor.room_id,
        "seats": _processor.seat_state,
        "summary": _processor.get_occupancy_summary(),
    })


@app.route("/api/camera", methods=["POST"])
def camera():
    """
    Receive camera frame + detections from Unity.

    Expected JSON payload:
    {
        "sensor": "Rail_Back_001",
        "frame": "<base64 JPEG>",  # processed locally, NOT forwarded
        "detections": [
            {"cls": "person", "confidence": 1.0, "bbox": [x,y,x,y]},
            ...
        ]
    }

    Raw frame is processed locally for privacy.
    Only seat occupancy is forwarded to edge.
    """
    if _processor is None:
        return jsonify({"error": "not initialized"}), 500

    try:
        data = request.get_json(force=True)
    except Exception as e:
        _log.warning("Invalid JSON in camera request: %s", e)
        return jsonify({"error": "invalid JSON"}), 400

    # Validate required fields
    if "sensor" not in data:
        return jsonify({"error": "missing 'sensor' field"}), 400

    # Process frame locally (frame data stays here, not forwarded)
    result = _processor.process_camera_frame(data)

    return jsonify({
        "status": "processed",
        "room_id": _processor.room_id,
        "result": result,
    })


@app.route("/api/telemetry", methods=["POST"])
def telemetry():
    """
    Receive radar telemetry from Unity.

    Expected JSON payload:
    {
        "sensor": "Rail_Back_001",
        "presence": 0.8,
        "motion": 0.2,
        ...
    }
    """
    if _processor is None:
        return jsonify({"error": "not initialized"}), 500

    try:
        data = request.get_json(force=True)
    except Exception as e:
        _log.warning("Invalid JSON in telemetry request: %s", e)
        return jsonify({"error": "invalid JSON"}), 400

    if "sensor" not in data:
        return jsonify({"error": "missing 'sensor' field"}), 400

    result = _processor.process_telemetry(data)

    return jsonify({
        "status": "processed",
        "room_id": _processor.room_id,
        "result": result,
    })


@app.route("/api/reset", methods=["POST"])
def reset():
    """Reset seat state to all empty."""
    if _processor is None:
        return jsonify({"error": "not initialized"}), 500

    _processor.reset()

    return jsonify({"status": "reset", "room_id": _processor.room_id})


@app.route("/api/alerts", methods=["GET"])
def alerts():
    """
    Get local ghost detection alerts from this RPi.

    Returns recent alerts from the ghost detection FSM.
    """
    if _processor is None:
        return jsonify({"error": "not initialized"}), 500

    limit = request.args.get("limit", 50, type=int)
    return jsonify({
        "room_id": _processor.room_id,
        "alerts": _processor.get_recent_alerts(limit=limit),
    })


@app.route("/api/motion", methods=["GET"])
def motion():
    """
    Get motion and dwell time analytics from this RPi.

    Returns motion tracking summary per seat.
    """
    if _processor is None:
        return jsonify({"error": "not initialized"}), 500

    return jsonify({
        "room_id": _processor.room_id,
        "motion": _processor.get_motion_summary(),
    })


@app.route("/api/heatmap", methods=["GET"])
def heatmap():
    """
    Get zone heatmap data from this RPi.

    Returns occupancy percentage per zone for heatmap visualization.
    """
    if _processor is None:
        return jsonify({"error": "not initialized"}), 500

    seats = _processor.seat_state
    heatmap_data = {}

    for zone in ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7"]:
        zone_seats = [s for s in seats.values() if s["zone_id"] == zone]
        occupied = sum(1 for s in zone_seats if s["is_occupied"])
        total = len(zone_seats)
        heatmap_data[zone] = {
            "occupied": occupied,
            "total": total,
            "percentage": round(occupied / max(total, 1) * 100, 1),
        }

    return jsonify({
        "room_id": _processor.room_id,
        "heatmap": heatmap_data,
    })


def run_server(
    host: str = "0.0.0.0",
    port: int = None,
    room_id: str = None,
    edge_url: str = None,
):
    """
    Start the Flask HTTP server.

    Args:
        host: Bind address (default: 0.0.0.0)
        port: HTTP port (default: from config)
        room_id: Room identifier (default: from config)
        edge_url: Central edge processor URL (default: from config)
    """
    global _processor

    port = port or RPI_HTTP_PORT
    room_id = room_id or ROOM_ID
    edge_url = edge_url or os.environ.get(
        "EDGE_PROCESSOR_URL", "http://localhost:5002"
    )

    init_app(room_id=room_id, edge_url=edge_url)

    def shutdown_handler(signum, frame):
        _log.info("Shutdown signal received, stopping server...")
        _shutdown_event.set()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    _log.info(
        "Starting RPi HTTP Server on %s:%d (room: %s)",
        host,
        port,
        room_id,
    )

    app.run(
        host=host,
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False,
    )
