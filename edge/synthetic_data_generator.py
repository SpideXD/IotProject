
import argparse
import json
import logging
import os
import random
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

from rpi_simulator.ghost_detector import GhostDetector, SeatState
from rpi_simulator.sensor_fusion import SensorFusion, CameraResult, RadarResult, FusedResult
from rpi_simulator.config import (
    DEFAULT_ZONE_SEATS,
    SEAT_TO_ZONE,
    GHOST_GRACE_PERIOD,
    GHOST_THRESHOLD,
    PRESENCE_THRESHOLD,
    MOTION_THRESHOLD,
    CAMERA_WEIGHT,
    RADAR_WEIGHT,
    AGREEMENT_BONUS,
)

MQTT_BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_KEEPALIVE = 60
MQTT_CLIENT_ID = f"liberty_twin_synthetic_{os.getpid()}"
MQTT_TOPIC_RPI_OCCUPANCY = "liberty_twin/sensor/{zone}/occupancy"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("synthetic_generator")

try:
    import paho.mqtt.client as paho_mqtt
    MQTT_AVAILABLE = True
except ImportError:
    MQTT_AVAILABLE = False
    logger.warning("paho-mqtt not installed. MQTT disabled.")

class Scenario(str, Enum):
    EMPTY = "empty"
    OCCUPIED = "occupied"
    SUSPECTED_GHOST = "suspected_ghost"
    CONFIRMED_GHOST = "confirmed_ghost"

@dataclass
class SeatGroundTruth:
    seat_id: str
    zone_id: str
    scenario: Scenario = Scenario.EMPTY
    dwell_time: float = 0.0
    _leave_threshold: float = None

class SyntheticDataGenerator:

    def __init__(
        self,
        zones: List[str] = None,
        ghost_grace_period: float = GHOST_GRACE_PERIOD,
        ghost_threshold: float = GHOST_THRESHOLD,
    ):
        self.zones = zones or list(DEFAULT_ZONE_SEATS.keys())

        self.ghost_detectors: Dict[str, GhostDetector] = {}
        for zone in self.zones:
            detector = GhostDetector(
                grace_period=ghost_grace_period,
                ghost_threshold=ghost_threshold,
                presence_threshold=PRESENCE_THRESHOLD,
                motion_threshold=MOTION_THRESHOLD,
            )
            detector.set_seat_zones(SEAT_TO_ZONE)
            self.ghost_detectors[zone] = detector

        self.sensor_fusion = SensorFusion(
            camera_weight=CAMERA_WEIGHT,
            radar_weight=RADAR_WEIGHT,
            agreement_bonus=AGREEMENT_BONUS,
            presence_threshold=PRESENCE_THRESHOLD,
        )

        self.ground_truth: Dict[str, SeatGroundTruth] = {}
        for zone in self.zones:
            for seat_id in DEFAULT_ZONE_SEATS[zone]:
                self.ground_truth[seat_id] = SeatGroundTruth(
                    seat_id=seat_id,
                    zone_id=zone,
                )

        logger.info(f"Initialized for zones: {self.zones}")

    def _generate_camera_detection(self, scenario: Scenario) -> Optional[CameraResult]:
        r = random.random()

        if scenario == Scenario.OCCUPIED:
            if r < 0.92:
                conf = 0.85 + random.uniform(-0.1, 0.1)
                return CameraResult(object_type="person", confidence=max(0.6, min(0.95, conf)))
            elif r < 0.97:
                return None
            else:
                return CameraResult(object_type="bag", confidence=0.25)

        elif scenario == Scenario.SUSPECTED_GHOST:
            if r < 0.15:
                return CameraResult(object_type="person", confidence=0.4)
            elif r < 0.35:
                return CameraResult(object_type="bag", confidence=0.5)
            return None

        elif scenario == Scenario.CONFIRMED_GHOST:
            if r < 0.75:
                conf = 0.65 + random.uniform(-0.15, 0.1)
                return CameraResult(object_type="bag", confidence=max(0.4, min(0.8, conf)))
            return None

        else:
            if r < 0.05:
                return CameraResult(object_type="bag", confidence=0.2)
            return None

    def _generate_radar_data(self, scenario: Scenario, dwell_time: float) -> RadarResult:
        if scenario == Scenario.OCCUPIED:
            presence = 0.8 + random.uniform(-0.15, 0.1)
            motion = 0.35 + random.uniform(-0.25, 0.25) if random.random() > 0.4 else 0.05
            return RadarResult(
                presence=max(0.5, min(0.95, presence)),
                motion=max(0.0, min(0.7, motion)),
                micro_motion=random.random() > 0.3,
            )

        elif scenario == Scenario.SUSPECTED_GHOST:
            if dwell_time < GHOST_GRACE_PERIOD * 0.5:
                presence = 0.6 + random.uniform(-0.1, 0.1)
            elif dwell_time < GHOST_GRACE_PERIOD:
                presence = 0.5 + random.uniform(-0.1, 0.1)
            else:
                presence = 0.4 + random.uniform(-0.05, 0.05)
            return RadarResult(
                presence=max(0.45, min(0.7, presence)),
                motion=0.05 if random.random() > 0.8 else 0.0,
                micro_motion=False,
            )

        elif scenario == Scenario.CONFIRMED_GHOST:
            return RadarResult(
                presence=0.45 + random.uniform(-0.05, 0.05),
                motion=0.0,
                micro_motion=False,
            )

        else:
            return RadarResult(
                presence=0.02 + random.uniform(-0.01, 0.01),
                motion=0.0,
                micro_motion=False,
            )

    def _update_ground_truth(self, delta_time: float):
        for seat_id, gt in self.ground_truth.items():
            gt.dwell_time += delta_time
            r = random.random()

            if gt.scenario == Scenario.EMPTY:
                if r < 0.03 * delta_time:
                    gt.scenario = Scenario.OCCUPIED
                    gt.dwell_time = 0

            elif gt.scenario == Scenario.OCCUPIED:
                if gt._leave_threshold is None:
                    gt._leave_threshold = random.uniform(30, 180)
                if gt.dwell_time > gt._leave_threshold:
                    if r < 0.4:
                        gt.scenario = Scenario.SUSPECTED_GHOST
                        gt.dwell_time = 0
                        gt._leave_threshold = None
                    else:
                        gt._leave_threshold = random.uniform(30, 180)

            elif gt.scenario == Scenario.SUSPECTED_GHOST:
                if gt.dwell_time > GHOST_THRESHOLD:
                    if r < 0.3:
                        gt.scenario = Scenario.OCCUPIED
                        gt.dwell_time = 0
                    elif r < 0.6:
                        gt.scenario = Scenario.CONFIRMED_GHOST
                        gt.dwell_time = 0
                    else:
                        gt.scenario = Scenario.EMPTY
                        gt.dwell_time = 0

            elif gt.scenario == Scenario.CONFIRMED_GHOST:
                if gt.dwell_time > random.uniform(180, 600):
                    if r < 0.6:
                        gt.scenario = Scenario.EMPTY
                        gt.dwell_time = 0

    def generate_for_zone(self, zone: str) -> Dict:
        detector = self.ghost_detectors[zone]
        seats_output = {}

        for seat_id in DEFAULT_ZONE_SEATS[zone]:
            gt = self.ground_truth[seat_id]

            camera_result = self._generate_camera_detection(gt.scenario)
            radar_result = self._generate_radar_data(gt.scenario, gt.dwell_time)

            fused = self.sensor_fusion.fuse(camera_result, radar_result)

            alert = detector.update(seat_id, fused)

            seat_record = detector.get_seat_record(seat_id)
            current_state = seat_record.state.value

            seats_output[seat_id] = {
                "zone_id": zone,
                "state": current_state,
                "ghost_state": current_state,
                "is_occupied": seat_record.state in (
                    SeatState.OCCUPIED,
                    SeatState.SUSPECTED_GHOST,
                    SeatState.CONFIRMED_GHOST,
                ),
                "object_type": fused.object_type,
                "confidence": fused.confidence,
                "yolo_match": camera_result is not None,
                "yolo_confidence": camera_result.confidence if camera_result else 0.0,
                "dwell_time": seat_record.state_entered_time,
                "time_since_motion": time.time() - seat_record.last_motion_time,
                "ghost_duration": seat_record.last_occupancy_score if seat_record.state == SeatState.CONFIRMED_GHOST else 0,
                "ghost_objects": ["bag"] if current_state in ("suspected_ghost", "confirmed_ghost") else [],
                "radar_presence": fused.radar_presence,
                "radar_motion": fused.radar_motion,
                "radar_micro_motion": fused.radar_micro_motion,
                "has_motion": fused.has_motion,
                "timestamp": time.time(),
            }

        total = len(seats_output)
        occupied = sum(1 for s in seats_output.values() if s["is_occupied"])
        empty = sum(1 for s in seats_output.values() if s["state"] == "empty")
        suspected = sum(1 for s in seats_output.values() if s["state"] == "suspected_ghost")
        confirmed = sum(1 for s in seats_output.values() if s["state"] == "confirmed_ghost")

        return {
            "source": f"synthetic_rpi_{zone}",
            "room_id": f"library_{zone.lower()}",
            "timestamp": time.time(),
            "scan_id": int(time.time() * 1000),
            "seats": seats_output,
            "zone_stats": {
                "total": total,
                "occupied": occupied,
                "empty": empty,
                "suspected": suspected,
                "confirmed": confirmed,
            },
        }

    def run(
        self,
        interval: float = 3.0,
        duration: float = None,
        dry_run: bool = False,
    ):
        mqtt_client = None

        if not dry_run and MQTT_AVAILABLE:
            try:
                client = paho_mqtt.Client(client_id=MQTT_CLIENT_ID)
                client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_KEEPALIVE)
                client.loop_start()
                mqtt_client = client
                logger.info(f"Connected to MQTT broker at {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
            except Exception as e:
                logger.warning(f"Failed to connect to MQTT: {e}. Running in dry-run mode.")
                dry_run = True
        else:
            logger.info("Running in DRY-RUN mode (no MQTT)")
            dry_run = True

        start_time = time.time()

        try:
            while True:
                iter_start = time.time()

                self._update_ground_truth(interval)

                for zone in self.zones:
                    data = self.generate_for_zone(zone)

                    ghosts = data['zone_stats']['suspected'] + data['zone_stats']['confirmed']
                    logger.info(
                        f"[{zone}] Occupied: {data['zone_stats']['occupied']}/4, "
                        f"Ghosts: {ghosts} ({data['zone_stats']['suspected']} suspected, "
                        f"{data['zone_stats']['confirmed']} confirmed)"
                    )

                    if not dry_run and mqtt_client and mqtt_client.is_connected():
                        topic = MQTT_TOPIC_RPI_OCCUPANCY.format(zone=zone)
                        mqtt_client.publish(topic, json.dumps(data), qos=1)

                if duration and (time.time() - start_time) >= duration:
                    break

                elapsed = time.time() - iter_start
                time.sleep(max(0.1, interval - elapsed))

        except KeyboardInterrupt:
            logger.info("Interrupted. Stopping.")
        finally:
            if mqtt_client:
                mqtt_client.loop_stop()
                mqtt_client.disconnect()

def main():
    parser = argparse.ArgumentParser(description="Synthetic Data Generator for Liberty Twin")
    parser.add_argument("--zones", type=str, help="Comma-separated zones (e.g., Z1,Z2)")
    parser.add_argument("--interval", type=float, default=3.0, help="Update interval (default: 3s)")
    parser.add_argument("--duration", type=float, help="Run for duration (seconds)")
    parser.add_argument("--dry-run", action="store_true", help="Print instead of sending to MQTT")
    parser.add_argument("--debug", action="store_true", help="Debug logging")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    zones = None
    if args.zones:
        zones = [z.strip().upper() for z in args.zones.split(",")]

    generator = SyntheticDataGenerator(zones=zones)
    generator.run(interval=args.interval, duration=args.duration, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
