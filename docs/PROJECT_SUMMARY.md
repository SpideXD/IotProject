# Liberty Twin Project Summary

## One-Line Pitch
**Privacy-preserving IoT system for library occupancy monitoring with ghost detection using a multi-tier edge architecture.**

## What Problem Does It Solve?

In university libraries, students waste 10-15 minutes searching for available seats. Meanwhile, 20-30% of "occupied" seats are actually abandoned (ghosts - bags reserving space while students are away).

**Liberty Twin solves this by:**
- Real-time seat availability monitoring (28 seats, 7 zones)
- Automatic ghost detection (2min grace, 5min confirmation)
- Privacy-first architecture (raw images never leave room)
- Multi-room support via central aggregation
- Digital twin dashboard visualization

---

## Architecture

### Multi-Tier Privacy-Preserving Design

```
[Room 1 Unity] → [RPi Simulator :5001] ─┐
[Room 2 Unity] → [RPi Simulator :5001] ─┼→ [Edge Processor :5002] → [Dashboard :5000]
[Room N Unity] → [RPi Simulator :5001] ─┘
       (many per-room)                    (one central)
```

**Key Innovation:** Raw camera images are processed locally on each RPi. Only processed text/occupancy data is sent to the central edge processor.

---

## How It Works

### 1. Simulation Layer (Unity 3D)

A virtual library with **28 seats across 7 zones**. Virtual students:
- Enter and sit at seats
- Study for random durations
- Leave bags and walk away (creating ghosts)
- Return later or leave with bags

**Rail Sensor Array:**
- 7 rails sweeping through zones
- Collects camera + radar data
- Ground truth bounding boxes from 3D scene
- Sends frames + detections to RPi Simulator

### 2. RPi Simulator (Per-Room, Privacy Boundary)

**Port: 5001**

- Receives camera frames + detections from Unity
- Runs YOLO inference locally (or uses ground truth detections)
- Maps detections to seat occupancy
- **Sends only TEXT/occupancy data to Edge** (privacy boundary)
- Delta compression (only send on state change)

### 3. Edge Processor (Central Aggregator)

**Port: 5002**

- Receives occupancy from ALL RPi simulators
- Tracks `room_id` for multi-room support
- Cross-room ghost detection
- InfluxDB persistence for historical data
- MQTT publishing to dashboard

### 4. Dashboard (React + Flask)

**Port: 5000**

- Real-time seat visualization
- Color-coded states: Green (empty), Red (occupied), Yellow (suspected), Purple (ghost)
- Ghost countdown timers
- Alert notifications
- Room selector for multi-room support
- Seat reservation system

---

## Technical Highlights

### Privacy by Design
- All image processing happens on RPi (per-room)
- Only processed text data sent to cloud
- Raw video/images never leave the device
- Enables real-world deployment compliance

### Multi-Room Aggregation
- Central Edge Processor aggregates multiple rooms
- Each room has its own RPi Simulator
- Cross-room pattern analysis
- Ghost correlation across zones

### Ghost Detection Algorithm
```
EMPTY → OCCUPIED (presence + motion detected)
  ↓
OCCUPIED → SUSPECTED_GHOST (no motion for 2 min)
  ↓
SUSPECTED_GHOST → GHOST (no motion for 5 min total)
  ↓
GHOST → OCCUPIED (person returns with motion)
     → EMPTY (bag removed)
```

### Sensor Fusion
- **Camera:** Object detection (person, bag, laptop, book, etc.)
- **Radar:** Presence, motion, micro-motion (breathing/fidgeting)
- **Fusion:** Combined confidence, sensor agreement bonus

---

## System Specifications

| Feature | Specification |
|---------|---------------|
| Total Seats | 28 |
| Zones | 7 (Z1-Z4 back, Z5-Z7 front) |
| Seat States | 4 (Empty, Occupied, SuspectedGhost, Ghost) |
| Grace Period | 2 minutes |
| Ghost Threshold | 5 minutes |
| RPi Simulator Port | 5001 |
| Edge Processor Port | 5002 |
| Dashboard Port | 5000 |
| MQTT Broker Port | 1883 |
| InfluxDB Port | 8086 |

---

## Data Flow

```
Unity ──► RPi Simulator (:5001) ──► Edge Processor (:5002) ──► Dashboard (:5000)
         │                              │
         │ POST /api/camera             │ POST /api/occupancy
         │ {frame, detections}           │ {seats: {...}}
         │                              │
         │ Only TEXT/occupancy           │ MQTT /state/seat/*
         │ never raw images             ▼
         ▼                              │
    YOLO inference                       │
    (on-device)                         ▼
                                     InfluxDB
                                     (historical)
```

---

## Key Features

- **Real-time occupancy** - Live seat status updates
- **Ghost detection** - Automatically identifies abandoned seats
- **Privacy-first** - No video leaves the device
- **Multi-room support** - Central aggregation of multiple rooms
- **Cost-effective** - One sensor array per room
- **Digital twin** - 3D visualization of library
- **Alert system** - Notifications for ghost seats
- **Reservation system** - Book seats with TTL
- **Historical data** - Trend analysis and reporting

---

## Demo Story (5 Minutes)

**Scene 1:** Show empty library (all green)

**Scene 2:** Student enters, sits at Seat S1
- Dashboard: S1 turns red
- Confidence: 89%

**Scene 3:** Student leaves, bag stays
- After 2 min: S1 turns yellow (suspected)
- Countdown timer: 3:00 remaining
- After 5 min: S1 turns purple (ghost)
- Alert: "Ghost detected at S1"

**Scene 4:** Student returns
- S1 immediately turns red
- Alert: "Person returned to ghost seat"

---

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Simulation | Unity 2022.3 LTS, C# |
| RPi Processing | Python 3.11, Flask, YOLOv8 |
| Edge Processing | Python 3.11, Flask, MQTT |
| Message Broker | Eclipse Mosquitto (MQTT) |
| Database | InfluxDB 2.7 (time-series) |
| Dashboard Frontend | React, Tailwind CSS |
| Dashboard Backend | Python Flask |
| Infrastructure | Docker, Docker Compose |

---

## Project Structure

```
/Users/agentswarm/Desktop/IotProject/
├── LibraryModel/              # Unity 3D Simulation
│   ├── Assets/Scripts/
│   │   ├── DashboardBridge.cs    # HTTP to RPi/Edge
│   │   ├── YoloCapture.cs        # Ground truth detections
│   │   ├── RailSensorController.cs
│   │   ├── SimStudent.cs
│   │   └── LibrarySimManager.cs
│   └── Assets/Scenes/
│       └── StudyHall.unity
│
├── edge/                      # Edge Processing
│   ├── processor.py            # Central aggregator (:5002)
│   ├── config.py
│   ├── ghost_detector.py
│   ├── sensor_fusion.py
│   └── rpi_simulator/          # Per-room processor (:5001)
│       ├── http_server.py
│       ├── room_processor.py
│       ├── main.py
│       ├── yolo_trainer.py
│       └── dataset_manager.py
│
├── dashboard/                 # Dashboard Backend (:5000)
│   ├── app.py
│   └── templates/
│
├── dashboard-frontend/         # Dashboard Frontend (React)
│   ├── src/
│   │   ├── App.tsx
│   │   └── components/
│   └── package.json
│
└── docs/                      # Documentation
    ├── ARCHITECTURE.md
    ├── README.md
    ├── MQTT_PROTOCOL.md
    └── ...
```

---

## Success Metrics

- **Ghost Detection Accuracy**: > 90%
- **False Positive Rate**: < 5%
- **System Latency**: < 500ms
- **Privacy**: Zero raw images transmitted to cloud
- **Multi-Room**: Supports N rooms via RPi aggregation

---

## Benefits

**For Students:**
- Find available seats faster
- Avoid ghost seats
- Reserve seats in advance

**For Library Management:**
- Understand usage patterns
- Optimize space allocation
- Reduce conflicts over seats

**For Privacy:**
- No personal data collected
- No video stored or transmitted
- All processing local (on RPi)

---

## Future Enhancements

- Real hardware deployment (RPi + camera + mmWave radar)
- Mobile app for students
- Integration with library booking system
- Heatmap analytics
- Machine learning for behavior prediction
- Face de-identification for enhanced privacy

---

## Getting Started

```bash
# 1. Start infrastructure
docker-compose up -d

# 2. Start Edge Processor (port 5002)
cd edge && source ../venv/bin/activate && python processor.py

# 3. Start RPi Simulator (port 5001)
cd edge/rpi_simulator && python main.py

# 4. Start Dashboard Backend (port 5000)
cd dashboard && flask run --port 5000

# 5. Start Dashboard Frontend
cd dashboard-frontend && npm install && npm run dev

# 6. Run Unity Scene
Open LibraryModel/Assets/Scenes/StudyHall.unity in Unity Editor
Press Play
```

---

**Ready to build Liberty Twin? Start with Phase 1: Unity Simulation!**
