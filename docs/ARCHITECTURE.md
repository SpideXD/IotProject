# Liberty Twin - System Architecture

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Component Details](#component-details)
3. [Data Flow](#data-flow)
4. [Communication Patterns](#communication-patterns)
5. [Deployment Architecture](#deployment-architecture)
6. [Scalability Considerations](#scalability-considerities)

---

## Architecture Overview

Liberty Twin follows a **multi-tier edge-cloud architecture** with privacy-preserving local processing.

### Privacy-First Design

**Key principle:** Raw camera images NEVER leave the room-level processor (RPi Simulator). Only processed text/occupancy data is sent to the central edge processor.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PRESENTATION LAYER                                │
│                              (Dashboard :5000)                               │
│                                                                             │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐│
│   │ Zone Grid    │  │ Ghost Alerts │  │ Analytics    │  │ Room Select  ││
│   │ (28 seats)   │  │ Countdown    │  │ Charts       │  │              ││
│   └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘│
│                                                                             │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │ HTTP REST + MQTT
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                               CLOUD LAYER                                   │
│                                                                             │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐  │
│   │ MQTT Broker      │    │ InfluxDB         │    │ Analytics        │  │
│   │ (Eclipse         │◄──►│ (Time-Series     │◄──►│ Engine           │  │
│   │  Mosquitto)      │    │  Database)       │    │                  │  │
│   │                  │    │                  │    │ • Peak hour       │  │
│   │ • Message        │    │ • Historical     │    │   detection       │  │
│   │   routing        │    │   occupancy      │    │ • Ghost patterns  │  │
│   │ • Pub/Sub        │    │ • State changes  │    │ • Utilization    │  │
│   └────────┬─────────┘    └──────────────────┘    └──────────────────┘  │
│            │                                                                  │
└────────────┼────────────────────────────────────────────────────────────────┘
             │ MQTT / HTTP
             ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          EDGE PROCESSOR (:5002)                             │
│                           (Central Aggregator)                              │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │                    CENTRAL AGGREGATION MODULE                    │     │
│   │                                                                   │     │
│   │  ┌────────────┐    ┌────────────┐    ┌──────────────────────┐   │     │
│   │  │ Multi-RPi │    │ Room       │    │ Cross-Room           │   │     │
│   │  │ Ingestion  │    │ Correlation │    │ Ghost Detection      │   │     │
│   │  │            │    │            │    │                      │   │     │
│   │  │ • Accepts │    │ • Pattern  │    │ • Tracks states     │   │     │
│   │  │   pre-proc │    │   analysis │    │ • 2min grace        │   │     │
│   │  │   occup.   │    │ • Aggreg.  │    │ • 5min ghost        │   │     │
│   │  └────────────┘    └────────────┘    └──────────────────────┘   │     │
│   └──────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │                    MQTT PUBLISHER                                 │     │
│   │  • Publishes seat states to MQTT                                 │     │
│   │  • Forwards to Dashboard via MQTT or HTTP                        │     │
│   └──────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │ HTTP POST (pre-processed occupancy)
                                      │ MQTT (legacy telemetry)
┌─────────────────────────────────────┴───────────────────────────────────────┐
│                         RPI SIMULATOR (:5001)                              │
│                      (Per-Room, Privacy Boundary)                         │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │                    LOCAL PROCESSING MODULE                         │     │
│   │                                                                   │     │
│   │  ┌────────────┐    ┌────────────┐    ┌──────────────────────┐   │     │
│   │  │ Camera     │    │ YOLO       │    │ Sensor Fusion         │   │     │
│   │  │ Input      │───►│ Inference  │───►│ (Camera + Radar)      │   │     │
│   │  │ (frames)   │    │ (on-device│    │                      │   │     │
│   │  │            │    │  privacy) │    │ • Object detection   │   │     │
│   │  └────────────┘    └────────────┘    │ • Motion analysis    │   │     │
│   │                                       │ • Confidence calc    │   │     │
│   │                                       └──────────┬───────────┘   │     │
│   │                                                  │               │     │
│   │  ┌──────────────────────────────────────────────▼───────────┐   │     │
│   │  │              OCCUPANCY MAPPING                                │   │     │
│   │  │  • Maps detections to seat IDs                               │   │     │
│   │  │  • Generates seat-level occupancy TEXT (not images)         │   │     │
│   │  │  • Delta compression (only send on change)                  │   │     │
│   │  └─────────────────────────────────────────────────────────────┘   │     │
│   └──────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │                    HTTP SERVER (Flask)                            │     │
│   │  POST /api/camera     - Receive camera frames + detections       │     │
│   │  POST /api/telemetry  - Receive radar telemetry                  │     │
│   │  GET  /api/status     - Processing status                        │     │
│   └──────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ▲
                                      │ HTTP (frames + detections)
┌─────────────────────────────────────┴───────────────────────────────────────┐
│                           SIMULATION LAYER                                  │
│                              (Unity 3D)                                     │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │                    VIRTUAL LIBRARY ROOM                            │     │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │     │
│   │  │ Section A    │  │ Aisles       │  │ Section B    │           │     │
│   │  │ (14 seats)   │  │              │  │ (14 seats)   │           │     │
│   │  │ 4 zones      │  │              │  │ 3 zones      │           │     │
│   │  └──────────────┘  └──────────────┘  └──────────────┘           │     │
│   └──────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │                    RAIL SENSOR ARRAY                              │     │
│   │  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │     │
│   │  │ Rail         │    │ Camera       │    │ Radar Simulator  │   │     │
│   │  │ Controller   │    │ (YoloCapture│    │ (Raycast + Noise)│   │     │
│   │  │              │    │  generates   │    │                  │   │     │
│   │  │ • 7 rails   │    │  ground      │    │ • Presence       │   │     │
│   │  │ • Sequential│    │  truth       │    │ • Velocity       │   │     │
│   │  │   sweep     │    │  detections) │    │ • Micro-motion   │   │     │
│   │  └──────────────┘    └──────────────┘    └──────────────────┘   │     │
│   └──────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │                    DASHBOARD BRIDGE                               │     │
│   │  • Sends frames + detections to RPi Simulator (:5001)            │     │
│   │  • Sends telemetry to Edge Processor (:5002)                     │     │
│   │  • Ground truth bounding boxes from 3D scene (perfect accuracy) │     │
│   └──────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Simulation Layer (Unity 3D)

**Purpose:** Generate realistic sensor data from virtual environment with ground truth detections.

**Key Components:**

#### RailSensorController
- Manages 7 rail positions (Back: Z1-Z4, Front: Z5-Z7)
- Sequential sweep through zones
- Collects data from 4 seats per zone
- Generates rail-specific sensor readings

#### YoloCapture
- Generates training data for YOLO model
- Produces ground truth bounding boxes (perfect accuracy from 3D scene)
- Captures camera frames with detection annotations
- Latest detections exposed via `latestDetections` for real-time use

#### DashboardBridge
- HTTP client sending data to RPi Simulator and Edge Processor
- Sends camera frames + detections to `:5001/api/camera`
- Sends radar telemetry to `:5002/api/telemetry`
- Can include ground truth detections (bypassing YOLO inference)

#### SimStudent
- Student behavior simulation
- Enters → Sits → Studies → Leaves bag (ghost) → Returns or leaves

---

### 2. RPi Simulator (Per-Room Processor)

**Purpose:** Privacy boundary - all image processing happens here. Only text/occupancy data leaves.

**Port:** `:5001`

**Key Components:**

#### RoomProcessor
- Receives camera frames + detections from Unity
- Optionally runs YOLO inference (for real hardware deployment)
- Maps detections to seat occupancy
- Enriches with radar telemetry
- Sends only occupancy TEXT to Edge Processor

#### http_server.py (Flask)
- `POST /api/camera` - Receives frames + detections
- `POST /api/telemetry` - Receives radar data
- `GET /api/status` - Processing status
- `GET /api/model-info` - YOLO model version

#### Bandwidth Optimization
- Delta compression: only sends when state changes
- Adaptive send intervals
- Can skip frame transmission when detections already provided

---

### 3. Edge Processor (Central Aggregator)

**Purpose:** Aggregates occupancy from multiple RPi simulators, performs cross-room ghost detection.

**Port:** `:5002`

**Key Components:**

#### process_occupancy_from_rpi()
- Receives pre-processed occupancy from RPi simulators
- Stores in multi-room aggregation storage
- Analyzes room correlation patterns

#### Ghost Detection
- Tracks ghost states across all rooms
- 2-minute grace period
- 5-minute ghost confirmation
- Multi-room correlation analysis

#### API Endpoints
- `POST /api/occupancy` - Receive RPi occupancy data
- `GET /api/seats` - All seat states with filtering
- `GET /api/rooms` - Active rooms status
- `GET /api/analytics/utilization` - Zone utilization
- `GET /api/heatmap/{room_id}` - Zone heatmap data
- `POST /api/reservation/{seat_id}` - Seat reservations

#### Rate Limiting & Reservations
- Rate limiting per client (1000 req/min)
- Seat reservation system (15min TTL, 2 per user)

---

### 4. Dashboard

**Port:** `:5000`

**Frontend:** React SPA in `dashboard-frontend/`
**Backend:** Python Flask in `dashboard/`

**Features:**
- Real-time seat visualization (28 seats)
- Zone grid with color-coded states
- Ghost alert feed with countdown timers
- Occupancy analytics charts
- Room selector for multi-room support
- Reservation system

---

## Data Flow

### End-to-End Data Flow Diagram

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Unity      │────►│ RPi Simulator│────►│ Edge         │────►│  Dashboard   │
│   (frames +   │     │ (:5001)      │     │ Processor    │     │  (:5000)     │
│   detections) │     │ YOLO locally │     │ (:5002)      │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                           │
                           │ Only TEXT/occupancy data
                           │ No raw images leave RPi
                           ▼
                     ┌──────────────┐
                     │ Edge         │
                     │ Stores       │
                     │ multi-room   │
                     │ occupancy    │
                     └──────────────┘

Timeline:
────────────────────────────────────────────────────────────────────────────────

T=0s    Unity captures frame
        → Ground truth detections: [{cls: "person", bbox: [...]}]
        → Radar telemetry: {S1: {presence: 0.85, motion: 0.65}}

T=0.1s  DashboardBridge POSTs to RPi Simulator (:5001/api/camera)
        {frame: "<base64>", detections: [...], sensor: "Rail_Back_001"}

T=0.2s  RPi Simulator maps detections to seats
        → S1: occupied (person, conf: 0.95)
        → S2: occupied (bag, conf: 0.88)

T=0.3s  RPi Simulator POSTs to Edge (:5002/api/occupancy)
        {source: "rpi_simulator", room_id: "room_1", seats: {S1: {...}, S2: {...}}}

T=0.4s  Edge Processor:
        → Stores in _occupancy_storage
        → Analyzes cross-room patterns
        → Publishes to MQTT

T=0.5s  Dashboard receives via MQTT/HTTP
        → Updates seat visuals
        → Shows S1 red, S2 with ghost timer

────────────────────────────────────────────────────────────────────────────────
```

---

## Communication Patterns

### 1. Unity → RPi Simulator (HTTP)

```
Unity ──► POST /api/camera ──► RPi Simulator
          {frame, detections, sensor}

Unity ──► POST /api/telemetry ──► RPi Simulator
          {zone_id, seats: {S1: {...}}}
```

### 2. RPi Simulator → Edge Processor (HTTP)

```
RPi ──► POST /api/occupancy ──► Edge Processor
        {source, room_id, timestamp, seats: {...}}
```

### 3. Edge → Dashboard (MQTT + HTTP Fallback)

```
Edge ──► MQTT liberty_twin/state/seat/{seat_id} ──► Dashboard
         (retained)

Edge ──► MQTT liberty_twin/alerts/ghost ──► Dashboard
         (alert notifications)
```

---

## Deployment Architecture

### Development Environment (Single Machine)

```
┌─────────────────────────────────────────────────────────────┐
│                     Development Laptop                       │
│                          (Mac/PC)                            │
│                                                              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│   │   Unity      │  │  Docker      │  │   Python     │   │
│   │   Editor     │  │  Compose     │  │   Services   │   │
│   │              │  │              │  │              │   │
│   │ • Simulation │  │ • Mosquitto  │  │ • RPi (:5001)│   │
│   │ • Dashboard  │  │ • InfluxDB   │  │ • Edge (:5002)│  │
│   └──────┬───────┘  └──────┬───────┘  │ • Dashboard(:5000)│
│          │                 │                 │            │
│          └─────────────────┼─────────────────┘            │
│                            │                              │
│                    localhost ports                          │
│                    5000, 5001, 5002                        │
│                    1883 (MQTT), 8086 (InfluxDB)            │
└─────────────────────────────────────────────────────────────┘
```

### Production Environment (Multi-Room)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLOUD VPS                                      │
│                         (AWS/DigitalOcean/etc)                              │
│                                                                             │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐    │
│   │ MQTT Broker      │    │ InfluxDB         │    │ Dashboard Server │    │
│   │ (Mosquitto)      │    │ (Time-Series)    │    │ (:5000)         │    │
│   │ Port: 1883/9001  │    │ Port: 8086       │    │ Nginx + React   │    │
│   └────────┬─────────┘    └──────────────────┘    └────────┬─────────┘    │
│            │                                                       │          │
└────────────┼───────────────────────────────────────────────────────┼──────────┘
             │ MQTT + HTTP                                           │ HTTP
             ▼                                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EDGE PROCESSOR (:5002)                               │
│                      (Central Aggregation Server)                            │
│                                                                             │
│   ┌──────────────────────────────────────────────────────────────────┐     │
│   │  • Multi-RPi ingestion (HTTP + MQTT)                             │     │
│   │  • Cross-room ghost detection                                      │     │
│   │  • InfluxDB persistence                                           │     │
│   │  • MQTT publishing to dashboard                                    │     │
│   └──────────────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────────────┘
             ▲                              ▲
             │ HTTP (:5001)                 │ MQTT
             │                              │
┌────────────┴────────────┐      ┌───────────┴────────────┐
│   RPI SIMULATOR 1      │      │    RPI SIMULATOR N      │
│   (Room 1 - Privacy)   │      │    (Room N - Privacy)    │
│                        │      │                         │
│   • YOLO on-device    │      │    • YOLO on-device     │
│   • Camera frames      │      │    • Camera frames       │
│   • Only TEXT exits   │      │    • Only TEXT exits     │
└────────────────────────┘      └─────────────────────────┘
```

---

## Scalability Considerations

### Current Scale
- **28 seats** in 7 zones (Z1-Z4 back, Z5-Z7 front)
- **1 room** simulated
- **RPi Simulator:** 1 instance (can support many)
- **Edge Processor:** 1 instance (central aggregator)

### Scaling to Multiple Rooms

**Architecture supports:**
- Multiple RPi Simulators (one per room)
- Each RPi sends to Edge at `:5002`
- Edge tracks `room_id` for multi-room correlation
- Dashboard room selector switches views

### Performance Optimization

- Delta compression reduces bandwidth (only send on state change)
- Rate limiting protects Edge (1000 req/min per client)
- InfluxDB batch writes for efficiency
- MQTT QoS 1 for reliable delivery

---

## Summary

This architecture provides:

1. **Privacy:** Raw images never leave RPi - only text/occupancy data
2. **Modularity:** Each layer can be developed and tested independently
3. **Scalability:** Easy to add more rooms (more RPi simulators)
4. **Reliability:** MQTT QoS ensures delivery, HTTP fallback available
5. **Real-time:** Sub-second latency from Unity to dashboard
6. **Extensibility:** Easy to add new sensors or algorithms

The RPi Simulator acts as a **privacy gateway** - the key architectural decision that enables real-world deployment where camera feeds cannot leave the premises.
