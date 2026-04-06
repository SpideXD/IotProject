# Liberty Twin - MQTT Protocol Specification

## Table of Contents
1. [Protocol Overview](#protocol-overview)
2. [Topic Structure](#topic-structure)
3. [Message Schemas](#message-schemas)
4. [QoS and Retain Policies](#qos-and-retain-policies)
5. [HTTP API Endpoints](#http-api-endpoints)
6. [Example Scenarios](#example-scenarios)

---

## Protocol Overview

Liberty Twin uses **MQTT 3.1.1** for inter-service communication and **HTTP REST** for RPi-to-Edge communication.

### Key Design Decision: HTTP for RPi → Edge

Due to the privacy architecture, camera frames never travel via MQTT. Instead:

- **RPi → Edge:** HTTP POST (frames + detections stay local to RPi)
- **Edge → Cloud/Dashboard:** MQTT (only occupancy text data)

### Protocol Version

- **MQTT**: 3.1.1
- **WebSocket**: MQTT over WebSocket (port 9001)
- **HTTP**: REST API (Flask)

### Port Configuration

| Service | Port | Protocol | Usage |
|---------|------|----------|-------|
| MQTT | 1883 | TCP | Edge ↔ Cloud/Dashboard |
| WebSocket | 9001 | WS/WSS | Dashboard WebSocket |
| RPi Simulator | 5001 | HTTP | Unity → RPi (frames + detections) |
| Edge Processor | 5002 | HTTP | RPi → Edge (occupancy only) |
| Dashboard | 5000 | HTTP | Web UI + REST API |

---

## Topic Structure

### MQTT Topics (Edge → Dashboard/Cloud)

All MQTT topics follow: `liberty_twin/{category}/{resource}`

```
liberty_twin/
│
├── state/
│   └── seat/
│       ├── S1              # Individual seat state (retained)
│       ├── S2
│       └── ...
│       └── S28
│
├── alerts/
│   ├── ghost_suspected     # Entered grace period
│   ├── ghost_confirmed     # Ghost confirmed
│   ├── person_returned     # Returned to ghost seat
│   └── state_change        # Any state transition
│
├── health/
│   ├── edge/
│   │   └── status         # Edge processor heartbeat
│   └── broker/
│       └── status         # MQTT broker status
│
└── sensor/
    └── {rail}/
        ├── telemetry      # Legacy telemetry (direct from Unity)
        └── camera         # Legacy camera (direct from Unity)
```

---

## Message Schemas

### 1. Seat State (Edge → Dashboard via MQTT)

**Topic**: `liberty_twin/state/seat/{S1-S28}`

**Retain**: YES

```json
{
  "seat_id": "S2",
  "room_id": "room_1",
  "zone_id": "Z1",
  "state": "suspected_ghost",
  "is_occupied": true,
  "occupancy_score": 0.85,
  "confidence": 0.82,
  "object_type": "bag",
  "ghost_state": "suspected_ghost",
  "dwell_time": 180.5,
  "time_since_motion": 125.3,
  "timestamp": 1743187200.123
}
```

### 2. Ghost Alert (Edge → Dashboard via MQTT)

**Topic**: `liberty_twin/alerts/ghost_confirmed`

**Retain**: NO

```json
{
  "alert_type": "ghost_confirmed",
  "seat_id": "S2",
  "zone_id": "Z1",
  "room_id": "room_1",
  "ghost_duration_s": 300,
  "confidence": 0.82,
  "details": "Ghost confirmed after 5 minutes of no motion",
  "timestamp": 1743187200.123
}
```

### 3. Health Status (Edge → Dashboard via MQTT)

**Topic**: `liberty_twin/health/edge/status`

```json
{
  "component": "edge_processor",
  "status": "online",
  "mqtt_connected": true,
  "influxdb_connected": true,
  "rooms_active": 1,
  "total_seats": 28,
  "occupancy_received": 1523,
  "mqtt_publishes": 8901,
  "timestamp": 1743187200.123
}
```

---

## HTTP API Endpoints

### RPi Simulator (Port 5001)

#### POST /api/camera

Receive camera frame + detections from Unity.

```json
{
  "sensor": "Rail_Back_001",
  "frame": "<base64 JPEG>",
  "detections": [
    {"cls": "person", "confidence": 1.0, "bbox": [0.2, 0.3, 0.4, 0.6]},
    {"cls": "bag", "confidence": 1.0, "bbox": [0.5, 0.4, 0.6, 0.7]}
  ]
}
```

Response: `{"ok": true}`

#### POST /api/telemetry

Receive radar telemetry from Unity (legacy direct path).

```json
{
  "zone_id": "Z1",
  "sensor": "Rail_Back_001",
  "timestamp": 1743187200.123,
  "seats": {
    "S1": {
      "seat_id": "S1",
      "presence": 0.85,
      "motion": 0.65,
      "micro_motion": false,
      "object_type": "person",
      "confidence": 0.89
    }
  }
}
```

### Edge Processor (Port 5002)

#### POST /api/occupancy

Receive pre-processed occupancy from RPi simulator.

```json
{
  "source": "rpi_simulator",
  "room_id": "room_1",
  "timestamp": 1743187200.123,
  "seats": {
    "S1": {
      "zone_id": "Z1",
      "is_occupied": true,
      "object_type": "person",
      "confidence": 0.95,
      "has_motion": true,
      "radar_presence": 0.8,
      "radar_motion": 0.65,
      "radar_micro_motion": false
    },
    "S2": {
      "zone_id": "Z1",
      "is_occupied": true,
      "object_type": "bag",
      "confidence": 0.88,
      "has_motion": false,
      "radar_presence": 0.75,
      "radar_motion": 0.02,
      "radar_micro_motion": false
    }
  }
}
```

Response: `{"ok": true, "received": 28, "occupied": 5}`

#### GET /api/seats

Get all seat states with optional filtering.

```
GET /api/seats?room=room_1&state=occupied
```

```json
{
  "seats": {
    "S1": {
      "seat_id": "S1",
      "room_id": "room_1",
      "zone_id": "Z1",
      "state": "occupied",
      "is_occupied": true,
      "occupancy_score": 0.95,
      "object_type": "person",
      "dwell_time": 320.5,
      "time_since_motion": 0.0
    }
  },
  "summary": {
    "total": 28,
    "occupied": 5,
    "empty": 23,
    "suspected_ghost": 0,
    "confirmed_ghost": 0
  }
}
```

#### GET /api/rooms

Get list of active rooms.

```json
{
  "rooms": [
    {
      "room_id": "room_1",
      "last_update": 1743187200.123,
      "seat_count": 28,
      "occupied": 5,
      "utilization": 0.179
    }
  ]
}
```

#### GET /api/analytics/utilization

Get zone utilization analytics.

```json
{
  "zones": {
    "Z1": {
      "total": 4,
      "occupied": 2,
      "utilization": 0.5,
      "states": {
        "occupied": 2,
        "empty": 2,
        "suspected_ghost": 0,
        "confirmed_ghost": 0
      }
    }
  },
  "overall": {
    "total_seats": 28,
    "occupied": 5,
    "utilization": 0.179
  }
}
```

#### POST /api/reservation/{seat_id}

Create a seat reservation.

```json
{
  "user_id": "student_123"
}
```

Response: `{"success": true, "seat_id": "S1", "expires_at": 1743188100.123}`

---

## QoS and Retain Policies

### Quality of Service (QoS)

| Topic Pattern | QoS | Reason |
|--------------|-----|--------|
| `liberty_twin/state/seat/*` | 1 | Important, at-least-once delivery |
| `liberty_twin/alerts/*` | 1 | Events should not be lost |
| `liberty_twin/health/*` | 0 | Periodic, latest is sufficient |

### Retain Flag

| Topic Pattern | Retain | Reason |
|--------------|--------|--------|
| `liberty_twin/state/seat/*` | **YES** | Dashboard shows last known state on connect |
| `liberty_twin/alerts/*` | NO | Events are transient |
| `liberty_twin/health/*` | NO | Heartbeats are periodic |

---

## Example Scenarios

### Scenario 1: Student Creates Ghost

```
T+0s    Unity publishes camera to RPi
        {frame: "<base64>", detections: [{cls: "person"}]}

T+0.1s  RPi receives, maps to seat occupancy
        S2: occupied (person)

T+0.2s  RPi sends occupancy to Edge
        POST /api/occupancy {S2: {is_occupied: true, object_type: "person"}}

T+0.3s  Edge publishes state
        MQTT liberty_twin/state/seat/S2 {state: "occupied"}

T+60s   Unity: student leaves bag
        {detections: [{cls: "bag"}]}

T+60.1s RPi: S2 now occupied (bag)

T+60.2s Edge: S2 → SuspectedGhost
        MQTT publish, start grace timer

T+180s  Grace period expires
        Edge: S2 → Ghost
        MQTT liberty_twin/alerts/ghost_confirmed
        Dashboard: S2 turns purple
```

### Scenario 2: Multi-Room Correlation

```
Room 1:
  - S2: Ghost (bag left)
  - S5: Ghost (bag left)

Room 2:
  - S17: Ghost (bag left)

Edge detects correlation:
  - Multiple ghosts in same zone suggests real abandonment
  - Zone-level ghost rate: 3 ghosts / 28 seats = 11%
  - Could trigger library-wide alert

Edge correlation analysis:
  - zone_ghost_counts: {Z1: 2, Z5: 1}
  - correlated_zones: ["Z1", "Z5"]  (2+ ghosts)
```

---

## Summary

This MQTT protocol specification ensures:

- **Reliable message delivery** with appropriate QoS levels
- **Real-time updates** with WebSocket support for dashboard
- **State persistence** with retained messages
- **Privacy** - raw images via HTTP to RPi, never via MQTT
- **Multi-room support** via room_id tracking

**Key difference from v1:** Camera frames travel via HTTP to RPi Simulator (port 5001), not via MQTT. Only processed occupancy text data travels via MQTT to the Edge and Dashboard.
