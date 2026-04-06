
import logging
from dataclasses import dataclass, field
from typing import Optional

from config import CAMERA_WEIGHT, RADAR_WEIGHT, AGREEMENT_BONUS, PRESENCE_THRESHOLD, MOTION_THRESHOLD

logger = logging.getLogger("sensor_fusion")

@dataclass
class CameraResult:
    object_type: str = "empty"
    confidence: float = 0.0

@dataclass
class RadarResult:
    presence: float = 0.0
    motion: float = 0.0
    micro_motion: bool = False

@dataclass
class FusedResult:
    occupancy_score: float = 0.0
    object_type: str = "empty"
    confidence: float = 0.0
    is_present: bool = False
    has_motion: bool = False
    radar_presence: float = 0.0
    radar_motion: float = 0.0
    radar_micro_motion: bool = False

class SensorFusion:

    def __init__(
        self,
        camera_weight: float = CAMERA_WEIGHT,
        radar_weight: float = RADAR_WEIGHT,
        agreement_bonus: float = AGREEMENT_BONUS,
        presence_threshold: float = PRESENCE_THRESHOLD,
    ):
        self.camera_weight = camera_weight
        self.radar_weight = radar_weight
        self.agreement_bonus = agreement_bonus
        self.presence_threshold = presence_threshold

    def fuse(
        self,
        camera_result: Optional[CameraResult] = None,
        radar_result: Optional[RadarResult] = None,
    ) -> FusedResult:
        cam_conf = 0.0
        cam_type = "empty"
        radar_pres = 0.0
        radar_mot = 0.0
        radar_micro = False

        if camera_result is not None:
            cam_conf = max(0.0, min(1.0, camera_result.confidence))
            cam_type = camera_result.object_type
        if radar_result is not None:
            radar_pres = max(0.0, min(1.0, radar_result.presence))
            radar_mot = max(0.0, min(1.0, radar_result.motion))
            radar_micro = radar_result.micro_motion

        occupancy = self.camera_weight * cam_conf + self.radar_weight * radar_pres

        camera_says_present = (cam_type != "empty" and cam_conf > 0.3)
        radar_says_present = (radar_pres >= self.presence_threshold)

        if camera_result is not None and radar_result is not None:
            if camera_says_present and radar_says_present:
                occupancy += self.agreement_bonus
                logger.debug("Agreement bonus applied (both say present)")
            elif not camera_says_present and not radar_says_present:
                occupancy = max(0.0, occupancy - self.agreement_bonus * 0.5)
                logger.debug("Agreement bonus: both say absent, reducing score")

        occupancy = max(0.0, min(1.0, occupancy))

        if cam_type != "empty" and cam_conf > 0.3:
            final_type = cam_type
        elif radar_pres >= self.presence_threshold:
            if radar_micro:
                final_type = "person"
            else:
                final_type = "object"
        else:
            final_type = "empty"

        has_motion = radar_mot > MOTION_THRESHOLD or radar_micro
        if camera_result is not None and cam_type == "person" and cam_conf > 0.5:
            has_motion = True

        result = FusedResult(
            occupancy_score=round(occupancy, 4),
            object_type=final_type,
            confidence=round(cam_conf if camera_result else radar_pres, 4),
            is_present=(occupancy >= self.presence_threshold),
            has_motion=has_motion,
            radar_presence=round(radar_pres, 4),
            radar_motion=round(radar_mot, 4),
            radar_micro_motion=radar_micro,
        )

        logger.debug(
            "Fused: cam(%s %.2f) + radar(pres=%.2f mot=%.2f micro=%s) "
            "-> occ=%.3f type=%s present=%s motion=%s",
            cam_type, cam_conf, radar_pres, radar_mot, radar_micro,
            result.occupancy_score, result.object_type,
            result.is_present, result.has_motion,
        )

        return result
