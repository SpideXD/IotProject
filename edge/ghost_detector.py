
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional

from config import (
    GHOST_GRACE_PERIOD,
    GHOST_THRESHOLD,
    PRESENCE_THRESHOLD,
    MOTION_THRESHOLD,
    SEAT_TO_ZONE,
)
from sensor_fusion import FusedResult

logger = logging.getLogger("ghost_detector")

class SeatState(str, Enum):
    EMPTY = "empty"
    OCCUPIED = "occupied"
    SUSPECTED_GHOST = "suspected_ghost"
    CONFIRMED_GHOST = "confirmed_ghost"

@dataclass
class SeatRecord:
    state: SeatState = SeatState.EMPTY
    last_motion_time: float = 0.0
    state_entered_time: float = 0.0
    last_update_time: float = 0.0
    last_object_type: str = "empty"
    last_occupancy_score: float = 0.0

@dataclass
class GhostAlert:
    alert_type: str
    seat_id: str
    zone_id: str
    timestamp: float
    previous_state: str
    new_state: str
    details: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.alert_type,
            "seat_id": self.seat_id,
            "zone_id": self.zone_id,
            "timestamp": self.timestamp,
            "previous_state": self.previous_state,
            "new_state": self.new_state,
            "details": self.details,
        }

class GhostDetector:

    def __init__(
        self,
        grace_period: float = GHOST_GRACE_PERIOD,
        ghost_threshold: float = GHOST_THRESHOLD,
        presence_threshold: float = PRESENCE_THRESHOLD,
        motion_threshold: float = MOTION_THRESHOLD,
    ):
        self.grace_period = grace_period
        self.ghost_threshold = ghost_threshold
        self.presence_threshold = presence_threshold
        self.motion_threshold = motion_threshold

        self._seats: Dict[str, SeatRecord] = {}

    def _get_or_create(self, seat_id: str) -> SeatRecord:
        if seat_id not in self._seats:
            now = time.time()
            self._seats[seat_id] = SeatRecord(
                state=SeatState.EMPTY,
                last_motion_time=now,
                state_entered_time=now,
                last_update_time=now,
            )
        return self._seats[seat_id]

    def get_state(self, seat_id: str) -> SeatState:
        return self._get_or_create(seat_id).state

    def get_all_states(self) -> Dict[str, str]:
        return {sid: rec.state.value for sid, rec in self._seats.items()}

    def get_seat_record(self, seat_id: str) -> SeatRecord:
        return self._get_or_create(seat_id)

    def update(self, seat_id: str, fused: FusedResult) -> Optional[GhostAlert]:
        now = time.time()
        rec = self._get_or_create(seat_id)
        prev_state = rec.state

        rec.last_update_time = now
        rec.last_object_type = fused.object_type
        rec.last_occupancy_score = fused.occupancy_score

        if fused.has_motion and fused.radar_motion > self.motion_threshold:
            rec.last_motion_time = now

        if fused.radar_micro_motion:
            rec.last_motion_time = now

        time_since_motion = now - rec.last_motion_time
        time_in_state = now - rec.state_entered_time

        new_state = prev_state

        if prev_state == SeatState.EMPTY:
            if fused.is_present and fused.has_motion:
                new_state = SeatState.OCCUPIED
            elif fused.is_present:
                new_state = SeatState.OCCUPIED

        elif prev_state == SeatState.OCCUPIED:
            if not fused.is_present:
                new_state = SeatState.EMPTY
            elif time_since_motion > self.grace_period:
                new_state = SeatState.SUSPECTED_GHOST

        elif prev_state == SeatState.SUSPECTED_GHOST:
            if not fused.is_present:
                new_state = SeatState.EMPTY
            elif fused.has_motion and fused.radar_motion > self.motion_threshold:
                new_state = SeatState.OCCUPIED
            elif fused.radar_micro_motion:
                new_state = SeatState.OCCUPIED
            elif time_since_motion > self.ghost_threshold:
                new_state = SeatState.CONFIRMED_GHOST

        elif prev_state == SeatState.CONFIRMED_GHOST:
            if not fused.is_present:
                new_state = SeatState.EMPTY
            elif fused.has_motion and fused.radar_motion > self.motion_threshold:
                new_state = SeatState.OCCUPIED
            elif fused.radar_micro_motion:
                new_state = SeatState.OCCUPIED

        if new_state != prev_state:
            rec.state = new_state
            rec.state_entered_time = now

            alert = self._make_alert(seat_id, prev_state, new_state, now, fused)
            if alert:
                logger.info(
                    "Seat %s: %s -> %s (%s)",
                    seat_id, prev_state.value, new_state.value, alert.alert_type,
                )
            else:
                logger.debug(
                    "Seat %s: %s -> %s (no alert)",
                    seat_id, prev_state.value, new_state.value,
                )
            return alert

        return None

    @staticmethod
    def _make_alert(
        seat_id: str,
        prev: SeatState,
        new: SeatState,
        ts: float,
        fused: FusedResult,
    ) -> Optional[GhostAlert]:
        zone_id = SEAT_TO_ZONE.get(seat_id, "unknown")

        if new == SeatState.SUSPECTED_GHOST:
            return GhostAlert(
                alert_type="ghost_suspected",
                seat_id=seat_id,
                zone_id=zone_id,
                timestamp=ts,
                previous_state=prev.value,
                new_state=new.value,
                details=f"Object type '{fused.object_type}' detected with no motion. "
                         f"Occupancy score: {fused.occupancy_score:.2f}",
            )

        if new == SeatState.CONFIRMED_GHOST:
            return GhostAlert(
                alert_type="ghost_confirmed",
                seat_id=seat_id,
                zone_id=zone_id,
                timestamp=ts,
                previous_state=prev.value,
                new_state=new.value,
                details=f"Ghost confirmed. Object '{fused.object_type}' present "
                         f"for extended period with no human motion.",
            )

        if (prev in (SeatState.SUSPECTED_GHOST, SeatState.CONFIRMED_GHOST)
                and new == SeatState.OCCUPIED):
            return GhostAlert(
                alert_type="person_returned",
                seat_id=seat_id,
                zone_id=zone_id,
                timestamp=ts,
                previous_state=prev.value,
                new_state=new.value,
                details="Motion detected - person has returned to the seat.",
            )

        if (prev in (SeatState.SUSPECTED_GHOST, SeatState.CONFIRMED_GHOST)
                and new == SeatState.EMPTY):
            return GhostAlert(
                alert_type="seat_cleared",
                seat_id=seat_id,
                zone_id=zone_id,
                timestamp=ts,
                previous_state=prev.value,
                new_state=new.value,
                details="Items removed. Seat is now available.",
            )

        return None
