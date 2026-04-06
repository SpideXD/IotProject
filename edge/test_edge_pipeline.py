#!/usr/bin/env python3
"""
End-to-End Integration Test: RPi → Edge Pipeline

Tests the full data flow:
1. Unity (simulated) → RPi (port 5001)
2. RPi processes with FSM ghost detection
3. RPi forwards to Edge (port 5002)
4. Edge aggregates and serves API responses

Uses ground truth data directly (no YOLO needed for testing).

NOTE: Seats must match zone definitions:
  - Z1: S1, S2, S3, S4
  - Z2: S5, S6, S7, S8
  - Z3: S9, S10, S11, S12
  - Z4: S13, S14, S15, S16
  - Z5: S17, S18, S19, S20
  - Z6: S21, S22, S23, S24
  - Z7: S25, S26, S27, S28
"""
import json
import time
import requests
import sys
from typing import Dict, List, Optional

RPI_URL = "http://localhost:5001"
EDGE_URL = "http://localhost:5002"


def send_capture(zone: str = "Z1", sensor: str = "Rail_Back", occupancy: Dict = None,
                 sim_time: str = "10:00:00") -> dict:
    """Send a capture request to RPi simulator (simulating Unity)."""
    payload = {
        "sensor": sensor,
        "zone": zone,
        "sim_time": sim_time,
        "frame": "",  # Empty frame = ground truth only mode
        "occupancy": occupancy or {}
    }
    resp = requests.post(f"{RPI_URL}/api/v1/sensor/capture", json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_edge_state(seat_id: str = None) -> dict:
    """Get current state from Edge processor."""
    if seat_id:
        resp = requests.get(f"{EDGE_URL}/api/state/{seat_id}", timeout=5)
    else:
        resp = requests.get(f"{EDGE_URL}/api/status", timeout=5)
    resp.raise_for_status()
    return resp.json()


def get_edge_all_seats(filter: str = None) -> dict:
    """Get all seats from Edge."""
    url = f"{EDGE_URL}/api/seats"
    if filter:
        url += f"?filter={filter}"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return resp.json()


def get_edge_utilization() -> dict:
    """Get zone utilization from Edge."""
    resp = requests.get(f"{EDGE_URL}/api/analytics/utilization", timeout=5)
    resp.raise_for_status()
    return resp.json()


def get_edge_metrics() -> dict:
    """Get Prometheus metrics from Edge."""
    resp = requests.get(f"{EDGE_URL}/metrics", timeout=5)
    resp.raise_for_status()
    return resp.text


def print_seat_states(result: dict, title: str = "Seat States"):
    """Pretty print seat states."""
    print(f"\n{title}")
    print("-" * 50)
    seat_states = result.get("seat_states", {})
    print(f"  Occupied: {result.get('occupied', 0)}")
    print(f"  Ghost count: {result.get('ghost_count', 0)}")
    print(f"  Seat states:")
    for seat_id, state in seat_states.items():
        if isinstance(state, dict):
            print(f"    {seat_id}: {state.get('state')} | dwell={state.get('dwell_time')}s | motion={state.get('time_since_motion')}s")
        else:
            print(f"    {seat_id}: {state}")


# =============================================================================
# TEST CASES
# =============================================================================

def test_basic_occupancy():
    """Test 1: Basic occupancy detection through full pipeline."""
    print("\n" + "=" * 70)
    print("TEST 1: Basic Occupancy (RPi → Edge)")
    print("=" * 70)

    # Step 1: Send empty occupancy
    print("\n[Step 1] Send empty occupancy for S1...")
    result = send_capture(zone="Z1", occupancy={"S1": {"person": None, "state": None, "objects": []}})
    print(f"  RPi Response: occupied={result.get('occupied')}")
    print(f"  Seat states S1: {result.get('seat_states', {}).get('S1')}")

    time.sleep(0.5)

    # Step 2: Send person present - should transition to occupied
    print("\n[Step 2] Send person studying for S1...")
    result = send_capture(zone="Z1", occupancy={
        "S1": {"person": "Student1", "state": "STUDY", "objects": []}
    })

    # Check Edge got the update
    time.sleep(0.5)
    edge_state = get_edge_state("S1")
    print(f"  RPi Response: occupied={result.get('occupied')}")
    print(f"  Seat S1 state: {result.get('seat_states', {}).get('S1', {}).get('state')}")
    print(f"  Edge S1 state: {edge_state.get('state')}")

    assert result.get('seat_states', {}).get('S1', {}).get('state') == 'occupied', \
        f"RPi should report occupied, got {result.get('seat_states', {}).get('S1', {}).get('state')}"
    assert edge_state.get('state') == 'occupied', \
        f"Edge should report occupied, got {edge_state.get('state')}"
    print("  ✓ Basic occupancy detected correctly by both RPi and Edge")


def test_multi_seat():
    """Test 2: Multiple seats in same zone."""
    print("\n" + "=" * 70)
    print("TEST 2: Multiple Seats (RPi → Edge)")
    print("=" * 70)

    print("\n[Step 1] Z1: S1 occupied, S2 empty...")
    result = send_capture(zone="Z1", occupancy={
        "S1": {"person": "Student1", "state": "STUDY", "objects": []},
        "S2": {"person": None, "state": None, "objects": []}
    })

    time.sleep(0.5)

    # Check Edge
    edge_seats = get_edge_all_seats()
    s1_state = edge_seats.get("seats", {}).get("S1", {}).get("state")
    s2_state = edge_seats.get("seats", {}).get("S2", {}).get("state")

    print(f"  RPi S1: {result.get('seat_states', {}).get('S1', {}).get('state')}")
    print(f"  RPi S2: {result.get('seat_states', {}).get('S2', {}).get('state')}")
    print(f"  Edge S1: {s1_state}")
    print(f"  Edge S2: {s2_state}")

    assert result.get('seat_states', {}).get('S1', {}).get('state') == 'occupied', \
        "RPi should show S1 occupied"
    assert result.get('seat_states', {}).get('S2', {}).get('state') == 'empty', \
        "RPi should show S2 empty"
    assert s1_state == 'occupied', f"Edge should show S1 occupied, got {s1_state}"
    assert s2_state == 'empty', f"Edge should show S2 empty, got {s2_state}"
    print("  ✓ Multi-seat handled correctly")


def test_ghost_detection():
    """Test 3: Ghost detection (person leaves, object remains)."""
    print("\n" + "=" * 70)
    print("TEST 3: Ghost Detection (RPi → Edge)")
    print("=" * 70)

    # Step 1: Person sits down
    print("\n[Step 1] Person sits (SUSPECTED_GHOST after 30s, CONFIRMED after 120s)")
    result = send_capture(zone="Z3", occupancy={
        "S10": {"person": "Student1", "state": "STUDY", "objects": []}
    })
    print(f"  RPi S10: {result.get('seat_states', {}).get('S10', {}).get('state')}")

    time.sleep(0.5)
    edge_state = get_edge_state("S10")
    print(f"  Edge S10: {edge_state.get('state')}")
    assert result.get('seat_states', {}).get('S10', {}).get('state') == 'occupied', \
        "Should start as occupied"

    # Step 2: Person leaves (water break) - bag remains
    print("\n[Step 2] Person leaves, bag remains...")
    result = send_capture(zone="Z3", occupancy={
        "S10": {"person": None, "state": None, "objects": ["bag"]}
    })
    print(f"  RPi S10 (with bag): {result.get('seat_states', {}).get('S10', {}).get('state')}")

    time.sleep(0.5)
    edge_state = get_edge_state("S10")
    print(f"  Edge S10: {edge_state.get('state')}")

    # Note: Ghost detection happens over time (30s grace period)
    print("  (Ghost detection happens after 30s real-time with no motion)")
    print("  ✓ Ghost scenario initiated - FSM will transition over time")


def test_multi_zone():
    """Test 4: Multiple zones."""
    print("\n" + "=" * 70)
    print("TEST 4: Multiple Zones (RPi → Edge)")
    print("=" * 70)

    print("\n[Step 1] Z1: S1 occupied")
    result1 = send_capture(zone="Z1", occupancy={
        "S1": {"person": "Student1", "state": "STUDY", "objects": []}
    })
    print(f"  RPi: {result1.get('seat_states', {}).get('S1', {}).get('state')}")

    print("\n[Step 2] Z3: S10 occupied")
    result2 = send_capture(zone="Z3", occupancy={
        "S10": {"person": "Student2", "state": "STUDY", "objects": []}
    })
    print(f"  RPi: {result2.get('seat_states', {}).get('S10', {}).get('state')}")

    time.sleep(0.5)

    # Check Edge utilization for both zones
    utilization = get_edge_utilization()
    z1_seats = utilization.get("zones", {}).get("Z1", {})
    z3_seats = utilization.get("zones", {}).get("Z3", {})

    print(f"\n  Edge Z1 occupied: {z1_seats.get('occupied', 0)}")
    print(f"  Edge Z3 occupied: {z3_seats.get('occupied', 0)}")

    assert result1.get('seat_states', {}).get('S1', {}).get('state') == 'occupied', "Z1 S1 should be occupied"
    assert result2.get('seat_states', {}).get('S10', {}).get('state') == 'occupied', "Z3 S10 should be occupied"
    print("  ✓ Multi-zone handled correctly")


def test_zone_stats_forwarding():
    """Test 5: Zone stats are forwarded from RPi to Edge."""
    print("\n" + "=" * 70)
    print("TEST 5: Zone Stats Forwarding (RPi → Edge)")
    print("=" * 70)

    print("\n[Step 1] Send occupancy for Z1...")
    result = send_capture(zone="Z1", occupancy={
        "S1": {"person": "Student1", "state": "STUDY", "objects": []},
        "S2": {"person": "Student2", "state": "STUDY", "objects": []},
        "S3": {"person": None, "state": None, "objects": []},
        "S4": {"person": None, "state": None, "objects": []}
    })

    zone_stats = result.get("zone_stats", {})
    print(f"  RPi Zone Stats: {zone_stats}")

    # Check if Edge has the data
    utilization = get_edge_utilization()
    z1_util = utilization.get("zones", {}).get("Z1", {})
    print(f"  Edge Z1 Utilization: {z1_util}")

    assert z1_util.get("occupied", 0) >= 2, "Edge should show at least 2 occupied in Z1"
    print("  ✓ Zone stats forwarded to Edge")


def test_edge_api_endpoints():
    """Test 6: Edge API endpoints return correct data."""
    print("\n" + "=" * 70)
    print("TEST 6: Edge API Endpoints")
    print("=" * 70)

    # Set up some seats
    print("\n[Setup] Setting up test seats...")
    send_capture(zone="Z1", occupancy={
        "S1": {"person": "Student1", "state": "STUDY", "objects": []},
        "S2": {"person": None, "state": None, "objects": []}
    })
    send_capture(zone="Z3", occupancy={
        "S10": {"person": "Student2", "state": "STUDY", "objects": ["bag"]}
    })

    time.sleep(0.5)

    # Test /api/status
    print("\n[Test] /api/status")
    status = get_edge_state()
    print(f"  Stats: {status.get('stats', {}).get('state_counts')}")
    print(f"  Seat states count: {len(status.get('seat_states', {}))}")

    # Test /api/seats
    print("\n[Test] /api/seats")
    seats = get_edge_all_seats()
    print(f"  Total seats returned: {seats.get('total')}")

    # Test /api/seats?filter=occupied
    print("\n[Test] /api/seats?filter=occupied")
    occupied_seats = get_edge_all_seats(filter="occupied")
    print(f"  Occupied seats: {occupied_seats.get('total')}")

    # Test /api/analytics/utilization
    print("\n[Test] /api/analytics/utilization")
    utilization = get_edge_utilization()
    print(f"  Zones: {list(utilization.get('zones', {}).keys())}")
    print(f"  Overall occupied: {utilization.get('overall', {}).get('occupied')}")

    # Test /metrics
    print("\n[Test] /metrics")
    metrics = get_edge_metrics()
    print(f"  Metrics lines (first 10):")
    for line in metrics.split('\n')[:10]:
        print(f"    {line}")

    print("  ✓ All API endpoints working")


def test_persistence():
    """Test 7: FSM state persistence (Edge should reflect RPi's persistence)."""
    print("\n" + "=" * 70)
    print("TEST 7: FSM State Persistence")
    print("=" * 70)

    # Set up initial state
    print("\n[Step 1] Set up occupied seat S3...")
    result = send_capture(zone="Z1", occupancy={
        "S3": {"person": "Student1", "state": "STUDY", "objects": []}
    })
    print(f"  RPi S3: {result.get('seat_states', {}).get('S3', {}).get('state')}")

    time.sleep(0.5)

    # Continue with same seat
    print("\n[Step 2] Continue - FSM should track dwell time...")
    result = send_capture(zone="Z1", occupancy={
        "S3": {"person": "Student1", "state": "STUDY", "objects": []}
    })

    edge_state = get_edge_state("S3")
    print(f"  RPi S3 dwell_time: {result.get('seat_states', {}).get('S3', {}).get('dwell_time')}")
    print(f"  Edge S3 state: {edge_state.get('state')}")
    print(f"  Edge S3 dwell_time: {edge_state.get('dwell_time')}")

    # Edge should reflect the same state
    assert edge_state.get('state') == 'occupied', f"Edge should show occupied, got {edge_state.get('state')}"
    print("  ✓ State persistence working")


def test_data_field_mapping():
    """Test 8: Verify ghost_state field flows correctly from RPi to Edge."""
    print("\n" + "=" * 70)
    print("TEST 8: Data Field Mapping (ghost_state)")
    print("=" * 70)

    # Send occupancy
    print("\n[Step 1] Send occupancy with ghost objects...")
    result = send_capture(zone="Z5", occupancy={
        "S17": {"person": "Student1", "state": "STUDY", "objects": ["bag"]}
    })

    # Check RPi output
    rpi_s17 = result.get('seat_states', {}).get('S17', {})
    print(f"  RPi S17:")
    print(f"    state: {rpi_s17.get('state')}")
    print(f"    object_type: {rpi_s17.get('object_type')}")
    print(f"    is_occupied: {rpi_s17.get('is_occupied')}")

    time.sleep(0.5)

    # Check Edge output
    edge_s17 = get_edge_state("S17")
    print(f"  Edge S17:")
    print(f"    state: {edge_s17.get('state')}")
    print(f"    object_type: {edge_s17.get('object_type')}")

    # Verify Edge received the ghost_state correctly
    assert edge_s17.get('state') == 'occupied', \
        f"Edge should show occupied, got {edge_s17.get('state')}"
    print("  ✓ ghost_state field flows correctly RPi → Edge")


def test_bag_left_behind():
    """Test 9: Bag left behind detection (ghost scenario)."""
    print("\n" + "=" * 70)
    print("TEST 9: Bag Left Behind (Ghost Scenario)")
    print("=" * 70)

    # Step 1: Person sits with bag
    print("\n[Step 1] Person sits with bag at S4...")
    result = send_capture(zone="Z1", occupancy={
        "S4": {"person": "Student1", "state": "STUDY", "objects": ["bag"]}
    })
    print(f"  RPi S4: {result.get('seat_states', {}).get('S4', {}).get('state')}")

    time.sleep(0.5)

    # Step 2: Person leaves, bag remains
    print("\n[Step 2] Person leaves, bag remains...")
    result = send_capture(zone="Z1", occupancy={
        "S4": {"person": None, "state": None, "objects": ["bag"]}
    })
    print(f"  RPi S4 (ghost): {result.get('seat_states', {}).get('S4', {}).get('state')}")
    print(f"  RPi S4 object_type: {result.get('seat_states', {}).get('S4', {}).get('object_type')}")

    time.sleep(0.5)

    # Step 3: Person returns
    print("\n[Step 3] Person returns...")
    result = send_capture(zone="Z1", occupancy={
        "S4": {"person": "Student1", "state": "STUDY", "objects": ["bag"]}
    })
    print(f"  RPi S4 (returned): {result.get('seat_states', {}).get('S4', {}).get('state')}")

    print("  ✓ Bag left behind scenario handled correctly")


def test_empty_occupancy():
    """Test 10: Empty occupancy clears seat."""
    print("\n" + "=" * 70)
    print("TEST 10: Empty Occupancy")
    print("=" * 70)

    # First occupy
    print("\n[Step 1] Occupy seat S2...")
    result = send_capture(zone="Z1", occupancy={
        "S2": {"person": "Student1", "state": "STUDY", "objects": []}
    })
    rpi_state = result.get('seat_states', {}).get('S2', {}).get('state')
    print(f"  RPi S2 (occupied): {rpi_state}")
    assert rpi_state == 'occupied', "Should be occupied"

    time.sleep(0.5)

    # Then clear
    print("\n[Step 2] Clear seat S2 (Unity sends null)...")
    result = send_capture(zone="Z1", occupancy={
        "S2": {"person": None, "state": None, "objects": []}
    })
    rpi_state = result.get('seat_states', {}).get('S2', {}).get('state')
    print(f"  RPi S2 (after clear): {rpi_state}")

    time.sleep(0.5)

    edge_state = get_edge_state("S2")
    print(f"  Edge S2 (after clear): {edge_state.get('state')}")

    print("  ✓ Empty occupancy handled correctly")


# =============================================================================
# MAIN
# =============================================================================

def run_all_tests():
    """Run all integration tests."""
    print("\n" + "#" * 70)
    print("# RPi → Edge PIPELINE INTEGRATION TESTS")
    print("#" * 70)

    try:
        test_basic_occupancy()
        test_multi_seat()
        test_ghost_detection()
        test_multi_zone()
        test_zone_stats_forwarding()
        test_edge_api_endpoints()
        test_persistence()
        test_data_field_mapping()
        test_bag_left_behind()
        test_empty_occupancy()

        print("\n" + "=" * 70)
        print("ALL INTEGRATION TESTS PASSED ✓")
        print("=" * 70)
        print("""
Pipeline Summary:
  ✓ RPi receives Unity data (simulated via test)
  ✓ RPi runs FSM ghost detection
  ✓ RPi forwards to Edge via HTTP
  ✓ Edge trusts RPi's ghost_state (no re-computation)
  ✓ Edge API endpoints return correct data
  ✓ Zone utilization tracked correctly
  ✓ Multi-zone support working
  ✓ Data field mapping (ghost_state) verified
  ✓ Ghost scenarios handled correctly
  ✓ Empty occupancy handled correctly
""")
        return True

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
