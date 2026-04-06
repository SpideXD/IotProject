# Liberty Twin - Complete Technical Documentation

## Executive Summary

**Liberty Twin** is a privacy-preserving IoT system that monitors library occupancy using a gimbal-mounted multi-modal sensor array. The system detects "ghost occupancy" (bags reserving seats), provides real-time zone state updates, and visualizes data through a live digital twin dashboard.

**Privacy Architecture:** Raw camera images are processed locally on each room's "RPi" (or simulator). Only processed text/occupancy data is sent to the central edge processor. This enables real-world deployment where camera feeds cannot leave the premises.

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Physical Layout](#3-physical-layout)
4. [Software Stack](#4-software-stack)
5. [Data Flow](#5-data-flow)
6. [State Machine](#6-state-machine)
7. [API Reference](#7-api-reference)
8. [Dashboard](#8-dashboard)
9. [Setup & Deployment](#9-setup--deployment)
10. [Project Structure](#10-project-structure)

---

## 1. System Overview

### 1.1 Purpose

Monitor 28 library seats across 7 zones to:
- Detect real-time occupancy
- Identify ghost occupancy (bags left behind)
- Provide cross-room analytics
- Visualize live status via digital twin dashboard

### 1.2 Key Features

- **28-seat monitoring** with per-seat granularity
- **Ghost detection** using temporal + motion analysis
- **Privacy-first** edge computing (no video leaves device)
- **Multi-room support** via RPi simulator aggregation
- **Digital twin** with React dashboard visualization
- **Sensor fusion** (Camera + Radar)
- **Seat reservations** with TTL

### 1.3 System Boundaries

```
Unity → RPi Simulator (:5001) → Edge Processor (:5002) → Dashboard (:5000)
         (YOLO locally)          (aggregation)           (visualization)
         Privacy boundary         Multi-room fusion
```

- **Unity**: Simulation generating sensor data with ground truth detections
- **RPi Simulator**: Per-room processor, YOLO inference, privacy boundary (port 5001)
- **Edge Processor**: Central aggregation, cross-room ghost detection (port 5002)
- **Dashboard**: Real-time visualization (port 5000)

---

## 2. Architecture

### 2.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         UNITY SIMULATION                            │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Virtual Library Room with 28 Seats                         │   │
│  │  ┌─────┐ ┌─────┐    ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐     │   │
│  │  │ Z1  │ │ Z2  │... │ Z4  │ │ Z5  │ │ Z6  │ │ Z7  │   │   │
│  │  │4seat│ │4seat│    │4seat│ │4seat│ │4seat│ │4seat│     │   │
│  │  └─────┘ └─────┘    └─────┘ └─────┘ └─────┘ └─────┘     │   │
│  │                                                             │   │
│  │  Rail Sensor Head + YoloCapture + DashboardBridge          │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                    │                                   │
                    │ HTTP (frames + detections)          │ HTTP (telemetry)
                    ▼                                   ▼
┌─────────────────────────────────┐  ┌─────────────────────────────────────┐
│    RPI SIMULATOR (:5001)        │  │       EDGE PROCESSOR (:5002)       │
│   ┌───────────────────────────┐ │  │  ┌─────────────────────────────────┐  │
│   │  YOLO Inference (local)   │ │  │  │  Multi-Room Aggregation       │  │
│   │  • Camera frames          │ │  │  │  • Receives occupancy from    │  │
│   │  • Ground truth bypass    │ │  │  │    all RPi simulators        │  │
│   │  • Object detection       │ │  │  │                               │  │
│   └───────────────────────────┘ │  │  │  Cross-Room Ghost Detection  │  │
│              │                   │  │  │  • 2min grace, 5min ghost   │  │
│              ▼                   │  │  │  • Multi-room correlation   │  │
│   ┌───────────────────────────┐ │  │  └─────────────────────────────────┘  │
│   │  Occupancy Mapping         │ │  │              │                        │
│   │  • Detections → Seat IDs  │ │  │              ▼                        │
│   │  • Radar enrichment       │ │  │  ┌─────────────────────────────────┐  │
│   │  • Delta compression       │ │  │  │  MQTT Publisher              │  │
│   └───────────────────────────┘ │  │  │  • Seat states to MQTT         │  │
│              │                   │  │  │  • Ghost alerts               │  │
│              │ HTTP (TEXT only)   │  │  └─────────────────────────────────┘  │
└──────────────┼───────────────────┘  └─────────────────────────────────────┘
               │                                      │
               ▼                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLOUD LAYER                                   │
│                                                                             │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐         │
│   │  MQTT Broker    │  │  InfluxDB       │  │  Dashboard          │         │
│   │  (Mosquitto)    │  │  (Time Series)  │  │  (:5000)           │         │
│   │                 │  │                 │  │  React SPA         │         │
│   │  Topics:        │  │  Historical     │  │                     │         │
│   │  /state/seat/* │  │  occupancy      │  │  • Zone grid       │         │
│   │  /alerts/*     │  │  State changes  │  │  • Ghost alerts    │         │
│   │                 │  │                 │  │  • Analytics       │         │
│   └─────────────────┘  └─────────────────┘  └─────────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Responsibilities

| Component | Port | Responsibility | Technology |
|-----------|------|---------------|------------|
| **Unity Simulation** | - | Generate sensor data, ground truth detections | Unity 3D, C# |
| **RPi Simulator** | 5001 | Local YOLO inference, privacy boundary | Python Flask |
| **Edge Processor** | 5002 | Multi-room aggregation, ghost detection | Python Flask |
| **MQTT Broker** | 1883 | Message routing | Eclipse Mosquitto |
| **InfluxDB** | 8086 | Historical data storage | InfluxDB 2.x |
| **Dashboard** | 5000 | Real-time visualization | React + Flask |

---

## 3. Physical Layout

### 3.1 Room Configuration

```
TOP-DOWN VIEW

Section A (Left - Back)                  Section B (Right - Back)
┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐
│      ZONE 1 (Back Left)             │  │      ZONE 5 (Back Right)           │
│  ┌─────┐  ┌─────┐                   │  │                   ┌─────┐  ┌─────┐│
│  │ S1  │  │ S2  │                   │  │                   │ S17 │  │ S18 ││
│  └─────┘  └─────┘                   │  │                   └─────┘  └─────┘│
│  ┌─────┐  ┌─────┐                   │  │                   ┌─────┐  ┌─────┐│
│  │ S5  │  │ S6  │                   │  │                   │ S21 │  │ S22 ││
│  └─────┘  └─────┘                   │  │                   └─────┘  └─────┘│
└─────────────────────────────────────┘  └─────────────────────────────────────┘

Section A (Left - Middle)                  Section B (Right - Middle)
┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐
│      ZONE 2 (Mid-Left)               │  │      ZONE 6 (Mid-Right)            │
│  ┌─────┐  ┌─────┐                   │  │                   ┌─────┐  ┌─────┐│
│  │ S9  │  │ S10 │                   │  │                   │ S25 │  │ S26 ││
│  └─────┘  └─────┘                   │  │                   └─────┘  └─────┘│
│  ┌─────┐  ┌─────┐                   │  │                   ┌─────┐  ┌─────┐│
│  │ S13 │  │ S14 │                   │  │                   │ S29 │  │ S30 ││
│  └─────┘  └─────┘                   │  │                   └─────┘  └─────┘│
└─────────────────────────────────────┘  └─────────────────────────────────────┘

Section A (Left - Front)                   Section B (Right - Front)
┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐
│      ZONE 3 (Front Left)             │  │      ZONE 7 (Front Right)          │
│  ┌─────┐  ┌─────┐                   │  │                   ┌─────┐  ┌─────┐│
│  │ S3  │  │ S4  │                   │  │                   │ S19 │  │ S20 ││
│  └─────┘  └─────┘                   │  │                   └─────┘  └─────┘│
│  ┌─────┐  ┌─────┐                   │  │                   ┌─────┐  ┌─────┐│
│  │ S7  │  │ S8  │                   │  │                   │ S23 │  │ S24 ││
│  └─────┘  └─────┘                   │  │                   └─────┘  └─────┘│
└─────────────────────────────────────┘  └─────────────────────────────────────┘

Section A (Left - Far Front)               Section B (Right - Far Front)
┌─────────────────────────────────────┐  ┌─────────────────────────────────────┐
│      ZONE 4 (Far Front Left)         │  │      (No Zone - Section B far front)│
│  ┌─────┐  ┌─────┐                   │  │                                    │
│  │ S11 │  │ S12 │                   │  │                                    │
│  └─────┘  └─────┘                   │  │                                    │
│  ┌─────┐  ┌─────┐                   │  │                                    │
│  │ S15 │  │ S16 │                   │  │                                    │
│  └─────┘  └─────┘                   │  │                                    │
└─────────────────────────────────────┘  └─────────────────────────────────────┘
```

### 3.2 Zone-to-Seat Mapping

| Zone | Seat Numbers | Section |
|------|-------------|---------|
| Z1 | S1, S2, S5, S6 | Left Back |
| Z2 | S9, S10, S13, S14 | Left Middle |
| Z3 | S3, S4, S7, S8 | Left Front |
| Z4 | S11, S12, S15, S16 | Left Far Front |
| Z5 | S17, S18, S21, S22 | Right Back |
| Z6 | S25, S26, S29, S30 | Right Middle |
| Z7 | S19, S20, S23, S24 | Right Front |

**Total: 28 seats across 7 zones**

---

## 4. Software Stack

### 4.1 Technology Selection

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Simulation** | Unity 2022.3 LTS | 3D environment, sensor simulation |
| **Game Logic** | C# | MonoBehaviour scripts |
| **RPi Processing** | Python 3.11, Flask | Local inference, HTTP API |
| **Edge Processing** | Python 3.11, Flask | Aggregation, ghost detection |
| **Dashboard Frontend** | React, Tailwind CSS | Real-time visualization |
| **Dashboard Backend** | Python Flask | REST API |
| **MQTT Broker** | Eclipse Mosquitto | Message routing |
| **Database** | InfluxDB 2.x | Time-series storage |

### 4.2 Project Structure

```
/Users/agentswarm/Desktop/IotProject/
├── LibraryModel/              # Unity project
│   ├── Assets/
│   │   ├── Scripts/
│   │   │   ├── DashboardBridge.cs    # HTTP client to RPi/Edge
│   │   │   ├── YoloCapture.cs       # Ground truth detections
│   │   │   ├── RailSensorController.cs
│   │   │   ├── SimStudent.cs
│   │   │   └── LibrarySimManager.cs
│   │   └── Scenes/
│   │       └── StudyHall.unity
│   └── Packages/
├── edge/                      # Edge processor
│   ├── processor.py           # Main edge service (:5002)
│   ├── config.py             # Edge configuration
│   ├── sensor_fusion.py      # Sensor fusion logic
│   ├── ghost_detector.py     # Ghost detection FSM
│   └── rpi_simulator/        # RPi simulator (per-room)
│       ├── http_server.py    # Flask server (:5001)
│       ├── room_processor.py # Occupancy mapping
│       ├── main.py           # Entry point
│       ├── config.py          # Training config
│       ├── yolo_trainer.py   # YOLO training
│       └── dataset_manager.py # Data processing
├── dashboard/                # Dashboard backend
│   ├── app.py               # Flask app
│   └── templates/
├── dashboard-frontend/       # Dashboard frontend
│   ├── src/
│   │   ├── App.tsx
│   │   └── components/
│   └── package.json
├── docs/                     # This documentation
│   ├── ARCHITECTURE.md
│   ├── README.md
│   ├── MQTT_PROTOCOL.md
│   └── ...
├── broker/                   # MQTT broker config
├── influxdb/                 # InfluxDB config
└── venv/                     # Python virtual environment
```

---

## 5. Data Flow

### 5.1 Unity → RPi Simulator → Edge → Dashboard

```
Unity                            RPi (:5001)                Edge (:5002)           Dashboard (:5000)
  │                                  │                           │                       │
  │── POST /api/camera ─────────────►│                           │                       │
  │   {frame, detections, sensor}    │                           │                       │
  │                                  │                           │                       │
  │                                  │── YOLO inference ────────►│                       │
  │                                  │   (or use detections)      │                       │
  │                                  │                           │                       │
  │                                  │── Occupancy TEXT ─────────►│                       │
  │                                  │   {seats: {S1: {...}}}    │                       │
  │                                  │                           │── MQTT ──────────────►│
  │                                  │                           │   /state/seat/*       │
  │                                  │                           │                       │
  │── POST /api/telemetry ──────────────────────────────────────►│                       │
  │   {zone_id, seats: {...}}        │                           │                       │
```

### 5.2 Occupancy Payload (RPi → Edge)

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

---

## 6. State Machine

### 6.1 Seat States

```
EMPTY ──────────────────────────► OCCUPIED
  ▲                                   │
  │                                   ▼
  │                       SUSPECTED_GHOST ◄────► GHOST
  │                           ▲
  │                           │
  └───────────────────────────┘
     (motion detected)

State Transitions:
• EMPTY → OCCUPIED: Presence detected with motion or person
• OCCUPIED → SUSPECTED_GHOST: No motion for 2 min (grace period)
• SUSPECTED_GHOST → GHOST: No motion for 5 min total
• SUSPECTED_GHOST → OCCUPIED: Motion detected (person returned)
• GHOST → OCCUPIED: Motion detected (person returned)
• SUSPECTED_GHOST/GHOST → EMPTY: Presence lost (bag removed)
• OCCUPIED → EMPTY: Presence lost (person left)
```

### 6.2 Ghost Detection Thresholds

| Parameter | Value | Description |
|-----------|-------|-------------|
| Grace Period | 120s | Time before suspected ghost |
| Ghost Threshold | 300s | Time before confirmed ghost |
| Presence Threshold | 0.6 | Radar presence to consider occupied |
| Motion Threshold | 0.15 | Radar motion to detect person |

---

## 7. API Reference

### 7.1 RPi Simulator (Port 5001)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/camera` | POST | Receive camera frames + detections |
| `/api/telemetry` | POST | Receive radar telemetry |
| `/api/status` | GET | Processing status |
| `/health` | GET | Health check |

### 7.2 Edge Processor (Port 5002)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/occupancy` | POST | Receive pre-processed occupancy from RPi |
| `/api/telemetry` | POST | Receive legacy telemetry |
| `/api/seats` | GET | All seat states with filtering |
| `/api/rooms` | GET | Active rooms status |
| `/api/analytics/utilization` | GET | Zone utilization analytics |
| `/api/analytics/rooms` | GET | Cross-room pattern analysis |
| `/api/heatmap/{room_id}` | GET | Zone heatmap data |
| `/api/reservation/{seat_id}` | POST/DELETE | Create/release reservation |
| `/api/reservations` | GET | All active reservations |
| `/health` | GET | Health check |

### 7.3 Dashboard Backend (Port 5000)

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/seat_state` | GET/POST | Seat state |
| `/api/alert` | POST | Alert notifications |
| `/api/stats` | GET | Dashboard statistics |

---

## 8. Dashboard

### 8.1 Features

- **Zone Grid**: 28 seats color-coded by state
  - Green: Empty
  - Red: Occupied
  - Yellow: Suspected Ghost (with countdown timer)
  - Purple: Confirmed Ghost
- **Ghost Alert Feed**: Real-time notifications
- **Occupancy Charts**: Historical visualization
- **Room Selector**: Multi-room support
- **Reservation System**: Book seats with 15-min TTL

### 8.2 Color Coding

| State | Color | Hex |
|-------|-------|-----|
| Empty | Green | `#22c55e` |
| Occupied | Red | `#ef4444` |
| Suspected Ghost | Yellow | `#eab308` |
| Confirmed Ghost | Purple | `#a855f7` |

---

## 9. Setup & Deployment

### 9.1 Prerequisites

- Unity 2022.3 LTS
- Python 3.11+
- Docker (for Mosquitto, InfluxDB)
- Node.js 18+ (for dashboard frontend)

### 9.2 Start Order

1. **Start infrastructure:**
   ```bash
   cd /Users/agentswarm/Desktop/IotProject
   docker-compose up -d  # Mosquitto + InfluxDB
   ```

2. **Start Edge Processor:**
   ```bash
   cd /Users/agentswarm/Desktop/IotProject/edge
   source ../venv/bin/activate
   python processor.py
   ```

3. **Start RPi Simulator:**
   ```bash
   cd /Users/agentswarm/Desktop/IotProject/edge/rpi_simulator
   python main.py
   ```

4. **Start Dashboard:**
   ```bash
   cd /Users/agentswarm/Desktop/IotProject/dashboard
   flask run --port 5000
   ```

5. **Start Dashboard Frontend:**
   ```bash
   cd /Users/agentswarm/Desktop/IotProject/dashboard-frontend
   npm install
   npm run dev
   ```

6. **Run Unity Scene:**
   - Open Unity Editor with LibraryModel project
   - Open StudyHall scene
   - Press Play

---

## 10. Project Structure

```
/Users/agentswarm/Desktop/IotProject/
├── LibraryModel/           # Unity 3D Simulation
│   ├── Assets/Scripts/     # C# scripts
│   └── Assets/Scenes/      # Unity scenes
│
├── edge/                   # Edge Processing
│   ├── processor.py        # Central aggregator (:5002)
│   ├── config.py           # Configuration
│   ├── ghost_detector.py   # Ghost detection FSM
│   ├── sensor_fusion.py    # Sensor fusion
│   └── rpi_simulator/      # Per-room processor (:5001)
│       ├── http_server.py  # Flask API
│       ├── room_processor.py # Occupancy mapping
│       ├── main.py         # Entry point
│       └── yolo_trainer.py # YOLO training
│
├── dashboard/             # Dashboard Backend
│   ├── app.py             # Flask app
│   └── templates/         # HTML templates
│
├── dashboard-frontend/     # Dashboard Frontend (React)
│   ├── src/
│   │   ├── App.tsx       # Main app
│   │   └── components/   # React components
│   └── package.json
│
├── docs/                 # Documentation
│   ├── ARCHITECTURE.md   # This file
│   ├── README.md
│   └── ...
│
├── broker/               # MQTT broker config
├── influxdb/             # InfluxDB config
└── venv/                 # Python virtual environment
```

---

## Document Version

**Version:** 2.0
**Last Updated:** March 2026
**Authors:** Liberty Twin Team
