"""
RoomProcessor - Core class for per-room seat occupancy processing.

Receives camera frames + detections from Unity, maps to seat IDs,
applies sensor fusion with radar, runs ghost detection FSM, tracks motion,
and sends delta-compressed occupancy to edge.

This runs on the RPi - raw data stays local, only occupancy goes to edge.
"""
import base64
import hashlib
import json
import logging
import time
import threading
from io import BytesIO
from typing import Any, Dict, List, Optional

import requests
from PIL import Image

try:
    from .config import (
        EDGE_PROCESSOR_URL,
        MIN_OCCUPANCY_CONFIDENCE,
        ROOM_ID,
        SEAT_TO_ZONE,
        SEND_DELTAS_ONLY,
        SENSOR_TO_ZONE,
        TOTAL_SEATS,
        USE_STATE_HASHING,
        ZONE_TO_SEATS,
        CAMERA_WEIGHT,
        RADAR_WEIGHT,
        AGREEMENT_BONUS,
        PRESENCE_THRESHOLD,
        MOTION_THRESHOLD,
        GHOST_GRACE_PERIOD,
        GHOST_THRESHOLD,
        YOLO_MODEL_PATH,
        YOLO_CONFIDENCE,
        YOLO_IOU_THRESHOLD,
        YOLO_IMAGE_SIZE,
    )
    from .sensor_fusion import SensorFusion, CameraResult, RadarResult, FusedResult
    from .ghost_detector import GhostDetector, GhostAlert
    from .motion_tracker import MotionTracker
except ImportError:
    from config import (
        EDGE_PROCESSOR_URL,
        MIN_OCCUPANCY_CONFIDENCE,
        ROOM_ID,
        SEAT_TO_ZONE,
        SEND_DELTAS_ONLY,
        SENSOR_TO_ZONE,
        TOTAL_SEATS,
        USE_STATE_HASHING,
        ZONE_TO_SEATS,
        CAMERA_WEIGHT,
        RADAR_WEIGHT,
        AGREEMENT_BONUS,
        PRESENCE_THRESHOLD,
        MOTION_THRESHOLD,
        GHOST_GRACE_PERIOD,
        GHOST_THRESHOLD,
        YOLO_MODEL_PATH,
        YOLO_CONFIDENCE,
        YOLO_IOU_THRESHOLD,
        YOLO_IMAGE_SIZE,
    )
    from sensor_fusion import SensorFusion, CameraResult, RadarResult, FusedResult
    from ghost_detector import GhostDetector, GhostAlert
    from motion_tracker import MotionTracker

# YOLO inference
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

_log = logging.getLogger("rpi_simulator.room_processor")

if not YOLO_AVAILABLE:
    _log.warning("Ultralytics YOLO not available, using Unity detections")


class RoomProcessor:
    """
    Per-room processor that:
    - Receives camera frames + detections from Unity
    - Maps detections to seat IDs using zone-based mapping
    - Caches radar telemetry for sensor fusion
    - Applies full sensor fusion (60% camera + 40% radar)
    - Runs ghost detection FSM locally
    - Tracks motion and dwell time
    - Applies delta compression (only sends on change)
    - Forwards only seat occupancy to central edge processor
    """

    def __init__(
        self,
        room_id: str = None,
        edge_url: str = None,
        send_deltas: bool = True,
    ):
        self.room_id = room_id or ROOM_ID
        self.edge_url = edge_url or EDGE_PROCESSOR_URL
        self.send_deltas = send_deltas

        # Initialize sensor fusion, ghost detector, motion tracker
        self._fusion = SensorFusion(
            camera_weight=CAMERA_WEIGHT,
            radar_weight=RADAR_WEIGHT,
            agreement_bonus=AGREEMENT_BONUS,
            presence_threshold=PRESENCE_THRESHOLD,
        )
        self._ghost_detector = GhostDetector(
            grace_period=GHOST_GRACE_PERIOD,
            ghost_threshold=GHOST_THRESHOLD,
            presence_threshold=PRESENCE_THRESHOLD,
            motion_threshold=MOTION_THRESHOLD,
        )
        self._motion_tracker = MotionTracker()

        # YOLO model for real-time inference
        self._yolo_model = None
        self._yolo_lock = threading.Lock()
        if YOLO_AVAILABLE:
            self._init_yolo()

        # Current seat occupancy state
        self._seat_state: dict[str, dict[str, Any]] = {}
        self._last_sent_hash: str = ""
        self._state_lock = threading.Lock()

        # Radar telemetry cache (from process_telemetry)
        self._radar_cache: dict[str, dict] = {}
        self._radar_lock = threading.Lock()

        # Stats
        self.frames_received = 0
        self.occupancy_sent = 0
        self.last_occupancy_sent_time = 0

        # Initialize default seat state
        self._init_seat_state()

        _log.info(
            "RoomProcessor initialized for %s, edge: %s, deltas: %s, YOLO: %s",
            self.room_id,
            self.edge_url,
            self.send_deltas,
            "loaded" if self._yolo_model else "disabled",
        )

    def _init_yolo(self):
        """Load the trained YOLO model for inference."""
        global YOLO_AVAILABLE
        try:
            import os
            if not os.path.exists(YOLO_MODEL_PATH):
                _log.warning(
                    "[YOLO] Model not found at %s, falling back to Unity detections",
                    YOLO_MODEL_PATH
                )
                YOLO_AVAILABLE = False
                return

            self._yolo_model = YOLO(YOLO_MODEL_PATH)
            _log.info("[YOLO] Loaded trained model from %s", YOLO_MODEL_PATH)
        except Exception as e:
            _log.error("[YOLO] Failed to load model: %s", e)
            self._yolo_model = None
            YOLO_AVAILABLE = False

    def _run_yolo_inference(self, frame_data: str) -> List[Dict[str, Any]]:
        """
        Run YOLO inference on a base64-encoded frame.

        Args:
            frame_data: Base64-encoded JPEG image

        Returns:
            List of detections with format:
            [{"cls": "person", "confidence": 0.95, "bbox": [x_min, y_min, x_max, y_max]}, ...]
        """
        if self._yolo_model is None:
            return []

        try:
            # Decode base64 image
            image_bytes = base64.b64decode(frame_data)
            pil_image = Image.open(BytesIO(image_bytes)).convert("RGB")

            # Run inference
            with self._yolo_lock:
                results = self._yolo_model.predict(
                    source=pil_image,
                    conf=YOLO_CONFIDENCE,
                    iou=YOLO_IOU_THRESHOLD,
                    imgsz=YOLO_IMAGE_SIZE,
                    verbose=False,
                )

            # Parse results
            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is None:
                    continue

                for box in boxes:
                    # Get box coordinates [x_min, y_min, x_max, y_max] in normalized format
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])

                    # Map class ID to class name
                    cls_name = result.names.get(cls_id, "unknown")

                    detections.append({
                        "cls": cls_name,
                        "confidence": conf,
                        "bbox": [x1, y1, x2, y2],
                    })

            _log.debug(
                "[%s] YOLO inference: %d detections",
                self.room_id,
                len(detections),
            )
            return detections

        except Exception as e:
            _log.error("[%s] YOLO inference failed: %s", self.room_id, e)
            return []

    def _init_seat_state(self):
        """Initialize all seats to empty state with extended fields."""
        for seat_id, zone_id in SEAT_TO_ZONE.items():
            self._seat_state[seat_id] = {
                "zone_id": zone_id,
                "is_occupied": False,
                "object_type": None,
                "confidence": 0.0,
                "has_motion": False,
                "radar_presence": 0.0,
                "radar_motion": 0.0,
                "source": None,
                # Fusion + Ghost + Motion fields (set during processing)
                "is_present": False,
                "occupancy_score": 0.0,
                "ghost_state": "empty",
                "dwell_time": 0.0,
                "time_since_motion": 0.0,
            }

    @property
    def seat_state(self) -> dict[str, dict[str, Any]]:
        """Return current seat state (thread-safe copy)."""
        with self._state_lock:
            return dict(self._seat_state)

    @property
    def status(self) -> dict[str, Any]:
        """Return processing status."""
        return {
            "room_id": self.room_id,
            "frames_received": self.frames_received,
            "occupancy_sent": self.occupancy_sent,
            "last_sent": self.last_occupancy_sent_time,
            "edge_url": self.edge_url,
            "seats_occupied": sum(
                1 for s in self._seat_state.values() if s["is_occupied"]
            ),
            "yolo_available": self._yolo_model is not None,
            "yolo_model_path": YOLO_MODEL_PATH if self._yolo_model else None,
        }

    def process_camera_frame(self, data: dict) -> dict[str, Any]:
        """
        Process camera frame with detections from Unity.

        Expected data format:
        {
            "sensor": "Rail_Back_001",
            "frame": "<base64 JPEG>",  # processed locally with YOLO inference
            "detections": [{"cls": "person", "confidence": 1.0, "bbox": [x,y,x,y]}]  # fallback if YOLO unavailable
        }

        If YOLO model is loaded, runs real-time inference on the frame.
        Otherwise, falls back to Unity's ground truth detections.

        Returns processing result.
        """
        sensor_name = data.get("sensor", "unknown")
        frame_data = data.get("frame")  # base64 encoded JPEG
        unity_detections = data.get("detections", [])

        # Use zone from payload if provided (Unity now sends it directly)
        # Otherwise fall back to SENSOR_TO_ZONE mapping
        zone_id = data.get("zone") or data.get("zone_id")
        if not zone_id:
            zone_id = SENSOR_TO_ZONE.get(sensor_name)
        if not zone_id:
            _log.warning("Unknown sensor %s, cannot map to zone", sensor_name)
            return {"status": "unknown_sensor", "sensor": sensor_name}

        self.frames_received += 1

        # Run YOLO inference if model is loaded
        detections = []
        inference_method = "unity_gt"

        if self._yolo_model is not None and frame_data:
            detections = self._run_yolo_inference(frame_data)
            inference_method = "yolo"
            _log.debug(
                "[%s] Camera frame from %s (zone %s): YOLO=%d detections",
                self.room_id,
                sensor_name,
                zone_id,
                len(detections),
            )
        else:
            # Fall back to Unity ground truth detections
            detections = unity_detections
            inference_method = "unity_gt"
            _log.debug(
                "[%s] Camera frame from %s (zone %s): Unity=%d detections",
                self.room_id,
                sensor_name,
                zone_id,
                len(detections),
            )

        # Convert detections to seat occupancy
        self._update_seats_from_detections(zone_id, detections)

        # Apply sensor fusion + ghost detection + motion tracking
        alerts = self._apply_sensor_fusion(zone_id)

        # Send occupancy to edge
        result = self._maybe_send_occupancy()
        if alerts:
            result["alerts"] = len(alerts)
        return result

    def process_telemetry(self, data: dict) -> dict[str, Any]:
        """
        Process radar telemetry from Unity.

        Expected data format:
        {
            "sensor": "Rail_Back_001",
            "presence": 0.8,
            "motion": 0.2,
            "micro_motion": False,
        }
        """
        sensor_name = data.get("sensor", "unknown")

        # Use zone from payload if provided (Unity now sends it directly)
        # Otherwise fall back to SENSOR_TO_ZONE mapping
        zone_id = data.get("zone") or data.get("zone_id")
        if not zone_id:
            zone_id = SENSOR_TO_ZONE.get(sensor_name)

        with self._radar_lock:
            self._radar_cache[sensor_name] = {
                "presence": data.get("presence", 0.0),
                "motion": data.get("motion", 0.0),
                "timestamp": time.time(),
                "zone_id": zone_id,  # Store zone with radar data
            }

        _log.debug(
            "[%s] Telemetry from %s (zone %s): presence=%.2f, motion=%.2f",
            self.room_id,
            sensor_name,
            zone_id,
            data.get("presence", 0.0),
            data.get("motion", 0.0),
        )

        if not zone_id:
            _log.warning("Unknown sensor %s, cannot map to zone", sensor_name)
            return {"status": "unknown_sensor", "sensor": sensor_name}
        if zone_id:
            # Apply sensor fusion with new radar data
            alerts = self._apply_sensor_fusion(zone_id)
            result = self._maybe_send_occupancy()
            if alerts:
                result["alerts"] = len(alerts)
            return result

        return self._maybe_send_occupancy()

    def _update_seats_from_detections(
        self, zone_id: str, detections: list[dict]
    ):
        """
        Map bounding box detections to seat IDs within a zone.

        Zone-based mapping: each zone has 4 seats.
        Detections are mapped based on horizontal position (left-to-right).
        """
        zone_seats = ZONE_TO_SEATS.get(zone_id, [])

        # Reset all seats in this zone first
        for seat_id in zone_seats:
            self._seat_state[seat_id]["is_occupied"] = False
            self._seat_state[seat_id]["object_type"] = None
            self._seat_state[seat_id]["confidence"] = 0.0
            self._seat_state[seat_id]["source"] = "camera"

        # Filter for persons and objects of interest
        person_detections = [d for d in detections if d.get("cls") == "person"]
        object_detections = [
            d for d in detections if d.get("cls") != "person"
        ]

        # Map person detections to seats (one person per seat max)
        seat_idx = 0
        for det in person_detections:
            if seat_idx >= len(zone_seats):
                break  # More persons than seats

            seat_id = zone_seats[seat_idx]
            confidence = det.get("confidence", 0.0)

            if confidence >= MIN_OCCUPANCY_CONFIDENCE:
                self._seat_state[seat_id]["is_occupied"] = True
                self._seat_state[seat_id]["object_type"] = det.get("cls", "person")
                self._seat_state[seat_id]["confidence"] = confidence
                seat_idx += 1

        # Map remaining seats with other objects
        for det in object_detections:
            if seat_idx >= len(zone_seats):
                break
            seat_id = zone_seats[seat_idx]
            confidence = det.get("confidence", 0.0)
            if confidence >= MIN_OCCUPANCY_CONFIDENCE:
                self._seat_state[seat_id]["is_occupied"] = True
                self._seat_state[seat_id]["object_type"] = det.get("cls", "object")
                self._seat_state[seat_id]["confidence"] = confidence
            seat_idx += 1

    def _apply_sensor_fusion(self, zone_id: str) -> List[GhostAlert]:
        """
        Apply full sensor fusion + ghost detection + motion tracking for a zone.

        Returns list of alerts generated during this update.
        """
        # First, enrich with radar data
        self._enrich_with_radar(zone_id)

        alerts = []

        # Apply fusion, ghost detection, and motion tracking per seat
        for seat_id in ZONE_TO_SEATS.get(zone_id, []):
            seat = self._seat_state[seat_id]

            # Build CameraResult from camera detection
            cam = CameraResult(
                object_type=seat.get("object_type", "empty"),
                confidence=seat.get("confidence", 0.0)
            )

            # Build RadarResult from cached radar
            radar = RadarResult(
                presence=seat.get("radar_presence", 0.0),
                motion=seat.get("radar_motion", 0.0),
                micro_motion=seat.get("has_motion", False)
            )

            # Fuse camera + radar
            fused = self._fusion.fuse(camera_result=cam, radar_result=radar)

            # Update motion tracker
            motion_info = self._motion_tracker.update(
                seat_id,
                has_motion=fused.has_motion,
                is_occupied=fused.is_present
            )

            # Update ghost detector
            alert = self._ghost_detector.update(seat_id, fused)
            if alert:
                alerts.append(alert)

            # Apply fused result to seat state
            seat["occupancy_score"] = fused.occupancy_score
            seat["is_present"] = fused.is_present
            seat["has_motion"] = fused.has_motion
            seat["ghost_state"] = self._ghost_detector.get_state(seat_id).value
            seat["dwell_time"] = motion_info.get("dwell_time", 0.0)
            seat["time_since_motion"] = motion_info.get("time_since_motion", 0.0)

            _log.debug(
                "[%s] Seat %s: occ=%.2f ghost=%s dwell=%.1fs",
                self.room_id, seat_id, fused.occupancy_score,
                seat["ghost_state"], seat["dwell_time"]
            )

        return alerts

    def _enrich_with_radar(self, zone_id: str):
        """
        Enrich seat states with radar data for a specific zone.

        Groups radar data by zone and applies to seats.
        """
        # Find sensors for this zone
        sensors_for_zone = [
            sensor for sensor, z in SENSOR_TO_ZONE.items() if z == zone_id
        ]

        # Collect radar data for this zone
        zone_presence = 0.0
        zone_motion = 0.0
        count = 0

        with self._radar_lock:
            for sensor_name in sensors_for_zone:
                if sensor_name in self._radar_cache:
                    radar_data = self._radar_cache[sensor_name]
                    zone_presence += radar_data.get("presence", 0.0)
                    zone_motion += radar_data.get("motion", 0.0)
                    count += 1

        if count == 0:
            return

        avg_presence = zone_presence / count
        avg_motion = zone_motion / count

        # Apply to all seats in zone
        for seat_id in ZONE_TO_SEATS.get(zone_id, []):
            seat = self._seat_state[seat_id]
            seat["radar_presence"] = avg_presence
            seat["radar_motion"] = avg_motion

            # If radar shows presence but camera doesn't, set has_motion
            if avg_presence > 0.6 and not seat["is_occupied"]:
                seat["has_motion"] = avg_motion > MOTION_THRESHOLD

    def _maybe_send_occupancy(self) -> dict[str, Any]:
        """
        Check if occupancy changed and send to edge if needed.

        Uses delta compression: only sends when state actually changed.
        """
        current_hash = self._compute_state_hash()

        # Skip if no change and delta mode
        if self.send_deltas and current_hash == self._last_sent_hash:
            return {"status": "no_change", "hash": current_hash}

        return self._send_occupancy_to_edge()

    def _compute_state_hash(self) -> str:
        """Compute hash of current seat state for delta detection."""
        if not USE_STATE_HASHING:
            return str(time.time())

        state_copy = {}
        with self._state_lock:
            for seat_id, seat_data in self._seat_state.items():
                state_copy[seat_id] = {
                    "is_occupied": seat_data["is_occupied"],
                    "confidence": seat_data["confidence"],
                    "object_type": seat_data["object_type"],
                    "ghost_state": seat_data["ghost_state"],
                }

        json_str = json.dumps(state_copy, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()[:16]

    def _send_occupancy_to_edge(self) -> dict[str, Any]:
        """
        Send seat occupancy to central edge processor.

        This is the ONLY data that leaves the RPi - no raw images.
        """
        timestamp = time.time()

        with self._state_lock:
            seats_copy = dict(self._seat_state)

        payload = {
            "source": "rpi_simulator",
            "room_id": self.room_id,
            "timestamp": timestamp,
            "seats": seats_copy,
        }

        try:
            resp = requests.post(
                f"{self.edge_url}/api/occupancy",
                json=payload,
                timeout=2,
            )
            resp.raise_for_status()

            self.last_occupancy_sent_time = timestamp
            self.occupancy_sent += 1
            self._last_sent_hash = self._compute_state_hash()

            _log.debug(
                "[%s] Occupancy sent to edge: %d occupied seats",
                self.room_id,
                sum(1 for s in seats_copy.values() if s["is_occupied"]),
            )

            return {"status": "sent", "timestamp": timestamp}

        except requests.RequestException as e:
            _log.warning("[%s] Failed to send to edge: %s", self.room_id, e)
            return {"status": "send_failed", "error": str(e)}

    def get_occupancy_summary(self) -> dict[str, Any]:
        """Get human-readable occupancy summary."""
        seats = self.seat_state
        return {
            "room_id": self.room_id,
            "total_seats": TOTAL_SEATS,
            "occupied": sum(1 for s in seats.values() if s["is_occupied"]),
            "empty": sum(1 for s in seats.values() if not s["is_occupied"]),
            "by_zone": {
                zone: {
                    "total": len(seats_in_zone := [s for s in seats.values() if s["zone_id"] == zone]),
                    "occupied": sum(1 for s in seats_in_zone if s["is_occupied"]),
                }
                for zone in ZONE_TO_SEATS.keys()
            },
        }

    def get_recent_alerts(self, limit: int = 50) -> list:
        """Get recent ghost detection alerts."""
        return self._ghost_detector.get_recent_alerts(limit=limit)

    def get_motion_summary(self) -> dict:
        """Get motion tracking summary."""
        return self._motion_tracker.get_summary()

    def reset(self):
        """Reset all state - reinitialize seat state and clear caches."""
        self._init_seat_state()
        self._last_sent_hash = ""
        with self._radar_lock:
            self._radar_cache.clear()
        self._ghost_detector.clear_alerts()
        self._motion_tracker.reset()
