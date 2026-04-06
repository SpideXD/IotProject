# Liberty Twin - Quick Reference

## System Overview

**Liberty Twin** monitors 28 library seats using a rail-mounted sensor array. The system detects ghost occupancy (bags reserving seats) with a privacy-preserving multi-tier architecture.

## Architecture

```
Unity ──► RPi Simulator (:5001) ──► Edge Processor (:5002) ──► Dashboard (:5000)
          │ HTTP (frames)              │ MQTT                 │
          │ Only TEXT leaves RPi       │                      ▼
          ▼                            ▼              InfluxDB (history)
    YOLO inference               Multi-room              Alerts
    (on-device privacy)         aggregation
```

**Key:** Raw camera images NEVER leave the RPi Simulator.

## Key Components

| Component | Port | Technology | Purpose |
|-----------|------|-----------|---------|
| Unity Simulation | - | Unity 3D, C# | Generate sensor data, ground truth |
| RPi Simulator | 5001 | Python Flask | Local YOLO inference, privacy |
| Edge Processor | 5002 | Python Flask | Multi-room aggregation, ghost detection |
| MQTT Broker | 1883 | Mosquitto | Message routing |
| Dashboard | 5000 | React + Flask | Real-time visualization |
| InfluxDB | 8086 | InfluxDB 2.x | Historical data |

## Seat Layout

**28 seats in 7 zones:**
- Section A (Left): Z1 (back), Z2 (mid), Z3 (front), Z4 (far front)
- Section B (Right): Z5 (back), Z6 (mid), Z7 (front)
- Each zone: 4 seats (except Z4 which is 4)

**Rail Sensor Array:**
- 7 rails sweep through zones
- Ground truth detections from 3D scene
- Sends frames + detections to RPi Simulator

## States

| State | Color | Description |
|-------|-------|-------------|
| Empty | Green `#22c55e` | No occupant |
| Occupied | Red `#ef4444` | Person actively using |
| SuspectedGhost | Yellow `#eab308` | Object present, no motion (2min grace) |
| ConfirmedGhost | Purple `#a855f7` | Confirmed abandoned (5min threshold) |

## Ports

| Service | Port | Protocol |
|---------|------|----------|
| RPi Simulator | 5001 | HTTP (Unity → RPi) |
| Edge Processor | 5002 | HTTP (RPi → Edge) |
| Dashboard | 5000 | HTTP + WebSocket |
| MQTT | 1883 | TCP |
| WebSocket | 9001 | WS/WSS |
| InfluxDB | 8086 | HTTP |

## MQTT Topics

**State (Edge → Dashboard):**
- `liberty_twin/state/seat/{S1-S28}` - Individual seat (RETAINED)

**Alerts (Edge → Dashboard):**
- `liberty_twin/alerts/ghost_suspected`
- `liberty_twin/alerts/ghost_confirmed`
- `liberty_twin/alerts/person_returned`

## HTTP Endpoints

**RPi Simulator (:5001):**
- `POST /api/camera` - Receive frames + detections
- `POST /api/telemetry` - Receive radar telemetry
- `GET /api/status` - Processing status

**Edge Processor (:5002):**
- `POST /api/occupancy` - Receive RPi occupancy data
- `GET /api/seats` - All seat states
- `GET /api/rooms` - Active rooms
- `GET /api/analytics/utilization` - Zone analytics
- `POST /api/reservation/{seat_id}` - Reserve seat

## Detection Thresholds

| Parameter | Value |
|-----------|-------|
| Grace Period | 120 seconds |
| Ghost Threshold | 300 seconds |
| Presence Threshold | 0.6 |
| Motion Threshold | 0.15 |

## Services and Operations

```bash
# Start infrastructure
docker-compose up -d

# Start RPi Simulator (port 5001)
cd edge/rpi_simulator && python main.py

# Start Edge Processor (port 5002)
cd edge && python processor.py

# Start Dashboard (port 5000)
cd dashboard && flask run --port 5000

# Start Dashboard Frontend
cd dashboard-frontend && npm run dev
```

## Troubleshooting

**Unity not connecting to RPi:**
- Check RPi Simulator is running on port 5001
- Verify DashboardBridge.cs target URL

**No occupancy in Edge:**
- Check RPi → Edge HTTP connectivity
- Verify /api/occupancy endpoint

**Dashboard not updating:**
- Check MQTT connection to broker
- Verify WebSocket connection in browser

## File Structure

```
/Users/agentswarm/Desktop/IotProject/
├── LibraryModel/           # Unity 3D Simulation
│   ├── Assets/Scripts/    # C# scripts
│   └── Assets/Scenes/      # Unity scenes
├── edge/
│   ├── processor.py         # Edge Processor (:5002)
│   └── rpi_simulator/     # RPi Simulator (:5001)
│       ├── http_server.py
│       ├── room_processor.py
│       └── main.py
├── dashboard/             # Dashboard Backend (:5000)
├── dashboard-frontend/     # Dashboard Frontend
├── docs/                  # This documentation
└── venv/                 # Python virtual environment
```

## Support

- Documentation: `/docs`
- Architecture: `docs/ARCHITECTURE.md`

## License

MIT License - Liberty Twin Team 2026
