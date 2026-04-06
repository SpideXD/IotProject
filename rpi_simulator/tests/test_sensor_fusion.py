"""
Unit tests for SensorFusion module.
"""
import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sensor_fusion import SensorFusion, CameraResult, RadarResult, FusedResult


class TestSensorFusion(unittest.TestCase):
    """Tests for SensorFusion class."""

    def setUp(self):
        """Set up test fixtures."""
        self.fusion = SensorFusion()

    def test_agreement_bonus_when_both_present(self):
        """When both camera and radar agree on presence, apply agreement bonus."""
        camera = CameraResult(object_type="person", confidence=0.7)
        radar = RadarResult(presence=0.7, motion=0.3, micro_motion=False)

        result = self.fusion.fuse(camera_result=camera, radar_result=radar)

        # Expected: 0.6*0.7 + 0.4*0.7 + 0.10 (agreement bonus) = 0.80
        self.assertGreater(result.occupancy_score, 0.7)
        self.assertTrue(result.is_present)
        self.assertEqual(result.object_type, "person")

    def test_agreement_penalty_when_both_absent(self):
        """When both camera and radar agree on absence, apply penalty."""
        camera = CameraResult(object_type="empty", confidence=0.0)
        radar = RadarResult(presence=0.0, motion=0.0, micro_motion=False)

        result = self.fusion.fuse(camera_result=camera, radar_result=radar)

        # Expected: 0.6*0 + 0.4*0 - 0.05 (agreement penalty) = 0
        self.assertEqual(result.occupancy_score, 0.0)
        self.assertFalse(result.is_present)
        self.assertEqual(result.object_type, "empty")

    def test_camera_weight_60_percent(self):
        """Camera should contribute 60% to occupancy score."""
        camera = CameraResult(object_type="person", confidence=1.0)
        radar = RadarResult(presence=0.0, motion=0.0, micro_motion=False)

        result = self.fusion.fuse(camera_result=camera, radar_result=radar)

        # Expected: 0.6*1.0 + 0.4*0 = 0.6
        self.assertEqual(result.occupancy_score, 0.6)
        self.assertTrue(result.is_present)

    def test_radar_weight_40_percent(self):
        """Radar should contribute 40% to occupancy score."""
        camera = CameraResult(object_type="empty", confidence=0.0)
        radar = RadarResult(presence=1.0, motion=0.0, micro_motion=False)

        result = self.fusion.fuse(camera_result=camera, radar_result=radar)

        # Expected: 0.6*0 + 0.4*1.0 = 0.4
        self.assertEqual(result.occupancy_score, 0.4)
        self.assertFalse(result.is_present)  # 0.4 < 0.6 threshold

    def test_micro_motion_detection(self):
        """Micro-motion from radar should be captured."""
        camera = CameraResult(object_type="empty", confidence=0.0)
        radar = RadarResult(presence=0.7, motion=0.0, micro_motion=True)  # Higher presence

        result = self.fusion.fuse(camera_result=camera, radar_result=radar)

        self.assertTrue(result.radar_micro_motion)
        # With presence >= 0.6 and micro_motion, object_type becomes "person"
        self.assertEqual(result.object_type, "person")

    def test_has_motion_threshold(self):
        """Motion should be detected when radar_motion > threshold (0.15)."""
        camera = CameraResult(object_type="person", confidence=0.8)
        radar = RadarResult(presence=0.7, motion=0.2, micro_motion=False)

        result = self.fusion.fuse(camera_result=camera, radar_result=radar)

        self.assertTrue(result.has_motion)
        self.assertTrue(result.is_present)

    def test_no_camera_result(self):
        """Should handle missing camera result gracefully."""
        radar = RadarResult(presence=0.8, motion=0.2, micro_motion=False)

        result = self.fusion.fuse(radar_result=radar)

        # With camera empty (0) and radar presence 0.8: score = 0.4*0.8 = 0.32
        # This is < 0.6 threshold, so not present
        self.assertFalse(result.is_present)
        self.assertEqual(result.object_type, "object")

    def test_no_radar_result(self):
        """Should handle missing radar result gracefully."""
        camera = CameraResult(object_type="person", confidence=1.0)  # Higher confidence

        result = self.fusion.fuse(camera_result=camera)

        # With camera person (1.0) and no radar: score = 0.6*1.0 = 0.6
        # This meets the presence threshold
        self.assertEqual(result.object_type, "person")
        self.assertTrue(result.is_present)
        # has_motion is True because camera person + conf > 0.5 triggers has_motion
        self.assertTrue(result.has_motion)

    def test_occupancy_score_bounded(self):
        """Occupancy score should always be between 0 and 1."""
        camera = CameraResult(object_type="person", confidence=1.0)
        radar = RadarResult(presence=1.0, motion=1.0, micro_motion=True)

        result = self.fusion.fuse(camera_result=camera, radar_result=radar)

        self.assertLessEqual(result.occupancy_score, 1.0)
        self.assertGreaterEqual(result.occupancy_score, 0.0)


if __name__ == "__main__":
    unittest.main()
