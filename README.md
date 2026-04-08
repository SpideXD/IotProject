# Liberty Twin

**Privacy-Preserving Library Occupancy Monitoring with Ghost Seat Detection**

An IoT system that monitors library seat occupancy using camera + radar sensor fusion, detects "ghost seats" (bags left behind without a person), and provides real-time visualization through a 3D digital twin and web dashboard.

Built for IIT ISM Dhanbad by Team OverThinker.

---

## The Problem

Students waste 10–15 minutes searching for available library seats. Meanwhile, 20–30% of apparently occupied seats are actually abandoned — bags and books left behind to reserve space while the student is away. There's no way to know which seats are truly available.

---

## The Solution

**Simulation-first IoT pipeline** spanning 4 layers:

1. **Unity 3D Digital Twin** — High-fidelity simulation of the IIT ISM Dhanbad library with 7 zones, 28 seats, and student behavior agents running on an internal clock acceleratable to 10× real-time
2. **RPi Simulator** — Replicates Raspberry Pi 4B behavior: YOLOv8 object detection (person, bag, chair) + ghost detection FSM. Works with both Unity simulation and physical hardware without code changes
3. **Edge Processor** — Central Flask aggregator on port 5002. Performs 60/40 camera-radar sensor fusion, maintains thread-safe occupancy state, exposes REST + MQTT pub/sub
4. **Cloud Dashboard** — React/TypeScript dashboard (Vite) with live seat maps, ghost alert countdown timers, 3D isometric pipeline view, and InfluxDB trend charts

```
Unity 3D → RPi Simulator → Edge Processor → React Dashboard → InfluxDB
   ↓             ↓                ↓               ↓               ↓
 Camera+      YOLO +          MQTT agg +        Live UI +       Historical
 Radar        Ghost FSM       Sensor Fusion      3D View         Storage
```

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Ghost Detection FSM** | 4-state temporal machine: OCCUPIED → SUSPECTED_GHOST (2 min no motion) → CONFIRMED_GHOST (5 min more) → EMPTY. Reverts immediately on student return |
| **Multi-Modal Fusion** | 60% camera + 40% radar + 10% agreement bonus. Camera tells WHAT is there; radar confirms WHETHER it's alive |
| **Student Behavior Simulation** | FSM-based agents: WALKING → SITTING → LEAVING → RETURNING → BREAK. Probabilistic durations, 70% return rate from breaks, 30% abandonment rate |
| **Time Acceleration** | Unity simulation runs 1×–10× real-time. A full 24-hour virtual day completes in 2.4 hours at 10× |
| **Simulation-First** | Complete system validated in simulation before any physical hardware purchased. Discovered pillar obstruction problem (6 library pillars blocking single camera) → led to 2-camera rail design |
| **Deep Dive Overlay** | Per-node inspection with live FPS, messages/minute, and state counts at 1–2 second polling intervals |
| **3D Pipeline View** | Interactive isometric visualization of the full Unity → RPi → Edge → Cloud data flow with live status indicators |

---

## Project Structure

```
liberty-twin/
├── edge/                          # Central edge processor
│   ├── processor.py               # Flask REST API + MQTT aggregation + ghost FSM
│   ├── multi_rpi_simulator.py     # Simulates multiple RPi zone nodes
│   ├── rpi_simulator/             # RPi simulator per zone
│   │   ├── server.py              # RPi HTTP server (receives from Unity)
│   │   ├── fsm_state.json        # FSM state persistence
│   │   └── YOLO inference        # ONNX-based object detection
│   └── requirements.txt
│
├── dashboard/                     # React/TypeScript dashboard
│   ├── src/
│   │   ├── App.tsx               # Main layout
│   │   ├── components/
│   │   │   ├── Dashboard.tsx      # Main dashboard with seat map
│   │   │   ├── Header.tsx        # Top header bar
│   │   │   ├── StatsBar.tsx      # KPI stat cards
│   │   │   ├── SeatMap.tsx       # Live seat grid visualization
│   │   │   ├── AlertFeed.tsx     # Ghost alert feed
│   │   │   ├── OccupancyChart.tsx # InfluxDB trend chart
│   │   │   ├── PipelineIsometric.tsx # 3D isometric pipeline view
│   │   │   └── DeepDiveOverlay.tsx  # Fullscreen node inspection
│   │   └── lib/
│   │       └── pipelineData.ts   # Pipeline node definitions
│   ├── package.json
│   └── vite.config.ts
│
├── LibraryModel/                  # Unity 3D digital twin
│   └── Assets/Scripts/           # C# sensor + student behavior scripts
│
├── broker/                        # Eclipse Mosquitto MQTT config
├── docs/                          # Architecture docs
└── scripts/                       # Startup scripts
```

---

## Getting Started

### Prerequisites

- Python 3.9+
- Node.js 18+ and npm
- Eclipse Mosquitto MQTT broker
- Unity 2022 LTS (for simulation)

### Run the Full Pipeline

```bash
# 1. Start MQTT broker
mosquitto -p 1883

# 2. Start Edge Processor (port 5002)
cd edge && pip install -r requirements.txt && python processor.py

# 3. Start RPi Simulator (ports 5001/5003)
cd edge && python multi_rpi_simulator.py

# 4. Start React Dashboard (port 3000)
cd dashboard && npm install && npm run dev

# 5. Open browser
open http://localhost:3000

# 6. (Optional) Open Unity LibraryModel scene and press Play
```

### Run Individual Components

```bash
# Edge processor only
cd edge && python processor.py

# RPi simulator only (single zone)
cd edge/rpi_simulator && python server.py --zone zone_a --port 5001

# Multi-zone RPi simulator
cd edge && python multi_rpi_simulator.py

# Dashboard only
cd dashboard && npm run dev
```

---

## Ghost Detection State Machine

```
EMPTY ──[presence detected]──▶ OCCUPIED
                                    │
                              no motion 2 min
                                    ▼
                            SUSPECTED_GHOST ◀──[motion detected]──┐
                                    │                              │
                            no motion 5 min more                    │
                                    ▼                              │
                            CONFIRMED_GHOST ──[person returns]──────┘
                                 Alert sent
```

**Key behavior:** If a student returns before CONFIRMED_GHOST (e.g., bathroom break under 7 minutes), the state reverts to OCCUPIED immediately — no false ghost alert is sent.

**Fusion formula:** `score = 0.6 × camera_confidence + 0.4 × radar_confidence + 0.1 × agreement_bonus`

---

## Hardware (Production Deployment)

| Component | Model | Purpose | Price (₹) |
|-----------|-------|---------|-----------|
| Camera | RPi Camera v2 (Sony IMX708) | Object detection | 350 |
| Radar | HiLink 24 GHz (HLK-LD2410B) | Micro-motion detection | 400 |
| Compute | Raspberry Pi 4B (8GB) | Edge processing per zone | 5,000 |
| Rail System | Aluminum extrusion + GT2 belt | Camera mounting | 1,300 |
| **Per Zone Total** | | | **~7,050** |

**Simulation mode:** No physical hardware required — Unity digital twin produces identical data formats.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Simulation | Unity 2022 LTS, C#, URP |
| Edge Compute | Python 3.12, YOLOv8 (ONNX), Flask, OpenCV |
| Messaging | MQTT (Eclipse Mosquitto, port 1883) |
| Storage | InfluxDB 2.7 (time-series) |
| Dashboard | React 18, TypeScript, Vite, Framer Motion, Recharts |
| AI Model | Ultralytics YOLOv8-nano (best.pt), trained on synthetic dataset |

---

## Team OverThinker — IIT ISM Dhanbad

| Name | Adm No. | Contribution |
|------|---------|-------------|
| Kumar Satyam | 22JE0507 | Unity 3D Simulation & Student Behavior Modeling |
| Adarsh Sen Singh | 22JE0038 | Unity 3D Modeling & Digital Twin Architecture |
| Ranit Nandi | 22JE0780 | YOLO Model Training & Dataset Curation |
| Divyanshu Singh | 22JE0333 | Model Fine-Tuning & RPi Simulator |
| Nakshatra Singh | 22JE0600 | Edge Processor & MQTT Pipeline |
| Kartik Kumar Singh | 22JE0461 | Dashboard, MQTT Broker & InfluxDB |

---

## Demo & Links

- **GitHub:** https://github.com/TheSpideX/liberty-twin
- **Dataset:** https://www.kaggle.com/datasets/spidexd/iot-project-v2
- **Model Training:** https://www.kaggle.com/code/spidexd/iot-model-training
- **Demo Video:** https://drive.google.com/drive/folders/12_o5Q8x0iKpvJoQKwMnbd5_4B8_u7Mhl
