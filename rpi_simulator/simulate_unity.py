#!/usr/bin/env python3
"""
Unity Simulator - Publishes test data like Unity would send.

This simulates the exact same data format that Unity sends to the RPi:
- Camera frames + detections via POST /api/camera
- Radar telemetry via POST /api/telemetry

Usage:
    python3 -m rpi_simulator.simulate_unity

Environment:
    RPI_URL - RPi HTTP server URL (default: http://localhost:5001)
    ROOM_ID - Room identifier (default: room_1)
"""
import os
import sys
import time
import random
import argparse
import threading
from dataclasses import dataclass
from typing import List, Optional

import requests

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rpi_simulator.config import SENSOR_TO_ZONE, ZONE_TO_SEATS

RPI_URL = os.environ.get("RPI_URL", "http://localhost:5001")
ROOM_ID = os.environ.get("ROOM_ID", "room_1")


@dataclass
class SeatSimulation:
    """Simulates a seat being occupied."""
    seat_id: str
    zone_id: str
    occupied: bool = False
    person_confidence: float = 0.0
    radar_presence: float = 0.0
    radar_motion: float = 0.0
    micro_motion: bool = False


class UnitySimulator:
    """
    Simulates Unity sensor data for testing RPi processor.

    Unity would normally send:
    - Camera detections with bounding boxes
    - Radar presence/motion/micro_motion

    This simulator creates realistic test patterns.
    """

    def __init__(self, rpi_url: str = RPI_URL, room_id: str = ROOM_ID):
        self.rpi_url = rpi_url
        self.room_id = room_id
        self.seats: List[SeatSimulation] = []
        self.running = False
        self._init_seats()

    def _init_seats(self):
        """Initialize seat simulations."""
        for zone_id, seat_ids in ZONE_TO_SEATS.items():
            for seat_id in seat_ids:
                self.seats.append(SeatSimulation(seat_id=seat_id, zone_id=zone_id))

    def _get_sensor_for_zone(self, zone_id: str) -> Optional[str]:
        """Get sensor name for a zone."""
        for sensor, zone in SENSOR_TO_ZONE.items():
            if zone == zone_id:
                return sensor
        return None

    def _build_camera_payload(self, zone_id: str) -> dict:
        """Build camera payload for a zone like Unity would."""
        zone_seats = [s for s in self.seats if s.zone_id == zone_id]
        detections = []

        # Sort by seat_id for consistent ordering
        zone_seats.sort(key=lambda x: x.seat_id)

        for seat in zone_seats:
            if seat.occupied and seat.person_confidence > 0:
                # Unity would provide bounding box based on seat position
                # We'll simulate realistic bbox positions per seat
                seat_num = int(seat.seat_id[1:]) if seat.seat_id.startswith('S') else 1
                x_offset = ((seat_num - 1) % 4) * 100

                detections.append({
                    "cls": "person",
                    "confidence": seat.person_confidence,
                    "bbox": [x_offset, 50, x_offset + 80, 150]  # [x1, y1, x2, y2]
                })

        sensor = self._get_sensor_for_zone(zone_id)
        if not sensor:
            return {}

        return {
            "sensor": sensor,
            "frame": "fake_base64_unity_frame",  # Unity would send real base64
            "detections": detections
        }

    def _build_telemetry_payload(self, zone_id: str) -> dict:
        """Build radar telemetry payload for a zone like Unity would."""
        zone_seats = [s for s in self.seats if s.zone_id == zone_id]
        sensor = self._get_sensor_for_zone(zone_id)
        if not sensor:
            return {}

        # Average radar values for the zone
        occupied_seats = [s for s in zone_seats if s.occupied]
        if occupied_seats:
            avg_presence = sum(s.radar_presence for s in occupied_seats) / len(occupied_seats)
            avg_motion = sum(s.radar_motion for s in occupied_seats) / len(occupied_seats)
            any_micro = any(s.micro_motion for s in occupied_seats)
        else:
            avg_presence = 0.0
            avg_motion = 0.0
            any_micro = False

        return {
            "sensor": sensor,
            "presence": avg_presence,
            "motion": avg_motion,
            "micro_motion": any_micro,
        }

    def _send_camera(self, zone_id: str) -> bool:
        """Send camera data for a zone."""
        payload = self._build_camera_payload(zone_id)
        if not payload:
            return False

        try:
            resp = requests.post(
                f"{self.rpi_url}/api/camera",
                json=payload,
                timeout=2
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def _send_telemetry(self, zone_id: str) -> bool:
        """Send radar telemetry for a zone."""
        payload = self._build_telemetry_payload(zone_id)
        if not payload:
            return False

        try:
            resp = requests.post(
                f"{self.rpi_url}/api/telemetry",
                json=payload,
                timeout=2
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def occupy_seat(self, seat_id: str, confidence: float = 0.9):
        """Simulate a person sitting on a seat."""
        for seat in self.seats:
            if seat.seat_id == seat_id:
                seat.occupied = True
                seat.person_confidence = confidence
                seat.radar_presence = random.uniform(0.7, 0.95)
                seat.radar_motion = random.uniform(0.1, 0.4)
                seat.micro_motion = random.choice([True, False])
                return True
        return False

    def vacate_seat(self, seat_id: str):
        """Simulate a person leaving a seat."""
        for seat in self.seats:
            if seat.seat_id == seat_id:
                seat.occupied = False
                seat.person_confidence = 0.0
                seat.radar_presence = 0.0
                seat.radar_motion = 0.0
                seat.micro_motion = False
                return True
        return False

    def set_zone_occupied(self, zone_id: str, count: int = None):
        """Set all seats in a zone as occupied."""
        zone_seats = [s for s in self.seats if s.zone_id == zone_id]
        if count is None:
            count = len(zone_seats)

        # First clear all
        for seat in zone_seats:
            seat.occupied = False

        # Then occupy first 'count' seats
        for i, seat in enumerate(zone_seats):
            if i >= count:
                break
            self.occupy_seat(seat.seat_id)

    def clear_all(self):
        """Clear all seats."""
        for seat in self.seats:
            seat.occupied = False
            seat.person_confidence = 0.0
            seat.radar_presence = 0.0
            seat.radar_motion = 0.0
            seat.micro_motion = False

    def send_all_zones(self):
        """Send data for all zones (camera + telemetry)."""
        results = {"camera": {}, "telemetry": {}}

        for zone_id in ["Z1", "Z2", "Z3", "Z4", "Z5", "Z6", "Z7"]:
            results["camera"][zone_id] = self._send_camera(zone_id)
            results["telemetry"][zone_id] = self._send_telemetry(zone_id)

        return results

    def get_state(self) -> dict:
        """Get current simulated state."""
        occupied = sum(1 for s in self.seats if s.occupied)
        return {
            "total_seats": len(self.seats),
            "occupied": occupied,
            "empty": len(self.seats) - occupied,
        }


class SimulationScenario:
    """Pre-defined simulation scenarios for testing."""

    @staticmethod
    def empty(sim: UnitySimulator):
        """All seats empty."""
        sim.clear_all()

    @staticmethod
    def one_person(sim: UnitySimulator):
        """One person on seat S1."""
        sim.clear_all()
        sim.occupy_seat("S1")

    @staticmethod
    def full_zone(sim: UnitySimulator):
        """All seats in zone Z1 occupied."""
        sim.clear_all()
        sim.set_zone_occupied("Z1", 4)

    @staticmethod
    def scattered(sim: UnitySimulator):
        """Scattered occupancy across zones."""
        sim.clear_all()
        sim.occupy_seat("S1")
        sim.occupy_seat("S5")
        sim.occupy_seat("S10")
        sim.occupy_seat("S15")
        sim.occupy_seat("S20")
        sim.occupy_seat("S25")

    @staticmethod
    def half_occupancy(sim: UnitySimulator):
        """50% occupancy across all zones."""
        sim.clear_all()
        for i in range(1, 29, 2):  # Odd seats
            sim.occupy_seat(f"S{i}")


def run_continuous(
    rpi_url: str = RPI_URL,
    interval: float = 1.0,
    scenario: str = "scattered",
):
    """Run continuous simulation with cycling scenarios."""
    sim = UnitySimulator(rpi_url=rpi_url)

    scenarios = {
        "empty": SimulationScenario.empty,
        "one": SimulationScenario.one_person,
        "full_zone": SimulationScenario.full_zone,
        "scattered": SimulationScenario.scattered,
        "half": SimulationScenario.half_occupancy,
    }

    scenario_func = scenarios.get(scenario, SimulationScenario.scattered)

    print(f"Starting Unity Simulator against {rpi_url}")
    print(f"Scenario: {scenario}")
    print(f"Interval: {interval}s")
    print("-" * 50)

    iteration = 0
    while True:
        iteration += 1
        state = sim.get_state()

        print(f"\n[Iteration {iteration}] State: {state['occupied']}/{state['total_seats']} occupied")

        # Cycle scenarios
        scenario_names = list(scenarios.keys())
        current_idx = scenario_names.index(scenario) if scenario in scenario_names else 0
        next_idx = (current_idx + 1) % len(scenario_names)
        next_scenario = scenario_names[next_idx]

        print(f"Applying scenario: {next_scenario}")
        scenario_func(sim)

        # Send data to RPi
        print("Sending to RPi...")
        results = sim.send_all_zones()

        camera_ok = sum(1 for v in results["camera"].values() if v)
        telemetry_ok = sum(1 for v in results["telemetry"].values() if v)

        print(f"  Camera: {camera_ok}/7 zones OK")
        print(f"  Telemetry: {telemetry_ok}/7 zones OK")

        # Get RPi state
        try:
            resp = requests.get(f"{rpi_url}/api/occupancy", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                summary = data.get("summary", {})
                print(f"  RPi reports: {summary.get('occupied', 0)} occupied, {summary.get('empty', 0)} empty")
        except:
            pass

        scenario = next_scenario
        time.sleep(interval)


def run_quick_test(rpi_url: str = RPI_URL):
    """Run a quick test of all scenarios."""
    sim = UnitySimulator(rpi_url=rpi_url)

    print(f"Running quick test against {rpi_url}")
    print("-" * 50)

    scenarios = [
        ("Empty", SimulationScenario.empty),
        ("One person (S1)", SimulationScenario.one_person),
        ("Full zone (Z1)", SimulationScenario.full_zone),
        ("Scattered", SimulationScenario.scattered),
        ("Half occupancy", SimulationScenario.half_occupancy),
    ]

    for name, func in scenarios:
        print(f"\n>>> Scenario: {name}")
        func(sim)

        print("Sending to RPi...")
        results = sim.send_all_zones()

        camera_ok = sum(1 for v in results["camera"].values() if v)
        telemetry_ok = sum(1 for v in results["telemetry"].values() if v)

        print(f"  Camera: {camera_ok}/7 zones OK")
        print(f"  Telemetry: {telemetry_ok}/7 zones OK")

        # Check RPi response
        try:
            resp = requests.get(f"{rpi_url}/api/occupancy", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                summary = data.get("summary", {})
                occupied = summary.get('occupied', 0)
                print(f"  RPi: {occupied} occupied, {summary.get('empty', 0)} empty")
        except Exception as e:
            print(f"  Error checking RPi: {e}")

        time.sleep(0.5)

    print("\n" + "=" * 50)
    print("Quick test complete!")


def main():
    parser = argparse.ArgumentParser(description="Unity Simulator for RPi testing")
    parser.add_argument(
        "--url",
        default=os.environ.get("RPI_URL", "http://localhost:5001"),
        help="RPi HTTP server URL"
    )
    parser.add_argument(
        "--continuous",
        "-c",
        action="store_true",
        help="Run continuously"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Interval between updates (seconds)"
    )
    parser.add_argument(
        "--scenario",
        choices=["empty", "one", "full_zone", "scattered", "half"],
        default="scattered",
        help="Initial scenario to run"
    )

    args = parser.parse_args()

    if args.continuous:
        run_continuous(rpi_url=args.url, interval=args.interval, scenario=args.scenario)
    else:
        run_quick_test(rpi_url=args.url)


if __name__ == "__main__":
    main()
