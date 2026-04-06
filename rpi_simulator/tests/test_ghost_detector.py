"""
Unit tests for GhostDetector FSM.
"""
import unittest
import unittest.mock as mock
import sys
import os
import time

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ghost_detector import GhostDetector, SeatState
from sensor_fusion import FusedResult


class TestGhostDetector(unittest.TestCase):
    """Tests for GhostDetector FSM."""

    def setUp(self):
        """Set up test fixtures with short timers for testing."""
        self.detector = GhostDetector(
            grace_period=0.05,   # 50ms for testing
            ghost_threshold=0.1,  # 100ms for testing
        )

    def _make_fused(self, is_present: bool = True, has_motion: bool = True,
                    occupancy_score: float = 0.8, radar_motion: float = 0.3,
                    radar_micro_motion: bool = False, object_type: str = "person"):
        """Helper to create FusedResult."""
        return FusedResult(
            occupancy_score=occupancy_score,
            object_type=object_type,
            confidence=0.8,
            is_present=is_present,
            has_motion=has_motion,
            radar_presence=0.8 if is_present else 0.0,
            radar_motion=radar_motion,
            radar_micro_motion=radar_micro_motion,
        )

    def test_initial_state_is_empty(self):
        """New seats should start in EMPTY state."""
        state = self.detector.get_state("S1")
        self.assertEqual(state, SeatState.EMPTY)

    def test_empty_to_occupied_on_present(self):
        """EMPTY -> OCCUPIED when presence detected."""
        fused = self._make_fused(is_present=True, has_motion=True)
        alert = self.detector.update("S1", fused)

        state = self.detector.get_state("S1")
        self.assertEqual(state, SeatState.OCCUPIED)

    def test_occupied_to_empty_when_absent(self):
        """OCCUPIED -> EMPTY when no presence."""
        # First occupy
        self.detector.update("S1", self._make_fused(is_present=True))
        # Then leave
        fused = self._make_fused(is_present=False, has_motion=False, occupancy_score=0.0)
        alert = self.detector.update("S1", fused)

        state = self.detector.get_state("S1")
        self.assertEqual(state, SeatState.EMPTY)

    def test_occupied_to_suspected_after_grace_period(self):
        """OCCUPIED -> SUSPECTED_GHOST after grace period with no motion."""
        # Occupy with motion
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=True))
        # Wait for grace period
        time.sleep(0.1)  # Small delay
        # Update with no motion but still present
        fused = self._make_fused(is_present=True, has_motion=False, radar_motion=0.0)
        alert = self.detector.update("S1", fused)

        state = self.detector.get_state("S1")
        # After grace period with no motion, should suspect ghost
        self.assertEqual(state, SeatState.SUSPECTED_GHOST)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, "ghost_suspected")

    def test_suspected_to_occupied_on_motion(self):
        """SUSPECTED_GHOST -> OCCUPIED when motion detected."""
        # Get to suspected state
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=True))  # empty->occupied
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=False, radar_motion=0.0))  # grace period

        # Motion returns
        fused = self._make_fused(is_present=True, has_motion=True, radar_motion=0.3)
        alert = self.detector.update("S1", fused)

        state = self.detector.get_state("S1")
        self.assertEqual(state, SeatState.OCCUPIED)

    def test_suspected_to_confirmed_after_threshold(self):
        """SUSPECTED_GHOST -> CONFIRMED_GHOST after ghost_threshold."""
        # Get to suspected state
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=True))  # empty->occupied
        time.sleep(0.06)  # Wait for grace_period
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=False, radar_motion=0.0))  # grace period -> suspected

        # Wait for ghost threshold (0.1)
        time.sleep(0.15)
        # Update with no motion
        fused = self._make_fused(is_present=True, has_motion=False, radar_motion=0.0)
        alert = self.detector.update("S1", fused)

        state = self.detector.get_state("S1")
        self.assertEqual(state, SeatState.CONFIRMED_GHOST)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, "ghost_confirmed")

    def test_confirmed_to_occupied_on_motion(self):
        """CONFIRMED_GHOST -> OCCUPIED when motion returns."""
        # Get to confirmed state
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=True))
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=False, radar_motion=0.0))
        time.sleep(0.1)
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=False, radar_motion=0.0))

        # Motion returns
        fused = self._make_fused(is_present=True, has_motion=True, radar_motion=0.3)
        alert = self.detector.update("S1", fused)

        state = self.detector.get_state("S1")
        self.assertEqual(state, SeatState.OCCUPIED)
        self.assertEqual(alert.alert_type, "person_returned")

    def test_seat_cleared_alert(self):
        """Alert when ghost seat becomes empty."""
        # Get to suspected - need to wait for grace_period
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=True))
        time.sleep(0.06)  # Wait for grace_period
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=False, radar_motion=0.0))

        # Now becomes empty
        fused = self._make_fused(is_present=False, has_motion=False, occupancy_score=0.0)
        alert = self.detector.update("S1", fused)

        state = self.detector.get_state("S1")
        self.assertEqual(state, SeatState.EMPTY)
        self.assertIsNotNone(alert)
        self.assertEqual(alert.alert_type, "seat_cleared")

    def test_micro_motion_revives_seat(self):
        """Micro-motion should prevent ghost detection."""
        # Occupy
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=True))
        # Update with no motion but micro_motion
        fused = self._make_fused(is_present=True, has_motion=False, radar_motion=0.0, radar_micro_motion=True)
        alert = self.detector.update("S1", fused)

        # Should stay occupied (micro_motion keeps it alive)
        state = self.detector.get_state("S1")
        self.assertEqual(state, SeatState.OCCUPIED)

    def test_get_recent_alerts(self):
        """Should track recent alerts."""
        # Create some alerts - need to wait for state transitions
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=True))
        time.sleep(0.06)  # Wait for grace_period
        self.detector.update("S1", self._make_fused(is_present=True, has_motion=False, radar_motion=0.0))  # -> suspected ghost

        alerts = self.detector.get_recent_alerts()
        self.assertGreater(len(alerts), 0)

    def test_get_all_states(self):
        """Should return all seat states."""
        self.detector.update("S1", self._make_fused(is_present=True))
        self.detector.update("S2", self._make_fused(is_present=False))

        states = self.detector.get_all_states()
        self.assertEqual(states["S1"], "occupied")
        self.assertEqual(states["S2"], "empty")


if __name__ == "__main__":
    unittest.main()
