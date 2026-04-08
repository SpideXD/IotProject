
import argparse
import json
import logging
import os
import random
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("multi_rpi")

MQTT_BROKER_HOST = os.environ.get("MQTT_HOST", "localhost")
MQTT_BROKER_PORT = int(os.environ.get("MQTT_PORT", 1883))
MQTT_KEEPALIVE = 60

ZONE_SEATS = {
    "Z1": ["S1", "S2", "S3", "S4"],
    "Z2": ["S5", "S6", "S7", "S8"],
    "Z3": ["S9", "S10", "S11", "S12"],
    "Z4": ["S13", "S14", "S15", "S16"],
    "Z5": ["S17", "S18", "S19", "S20"],
    "Z6": ["S21", "S22", "S23", "S24"],
    "Z7": ["S25", "S26", "S27", "S28"],
}

SEAT_TO_ZONE = {}
for zone, seats in ZONE_SEATS.items():
    for seat in seats:
        SEAT_TO_ZONE[seat] = zone

class GhostFSM:
    def __init__(self, seat_id: str):
        self.seat_id = seat_id
        self.state = "empty"
        self.last_motion_time = time.time()
        self.last_state_change = time.time()
        self.dwell_time = 0
        self.ghost_duration = 0

        self.GRACE_PERIOD = 30.0
        self.CONFIRM_PERIOD = 120.0

    def update(self, is_present: bool, has_objects: bool = False) -> Dict:
        now = time.time()

        if is_present:
            self.last_motion_time = now
            if self.state in ("empty", "suspected_ghost", "confirmed_ghost"):
                self.state = "occupied"
                self.last_state_change = now
            self.dwell_time = now - self.last_state_change
            self.ghost_duration = 0
        else:
            self.dwell_time = 0
            time_since_motion = now - self.last_motion_time

            if self.state == "occupied":
                if time_since_motion >= self.CONFIRM_PERIOD:
                    self.state = "confirmed_ghost"
                    self.ghost_duration = time_since_motion
                elif time_since_motion >= self.GRACE_PERIOD:
                    self.state = "suspected_ghost"
                    self.ghost_duration = time_since_motion
                else:
                    self.ghost_duration = time_since_motion

            elif self.state == "suspected_ghost":
                if time_since_motion >= self.CONFIRM_PERIOD:
                    self.state = "confirmed_ghost"
                self.ghost_duration = time_since_motion

            elif self.state == "confirmed_ghost":
                self.ghost_duration = time_since_motion

        return self.get_state()

    def get_state(self) -> Dict:
        return {
            "state": self.state,
            "dwell_time": self.dwell_time,
            "ghost_duration": self.ghost_duration,
            "time_since_motion": time.time() - self.last_motion_time,
            "is_occupied": self.state == "occupied",
        }

class ZoneFSM:
    def __init__(self, zone: str):
        self.zone = zone
        self.seats = {seat: GhostFSM(seat) for seat in ZONE_SEATS[zone]}
        self.state_file = f"/tmp/multi_rpi_fsm_{zone}.json"
        self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file) as f:
                    data = json.load(f)
                for seat_id, state_data in data.items():
                    if seat_id in self.seats:
                        fsm = self.seats[seat_id]
                        fsm.state = state_data.get("state", "empty")
                        fsm.last_motion_time = state_data.get("last_motion_time", time.time())
                        fsm.last_state_change = state_data.get("last_state_change", time.time())
                        fsm.dwell_time = state_data.get("dwell_time", 0)
                        fsm.ghost_duration = state_data.get("ghost_duration", 0)
                logger.info(f"Loaded FSM state for {self.zone} from {self.state_file}")
            except Exception as e:
                logger.warning(f"Failed to load FSM state for {self.zone}: {e}")

    def _save_state(self):
        try:
            data = {}
            for seat_id, fsm in self.seats.items():
                data[seat_id] = {
                    "state": fsm.state,
                    "last_motion_time": fsm.last_motion_time,
                    "last_state_change": fsm.last_state_change,
                    "dwell_time": fsm.dwell_time,
                    "ghost_duration": fsm.ghost_duration,
                }
            with open(self.state_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save FSM state for {self.zone}: {e}")

    def update(self, occupancy: Dict[str, Dict]) -> Dict[str, Dict]:
        results = {}
        for seat_id, fsm in self.seats.items():
            seat_data = occupancy.get(seat_id, {})
            is_present = seat_data.get("is_present", False)
            has_objects = seat_data.get("has_objects", False)
            results[seat_id] = fsm.update(is_present, has_objects)
        self._save_state()
        return results

class MultiRPiSimulator:
    def __init__(self, zones: List[str], interval: float = 5.0):
        self.zones = zones
        self.interval = interval
        self.mqtt_client = None
        self.fsms = {zone: ZoneFSM(zone) for zone in zones}
        self.running = False
        self.stats = {
            "total_messages": 0,
            "by_zone": {zone: 0 for zone in zones}
        }

        self.zone_patterns = self._init_patterns()

    def _init_patterns(self) -> Dict[str, Dict]:
        return {
            "Z1": {"occupied_prob": 0.75, "ghost_prob": 0.1, "name": "Study Hall"},
            "Z2": {"occupied_prob": 0.60, "ghost_prob": 0.15, "name": "Reading Room"},
            "Z3": {"occupied_prob": 0.80, "ghost_prob": 0.08, "name": "Main Study"},
            "Z4": {"occupied_prob": 0.45, "ghost_prob": 0.12, "name": "Corner Section"},
            "Z5": {"occupied_prob": 0.55, "ghost_prob": 0.10, "name": "East Wing"},
            "Z6": {"occupied_prob": 0.70, "ghost_prob": 0.05, "name": "West Wing"},
            "Z7": {"occupied_prob": 0.30, "ghost_prob": 0.20, "name": "Relaxation Zone"},
        }

    def _connect_mqtt(self) -> bool:
        try:
            import paho.mqtt.client as paho_mqtt
            try:
                client = paho_mqtt.Client(
                    callback_api_version=paho_mqtt.CallbackAPIVersion.VERSION2,
                    client_id=f"multi_rpi_simulator_{os.getpid()}",
                )
            except (AttributeError, TypeError):
                client = paho_mqtt.Client(
                    client_id=f"multi_rpi_simulator_{os.getpid()}"
                )

            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, MQTT_KEEPALIVE)
            client.loop_start()
            self.mqtt_client = client
            logger.info(f"Connected to MQTT broker at {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
            return True
        except ImportError:
            logger.error("paho-mqtt not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code.is_failure:
            logger.warning(f"MQTT connection refused: {reason_code}")
        else:
            logger.info("MQTT connected successfully")

    def _on_disconnect(self, client, userdata, flags, reason_code=None, properties=None):
        logger.warning(f"MQTT disconnected (rc={reason_code})")

    def _generate_occupancy(self, zone: str) -> Dict[str, Dict]:
        pattern = self.zone_patterns.get(zone, {"occupied_prob": 0.5, "ghost_prob": 0.1})
        seats_data = {}

        for seat_id in ZONE_SEATS[zone]:
            rand = random.random()

            if rand < pattern["occupied_prob"]:
                seats_data[seat_id] = {
                    "is_present": True,
                    "has_objects": False,
                    "object_type": "person"
                }
            elif rand < pattern["occupied_prob"] + pattern["ghost_prob"]:
                seats_data[seat_id] = {
                    "is_present": False,
                    "has_objects": True,
                    "object_type": "bag"
                }
            else:
                seats_data[seat_id] = {
                    "is_present": False,
                    "has_objects": False,
                    "object_type": "empty"
                }

        return seats_data

    def _build_payload(self, zone: str, occupancy: Dict[str, Dict], seat_states: Dict[str, Dict]) -> Dict:
        seats_output = {}

        for seat_id in ZONE_SEATS[zone]:
            occ = occupancy.get(seat_id, {"is_present": False, "has_objects": False, "object_type": "empty"})
            state = seat_states.get(seat_id, {"state": "empty", "is_occupied": False, "dwell_time": 0})

            seats_output[seat_id] = {
                "zone_id": zone,
                "ghost_state": state["state"],
                "is_occupied": state["is_occupied"],
                "object_type": occ["object_type"],
                "confidence": 0.95,
                "yolo_match": True,
                "yolo_confidence": 0.9,
                "dwell_time": state["dwell_time"],
                "time_since_motion": state.get("time_since_motion", 0),
                "ghost_duration": state.get("ghost_duration", 0),
                "ghost_objects": ["bag"] if occ.get("has_objects") else [],
                "timestamp": time.time()
            }

        return {
            "source": f"multi_rpi_{zone}",
            "room_id": f"library_{zone.lower()}",
            "timestamp": time.time(),
            "scan_id": int(time.time() * 1000),
            "seats": seats_output,
            "zone_stats": {
                "total": len(ZONE_SEATS[zone]),
                "occupied": sum(1 for s in seat_states.values() if s["is_occupied"]),
                "empty": sum(1 for s in seat_states.values() if s["state"] == "empty"),
                "suspected": sum(1 for s in seat_states.values() if s["state"] == "suspected_ghost"),
                "confirmed": sum(1 for s in seat_states.values() if s["state"] == "confirmed_ghost"),
            }
        }

    def _publish_zone(self, zone: str):
        occupancy = self._generate_occupancy(zone)

        seat_states = self.fsms[zone].update(occupancy)

        payload = self._build_payload(zone, occupancy, seat_states)

        topic = f"liberty_twin/sensor/{zone}/occupancy"
        if self.mqtt_client and self.mqtt_client.is_connected():
            result = self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
            if result.is_published:
                self.stats["total_messages"] += 1
                self.stats["by_zone"][zone] += 1

                zone_stats = payload["zone_stats"]
                logger.info(
                    f"[{zone}] Published: {zone_stats['occupied']}/{zone_stats['total']} occupied, "
                    f"{zone_stats['suspected']} suspected, {zone_stats['confirmed']} confirmed ghost"
                )
            else:
                logger.warning(f"[{zone}] MQTT publish returned {result}")
        else:
            logger.warning(f"[{zone}] MQTT client not connected")

    def _run_cycle(self):
        for zone in self.zones:
            self._publish_zone(zone)

    def run(self, duration: Optional[int] = None):
        if not self._connect_mqtt():
            logger.error("Cannot run without MQTT connection")
            return

        self.running = True
        start_time = time.time()

        logger.info(f"Starting Multi-RPi Simulator for zones: {', '.join(self.zones)}")
        logger.info(f"Update interval: {self.interval}s | Duration: {'infinite' if duration is None else f'{duration}s'}")

        try:
            while self.running:
                self._run_cycle()

                if duration and (time.time() - start_time) >= duration:
                    break

                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        logger.info(f"Multi-RPi Simulator stopped. Total messages: {self.stats['total_messages']}")

def print_console_dashboard(edge_url: str = "http://localhost:5002", interval: int = 5):
    import requests

    print("\n" + "=" * 70)
    print("MULTI-RPI SIMULATION DASHBOARD")
    print("=" * 70)

    try:
        while True:
            try:
                resp = requests.get(f"{edge_url}/api/status", timeout=2)
                data = resp.json()

                stats = data.get("stats", {})
                state_counts = stats.get("state_counts", {})

                print(f"\n[{time.strftime('%H:%M:%S')}] Edge Status:")
                print(f"  Occupied: {state_counts.get('occupied', 0)}")
                print(f"  Empty:    {state_counts.get('empty', 0)}")
                print(f"  Suspected: {state_counts.get('suspected_ghost', 0)}")
                print(f"  Confirmed: {state_counts.get('confirmed_ghost', 0)}")
                print(f"  RPi Sources: {', '.join(stats.get('rpi_sources', []))}")

                seat_states = data.get("seat_states", {})
                occupied_seats = [s for s, state in seat_states.items() if state == "occupied"]
                print(f"  Occupied Seats: {', '.join(occupied_seats) if occupied_seats else 'none'}")

            except Exception as e:
                print(f"  Error fetching Edge status: {e}")

            time.sleep(interval)
    except KeyboardInterrupt:
        print("\nDashboard stopped")

def main():
    parser = argparse.ArgumentParser(description="Multi-RPi Simulator for Liberty Twin")
    parser.add_argument(
        "--zones",
        type=str,
        default="Z1,Z2,Z3,Z4,Z5,Z6,Z7",
        help="Comma-separated list of zones to simulate (default: all)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Update interval in seconds (default: 5)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=None,
        help="Run for N seconds then stop (default: run indefinitely)"
    )
    parser.add_argument(
        "--edge-url",
        type=str,
        default="http://localhost:5002",
        help="Edge processor URL for dashboard (default: http://localhost:5002)"
    )
    parser.add_argument(
        "--dashboard",
        action="store_true",
        help="Show console dashboard alongside simulation"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset FSM state files before starting"
    )
    args = parser.parse_args()

    zones = [z.strip() for z in args.zones.split(",")]
    invalid_zones = [z for z in zones if z not in ZONE_SEATS]
    if invalid_zones:
        logger.error(f"Invalid zones: {invalid_zones}")
        logger.error(f"Valid zones: {list(ZONE_SEATS.keys())}")
        sys.exit(1)

    if args.reset:
        import glob
        for f in glob.glob("/tmp/multi_rpi_fsm_*.json"):
            os.remove(f)
            logger.info(f"Removed {f}")

    simulator = MultiRPiSimulator(zones, interval=args.interval)

    if args.dashboard:
        import requests
        from threading import Thread

        def run_dashboard():
            print_console_dashboard(args.edge_url, interval=args.interval)

        dashboard_thread = Thread(target=run_dashboard, daemon=True)
        dashboard_thread.start()

        simulator.run(duration=args.duration)
    else:
        simulator.run(duration=args.duration)

    print("\n" + "=" * 70)
    print("SIMULATION COMPLETE")
    print("=" * 70)
    print(f"Total MQTT messages sent: {simulator.stats['total_messages']}")
    for zone, count in simulator.stats["by_zone"].items():
        print(f"  {zone}: {count} messages")

if __name__ == "__main__":
    main()
