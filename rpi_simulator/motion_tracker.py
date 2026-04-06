"""
Motion Tracker for RPi Simulator.

Tracks motion patterns and dwell time per seat.
This module runs locally on the RPi to keep raw data private.
"""
import logging
import time
from typing import Dict

logger = logging.getLogger("rpi_simulator.motion_tracker")

class MotionTracker:
    """
    Track motion and dwell time for each seat.

    - Dwell time: How long a seat has been continuously occupied
    - Time since motion: Time since last detected motion
    - Micro-motion: Small movements detected by radar
    """

    def __init__(self):
        self._seat_motion: Dict[str, float] = {}  # seat_id -> last_motion_time
        self._seat_dwell: Dict[str, float] = {}   # seat_id -> dwell_start_time
        self._seat_occupied: Dict[str, bool] = {}  # seat_id -> was_last_occupied

    def update(
        self,
        seat_id: str,
        has_motion: bool,
        is_occupied: bool,
    ) -> dict:
        """
        Update motion state for a seat.

        Args:
            seat_id: Seat identifier
            has_motion: Whether motion was detected
            is_occupied: Whether the seat is currently occupied

        Returns:
            dict with dwell_time, time_since_motion, and motion_status
        """
        now = time.time()

        # Initialize if first time
        if seat_id not in self._seat_motion:
            self._seat_motion[seat_id] = now
            self._seat_dwell[seat_id] = 0.0
            self._seat_occupied[seat_id] = False

        was_occupied = self._seat_occupied.get(seat_id, False)

        # Calculate time since last motion
        time_since_motion = now - self._seat_motion[seat_id]

        # Update motion time if motion detected
        if has_motion:
            self._seat_motion[seat_id] = now
            time_since_motion = 0.0

        # Update dwell time
        if is_occupied:
            if not was_occupied:
                # Seat just became occupied, start dwell timer
                self._seat_dwell[seat_id] = now
            dwell_time = now - self._seat_dwell[seat_id]
        else:
            # Seat is empty, dwell time stops
            dwell_time = 0.0
            self._seat_dwell[seat_id] = 0.0

        # Update occupied state
        self._seat_occupied[seat_id] = is_occupied

        # Determine motion status
        if time_since_motion < 5.0:
            motion_status = "active"
        elif time_since_motion < 30.0:
            motion_status = "idle"
        elif time_since_motion < 120.0:
            motion_status = "suspicious"
        else:
            motion_status = "ghost"

        result = {
            "dwell_time": round(dwell_time, 2),
            "time_since_motion": round(time_since_motion, 2),
            "motion_status": motion_status,
            "has_motion": has_motion,
            "is_occupied": is_occupied,
        }

        logger.debug(
            "Motion [%s]: dwell=%.1fs since_motion=%.1fs status=%s",
            seat_id, dwell_time, time_since_motion, motion_status,
        )

        return result

    def get_dwell_time(self, seat_id: str) -> float:
        """Get current dwell time for a seat in seconds."""
        return self._seat_dwell.get(seat_id, 0.0)

    def get_time_since_motion(self, seat_id: str) -> float:
        """Get time since last motion for a seat in seconds."""
        if seat_id not in self._seat_motion:
            return 0.0
        return time.time() - self._seat_motion[seat_id]

    def get_motion_status(self, seat_id: str) -> str:
        """Get motion status string for a seat."""
        time_since = self.get_time_since_motion(seat_id)

        if time_since < 5.0:
            return "active"
        elif time_since < 30.0:
            return "idle"
        elif time_since < 120.0:
            return "suspicious"
        else:
            return "ghost"

    def get_summary(self) -> dict:
        """Get motion summary for all seats."""
        summary = {
            "total_seats": len(self._seat_occupied),
            "occupied_seats": sum(1 for v in self._seat_occupied.values() if v),
            "active_motion": sum(
                1 for sid in self._seat_occupied
                if self._seat_occupied[sid] and self.get_motion_status(sid) == "active"
            ),
            "idle": sum(
                1 for sid in self._seat_occupied
                if self._seat_occupied[sid] and self.get_motion_status(sid) == "idle"
            ),
            "suspicious": sum(
                1 for sid in self._seat_occupied
                if self.get_motion_status(sid) == "suspicious"
            ),
            "ghost": sum(
                1 for sid in self._seat_occupied
                if self.get_motion_status(sid) == "ghost"
            ),
            "per_seat": {},
        }

        # Per-seat details
        for seat_id in self._seat_occupied:
            summary["per_seat"][seat_id] = {
                "dwell_time": round(self.get_dwell_time(seat_id), 2),
                "time_since_motion": round(self.get_time_since_motion(seat_id), 2),
                "motion_status": self.get_motion_status(seat_id),
                "is_occupied": self._seat_occupied[seat_id],
            }

        return summary

    def reset(self):
        """Reset all motion tracking."""
        self._seat_motion.clear()
        self._seat_dwell.clear()
        self._seat_occupied.clear()
