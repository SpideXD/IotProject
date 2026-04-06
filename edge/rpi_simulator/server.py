#!/usr/bin/env python3
"""
RPi Simulator HTTP Server - Receives camera frames from Unity and processes them.

Listens for camera frames from Unity simulation, runs YOLO inference,
applies ghost detection via image differencing, and forwards occupancy to Edge Processor.

Usage:
    python server.py                    # Start server on port 5001
    python server.py --port 5001        # Custom port
    python server.py --no-verify        # Skip SSL verification (dev)
"""
import argparse
import base64
import io
import logging
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Optional, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rpi_simulator.config import (
    MODEL_PATH,
    CLASS_NAMES,
    CONF_THRESHOLD,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("rpi_server")

# Try to import optional dependencies
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False
    logger.warning("OpenCV not installed. Image processing disabled.")

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    logger.warning("ultralytics not installed. YOLO inference disabled.")


class YOLOInference:
    """Handles YOLO inference on camera frames."""

    def __init__(self, model_path: str, conf_threshold: float = 0.35):
        self.model_path = model_path
        self.conf_threshold = conf_threshold
        self.model = None
        self._lock = threading.Lock()

    def load(self) -> bool:
        """Load YOLO model. Returns True if successful."""
        if not ULTRALYTICS_AVAILABLE:
            logger.error("ultralytics not installed")
            return False

        if not os.path.exists(self.model_path):
            logger.error(f"Model not found: {self.model_path}")
            return False

        try:
            self.model = YOLO(self.model_path)
            logger.info(f"YOLO model loaded from {self.model_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            return False

    def infer(self, frame_bytes: bytes) -> List[Dict]:
        """
        Run YOLO inference on a frame.

        Args:
            frame_bytes: JPEG image data

        Returns:
            List of detections, each with {class_id, class_name, confidence, bbox}
        """
        if self.model is None:
            return []

        with self._lock:
            try:
                # Decode image
                nparr = np.frombuffer(frame_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    return []

                # Run inference
                results = self.model(img, conf=self.conf_threshold, verbose=False)

                detections = []
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])

                        # Get bounding box (xyxy format)
                        x1, y1, x2, y2 = box.xyxy[0].tolist()

                        detections.append({
                            "class_id": cls_id,
                            "class_name": CLASS_NAMES[cls_id] if cls_id < len(CLASS_NAMES) else "unknown",
                            "confidence": round(conf, 4),
                            "bbox": {
                                "x1": round(x1, 1),
                                "y1": round(y1, 1),
                                "x2": round(x2, 1),
                                "y2": round(y2, 1),
                            }
                        })

                return detections

            except Exception as e:
                logger.error(f"YOLO inference error: {e}")
                return []


class ImageGhostDetector:
    """Detects ghost objects via image differencing (legacy)."""

    def __init__(self, threshold: int = 30):
        self.threshold = threshold
        self.prev_frame: Optional[np.ndarray] = None
        self.prev_gray: Optional[np.ndarray] = None
        self._lock = threading.Lock()

    def detect_ghosts(self, frame_bytes: bytes) -> List[Dict]:
        """
        Detect ghost objects via image differencing.

        Returns list of ghost regions with {bbox, diff_score}
        """
        if not OPENCV_AVAILABLE:
            return []

        with self._lock:
            try:
                # Decode image
                nparr = np.frombuffer(frame_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    return []

                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                ghosts = []

                if self.prev_gray is not None:
                    # Compute absolute difference
                    diff = cv2.absdiff(self.prev_gray, gray)

                    # Threshold the difference
                    thresh = cv2.threshold(diff, self.threshold, 255, cv2.THRESH_BINARY)[1]

                    # Find contours
                    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                    for cnt in contours:
                        area = cv2.contourArea(cnt)
                        if area > 500:  # Filter small noise
                            x, y, w, h = cv2.boundingRect(cnt)
                            mean_diff = cv2.mean(diff[y:y+h, x:x+w])[0]

                            ghosts.append({
                                "bbox": {"x1": x, "y1": y, "x2": x+w, "y2": y+h},
                                "diff_score": round(float(mean_diff), 2),
                                "area": int(area),
                            })

                # Update previous frame
                self.prev_gray = gray.copy()

                return ghosts

            except Exception as e:
                logger.error(f"Ghost detection error: {e}")
                return []


class ImageCache:
    """Caches recent frames per sensor for temporal analysis."""

    def __init__(self, max_cache_size: int = 10):
        self._cache: Dict[str, List[bytes]] = {}
        self._lock = threading.Lock()
        self.max_cache_size = max_cache_size

    def add(self, sensor_id: str, frame_bytes: bytes):
        """Add a frame to the sensor's cache."""
        with self._lock:
            if sensor_id not in self._cache:
                self._cache[sensor_id] = []
            self._cache[sensor_id].append(frame_bytes)
            if len(self._cache[sensor_id]) > self.max_cache_size:
                self._cache[sensor_id].pop(0)

    def get_recent(self, sensor_id: str, count: int = 5) -> List[bytes]:
        """Get N most recent frames for a sensor."""
        with self._lock:
            if sensor_id not in self._cache:
                return []
            return self._cache[sensor_id][-count:]


class CalibrationStore:
    """Stores zone/seat layout received from Unity during calibration."""

    def __init__(self):
        self.zones: Dict[str, List[str]] = {}
        self.seat_regions: Dict[str, Dict] = {}
        self.seat_to_zone: Dict[str, str] = {}
        self.calibrated = False
        self._lock = threading.Lock()

    def receive_calibration(self, data: dict) -> bool:
        """
        Receive calibration data from Unity.

        Expected format:
        {
            "zones": {
                "Z1": ["S1", "S2", "S3", "S4"],
                "Z2": ["S5", "S6", "S7", "S8"]
            },
            "seat_regions": {
                "S1": {"x1": 100, "y1": 200, "x2": 150, "y2": 280},
                ...
            }
        }
        """
        with self._lock:
            zones = data.get("zones", {})
            seat_regions = data.get("seat_regions", {})

            if not zones:
                logger.warning("Calibration received with no zones")
                return False

            self.zones = zones
            self.seat_regions = seat_regions
            self.seat_to_zone = {}
            for zone, seats in zones.items():
                for seat in seats:
                    self.seat_to_zone[seat] = zone

            self.calibrated = True
            logger.info(f"Calibration received: {len(zones)} zones, {len(seat_regions)} seat regions")
            return True

    def get_zone_for_seat(self, seat_id: str) -> str:
        return self.seat_to_zone.get(seat_id, "UNKNOWN")

    def get_seats_in_zone(self, zone: str) -> List[str]:
        return self.zones.get(zone, [])

    def get_all_seats(self) -> List[str]:
        seats = []
        for zone_seats in self.zones.values():
            seats.extend(zone_seats)
        return seats


class SpatialMapper:
    """Maps YOLO pixel detections to seat IDs using calibration data."""

    def __init__(self, calibration: CalibrationStore):
        self.calibration = calibration
        self._seat_region_cache: Dict[str, Dict] = {}

    def _get_seat_region(self, seat_id: str) -> Optional[Dict]:
        """Get pixel region for a seat (with caching for speed)."""
        if seat_id in self._seat_region_cache:
            return self._seat_region_cache[seat_id]

        region = self.calibration.seat_regions.get(seat_id)
        if region:
            self._seat_region_cache[seat_id] = region
        return region

    def _bbox_center_overlaps_region(self, bbox: Dict, region: Dict) -> bool:
        """Check if the center of a bbox overlaps with a seat region."""
        x1 = bbox.get("x1", 0)
        y1 = bbox.get("y1", 0)
        x2 = bbox.get("x2", 0)
        y2 = bbox.get("y2", 0)

        rx1 = region.get("x1", 0)
        ry1 = region.get("y1", 0)
        rx2 = region.get("x2", 0)
        ry2 = region.get("y2", 0)

        # Check if bbox center is within region
        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        return rx1 <= cx <= rx2 and ry1 <= cy <= ry2

    def _bbox_overlaps_region(self, bbox: Dict, region: Dict, threshold: float = 0.3) -> bool:
        """Check if bbox overlaps with region by at least threshold."""
        x1 = bbox.get("x1", 0)
        y1 = bbox.get("y1", 0)
        x2 = bbox.get("x2", 0)
        y2 = bbox.get("y2", 0)

        rx1 = region.get("x1", 0)
        ry1 = region.get("y1", 0)
        rx2 = region.get("x2", 0)
        ry2 = region.get("y2", 0)

        # Calculate intersection
        inter_x1 = max(x1, rx1)
        inter_y1 = max(y1, ry1)
        inter_x2 = min(x2, rx2)
        inter_y2 = min(y2, ry2)

        if inter_x2 <= inter_x1 or inter_y2 <= inter_y1:
            return False

        # Calculate overlap ratio
        inter_area = (inter_x2 - inter_x1) * (inter_y2 - inter_y1)
        bbox_area = (x2 - x1) * (y2 - y1)

        overlap_ratio = inter_area / max(bbox_area, 1)
        return overlap_ratio >= threshold

    def map_detections(self, detections: List[Dict], zone: str) -> Dict[str, List[Dict]]:
        """
        Map YOLO detections to seats in a zone.

        Args:
            detections: YOLO detections [{class_name, confidence, bbox}, ...]
            zone: Zone identifier

        Returns:
            Dict of seat_id -> list of detections at that seat
            e.g., {"S1": [{"class_name": "person", "confidence": 0.92, "bbox": {...}}]}
        """
        seat_detections: Dict[str, List[Dict]] = {}
        seats = self.calibration.get_seats_in_zone(zone)

        if not seats:
            # Fallback: return empty if not calibrated
            for seat_id in ["S1", "S2", "S3", "S4"]:  # Default
                seat_detections[seat_id] = []
            return seat_detections

        # Initialize all seats with empty detection lists
        for seat_id in seats:
            seat_detections[seat_id] = []

        # For each detection, try to assign to a seat
        for det in detections:
            det_class = det.get("class_name", "")
            det_conf = det.get("confidence", 0)
            det_bbox = det.get("bbox", {})

            # Try to match detection to a seat
            matched = False
            for seat_id in seats:
                region = self._get_seat_region(seat_id)
                if region:
                    if self._bbox_overlaps_region(det_bbox, region, threshold=0.3):
                        seat_detections[seat_id].append({
                            "class_name": det_class,
                            "confidence": det_conf,
                            "bbox": det_bbox,
                            "matched_seat": seat_id
                        })
                        matched = True
                        break

            # If no region match but detection exists, assign to first empty seat heuristic
            if not matched and det_class == "person":
                # Assign to first seat with no person detected
                for seat_id in seats:
                    has_person = any(d["class_name"] == "person" for d in seat_detections[seat_id])
                    if not has_person:
                        seat_detections[seat_id].append({
                            "class_name": det_class,
                            "confidence": det_conf,
                            "bbox": det_bbox,
                            "matched_seat": None,  # No precise region match
                            "heuristic": True
                        })
                        break

        return seat_detections


class ComparisonLayer:
    """Compares ground truth vs YOLO detections to build confidence matrix."""

    def __init__(self):
        from rpi_simulator.config import (
            YOLO_AGREEMENT_BONUS,
            YOLO_DISAGREEMENT_PENALTY,
            YOLO_BASE_CONFIDENCE,
            YOLO_MISS_CONFIDENCE,
            YOLO_FALSE_POSITIVE_CONFIDENCE,
        )
        self.agreement_bonus = YOLO_AGREEMENT_BONUS
        self.disagreement_penalty = YOLO_DISAGREEMENT_PENALTY
        self.base_confidence = YOLO_BASE_CONFIDENCE
        self.miss_confidence = YOLO_MISS_CONFIDENCE
        self.false_positive_confidence = YOLO_FALSE_POSITIVE_CONFIDENCE

    def compare(self, ground_truth: Dict[str, Dict], yolo_detections: Dict[str, List[Dict]]) -> Dict[str, Dict]:
        """
        Compare ground truth vs YOLO detections per seat.

        Args:
            ground_truth: {seat_id: {"object": "person"|"bag"|"empty", ...}}
            yolo_detections: {seat_id: [{"class_name": ..., "confidence": ..., "bbox": ...}, ...]}

        Returns:
            {seat_id: {
                "yolo_match": bool,
                "diff_flag": bool,
                "diff_type": null|"miss"|"false_positive"|"misclass",
                "yolo_confidence": float,
                "yolo_classes": [class_names detected],
                "yolo_detections": [...detections...]
            }}
        """
        results = {}

        for seat_id, gt_info in ground_truth.items():
            gt_object = gt_info.get("object", "empty")
            yolo_at_seat = yolo_detections.get(seat_id, [])

            # Extract YOLO classes and confidences at this seat
            yolo_classes = [d["class_name"] for d in yolo_at_seat]
            yolo_confs = [d["confidence"] for d in yolo_at_seat]
            yolo_avg_conf = sum(yolo_confs) / max(len(yolo_confs), 1)

            # Determine if YOLO detected something at this seat
            has_yolo_person = "person" in yolo_classes
            has_yolo_bag = "bag" in yolo_classes

            # Compare GT vs YOLO
            result = {
                "yolo_match": False,
                "diff_flag": False,
                "diff_type": None,
                "yolo_confidence": yolo_avg_conf,
                "yolo_classes": yolo_classes,
                "yolo_detections": yolo_at_seat,
                "gt_object": gt_object
            }

            # Case 1: GT empty
            if gt_object == "empty":
                if has_yolo_person or has_yolo_bag:
                    # YOLO false positive
                    result["yolo_match"] = False
                    result["diff_flag"] = True
                    result["diff_type"] = "false_positive"
                    result["yolo_confidence"] = self.false_positive_confidence
                else:
                    # YOLO correctly agreed (empty = empty)
                    result["yolo_match"] = True
                    result["diff_flag"] = False
                    result["diff_type"] = None
                    result["yolo_confidence"] = yolo_avg_conf if yolo_avg_conf > 0 else self.base_confidence

            # Case 2: GT person
            elif gt_object == "person":
                if has_yolo_person:
                    # YOLO correctly detected person
                    result["yolo_match"] = True
                    result["diff_flag"] = False
                    result["diff_type"] = None
                    result["yolo_confidence"] = yolo_avg_conf + self.agreement_bonus
                elif has_yolo_bag:
                    # YOLO saw bag, GT says person - misclass
                    result["yolo_match"] = False
                    result["diff_flag"] = True
                    result["diff_type"] = "misclass"
                    result["yolo_confidence"] = yolo_avg_conf - self.disagreement_penalty
                else:
                    # YOLO missed detection
                    result["yolo_match"] = False
                    result["diff_flag"] = True
                    result["diff_type"] = "miss"
                    result["yolo_confidence"] = self.miss_confidence

            # Case 3: GT bag (ghost)
            elif gt_object == "bag":
                if has_yolo_bag:
                    # YOLO correctly detected bag
                    result["yolo_match"] = True
                    result["diff_flag"] = False
                    result["diff_type"] = None
                    result["yolo_confidence"] = yolo_avg_conf + self.agreement_bonus
                elif has_yolo_person:
                    # YOLO saw person, GT says bag - misclass
                    result["yolo_match"] = False
                    result["diff_flag"] = True
                    result["diff_type"] = "misclass"
                    result["yolo_confidence"] = yolo_avg_conf - self.disagreement_penalty
                else:
                    # YOLO missed the bag
                    result["yolo_match"] = False
                    result["diff_flag"] = True
                    result["diff_type"] = "miss"
                    result["yolo_confidence"] = self.miss_confidence

            results[seat_id] = result

        return results

    def calculate_zone_stats(self, comparisons: Dict[str, Dict]) -> Dict:
        """Calculate YOLO accuracy stats for a zone."""
        total = len(comparisons)
        if total == 0:
            return {"yolo_accuracy": 0, "yolo_misses": 0, "yolo_false_positives": 0, "yolo_misclasses": 0}

        matches = sum(1 for c in comparisons.values() if c["yolo_match"])
        misses = sum(1 for c in comparisons.values() if c["diff_type"] == "miss")
        false_positives = sum(1 for c in comparisons.values() if c["diff_type"] == "false_positive")
        misclasses = sum(1 for c in comparisons.values() if c["diff_type"] == "misclass")

        return {
            "yolo_accuracy": round(matches / total, 3),
            "yolo_misses": misses,
            "yolo_false_positives": false_positives,
            "yolo_misclasses": misclasses,
            "total_seats": total
        }


class SeatTracker:
    """Per-seat state machine using ground truth as the source of truth."""

    # States
    EMPTY = "empty"
    OCCUPIED = "occupied"
    SUSPECTED_GHOST = "suspected_ghost"
    CONFIRMED_GHOST = "confirmed_ghost"

    def __init__(self, seat_id: str):
        self.seat_id = seat_id
        self.state = self.EMPTY
        self.scan_count = 0
        self.ghost_scan_count = 0
        self.last_state_change = time.time()
        self.last_motion = time.time()
        self.dwell_time = 0
        self.object_type = "empty"

    def update(self, ground_truth_object: str, comparison_data: Dict):
        """
        Update FSM based on ground truth (YOLO comparison is read-only).

        Args:
            ground_truth_object: "person" | "bag" | "empty"
            comparison_data: YOLO comparison result for this seat
        """
        now = time.time()

        # Update dwell time
        if self.state == self.OCCUPIED or self.state == self.CONFIRMED_GHOST:
            self.dwell_time = now - self.last_state_change

        # FSM transitions based on GROUND TRUTH (not YOLO)
        if ground_truth_object == "person":
            self._handle_person_detected(now)
        elif ground_truth_object == "bag":
            self._handle_bag_detected(now)
        elif ground_truth_object == "empty":
            self._handle_empty(now)

        # Update motion tracking
        if ground_truth_object != "empty":
            self.last_motion = now

        self.object_type = ground_truth_object

    def _handle_person_detected(self, now: float):
        """Person detected - move toward occupied."""
        from rpi_simulator.config import OCCUPIED_SCAN_THRESHOLD

        self.last_motion = now

        if self.state == self.EMPTY:
            self.scan_count += 1
            if self.scan_count >= OCCUPIED_SCAN_THRESHOLD:
                self._transition_to(self.OCCUPIED, now)
                self.scan_count = 0
        elif self.state == self.OCCUPIED:
            self.scan_count = 0  # Reset counter on continued presence
            self.last_state_change = now  # Update dwell base
        elif self.state in (self.SUSPECTED_GHOST, self.CONFIRMED_GHOST):
            # Person back - return to occupied
            self._transition_to(self.OCCUPIED, now)
            self.ghost_scan_count = 0
            self.scan_count = 0

    def _handle_bag_detected(self, now: float):
        """Bag detected - ghost tracking."""
        from rpi_simulator.config import GHOST_SCAN_THRESHOLD, SUSPECTED_GHOST_THRESHOLD

        if self.state == self.OCCUPIED:
            # Person left, bag appeared
            self.ghost_scan_count = 1
            self._transition_to(self.SUSPECTED_GHOST, now)
        elif self.state == self.SUSPECTED_GHOST:
            self.ghost_scan_count += 1
            if self.ghost_scan_count >= GHOST_SCAN_THRESHOLD:
                self._transition_to(self.CONFIRMED_GHOST, now)
        elif self.state == self.CONFIRMED_GHOST:
            self.ghost_scan_count += 1  # Continue tracking duration
        elif self.state == self.EMPTY:
            # Bag detected in empty seat - suspicious
            self.ghost_scan_count = 1
            self._transition_to(self.SUSPECTED_GHOST, now)

    def _handle_empty(self, now: float):
        """Seat became empty."""
        from rpi_simulator.config import EMPTY_SCAN_THRESHOLD

        if self.state == self.EMPTY:
            self.scan_count = 0
            self.ghost_scan_count = 0
        elif self.state == self.OCCUPIED:
            self.scan_count += 1
            if self.scan_count >= EMPTY_SCAN_THRESHOLD:
                self._transition_to(self.EMPTY, now)
        elif self.state == self.SUSPECTED_GHOST:
            # Bag left before confirmed - clear
            self._transition_to(self.EMPTY, now)
            self.ghost_scan_count = 0
        elif self.state == self.CONFIRMED_GHOST:
            self.scan_count += 1
            if self.scan_count >= EMPTY_SCAN_THRESHOLD:
                self._transition_to(self.EMPTY, now)
                self.ghost_scan_count = 0

    def _transition_to(self, new_state: str, now: float):
        """Internal: change state."""
        if self.state != new_state:
            self.state = new_state
            self.last_state_change = now
            logger.debug(f"Seat {self.seat_id}: state -> {new_state}")

    def get_state(self) -> Dict:
        """Get current state data for this seat."""
        return {
            "state": self.state,
            "object_type": self.object_type,
            "is_occupied": self.state in (self.OCCUPIED, self.SUSPECTED_GHOST, self.CONFIRMED_GHOST),
            "dwell_time": round(self.dwell_time, 1),
            "time_since_motion": round(time.time() - self.last_motion, 1),
            "ghost_duration": self.ghost_scan_count
        }


# Import time-based FSM from local ghost_detector.py (NOT the parent's)
from rpi_simulator.ghost_detector import GhostDetector as TimeBasedGhostDetector
from sensor_fusion import SensorFusion, CameraResult, RadarResult, FusedResult

# Import SEAT_TO_ZONE for the FSM (from config in same directory)
from config import SEAT_TO_ZONE as CONFIG_SEAT_TO_ZONE


class EnhancedOutputBuilder:
    """Builds enhanced payload for edge processor."""

    def __init__(self, comparison_layer: ComparisonLayer):
        self.comparison_layer = comparison_layer

    def build(self,
              ground_truth: Dict[str, Dict],
              comparisons: Dict[str, Dict],
              seat_states: Dict[str, Dict],
              zone: str,
              sensor_id: str) -> Dict:
        """
        Build enhanced payload with all required fields.

        Returns:
            {
                "source": "rpi_...",
                "room_id": "library_...",
                "timestamp": ...,
                "scan_id": ...,
                "seats": {
                    seat_id: {
                        "zone_id": ...,
                        "state": ...,
                        "is_occupied": ...,
                        "object_type": ...,
                        "confidence": ...,
                        "yolo_match": ...,
                        "yolo_confidence": ...,
                        "diff_flag": ...,
                        "diff_type": ...,
                        "dwell_time": ...,
                        "time_since_motion": ...,
                        "yolo_bboxes": [...],
                        "ghost_duration": ...
                    }
                },
                "zone_stats": {...}
            }
        """
        from rpi_simulator.config import DEFAULT_ZONE_SEATS

        # Get seats for this zone
        seats_in_zone = DEFAULT_ZONE_SEATS.get(zone, list(ground_truth.keys()))
        if not seats_in_zone:
            seats_in_zone = list(ground_truth.keys())

        # Build per-seat data
        seats_output = {}
        for seat_id in seats_in_zone:
            gt_info = ground_truth.get(seat_id, {"object": "empty"})
            comparison = comparisons.get(seat_id, {})
            state_info = seat_states.get(seat_id, {})

            seats_output[seat_id] = {
                "zone_id": zone,
                "state": state_info.get("state", "empty"),
                "is_occupied": state_info.get("is_occupied", False),
                "object_type": gt_info.get("object", "empty"),
                "ghost_objects": gt_info.get("objects", []),  # Ghost objects left at seat
                "confidence": comparison.get("yolo_confidence", 0.5),
                "yolo_match": comparison.get("yolo_match", True),
                "yolo_confidence": comparison.get("yolo_confidence", 0),
                "diff_flag": comparison.get("diff_flag", False),
                "diff_type": comparison.get("diff_type"),
                "dwell_time": state_info.get("dwell_time", 0),
                "time_since_motion": state_info.get("time_since_motion", 0),
                "ghost_duration": state_info.get("ghost_duration", 0),
                "yolo_bboxes": comparison.get("yolo_detections", []),
                "timestamp": time.time()
            }

        # Zone stats from comparison layer
        zone_stats = self.comparison_layer.calculate_zone_stats(comparisons)

        return {
            "source": f"rpi_{sensor_id}",
            "room_id": f"library_{zone.lower()}",
            "timestamp": time.time(),
            "scan_id": int(time.time() * 1000),
            "seats": seats_output,
            "zone_stats": zone_stats
        }


class OccupancyProcessor:
    """Processes detections into seat occupancy."""

    # Zone definitions (these should come from config in production)
    ZONE_SEATS = {
        "Z1": ["S1", "S2", "S3", "S4"],
        "Z2": ["S5", "S6", "S7", "S8"],
        "Z3": ["S9", "S10", "S11", "S12"],
        "Z4": ["S13", "S14", "S15", "S16"],
        "Z5": ["S17", "S18", "S19", "S20"],
        "Z6": ["S21", "S22", "S23", "S24"],
        "Z7": ["S25", "S26", "S27", "S28"],
    }

    def __init__(self):
        self.seat_to_zone = {}
        for zone, seats in self.ZONE_SEATS.items():
            for seat in seats:
                self.seat_to_zone[seat] = zone

    def process(self, zone: str, detections: List[Dict], ghosts: List[Dict]) -> Dict[str, Dict]:
        """
        Convert detections and ghosts into seat occupancy.

        Args:
            zone: Zone identifier (e.g., "Z1")
            detections: YOLO detections in the frame
            ghosts: Ghost regions from image differencing

        Returns:
            Dict of seat_id -> {state, confidence, object_type}
        """
        seats = self.ZONE_SEATS.get(zone, [])
        occupancy = {}

        # Count person detections per zone (simplified - real impl would use spatial mapping)
        person_count = sum(1 for d in detections if d["class_name"] == "person")
        bag_count = sum(1 for d in detections if d["class_name"] == "bag")

        # Simple heuristic: distribute detections across seats in zone
        # Real implementation would use spatial coordinates from bounding boxes
        occupied_seats = min(person_count, len(seats))
        ghost_seats = min(bag_count, len(seats) - occupied_seats)

        for i, seat_id in enumerate(seats):
            if i < occupied_seats:
                occupancy[seat_id] = {
                    "state": "occupied",
                    "confidence": 0.95,
                    "object_type": "person",
                }
            elif i < occupied_seats + ghost_seats:
                occupancy[seat_id] = {
                    "state": "ghost",
                    "confidence": 0.80,
                    "object_type": "bag",
                }
            else:
                occupancy[seat_id] = {
                    "state": "empty",
                    "confidence": 0.90,
                    "object_type": "empty",
                }

        return occupancy


def forward_to_edge_processor(data: dict, edge_url: str = "http://localhost:5002") -> bool:
    """Forward occupancy data to Edge Processor."""
    import requests
    try:
        resp = requests.post(
            f"{edge_url}/api/occupancy",
            json=data,
            timeout=2
        )
        return resp.status_code == 200
    except Exception as e:
        logger.debug(f"Failed to forward to Edge: {e}")
        return False


def run_server(port: int = 5001, model_path: Optional[str] = None, edge_url: str = "http://localhost:5002", reset_fsm: bool = False):
    """Start the RPi simulator HTTP server."""

    # Initialize components
    yolo = YOLOInference(model_path or MODEL_PATH)
    image_ghost_detector = ImageGhostDetector()  # Legacy image differencing
    sensor_fusion = SensorFusion()
    fsm_detector = TimeBasedGhostDetector()  # Time-based FSM
    fsm_detector.set_seat_zones(CONFIG_SEAT_TO_ZONE)

    # FSM state persistence
    fsm_state_file = os.path.join(os.path.dirname(__file__), "fsm_state.json")
    if reset_fsm:
        logger.info("Reset flag set - clearing FSM state")
        fsm_detector.save_state(fsm_state_file)  # Save empty state
    else:
        # Load persisted FSM state if available
        fsm_detector.load_state(fsm_state_file)

    image_cache = ImageCache()
    comparison_layer = ComparisonLayer()
    output_builder = EnhancedOutputBuilder(comparison_layer)

    # Initialize calibration
    calibration = CalibrationStore()

    # Load YOLO model
    yolo_loaded = yolo.load()
    if not yolo_loaded:
        logger.warning("YOLO model not loaded. Inference disabled.")

    # Import Flask
    try:
        from flask import Flask, request, jsonify
    except ImportError:
        logger.error("Flask not installed. Run: pip install flask")
        return

    app = Flask("rpi_simulator")
    app.logger.setLevel(logging.INFO)

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "yolo_loaded": yolo_loaded,
            "opencv_available": OPENCV_AVAILABLE,
            "calibrated": calibration.calibrated,
        })

    @app.route("/api/calibration", methods=["POST"])
    def calibration_endpoint():
        """
        Receive zone/seat layout calibration from Unity.

        Expected JSON payload:
        {
            "zones": {
                "Z1": ["S1", "S2", "S3", "S4"],
                "Z2": ["S5", "S6", "S7", "S8"]
            },
            "seat_regions": {
                "S1": {"x1": 100, "y1": 200, "x2": 150, "y2": 280},
                ...
            }
        }
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "no JSON body"}), 400

        success = calibration.receive_calibration(data)
        if not success:
            return jsonify({"error": "invalid calibration data"}), 400

        return jsonify({
            "ok": True,
            "zones": list(calibration.zones.keys()),
            "total_seats": len(calibration.get_all_seats())
        })

    @app.route("/api/v1/sensor/capture", methods=["POST"])
    def sensor_capture():
        """
        Receive sensor capture from Unity simulation with occupancy data.

        Expected JSON payload:
        {
            "sensor": "Rail_Back",
            "zone": "Z1",
            "sim_time": "10:30",
            "frame": "base64_jpeg_data",
            "occupancy": {
                "S1": {"person": "Student_1", "state": "STUDY", "objects": ["bag"]},
                "S2": {"person": null, "state": null, "objects": []},
                "S3": {"person": "Student_3", "state": "SIT", "objects": ["laptop", "cup"]}
            }
        }

        RPi derives:
        - ground_truth object: person != null -> "person", person == null && objects -> "bag", else -> "empty"
        - FSM uses person + objects to track occupancy and ghost states
        """
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "no JSON body"}), 400

        sensor_id = data.get("sensor", "unknown")
        zone = data.get("zone", "Z1")
        sim_time = data.get("sim_time", "")
        occupancy = data.get("occupancy", {})

        # Convert occupancy to ground_truth format for internal processing
        # Derive "object" type: person != null -> "person", objects exist -> "bag", else -> "empty"
        ground_truth = {}
        for seat_id, seat_data in occupancy.items():
            person = seat_data.get("person")
            objects = seat_data.get("objects", [])
            state = seat_data.get("state", "")

            if person is not None:
                # Person is present
                ground_truth[seat_id] = {"object": "person", "state": state, "objects": objects}
            elif objects and len(objects) > 0:
                # No person, but has ghost objects (bag, laptop, etc.)
                ground_truth[seat_id] = {"object": "bag", "state": state, "objects": objects}
            else:
                # Empty seat
                ground_truth[seat_id] = {"object": "empty", "state": state, "objects": []}

        # Decode frame (for YOLO inference, even if we use GT for FSM)
        frame_b64 = data.get("frame", "")
        if frame_b64:
            try:
                frame_bytes = base64.b64decode(frame_b64)
                image_cache.add(sensor_id, frame_bytes)
            except Exception as e:
                logger.warning(f"Failed to decode frame: {e}")
                frame_bytes = None
        else:
            frame_bytes = None

        # Run YOLO inference (even with GT available, we want YOLO comparison)
        detections = []
        if yolo_loaded and frame_bytes:
            detections = yolo.infer(frame_bytes)

        # Run ghost detection (legacy - still useful for verification)
        ghosts = image_ghost_detector.detect_ghosts(frame_bytes) if frame_bytes else []

        # Step 1: Spatial mapping - where are YOLO detections in the frame?
        spatial_mapper = SpatialMapper(calibration)
        yolo_seat_detections = spatial_mapper.map_detections(detections, zone)

        # Step 2: Comparison layer - compare GT vs YOLO for confidence matrix
        comparisons = comparison_layer.compare(ground_truth, yolo_seat_detections)

        # Step 3: Update time-based FSM for each seat
        # Create FusedResult from YOLO detections and ground truth
        for seat_id, gt_info in ground_truth.items():
            gt_object = gt_info.get("object", "empty")
            yolo_info = yolo_seat_detections.get(seat_id, {})
            yolo_confidence = yolo_info.get("confidence", 0.0) if yolo_info else 0.0

            # Create CameraResult - use YOLO when available, otherwise fall back to ground truth
            # This is because: YOLO miss (no detection) != camera sees empty (detection says empty)
            if yolo_info:
                cam_result = CameraResult(object_type=gt_object, confidence=yolo_confidence)
            else:
                # YOLO didn't detect - use ground truth with reduced confidence (simulates real miss)
                cam_result = CameraResult(object_type=gt_object, confidence=0.85)

            # Create a simple RadarResult (Unity doesn't have radar, so we use motion state)
            # If person is present, assume some motion; if bag/empty, no motion
            radar_motion = 0.8 if gt_object == "person" else 0.1 if gt_object == "bag" else 0.0
            radar_result = RadarResult(
                presence=1.0 if gt_object == "person" else 0.5 if gt_object == "bag" else 0.0,
                motion=radar_motion,
                micro_motion=(gt_object == "person")
            )

            # Fuse camera and radar
            fused = sensor_fusion.fuse(cam_result, radar_result)

            # Update FSM with fused result
            fsm_detector.update(seat_id, fused)

        # Get all seat states from time-based FSM
        seat_states = fsm_detector.get_all_seats()

        # Persist FSM state to disk (survives restarts)
        fsm_detector.save_state(fsm_state_file)

        # Step 5: Build enhanced output
        output = output_builder.build(
            ground_truth=ground_truth,
            comparisons=comparisons,
            seat_states=seat_states,
            zone=zone,
            sensor_id=sensor_id
        )

        # Forward to Edge Processor
        forwarded = forward_to_edge_processor(output, edge_url)

        # Build response
        result = {
            "sensor": sensor_id,
            "zone": zone,
            "sim_time": sim_time,
            "timestamp": time.time(),
            "detections": detections,
            "ghosts": ghosts,
            "occupancy": occupancy,  # Original occupancy from Unity
            "ground_truth": ground_truth,  # Derived GT object type
            "seat_states": seat_states,  # FSM states for all seats
            "comparisons": {seat_id: {
                "yolo_match": c["yolo_match"],
                "diff_flag": c["diff_flag"],
                "diff_type": c["diff_type"],
                "yolo_confidence": c["yolo_confidence"]
            } for seat_id, c in comparisons.items()},
            "seat_count": len(seat_states),
            "occupied": sum(1 for s in seat_states.values() if s.get("is_occupied")),
            "ghost_count": sum(1 for s in seat_states.values() if s.get("state") in ("suspected_ghost", "confirmed_ghost")),
            "yolo_accuracy": comparisons[list(comparisons.keys())[0]]["yolo_match"] if comparisons else True,
            "forwarded_to_edge": forwarded
        }

        return jsonify(result)

    @app.route("/api/v1/fsm/reset", methods=["POST"])
    def reset_fsm():
        """Reset FSM state - call this when Unity simulation starts fresh."""
        nonlocal fsm_detector
        fsm_detector = TimeBasedGhostDetector()
        fsm_detector.set_seat_zones(CONFIG_SEAT_TO_ZONE)
        fsm_detector.save_state(fsm_state_file)
        logger.info("FSM state reset - simulation started fresh")
        return jsonify({"status": "reset", "message": "FSM state cleared"})

    @app.route("/api/v1/fsm/state", methods=["GET"])
    def get_fsm_state():
        """Get current FSM state for debugging."""
        seat_states = fsm_detector.get_all_seats()
        return jsonify({
            "seat_count": len(seat_states),
            "seats": seat_states
        })

    @app.route("/api/detect", methods=["POST"])
    def detect():
        """Simple detection endpoint - just YOLO, no occupancy processing."""
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "no JSON body"}), 400

        frame_b64 = data.get("frame", "")
        if not frame_b64:
            return jsonify({"error": "no frame data"}), 400

        try:
            frame_bytes = base64.b64decode(frame_b64)
        except Exception as e:
            return jsonify({"error": f"invalid base64: {e}"}), 400

        detections = []
        if yolo_loaded:
            detections = yolo.infer(frame_bytes)

        ghosts = image_ghost_detector.detect_ghosts(frame_bytes)

        return jsonify({
            "detections": detections,
            "ghosts": ghosts,
            "yolo_available": yolo_loaded,
        })

    @app.route("/api/stats", methods=["GET"])
    def stats():
        """Get processing statistics."""
        return jsonify({
            "yolo_loaded": yolo_loaded,
            "model_path": model_path or MODEL_PATH,
            "confidence_threshold": CONF_THRESHOLD,
            "classes": CLASS_NAMES,
        })

    logger.info(f"Starting RPi Simulator HTTP server on port {port}")
    logger.info(f"Forwarding to Edge Processor at {edge_url}")

    app.run(host="0.0.0.0", port=port, threaded=True, debug=False)


def main():
    parser = argparse.ArgumentParser(description="RPi Simulator HTTP Server")
    parser.add_argument("--port", type=int, default=5001, help="Port to listen on (default: 5001)")
    parser.add_argument("--model", type=str, default=None, help="Path to YOLO model")
    parser.add_argument("--edge-url", type=str, default="http://localhost:5002", help="Edge Processor URL")
    parser.add_argument("--reset", action="store_true", help="Reset FSM state on startup (for fresh simulation)")
    args = parser.parse_args()

    model_path = args.model
    if model_path is None:
        # Try to find trained model (best.pt is the trained YOLO model)
        default_models = [
            os.path.join(os.path.dirname(__file__), "best.pt"),
            os.path.join(os.path.dirname(__file__), "best_1.pt"),
            os.path.join(os.path.dirname(__file__), "yolov8s_trained.pt"),
            MODEL_PATH,
        ]
        for p in default_models:
            if os.path.exists(p):
                model_path = p
                break

    run_server(port=args.port, model_path=model_path, edge_url=args.edge_url, reset_fsm=args.reset)


if __name__ == "__main__":
    main()
