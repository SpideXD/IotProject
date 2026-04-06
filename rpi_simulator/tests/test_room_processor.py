"""
Integration tests for RoomProcessor.
"""
import unittest
import sys
import os
import json
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock the requests module before importing RoomProcessor
sys.modules['requests'] = MagicMock()

from room_processor import RoomProcessor


class TestRoomProcessor(unittest.TestCase):
    """Integration tests for RoomProcessor."""

    def setUp(self):
        """Set up test fixtures."""
        self.processor = RoomProcessor(
            room_id="test_room",
            edge_url="http://localhost:5002",
            send_deltas=False,  # Always send for testing
        )

    def test_process_camera_frame_updates_seats(self):
        """Camera frame should update seat states."""
        data = {
            "sensor": "Rail_Back_001",
            "frame": "fake_base64_data",
            "detections": [
                {"cls": "person", "confidence": 0.9, "bbox": [0, 0, 100, 100]}
            ]
        }

        result = self.processor.process_camera_frame(data)

        self.assertEqual(result["status"], "sent")

        # Check seat state
        seat_state = self.processor.seat_state
        # Z1 has seats S1-S4, first person should be on S1
        self.assertTrue(seat_state["S1"]["is_occupied"])
        self.assertEqual(seat_state["S1"]["object_type"], "person")

    def test_process_telemetry_caches_radar(self):
        """Telemetry should cache radar data."""
        data = {
            "sensor": "Rail_Back_001",
            "presence": 0.8,
            "motion": 0.3,
            "micro_motion": False
        }

        result = self.processor.process_telemetry(data)

        self.assertEqual(result["status"], "sent")

        # Check seat state has radar data
        seat_state = self.processor.seat_state
        # S1-S4 are in Z1 (mapped to Rail_Back_001)
        self.assertGreater(seat_state["S1"]["radar_presence"], 0)

    def test_delta_compression_skips_no_change(self):
        """Should skip sending when state hasn't changed."""
        processor = RoomProcessor(
            room_id="test_room",
            edge_url="http://localhost:5002",
            send_deltas=True,  # Delta mode
        )

        # First update
        data1 = {
            "sensor": "Rail_Back_001",
            "detections": [{"cls": "person", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
        }
        result1 = processor.process_camera_frame(data1)
        self.assertEqual(result1["status"], "sent")

        # Same update again - should skip
        result2 = processor.process_camera_frame(data1)
        self.assertEqual(result2["status"], "no_change")

    def test_reset_clears_state(self):
        """Reset should clear all seat states."""
        # First, occupy some seats
        data = {
            "sensor": "Rail_Back_001",
            "detections": [{"cls": "person", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
        }
        self.processor.process_camera_frame(data)

        # Reset
        self.processor._init_seat_state()

        # Check all empty
        seat_state = self.processor.seat_state
        for seat in seat_state.values():
            self.assertFalse(seat["is_occupied"])

    def test_get_occupancy_summary(self):
        """Should return correct occupancy summary."""
        # Occupy one seat
        data = {
            "sensor": "Rail_Back_001",
            "detections": [{"cls": "person", "confidence": 0.9, "bbox": [0, 0, 100, 100]}]
        }
        self.processor.process_camera_frame(data)

        summary = self.processor.get_occupancy_summary()

        self.assertEqual(summary["room_id"], "test_room")
        self.assertEqual(summary["total_seats"], 28)
        self.assertEqual(summary["occupied"], 1)
        self.assertEqual(summary["empty"], 27)

    def test_unknown_sensor_returns_error(self):
        """Unknown sensor should return error status."""
        data = {
            "sensor": "Unknown_Sensor",
            "detections": []
        }

        result = self.processor.process_camera_frame(data)

        self.assertEqual(result["status"], "unknown_sensor")

    def test_multiple_detections_per_zone(self):
        """Should handle multiple detections in same zone."""
        # 4 persons in zone Z1 (S1-S4)
        data = {
            "sensor": "Rail_Back_001",
            "detections": [
                {"cls": "person", "confidence": 0.9, "bbox": [0, 0, 50, 50]},
                {"cls": "person", "confidence": 0.8, "bbox": [50, 0, 100, 50]},
                {"cls": "person", "confidence": 0.85, "bbox": [100, 0, 150, 50]},
                {"cls": "person", "confidence": 0.75, "bbox": [150, 0, 200, 50]},
            ]
        }

        self.processor.process_camera_frame(data)

        seat_state = self.processor.seat_state
        # All 4 seats in Z1 should be occupied
        for seat_id in ["S1", "S2", "S3", "S4"]:
            self.assertTrue(seat_state[seat_id]["is_occupied"], f"{seat_id} should be occupied")

    def test_status_property(self):
        """Status should return correct info."""
        status = self.processor.status

        self.assertEqual(status["room_id"], "test_room")
        self.assertEqual(status["frames_received"], 0)
        self.assertEqual(status["edge_url"], "http://localhost:5002")


if __name__ == "__main__":
    unittest.main()
