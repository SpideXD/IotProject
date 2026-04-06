# Liberty Twin

**Privacy-Preserving Library Occupancy Monitoring with Ghost Seat Detection**

An IoT system that monitors library seat occupancy using camera + radar sensor fusion, detects "ghost seats" (bags left behind without a person), and provides real-time visualization through a 3D digital twin and web dashboard.

Built for IIT ISM Dhanbad library by Team OverThinker.

---

## The Problem

Students waste 10-15 minutes searching for available library seats. Meanwhile, 20-30% of apparently occupied seats are actually abandoned — bags and books left behind to reserve space while the student is away. There's no way to know which seats are truly available.

## The Solution

Two rail-mounted sensors (camera + mmWave radar) scan 28 seats across 7 zones. A Raspberry Pi processes the data at the edge — classifying objects, fusing sensor readings, and running a ghost detection state machine. Results are displayed on a real-time web dashboard and a 3D digital twin.

```
Sensors → MQTT → Raspberry Pi (edge processing) → Dashboard + InfluxDB
               ↓
         Object Detection (YOLOv8)
         Sensor Fusion (60% camera + 40% radar)
         Ghost State Machine (Empty → Occupied → Suspected → Ghost)
```

---

## Project Structure

```
liberty-twin/
├── edge/                    # Edge processor (Python, runs on Pi)
│   ├── processor.py         # Main: MQTT, detection, fusion, ghost FSM
│   ├── ghost_detector.py    # Per-seat ghost state machine
│   ├── sensor_fusion.py     # Camera + radar fusion engine
│   └── config.py            # Thresholds, topics, zone mapping
│
├── dashboard/               # Web dashboard (Flask + SocketIO)
│   ├── app.py               # Server with MQTT subscriber
│   ├── templates/           # HTML templates
│   └── static/              # CSS + JavaScript
│
├── LibraryModel/            # Unity 3D simulation
│   └── Assets/Scripts/      # C# scripts (sensor, students, library)
│
├── broker/                  # Mosquitto MQTT config
├── scripts/                 # Startup scripts
└── docs/                    # Architecture, protocols, report
```

---

## Demo Videos

### 3D Library Model
<video src="3d_library_model_final.mp4" controls width="100%">
  Your browser does not support the video tag.
</video>

### Web Dashboard & Code
<video src="web_and_code_compressed.mp4" controls width="100%">
  Your browser does not support the video tag.
</video>

---

## How to Run

**Start backend services:**
```bash
bash scripts/start_all.sh
```

**Or start individually:**
```bash
# Terminal 1: Edge processor
cd edge && pip install -r requirements.txt && python processor.py

# Terminal 2: Dashboard
cd dashboard && pip install -r requirements.txt && python app.py

# Terminal 3: Open browser
open http://localhost:5000

# Unity: Open LibraryModel in Unity, press Play
```

## Hardware (Production)

| Component | Model | Purpose | Price |
|-----------|-------|---------|-------|
| Camera | OV5647 (RPi Cam v1) | Object classification | ₹350 |
| Radar | HLK-LD2410B (24GHz) | Presence + micro-motion | ₹400 |
| Compute | Raspberry Pi 4 (8GB) | All edge processing | ₹5,000 |
| Rail | V-slot + GT2 belt + Nema17 | Sensor movement | ₹1,300 |
| **Total** | | **2 rails + Pi + accessories** | **~₹11,500** |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Simulation | Unity 6000.3, C#, URP |
| Edge | Python 3.11, YOLOv8-nano, OpenCV |
| Messaging | MQTT (Eclipse Mosquitto) |
| Storage | InfluxDB 2.7 |
| Dashboard | Flask, SocketIO, Chart.js |

## Ghost Detection

```
EMPTY → [presence detected] → OCCUPIED
                                  ↓
                          no motion for 2 min
                                  ↓
                          SUSPECTED GHOST
                                  ↓
                          no motion for 5 min
                                  ↓
                          CONFIRMED GHOST → Alert sent
                                  ↓
                          [person returns] → OCCUPIED
```

Sensor fusion: `score = 0.6 × camera_confidence + 0.4 × radar_presence + 0.10 agreement_bonus`

## Team

**Team OverThinker**
- Kumar Satyam (22JE0507) — Team Leader

IIT (ISM) Dhanbad
