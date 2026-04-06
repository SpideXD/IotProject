"""
Unit tests for MotionTracker module.
"""
import unittest
import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from motion_tracker import MotionTracker


class TestMotionTracker(unittest.TestCase):
    """Tests for MotionTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.tracker = MotionTracker()

    def test_dwell_time_increases_when_occupied(self):
        """Dwell time should increase while seat is occupied."""
        # First update - seat becomes occupied
        self.tracker.update("S1", has_motion=True, is_occupied=True)

        # Wait a bit
        time.sleep(0.05)

        # Second update - still occupied
        result = self.tracker.update("S1", has_motion=True, is_occupied=True)

        self.assertGreater(result["dwell_time"], 0)
        self.assertEqual(result["motion_status"], "active")
        self.assertTrue(result["is_occupied"])

    def test_dwell_time_resets_on_leave(self):
        """Dwell time should reset when seat becomes empty."""
        # Occupy
        self.tracker.update("S1", has_motion=True, is_occupied=True)
        time.sleep(0.05)

        # Leave
        result = self.tracker.update("S1", has_motion=False, is_occupied=False)

        self.assertEqual(result["dwell_time"], 0)
        self.assertFalse(result["is_occupied"])

    def test_micro_motion_resets_timer(self):
        """Motion should reset time since motion counter."""
        # First update with motion
        self.tracker.update("S1", has_motion=True, is_occupied=True)

        # Wait
        time.sleep(0.05)

        # Second update with motion again
        result = self.tracker.update("S1", has_motion=True, is_occupied=True)

        # Time since motion should be near zero
        self.assertLess(result["time_since_motion"], 0.1)
        self.assertEqual(result["motion_status"], "active")

    def test_no_motion_tracking(self):
        """Should track seats even with no motion."""
        # First update - seat seen for first time
        result = self.tracker.update("S1", has_motion=False, is_occupied=False)

        self.assertEqual(result["dwell_time"], 0)
        self.assertFalse(result["is_occupied"])

    def test_motion_status_active(self):
        """Motion status should be 'active' when recent motion."""
        self.tracker.update("S1", has_motion=True, is_occupied=True)
        result = self.tracker.update("S1", has_motion=True, is_occupied=True)

        self.assertEqual(result["motion_status"], "active")

    def test_motion_status_idle(self):
        """Motion status should be 'idle' after 5 seconds."""
        # Update with motion
        self.tracker.update("S1", has_motion=True, is_occupied=True)

        # Wait 6 seconds
        time.sleep(6)

        result = self.tracker.update("S1", has_motion=False, is_occupied=True)

        self.assertEqual(result["motion_status"], "idle")

    def test_motion_status_suspicious(self):
        """Motion status should be 'suspicious' after 30 seconds."""
        # Update with motion
        self.tracker.update("S1", has_motion=True, is_occupied=True)

        # Wait 31 seconds
        time.sleep(31)

        result = self.tracker.update("S1", has_motion=False, is_occupied=True)

        self.assertEqual(result["motion_status"], "suspicious")

    def test_get_summary(self):
        """Should return summary of all seats."""
        self.tracker.update("S1", has_motion=True, is_occupied=True)
        self.tracker.update("S2", has_motion=False, is_occupied=True)
        self.tracker.update("S3", has_motion=False, is_occupied=False)

        summary = self.tracker.get_summary()

        self.assertEqual(summary["total_seats"], 3)
        self.assertEqual(summary["occupied_seats"], 2)
        self.assertIn("S1", summary["per_seat"])

    def test_reset(self):
        """Should reset all tracking."""
        self.tracker.update("S1", has_motion=True, is_occupied=True)
        self.tracker.update("S2", has_motion=True, is_occupied=True)

        self.tracker.reset()

        summary = self.tracker.get_summary()
        self.assertEqual(summary["total_seats"], 0)


if __name__ == "__main__":
    unittest.main()
