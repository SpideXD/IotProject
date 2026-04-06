#!/usr/bin/env python3
"""
RPi Simulator - Per-room processing node entry point.

Usage:
    python -m rpi_simulator.main
    python rpi_simulator/main.py

Environment variables:
    RPI_HTTP_PORT      - HTTP server port (default: 5001)
    EDGE_PROCESSOR_URL - Central edge processor URL (default: http://localhost:5002)
    ROOM_ID           - Unique room identifier (default: room_1)
    LOG_LEVEL         - Logging level (default: INFO)
"""
import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rpi_simulator.http_server import run_server


def main():
    """Start the RPi simulator HTTP server."""
    room_id = os.environ.get("ROOM_ID", "room_1")
    port = int(os.environ.get("RPI_HTTP_PORT", 5001))
    edge_url = os.environ.get(
        "EDGE_PROCESSOR_URL", "http://localhost:5002"
    )

    print(f"Starting RPi Simulator for room: {room_id}")
    print(f"  HTTP Server: http://0.0.0.0:{port}")
    print(f"  Edge Processor: {edge_url}")
    print()

    run_server(
        host="0.0.0.0",
        port=port,
        room_id=room_id,
        edge_url=edge_url,
    )


if __name__ == "__main__":
    main()
