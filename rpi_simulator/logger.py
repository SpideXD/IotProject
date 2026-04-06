"""
Local JSON logging for occupancy decisions (audit trail).
"""
import json
import os
import threading
from datetime import datetime, timezone
from typing import Any

from .config import AUDIT_LOG_PATH, LOG_FORMAT, LOG_LEVEL

_log = logging.getLogger("rpi_simulator.logger")


class OccupancyLogger:
    """Thread-safe JSON logger for occupancy decisions."""

    def __init__(self, path: str = None):
        self.path = path or AUDIT_LOG_PATH
        self._lock = threading.Lock()
        self._buffer = []
        self._buffer_size = 10  # Flush after N entries

    def log_decision(
        self,
        room_id: str,
        seats: dict[str, dict[str, Any]],
        source: str = "camera",
        detections_count: int = 0,
    ):
        """Log an occupancy decision."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "room_id": room_id,
            "source": source,
            "detections_count": detections_count,
            "seats": seats,
            "occupied_count": sum(
                1 for s in seats.values() if s.get("is_occupied", False)
            ),
        }
        with self._lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self._buffer_size:
                self._flush()

    def _flush(self):
        """Write buffered entries to disk."""
        if not self._buffer:
            return
        try:
            # Read existing log if file exists
            existing = []
            if os.path.exists(self.path):
                with open(self.path, "r") as f:
                    existing = json.load(f)

            # Append new entries
            existing.extend(self._buffer)
            # Keep last 10000 entries
            existing = existing[-10000:]

            # Write back
            with open(self.path, "w") as f:
                json.dump(existing, f)
            self._buffer.clear()
        except Exception as e:
            _log.error("Failed to flush audit log: %s", e)

    def close(self):
        """Flush remaining entries on shutdown."""
        with self._lock:
            self._flush()


import logging
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
