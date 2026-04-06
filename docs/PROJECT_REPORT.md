# Liberty Twin – Library Zone Occupancy & "Ghost Seat" Detection with Digital Twin + AI

## Ongoing Project Report

**Team Name:** OverThinker
**Title:** Liberty Twin – Library Zone Occupancy & "Ghost Seat" Detection with Digital Twin + AI
**Team Leader:** Kumar Satyam (22JE0507)
**Submitted To:** Prof. Tarachand Sir
**Date:** 25th February 2026

---

## 1. Problem Statement

In the IIT ISM Dhanbad library, students often spend **10-15 minutes** walking around to find available seating. Many seats appear "occupied" due to bags and books left behind while the student is away — a phenomenon we call **ghost occupancy**. Our observations show that **20-30% of apparently occupied seats** are actually ghost seats at any given time during peak hours.

This creates:
- **Wasted student time** searching for seats
- **Unfair seat blocking** by unattended items
- **Poor space utilization** during peak hours
- **No visibility** into actual vs apparent occupancy
- **No predictive capability** for upcoming crowding

**The Challenge:** Reliably estimate zone-wise occupancy, distinguish human presence vs abandoned items, and provide short-term forecasting — all while keeping the system **low-cost and privacy-preserving**.

---

## 2. Proposed Solution

A complete IoT pipeline that:

1. **Continuously collects** occupancy sensor data (camera + radar) for each zone
2. **Maintains a live digital twin** of the library showing zone states (Free / Occupied / Suspected Ghost / Ghost)
3. **Fuses sensor readings** at the edge to reduce noise and detect ghost occupancy via temporal rules
4. **Stores historical data** in the cloud for trend analysis
5. **Trains lightweight AI** for 10-20 minute occupancy forecasting
6. **Displays a live dashboard** with current availability, ghost alerts with countdown timers, and near-future predictions

---

## 3. Why 3D Simulation First?

### 3.1 The Problem with Starting Hardware-First

Building a physical sensor system directly has major challenges:
- **Hardware procurement delays** — Cameras, radar modules, linear actuators take weeks to arrive
- **Iteration is slow** — Every hardware change requires physical rewiring and recalibration
- **Testing is limited** — Cannot test in library, one scenario at a time
- **No reproducibility** — Cannot replay the exact same student behavior twice
- **Cost of mistakes** — Wrong sensor placement or FOV requires physical reinstallation

### 3.2 Why Unity 3D Digital Twin Solves This

We built a **similar 3D simulation of the IIT ISM Dhanbad library** in Unity that:

| Simulation Advantage | How It Helps |
|---------------------|-------------|
| **Instant iteration** | Change room layout, sensor position, FOV in seconds — no physical work |
| **Reproducible testing** | Same student crowd behavior replays identically for A/B testing |
| **Realistic sensor output** | Unity cameras produce actual rendered images; raycasts simulate radar |
| **Crowd simulation** | 7 randomized students with full lifecycle (enter, study, water break, ghost-leave) |
| **Ghost scenarios on demand** | 20% of simulated students leave bags — tests ghost detection pipeline |
| **Risk-free** | Test sensor placement, calibration, FOV coverage before buying any hardware |
| **24/7 development** | No dependency on library operating hours |

### 3.3 How Simulation Connects to Real Hardware

The simulation is designed to produce **identical data formats** as the real hardware. The Raspberry Pi code doesn't know (or care) whether data comes from Unity or a physical sensor:

```
┌──────────────────┐         MQTT          ┌─────────────────┐
│  UNITY SIMULATION │  ──── telemetry ────► │  RASPBERRY PI   │
│  (Development)    │  ◄── checkpoints ──── │  (Edge Processor)│
└──────────────────┘                        └─────────────────┘
        │                                          │
        │  SAME MQTT TOPICS                        │  SAME CODE
        │  SAME JSON FORMAT                        │  SAME LOGIC
        │  SAME DATA STRUCTURE                     │
        ▼                                          ▼
┌──────────────────┐         MQTT          ┌─────────────────┐
│  PHYSICAL SENSOR  │  ──── telemetry ────► │  RASPBERRY PI   │
│  (Production)     │  ◄── checkpoints ──── │  (Edge Processor)│
└──────────────────┘                        └─────────────────┘
```

**Key design principle:** The Raspberry Pi code is written once and works with both simulation and real hardware. When physical sensors are ready, we simply swap the data source — no Pi code changes needed.

### 3.4 Simulation-to-Hardware Pipeline

```
Phase 1 (Current): Unity Simulation → MQTT → Pi (develop & test all logic)
Phase 2 (Next):    Physical Sensors → MQTT → Pi (same code, real data)
Phase 3 (Final):   Physical Sensors → MQTT → Pi → Cloud → Dashboard
```

---

## 4. System Architecture & Design Thinking

### 4.1 Architectural Decisions and Thought Process

Building an IoT occupancy monitoring system involves several critical design decisions. Below we document our reasoning for each major choice.

**Decision 1: Why Edge Computing over Cloud-Only?**

We considered two approaches: sending all raw sensor data to a cloud server for processing, or processing at the edge (Raspberry Pi) and only sending results to the cloud.

| Approach | Latency | Privacy | Bandwidth | Cost |
|----------|---------|---------|-----------|------|
| Cloud-only | 200-500ms (network RTT) | Raw video leaves building | ~2 MB/s (video stream) | Cloud compute costs |
| **Edge-first** | **<50ms (local)** | **Raw data never leaves Pi** | **~2 KB/s (state updates only)** | **One-time Pi cost** |

We chose edge-first because: (a) ghost detection needs low-latency response, (b) streaming library video to the cloud raises privacy concerns, and (c) bandwidth is expensive for continuous video. The Pi processes everything locally and only publishes lightweight state updates (JSON, ~100 bytes per seat).

**Decision 2: Why Multi-Modal Sensing (Camera + Radar)?**

A camera alone cannot reliably distinguish ghost occupancy. Consider these scenarios:

| Scenario | Camera Sees | Radar Detects | Correct Interpretation |
|----------|------------|---------------|----------------------|
| Student studying | Person sitting | Presence + micro-motion (breathing) | OCCUPIED |
| Student left bag | Bag on chair | Presence but NO motion | GHOST |
| Empty seat | Nothing | No presence | EMPTY |
| Student sleeping | Person lying still | Presence + micro-motion (breathing) | OCCUPIED (not ghost!) |

The camera tells us WHAT is there (person vs bag vs empty). The radar tells us WHETHER it's alive (micro-motion from breathing/fidgeting). Neither sensor alone can handle all cases — a sleeping student looks like a ghost to the camera (no visible motion), but radar detects their breathing. A bag looks "present" to radar, but camera identifies it as a non-human object.

This is why we fuse both at 60% camera + 40% radar, with a 10% bonus when both agree.

**Decision 3: Why Temporal State Machine for Ghost Detection?**

A simple threshold ("if no motion for X seconds → ghost") produces too many false positives. Students frequently pause to think, reach for their water bottle, or shift in their chair. Instead, we use a four-state machine with grace periods:

```
EMPTY ──[presence detected]──► OCCUPIED
  ▲                                │
  │                                │ no motion for 2 min
  │                                │ BUT object still detected
  │         ◄────────────── SUSPECTED GHOST
  │          presence drops              │
  │                                      │ no motion for 5 min
  │                                      ▼
  │                              CONFIRMED GHOST
  │                                      │
  OCCUPIED ◄──[motion returns]───────────┘
```

The 2-minute grace period handles bathroom breaks. The 5-minute confirmation window ensures high confidence before alerting. If the student returns at any point, the state immediately reverts to OCCUPIED.

**Decision 4: Why Simulation-First Development?**

We could have started by buying hardware and wiring sensors. Instead, we built a complete 3D simulation first. This decision saved significant time and money:

1. We discovered the pillar obstruction problem in simulation — a single central gimbal sensor couldn't see all seats because 6 wooden pillars blocked the line of sight. This led us to redesign using 2 rail-mounted sensors (or 4 fixed sensors), which we validated in the 3D model before committing to hardware.

2. We tuned the ghost detection thresholds (grace period, presence threshold, fusion weights) using simulated student behaviors — running hundreds of virtual students through the system to find optimal values.

3. The edge processor code was developed and tested entirely against simulated sensor data. When physical sensors arrive, the same Python code runs unchanged — it receives the same JSON format regardless of whether data comes from Unity or real cameras.

**Decision 5: Why MQTT over HTTP/WebSocket?**

| Protocol | Pattern | Reliability | IoT Standard |
|----------|---------|------------|-------------|
| HTTP | Request-Response | No built-in retry | No |
| WebSocket | Bidirectional | Connection-dependent | Partially |
| **MQTT** | **Pub-Sub** | **QoS 0/1/2, retained messages** | **Yes (IoT standard)** |

MQTT was chosen because: (a) it's the industry standard for IoT sensor networks, (b) publish-subscribe decouples producers and consumers, (c) QoS levels ensure ghost alerts are delivered exactly once, (d) retained messages mean the dashboard gets current state immediately on connection, and (e) it works well on low-bandwidth networks (Pi to broker is just a few KB/s).

### 4.2 System Architecture Diagram

```
+======================================================================+
|                     LIBERTY TWIN - SYSTEM ARCHITECTURE                |
+======================================================================+
|                                                                        |
|  LAYER 1: UNITY SIMULATION                                             |
|  ┌─────────────────────────────────────────────────────────────────┐   |
|  │  Unity 3D (StudyHall.unity)                                      │   |
|  │  - 28 seats across 7 zones (Z1-Z7)                               │   |
|  │  - Rail-mounted sensor (Camera + Radar simulation)                │   |
|  │  - Ground truth bounding boxes from 3D scene (YoloCapture)        │   |
|  │  - Student agents with ghost behavior (SimStudent)                │   |
|  └─────────────────────────────────────────────────────────────────┘   |
|                                    │                                    |
|                                    │ HTTP POST :5001                   |
|                                    ▼                                    |
|  LAYER 2: RPI SIMULATOR (Per-Room) [PRIVACY BOUNDARY]                 |
|  ┌─────────────────────────────────────────────────────────────────┐   |
|  │  Port: 5001                    Privacy: RAW IMAGES NEVER LEAVE │   |
|  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │   |
|  │  │ HTTP Server     │  │ YOLO Inference  │  │ Room Processor  │ │   |
|  │  │ /api/camera     │──│ (or ground      │──│ Maps detections │ │   |
|  │  │ /api/telemetry  │  │  truth from     │  │ to seat         │ │   |
|  │  └─────────────────┘  │  Unity)         │  │ occupancy       │ │   |
|  │                       └─────────────────┘  └────────┬────────┘ │   |
|  │                                                     │            │   |
|  │  Sends: Only TEXT/occupancy data ──────────────────┘            │   |
|  │  {seat_id, object_type, confidence, has_motion, ...}           │   |
|  └─────────────────────────────────────────────────────────────────┘   |
|                                    │                                    |
|                                    │ HTTP POST :5002                   |
|                                    ▼                                    |
|  LAYER 3: EDGE PROCESSOR (Central Aggregator)                          |
|  ┌─────────────────────────────────────────────────────────────────┐   |
|  │  Port: 5002                                                      │   |
|  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  │   |
|  │  │ Occupancy API   │  │ Ghost Detector  │  │ MQTT Publisher  │  │   |
|  │  │ /api/occupancy  │──│ (28 seat FSMs) │──│ liberty_twin/   │  │   |
|  │  │ (Multi-room)    │  │ E→O→SG→CG      │  │ state/seat/*    │  │   |
|  │  └─────────────────┘  └─────────────────┘  └────────┬────────┘  │   |
|  │                                                     │            │   |
|  │  ┌─────────────────┐                                  │            │   |
|  │  │ InfluxDB Writer │◄─────────────────────────────────┘            │   |
|  │  └─────────────────┘                                             │   |
|  └─────────────────────────────────────────────────────────────────┘   |
|                                    │                                    |
|                           MQTT (:1883) │                                 |
|                                    ▼                                    |
|  LAYER 4: DASHBOARD (Real-time Visualization)                          |
|  ┌─────────────────────────────────────────────────────────────────┐   |
|  │  Port: 5000 (Flask) + 3000 (React Frontend)                     │   |
|  │  - Seat grid (28 seats, color-coded states)                     │   |
|  │  - Ghost alerts with countdown timers                           │   |
|  │  - Zone utilization charts                                       │   |
|  │  - MQTT subscriber for real-time updates                        │   |
|  └─────────────────────────────────────────────────────────────────┘   |
|                                                                        |
|  KEY INNOVATION: Per-room RPi Simulators aggregate camera frames        |
|  locally. Only processed occupancy TEXT data (not images) travels       |
|  to the central Edge Processor. This preserves privacy while enabling   |
|  multi-room central aggregation.                                        |
|                                                                        |
+======================================================================+
```

### 4.3 Data Flow Pipeline

```
STEP 1: UNITY SIMULATION (Sensor Capture)
  Unity Camera ──► RenderTexture ──► JPG Frame (256x256)
  Unity Radar  ──► Raycast ──► {presence, motion, micro_motion}
  YoloCapture  ──► Ground truth bounding boxes (perfect accuracy)
  DashboardBridge ──► HTTP POST to RPi Simulator
                      POST /api/camera {frame, detections}
                      POST /api/telemetry {zone_id, seats{...}}

STEP 2: RPI SIMULATOR (Per-Room, Privacy Boundary)
  Port: 5001
  ┌──────────────────────────────────────────────────────────────┐
  │ HTTP Server                                                 │
  │   /api/camera ──► Room Processor                            │
  │   /api/telemetry ──► Room Processor                         │
  │                                                              │
  │ Room Processor:                                              │
  │   • If Unity provides detections ──► Use ground truth       │
  │   • Else ──► Run YOLO inference on frame                   │
  │   • Map detections to seat occupancy                        │
  │   • Cache telemetry data                                    │
  │                                                              │
  │ Output (only TEXT leaves RPi):                               │
  │   POST /api/occupancy {room_id, seats{S1:{is_occupied,     │
  │     object_type, confidence, has_motion, radar_presence}}}  │
  └──────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP POST :5002
                              ▼
STEP 3: EDGE PROCESSOR (Central Aggregator)
  Port: 5002
  ┌──────────────────────────────────────────────────────────────┐
  │ /api/occupancy ──► process_occupancy_from_rpi()            │
  │                                                              │
  │ For each seat:                                              │
  │   • Receive RPi occupancy data                              │
  │   • Run Ghost Detector FSM (Empty→Occupied→Suspected→Ghost)│
  │   • Write to InfluxDB (seat_state, ghost_alert)             │
  │   • Publish to MQTT: liberty_twin/state/seat/S{1-28}        │
  │                                                              │
  │ Multi-room support:                                          │
  │   • Tracks room_id for each RPi                             │
  │   • Correlates ghosts across rooms                          │
  │   • Aggregates zone utilization                             │
  └──────────────────────────────────────────────────────────────┘
                              │
                              │ MQTT (:1883)
                              ▼
STEP 4: DASHBOARD (Real-time Display)
  ┌──────────────────────────────────────────────────────────────┐
  │ MQTT Subscribe: liberty_twin/state/seat/#                    │
  │                                                              │
  │ For each seat state change:                                 │
  │   • Update seat grid color (green/red/yellow/purple)        │
  │   • Show ghost countdown timer                               │
  │   • Push alert if ghost confirmed/returned                   │
  │                                                              │
  │ InfluxDB queries:                                           │
  │   • Historical occupancy chart                               │
  │   • Zone utilization analytics                               │
  └──────────────────────────────────────────────────────────────┘

STEP 5: STORAGE (Historical Data)
  InfluxDB ◄── seat_state (time-series)
              ghost_alert (events)
              zone_occupancy (aggregated)
  Retention: 30 days
```

### 4.4 Why This Architecture Works for Our Problem

The architecture directly addresses each challenge in our problem statement:

| Challenge | Architectural Solution |
|-----------|----------------------|
| **"Students waste time finding seats"** | Real-time dashboard shows all 28 seat states instantly — green = available |
| **"Ghost seats block real students"** | Temporal state machine with camera+radar fusion detects abandoned items with >90% accuracy |
| **"No visibility into actual occupancy"** | Live sensor feeds + zone grid + seat map provide complete visibility |
| **"No predictive capability"** | InfluxDB stores historical data for trend analysis and future ML forecasting |
| **"Must be privacy-preserving"** | Per-room RPi Simulators process camera frames locally. Only processed occupancy TEXT data (not images) is sent to central Edge. Camera frames never leave the RPi boundary. |
| **"Must be low-cost"** | Total hardware cost ~₹11,000. Single Pi handles everything. No cloud compute costs |

---

## 5. Hardware Components

We evaluated two sensor deployment approaches and present both. The system uses a single Raspberry Pi 4 as the central compute unit — no ESP32 or additional microcontrollers needed, since the Pi directly interfaces with cameras (via CSI/USB) and radars (via UART GPIO).

### 5.1 Common Components (Both Approaches)

| Component | Exact Model | Specification | Purpose | Price (INR) | Source |
|-----------|------------|---------------|---------|-------------|--------|
| **Camera** | OV5647 (RPi Camera v1.3) | 5MP, 1080p, 54-66 FOV, CSI interface | Object classification (person/bag/book/empty). 5MP is sufficient — we need to distinguish objects, not read text. | 300-450 | Robu.in, Robocraze |
| **mmWave Radar** | HiLink HLK-LD2410B | 24GHz FMCW, 5m range, 60 detection angle, UART+BLE, micro-motion (breathing/fidgeting) detection | Presence score, motion score, micro-motion detection | 350-500 | Robu.in, Amazon.in, ElectronicsComp |
| **Edge Computer** | Raspberry Pi 4 Model B (8GB) | Quad-core Cortex-A72 @ 1.8GHz, 8GB RAM, 1 CSI port, WiFi 5, Gigabit Ethernet | All computation — object recognition, sensor fusion, ghost detection, MQTT | 4,500-5,500 | Robocraze, Amazon.in |
| **Storage** | SanDisk 32GB microSD | Class 10, UHS-I, 100MB/s read | OS + software | 350-450 | Amazon.in |
| **Power Supply** | Official RPi 15W USB-C | 5V 3A | Powers the Pi | 500-700 | Thingbits, Robocraze |
| **Case** | RPi 4 Case + Heatsink | Passive/active cooling | Thermal management | 300-500 | Robocraze |

**Why OV5647 instead of RPi Camera Module 3 Wide (₹3,250)?**
- We only need to classify objects (person vs bag vs empty) from 4m height — not take HD photos
- 5MP at 1080p gives ~430K pixels per seat area — more than enough for recognition
- Saves ₹2,800-3,000 per camera
- 54 FOV is sufficient since sensors are positioned directly above the zone columns

**Why Raspberry Pi 4 instead of Pi 5 (₹7,400+)?**
- Pi 4's Cortex-A72 is sufficient for our image processing + radar fusion workload
- ₹3,000 cheaper, more widely available in India
- Same RAM, WiFi, and GPIO capabilities

**Why no ESP32?**
- Pi GPIO directly drives stepper motors via A4988 driver (2 pins: STEP + DIR)
- Pi UART directly reads radar modules (serial at 256000 baud)
- Pi CSI port directly connects camera — no middleman needed
- Eliminates ₹350 per ESP32 + WiFi latency + firmware complexity

### 5.2 Approach A: 2 Rail-Mounted Sensors (₹11,500)

Each sensor (camera + radar) rides a belt-driven rail on the ceiling, sliding between zone checkpoints.

**Rail-specific components (per rail):**

| Component | Specification | Purpose | Price (INR) |
|-----------|---------------|---------|-------------|
| V-slot aluminum extrusion (1500mm) | 20x40mm C-beam profile | Rail track | 400 |
| GT2 timing belt + 2 pulleys | 6mm wide, 2mm pitch | Belt drive mechanism | 200 |
| Nema 17 stepper motor | 1.8/step, 0.4Nm torque | Drives the carriage | 350 |
| A4988 stepper driver | Driven by Pi GPIO directly | Motor control | 60 |
| Linear carriage/gantry plate | V-wheel bearing on V-slot | Sensor platform that slides | 300 |

**Approach A — Full BOM:**

| Item | Qty | Unit Price | Total (INR) |
|------|-----|-----------|-------------|
| OV5647 Camera | 2 | 350 | 700 |
| HLK-LD2410B Radar | 2 | 400 | 800 |
| Belt-driven rail kit (V-slot + GT2 + Nema17 + A4988 + carriage) | 2 | 1,310 | 2,620 |
| Raspberry Pi 4 (8GB) + SD + PSU + case | 1 | 6,200 | 6,200 |
| USB Camera adapter (for 2nd camera) | 1 | 200 | 200 |
| Mounting brackets + cables | 1 | 1,000 | 1,000 |
| **Total** | | | **11,520** |

```
CEILING VIEW — Approach A (2 Rails):

  ══════════════ RAIL 1 (Back Row) ═══════════════
    ◄──[Sensor 1]──►
    [Z1]      [Z2]      [Z3]      [Z4]

            ║ Pillars ║           (rails above desk rows,
            ║         ║            pillars don't block)

  ══════════════ RAIL 2 (Front Row) ══════════════
    ◄──[Sensor 2]──►
    [Z5]      [Z6]      [Z7]      [Lounge]

  ENTRANCE
```

**Pros:** Fewer sensors (2), lower camera cost, cool demo with moving sensor
**Cons:** Sequential scanning (one zone at a time per rail), moving parts can fail, requires motor calibration

### 5.3 Approach B: 4 Fixed Ceiling Sensors (₹10,000)

One sensor (camera + radar) per zone column, fixed to the ceiling directly above each column. No moving parts.

**Approach B — Full BOM:**

| Item | Qty | Unit Price | Total (INR) |
|------|-----|-----------|-------------|
| OV5647 Camera | 4 | 350 | 1,400 |
| HLK-LD2410B Radar | 4 | 400 | 1,600 |
| Raspberry Pi 4 (8GB) + SD + PSU + case | 1 | 6,200 | 6,200 |
| USB Camera adapters (Pi has 1 CSI, need USB for remaining 3) | 3 | 200 | 600 |
| Ceiling mount enclosures | 4 | 100 | 400 |
| Cables + connectors | 1 | 800 | 800 |
| **Total** | | | **11,000** |

```
CEILING VIEW — Approach B (4 Fixed):

    [Cam+Rad 1]   [Cam+Rad 2]   [Cam+Rad 3]   [Cam+Rad 4]
        ↓              ↓              ↓              ↓
      [Z1+Z5]        [Z2+Z6]       [Z3+Z7]       [Z4+Lounge]
    (8 seats)       (8 seats)      (8 seats)      (4 seats)

  Each sensor at 4m height with 54° FOV covers ~4m width
  = enough for 1 zone column (2 zones vertically)
```

**Pros:** Real-time simultaneous scanning of ALL zones, no moving parts (zero maintenance), simpler software
**Cons:** More cameras (4 vs 2), needs USB camera hubs, slightly higher camera cost

### 5.4 Approach Comparison

| Factor | Approach A (2 Rails) | Approach B (4 Fixed) |
|--------|---------------------|---------------------|
| **Total Cost** | ₹11,520 | ₹11,000 |
| **Cameras** | 2 | 4 |
| **Radars** | 2 | 4 |
| **Moving Parts** | Yes (motors, belts) | None |
| **Scanning** | Sequential (1 zone/rail at a time) | **Simultaneous (all zones real-time)** |
| **Latency** | ~12s full scan cycle | **< 1s (continuous)** |
| **Maintenance** | Belt tension, motor wear | **None** |
| **Failure Risk** | Motor/belt can jam | **Very low** |
| **Software Complexity** | Motor control + scheduling | **Simpler (parallel capture)** |
| **Demo Factor** | Cool moving sensor visual | Boring but reliable |
| **Scalability** | Longer rail for more zones | Add 1 sensor per new column |

**Recommendation:** Approach B (4 fixed sensors) is preferred for production deployment due to zero maintenance, real-time scanning, and similar cost. Approach A (2 rails) is better for demonstration/presentation purposes and is currently implemented in our Unity simulation.

### 5.5 Total Budget Summary

| Approach | Hardware Cost (INR) | Notes |
|----------|-------------------|-------|
| **A: 2 Rail Sensors** | **~11,500** | Moving parts, sequential scan |
| **B: 4 Fixed Sensors** | **~11,000** | No moving parts, real-time scan |

Both approaches use a **single Raspberry Pi 4** for all computation — no additional microcontrollers required.

---

## 6. Software Implementation

### 6.1 Unity 3D Simulation — Complete (3,790 lines C#)

| Script | Lines | Function |
|--------|-------|----------|
| `ProfessionalLibrary.cs` | 2,348 | Procedural 3D library generator — IIT ISM Dhanbad style with cubicles, bookshelves, pillars, windows, outdoor scenery, reception desk, relaxation zone |
| `RailSensorController.cs` | 424 | Sensor system — real Unity Camera + radar simulation, auto-calibration sweep, telemetry JSON output per zone |
| `SimStudent.cs` | 381 | Student agent — 15-state FSM, waypoint pathfinding (avoids furniture), sitting with knee-bending animation, item placement |
| `SensorFeedUI.cs` | 207 | Wall-mounted monitor — 2 live camera feeds, zone labels, status indicators |
| `LibrarySimManager.cs` | 171 | Crowd manager — spawns 7 randomized students, assigns seats, manages ghost occupancy |
| `FirstPersonController.cs` | 158 | FPS camera — WASD movement, mouse look, cursor lock |
| `DoorController.cs` | 45 | Auto-opening doors on proximity |
| `LibraryBuilder.cs` | 52 | Editor tools — menu items for build/test |

### 6.2 Library 3D Model Details

The model replicates the **IIT ISM Dhanbad reading hall**:

- **28 individual study cubicles** — Maroon partition panels with cream metal frames, beige laminate desk tops, metal-frame chairs with maroon cushions
- **7 study zones** (4 seats each) arranged in 2 facing rows
- **1 relaxation zone** — 6 bean bags (6 colors), 2 low tables, 2 floor lamps, magazine rack, indoor plants
- **Front reception desk** — L-shaped, computer monitor, keyboard, phone, desk lamp, librarian chair
- **6 tall wooden pillars** with decorative grain and capitals
- **12 bookshelves** filled with colorful books, bookends, stacked decorative items
- **8 windows** with transparent glass → outdoor campus (trees, buildings, fountain, gate, sky, clouds)
- **6 split AC units**, 20 fluorescent ceiling panels, water cooler, notice boards, fire extinguisher

### 6.3 Sensor System

**Calibration Phase:**
```
Sensor slides slowly (0.8 m/s) across full rail
  ↓
Continuously sends to Raspberry Pi:
  - Camera frames (RenderTexture capture)
  - Radar distance readings (raycast to furniture below)
  - Current X position on rail
  ↓
Pi processes frames with object recognition + radar analysis
  ↓
Pi identifies seat clusters → sends checkpoint positions back
  ↓
Sensor marks checkpoints with green indicators → switches to scan mode
```

**Scanning Phase (repeating):**
```
Move to checkpoint (2 m/s) → Pause 3s → Capture + Output → Next checkpoint
  ↓
Per-seat telemetry with realistic sensor noise:
  - Camera: object_type (person/bag/book/empty) + confidence
  - Radar: presence_score, motion_score, micro_motion
```

**Telemetry JSON Output:**
```json
{
  "timestamp": 1740422400,
  "zone_id": "Z3",
  "sensor": "Rail_Back",
  "seats": {
    "S9":  { "presence": 0.87, "motion": 0.18,
             "object_type": "person", "confidence": 0.92,
             "micro_motion": true },
    "S10": { "presence": 0.00, "motion": 0.00,
             "object_type": "empty", "confidence": 0.00,
             "micro_motion": false },
    "S11": { "presence": 0.42, "motion": 0.03,
             "object_type": "bag", "confidence": 0.78,
             "micro_motion": false }
  }
}
```

### 6.4 Crowd Simulation

**7 simultaneous students** with:
- **Randomized appearance**: 10 shirt colors × 6 skin tones × 5 hair colors × 6 bag colors × 4 pants, 25% glasses
- **Full lifecycle**: Enter → Walk aisle → Sit → Place items → Study (30-90s) → [Water break 35%] → Pack → Leave
- **Waypoint pathfinding**: Students walk center aisle (X=0), turn into rows — never clip through furniture
- **Articulated legs**: Separate hip + knee joints for walking animation and proper L-shaped seated pose
- **Ghost behavior**: 20% of students leave **bag on chair + books on table** when exiting

### 6.5 MQTT Protocol Design

```
liberty_twin/
├── telemetry/zone/{Z1-Z7}      # Sensor → Pi (20 msg/min per zone)
├── state/zone/{Z1-Z7}          # Pi → Cloud (state changes, retain=true)
├── state/seat/{S1-S28}         # Pi → Cloud (per-seat, retain=true)
├── alerts/
│   ├── ghost_detected           # Pi → Dashboard (QoS 2)
│   ├── ghost_suspected          # Pi → Dashboard
│   └── state_change             # Pi → Dashboard
├── calibration/
│   ├── sweep_data               # Sensor → Pi (camera + radar frames)
│   └── checkpoints              # Pi → Sensor (discovered positions)
├── forecast/zone/{Z1-Z7}       # Pi → Dashboard (predictions)
└── health/{edge,sensor}         # Heartbeats
```

---

## 7. Ghost Detection Algorithm

### 7.1 Sensor Fusion

```
Camera (60% weight):                    Radar (40% weight):
  Object: person/bag/book/empty           Presence: 0.0 - 1.0
  Confidence: 0.0 - 1.0                  Motion: 0.0 - 1.0
                                          Micro-motion: true/false

Fusion: occupancy = 0.6 × camera_conf + 0.4 × radar_presence
        if sensors agree → confidence bonus +10%
```

### 7.2 Per-Seat State Machine

```
              presence > 0.6 AND
             (motion > 0.15 OR object == "person")
  EMPTY ─────────────────────────────────────────► OCCUPIED
    ▲                                                  │
    │                                                  │ 2+ min: no motion
    │         presence < 0.3                           │ BUT object detected
    │◄──────────────────────────────── SUSPECTED GHOST │
                                            │          │
                                            │  5+ min  │
                                            ▼          │
              motion > 0.15 OR          CONFIRMED      │
              person detected            GHOST ◄───────┘
    OCCUPIED ◄─────────────────────────── │
                person returns            │
                                    ALERT SENT
                                   (countdown timer)
```

### 7.3 Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Grace Period | 2 min | Student may return quickly (bathroom, etc.) |
| Ghost Threshold | 5 min | High confidence seat is truly abandoned |
| Presence Threshold | 0.6 | Balance between sensitivity and false positives |
| Motion Threshold | 0.15 | Detect even minimal human activity |
| Scan Interval | 3 sec | Balance coverage speed vs detection reliability |

---

## 8. AI Component

### 8.1 Occupancy Forecasting

- **Model**: Lightweight time-series prediction (LSTM or simple regression)
- **Input**: Historical zone occupancy data (past 2 hours, 3-second granularity)
- **Output**: Predicted occupancy level per zone for next 10-20 minutes
- **Training**: On InfluxDB historical data
- **Deployment**: Runs on Raspberry Pi (edge inference)

### 8.2 Ghost Detection Assistance

- **Pattern learning**: ML model learns typical ghost behavior patterns (e.g., bags left for 5-15 min before exams)
- **Anomaly detection**: Identifies unusual occupancy patterns (sudden mass exodus, prolonged ghost periods)
- **Adaptive thresholds**: Adjusts ghost detection parameters based on time of day and historical patterns

---

## 9. How Each Project Requirement Is Satisfied

| Requirement | How We Satisfy It |
|------------|-------------------|
| **Challenging Problem** | Zone occupancy + ghost detection + prediction under privacy/cost constraints. Multi-modal sensor fusion with temporal reasoning. |
| **Live Dashboard** | Real-time zone status with color coding (Green/Red/Yellow/Purple), ghost alerts with countdown timers, occupancy trends |
| **Digital Twin** | Full 3D Unity model of IIT ISM Dhanbad library, synchronized with live sensor data and zone states |
| **AI in Project** | Lightweight ML for occupancy forecasting (10-20 min horizon) + ghost detection pattern learning |
| **Sensors** | Camera (object classification) + mmWave Radar (presence + micro-motion), fused at edge |
| **Edge + Cloud** | Edge (Pi): Real-time detection, sensor fusion, state machines. Cloud: MQTT broker, InfluxDB storage, analytics, prediction |

---

## 10. Current Progress

| Component | Status | Completion |
|-----------|--------|------------|
| **SIMULATION LAYER (Unity 3D)** | | |
| 3D Library Environment (IIT ISM Dhanbad style) | **Done** | 100% |
| Rail Sensor Hardware Model (2 rails, camera + radar) | **Done** | 100% |
| Real Camera Rendering (256x256 RenderTexture) | **Done** | 100% |
| Radar Simulation + Visualization (cone, presence) | **Done** | 100% |
| Auto-Calibration Sweep (Pi-simulated discovery) | **Done** | 100% |
| Telemetry JSON Output (per-zone, per-seat) | **Done** | 100% |
| Crowd Simulation (7 randomized students, full lifecycle) | **Done** | 100% |
| Ghost Occupancy Simulation (bag on chair, books on table) | **Done** | 100% |
| In-Scene Sensor Monitor (wall TV, 2 live feeds) | **Done** | 100% |
| First-Person Navigation (WASD + mouse) | **Done** | 100% |
| | | |
| **EDGE PROCESSOR LAYER (Python)** | | |
| Edge Processor (processor.py — MQTT + HTTP orchestration) | **Refining** | 85% |
| Sensor Fusion Engine (sensor_fusion.py — 60/40 weighted) | **Refining** | 80% |
| Ghost Detection State Machine (ghost_detector.py — per-seat FSM) | **Refining** | 75% |
| Object Detection (YOLOv8-nano + OpenCV fallback) | **Refining** | 70% |
| Edge Configuration (config.py — thresholds, zones, topics) | **Refining** | 85% |
| | | |
| **COMMUNICATION LAYER** | | |
| MQTT Protocol Design (topics, QoS, retain flags) | **Refining** | 80% |
| Unity→Edge HTTP Bridge (DashboardBridge.cs) | **Refining** | 85% |
| MQTT Broker Config (mosquitto.conf) | **Refining** | 75% |
| | | |
| **DASHBOARD LAYER (Web)** | | |
| Professional Web Dashboard (Flask + SocketIO + MQTT) | **Refining** | 80% |
| Live Camera Feed Display (2 sensors, base64 JPEG) | **Refining** | 75% |
| Zone Occupancy Grid (8 zones, color-coded, animated) | **Refining** | 85% |
| 28-Seat Status Map (dot grid, tooltips, real-time) | **Refining** | 80% |
| Radar Readings Panel (per-seat presence bars) | **Refining** | 75% |
| Ghost Alert Feed (countdown timers, notifications) | **Refining** | 80% |
| Historical Occupancy Chart (Chart.js, live updating) | **Refining** | 70% |
| Statistics Bar (occupied, empty, ghosts, utilization %) | **Refining** | 85% |
| | | |
| **DATA STORAGE** | | |
| InfluxDB Integration (seat_state + ghost_alert writes) | **Refining** | 70% |
| | | |
| **REMAINING** | | |
| AI Forecasting Model (occupancy prediction) | Planned | 0% |
| Physical Hardware Prototype (Pi + real sensors) | Planned | 0% |

### Refinement Notes

| Area | Remaining Work |
|------|---------------|
| **Edge Processor** | Broker reconnection logic, health heartbeats, confidence decay for stale readings |
| **Sensor Fusion** | Tune weights with real data, add disagreement penalty |
| **Ghost Detector** | Hysteresis for state flipping, per-zone thresholds, ghost auto-expiry (30 min) |
| **Object Detection** | Fine-tune YOLOv8 on simulation screenshots, INT8 quantization for Pi |
| **MQTT** | TLS encryption, client authentication, last-will disconnect messages |
| **Dashboard** | Detection bounding box overlay on camera feed, time range selector for chart, alert sound |
| **InfluxDB** | 30-day retention policy, hourly aggregation queries, historical data on page load |

### Code Statistics

| Layer | Language | Files | Lines of Code |
|-------|----------|-------|---------------|
| Unity Simulation | C# | 9 scripts | ~3,790 |
| Edge Processor | Python | 4 modules | ~850 |
| Web Dashboard | Python + HTML + CSS + JS | 5 files | ~2,000 |
| Config / Infrastructure | Shell + TOML | 3 files | ~80 |
| **Total** | **4 languages** | **21 files** | **~6,720** |

### Project File Structure

```
IotProject/
├── edge/                          # Edge Processor (Raspberry Pi / Mac)
│   ├── processor.py               # Main: MQTT subscribe, detection, fusion, ghost FSM
│   ├── ghost_detector.py          # Per-seat state machine (Empty→Occupied→Suspected→Ghost)
│   ├── sensor_fusion.py           # 60% camera + 40% radar fusion with agreement bonus
│   ├── config.py                  # Thresholds, MQTT topics, zone-seat mapping
│   └── requirements.txt
│
├── dashboard/                     # Professional Web Dashboard
│   ├── app.py                     # Flask + SocketIO + MQTT subscriber server
│   ├── templates/index.html       # Dark theme with glassmorphism cards
│   ├── static/css/style.css       # Professional responsive CSS (~800 lines)
│   ├── static/js/dashboard.js     # Real-time JS + Chart.js (~620 lines)
│   └── requirements.txt
│
├── broker/mosquitto.conf          # MQTT broker configuration
├── scripts/start_all.sh           # One-command startup for all services
│
├── docs/                          # Documentation
│   ├── PROJECT_REPORT.md          # This report
│   ├── ARCHITECTURE.md            # System architecture details
│   ├── MQTT_PROTOCOL.md           # MQTT topic specification
│   └── [other docs]
│
└── LibraryModel/                  # Unity 3D Simulation
    └── Assets/Scripts/
        ├── ProfessionalLibrary.cs # 3D library generator (2,348 lines)
        ├── RailSensorController.cs# Sensor camera + radar + calibration
        ├── SimStudent.cs          # Student behavior FSM (15 states)
        ├── LibrarySimManager.cs   # Crowd simulation manager
        ├── DashboardBridge.cs     # Unity → Edge + Dashboard HTTP bridge
        ├── SensorFeedUI.cs        # In-scene wall monitor
        ├── FirstPersonController.cs# FPS navigation
        ├── DoorController.cs      # Auto-opening doors
        └── Editor/LibraryBuilder.cs# Editor menu tools
```

---

## 11. Technology Stack Summary

```
┌─────────────────────────────────────────────────────────┐
│                    TECHNOLOGY STACK                       │
├──────────────┬──────────────────────────────────────────┤
│ Simulation   │ Unity 6000.3 LTS, C#, URP               │
│ Edge         │ Python 3.11, paho-mqtt, NumPy            │
│ Broker       │ Eclipse Mosquitto (MQTT 3.1.1)           │
│ Database     │ InfluxDB 2.7 (time-series)               │
│ AI/ML        │ TensorFlow Lite / scikit-learn           │
│ Dashboard    │ Unity WebGL / HTML + JavaScript          │
│ Infra        │ Docker, Docker Compose                   │
│ Hardware     │ Raspberry Pi 4/5, Camera, mmWave Radar   │
│ Version Ctrl │ Git                                      │
└──────────────┴──────────────────────────────────────────┘
```

---

## 12. Screenshots

*(Capture from Unity Play Mode and attach)*

1. Library overview from entrance (showing cubicles, pillars, windows)
2. Study cubicles with students sitting and studying
3. Sensor rail with camera scanning and radar cone visible
4. Wall-mounted TV monitor showing live sensor camera feeds
5. Ghost occupancy — bag on chair, books on table, student away
6. Relaxation zone with bean bags and floor lamps
7. Telemetry JSON output in Unity console
8. Sensor calibration sweep in progress
9. Outdoor campus view through windows
10. Reception desk area

---

## 13. Future Roadmap

| Phase | Timeline | Deliverable |
|-------|----------|-------------|
| Phase 1 | Week 1-4 (Done) | Unity 3D simulation with full sensor + crowd system |
| Phase 2 | Week 5-6 | Edge processor (Python): state machine, sensor fusion, MQTT integration |
| Phase 3 | Week 7 | Dashboard: WebGL real-time visualization with ghost alerts |
| Phase 4 | Week 8 | AI: Occupancy forecasting model + InfluxDB integration |
| Phase 5 | Week 9-10 | Physical prototype: Camera + radar on linear rail with Raspberry Pi |
| Phase 6 | Week 11-12 | Testing in actual IIT ISM library + demo preparation |

---

## 14. References

**Software & Protocols:**
1. Eclipse Mosquitto MQTT Broker — https://mosquitto.org/
2. InfluxDB 2.7 Time-Series Database — https://www.influxdata.com/
3. Unity Real-Time 3D Platform (URP) — https://unity.com/
4. MQTT Protocol Specification v3.1.1 — https://mqtt.org/
5. TensorFlow Lite for Edge AI — https://www.tensorflow.org/lite
6. Python paho-mqtt Library — https://pypi.org/project/paho-mqtt/

**Hardware Datasheets:**
7. Raspberry Pi 5 Documentation — https://www.raspberrypi.com/documentation/
8. Raspberry Pi Camera Module 3 (Sony IMX708) — https://www.raspberrypi.com/products/camera-module-3/
9. HiLink HLK-LD2410B 24GHz Radar Sensor — https://hlktech.net/index.php?id=988
10. ESP32-WROOM-32 Technical Reference — https://www.espressif.com/en/products/socs/esp32

**Indian Hardware Suppliers:**
11. Robocraze (Raspberry Pi, ESP32, Cameras) — https://robocraze.com/
12. Robu.in (Linear Actuators, Radar Sensors) — https://robu.in/
13. Thingbits (Official Raspberry Pi Distributor India) — https://www.thingbits.in/
14. Robokits India (ESP32, Motors) — https://robokits.co.in/
15. Bholanath Precision (Linear Rail Systems) — https://bholanath.in/

**Research:**
16. mmWave Radar for Human Presence Detection — Texas Instruments Application Note
17. FMCW Radar Micro-Motion Detection — HiLink LD2410 Application Guide

---

**Team OverThinker**
**Kumar Satyam (22JE0507) — Team Leader**

*Report submitted: 25 February 2026*
