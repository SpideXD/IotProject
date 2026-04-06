"""
RPi Simulator - Per-room processing node.

Keeps raw camera images local, sends only seat occupancy to central edge.
"""
from .http_server import app, init_app, run_server
from .room_processor import RoomProcessor

__version__ = "1.0.0"
__all__ = ["RoomProcessor", "app", "init_app", "run_server"]
