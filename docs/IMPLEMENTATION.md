# Liberty Twin - Implementation Guide

## Quick Start

This guide walks through implementing the Liberty Twin system step-by-step.

---

## Phase 1: Unity Simulation Setup

### Step 1: Project Structure

The Unity project is located in `/Users/agentswarm/Desktop/IotProject/LibraryModel/`

Key scripts in `Assets/Scripts/`:

| Script | Purpose |
|--------|---------|
| `DashboardBridge.cs` | HTTP client sending frames + detections to RPi Simulator |
| `YoloCapture.cs` | Generates ground truth bounding boxes from 3D scene |
| `RailSensorController.cs` | Manages 7 rail positions, sequential sweep |
| `SimStudent.cs` | Student behavior (enter, sit, study, leave bag) |
| `LibrarySimManager.cs` | Overall scene management |

### Step 2: Core Components

**RailSensorController** - Manages sensor rails:
- 7 rail positions (Back: Z1-Z4, Front: Z5-Z7)
- Sequential sweep through zones
- Collects data from 4 seats per zone
- Publishes telemetry via DashboardBridge

**YoloCapture** - Ground truth detection:
- Gets exact bounding boxes from 3D scene objects
- Exposes `latestDetections` with perfect accuracy
- Detection classes: person, bag, laptop, book, cup, phone, backpack

**DashboardBridge** - HTTP communication:
- Sends to `http://localhost:5001/api/camera` (RPi Simulator)
- Sends to `http://localhost:5002/api/telemetry` (Edge - legacy)
- Includes frame (base64) + detections JSON

**SimStudent** - Behavior simulation:
- Enters library, walks to seat
- Sits and studies (random duration)
- Stands up, leaves bag (ghost)
- Returns later or leaves with bag

### Step 3: Running Unity

1. Open Unity Hub
2. Open project: `/Users/agentswarm/Desktop/IotProject/LibraryModel/`
3. Open scene: `Assets/Scenes/StudyHall.unity`
4. Press **Play**

---

## Phase 2: RPi Simulator (Per-Room Processor)

### Step 1: Environment Setup

```bash
cd /Users/agentswarm/Desktop/IotProject/edge/rpi_simulator
source ../../venv/bin/activate
pip install flask paho-mqtt requests numpy opencv-python
```

### Step 2: Running RPi Simulator

```bash
cd /Users/agentswarm/Desktop/IotProject/edge/rpi_simulator
python main.py
```

Output:
```
============================================================
  RPi Simulator - Privacy-Preserving Edge Processor
============================================================
  Room ID: room_1
  Edge URL: http://localhost:5002
  HTTP API: http://0.0.0.0:5001
============================================================
```

### Step 3: Key Components

**http_server.py** - Flask HTTP server:
- `POST /api/camera` - Receives frames + detections
- `POST /api/telemetry` - Receives radar telemetry
- `GET /api/status` - Processing status

**room_processor.py** - RoomProcessor class:
- `process_camera_frame()` - Maps detections to seat occupancy
- `process_telemetry()` - Caches radar data
- `_send_occupancy_to_edge()` - POST to Edge at :5002

### Step 4: Configuration

In `rpi_simulator/config.py`:
```python
RPI_HTTP_PORT = 5001
EDGE_PROCESSOR_URL = "http://localhost:5002"
SEND_DELTAS_ONLY = True
MIN_OCCUPANCY_CONFIDENCE = 0.35
```

---

## Phase 3: Edge Processor (Central Aggregator)

### Step 1: Environment Setup

```bash
cd /Users/agentswarm/Desktop/IotProject/edge
source ../venv/bin/activate
pip install flask paho-mqtt influxdb-client requests
```

### Step 2: Running Edge Processor

```bash
cd /Users/agentswarm/Desktop/IotProject/edge
python processor.py
```

Output:
```
============================================================
  LIBERTY TWIN - Edge Processor (Aggregator)
============================================================
  MQTT:     CONNECTED
  InfluxDB: CONNECTED
  HTTP API: http://0.0.0.0:5002
  Seats:    28 across 7 zones
  Mode:     RPi receives pre-processed occupancy data
============================================================
```

### Step 3: Key Components

**processor.py** - Main edge service:
- `process_occupancy_from_rpi()` - Receives pre-processed occupancy
- `process_telemetry()` - Legacy telemetry handling
- Ghost detection across all rooms
- MQTT publishing to dashboard

**ghost_detector.py** - Ghost detection FSM:
- 4 states: empty, occupied, suspected_ghost, confirmed_ghost
- Tracks dwell_time, time_since_motion
- Emits alerts on state transitions

### Step 4: API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/occupancy` | POST | Receive RPi occupancy data |
| `/api/seats` | GET | All seat states |
| `/api/rooms` | GET | Active rooms |
| `/api/analytics/utilization` | GET | Zone analytics |
| `/api/reservation/{seat_id}` | POST/DELETE | Seat reservation |

---

## Phase 4: Dashboard

### Step 1: Start Dashboard Backend

```bash
cd /Users/agentswarm/Desktop/IotProject/dashboard
flask run --port 5000
```

### Step 2: Start Dashboard Frontend

```bash
cd /Users/agentswarm/Desktop/IotProject/dashboard-frontend
npm install
npm run dev
```

Dashboard available at: **http://localhost:3000**

### Step 3: Features

- **Zone Grid**: 28 seats color-coded by state
- **Ghost Alerts**: Real-time notifications
- **Occupancy Charts**: Historical visualization
- **Room Selector**: Multi-room support
- **Reservation System**: Book seats with TTL

---

## Phase 5: Integration & Testing

### Step 1: Start Infrastructure

```bash
cd /Users/agentswarm/Desktop/IotProject
docker-compose up -d
```

### Step 2: Start Services in Order

1. **Start Edge Processor** (port 5002)
   ```bash
   cd edge && python processor.py
   ```

2. **Start RPi Simulator** (port 5001)
   ```bash
   cd edge/rpi_simulator && python main.py
   ```

3. **Start Dashboard**
   ```bash
   cd dashboard && flask run --port 5000 &
   cd dashboard-frontend && npm run dev
   ```

4. **Run Unity Scene**
   - Open Unity Editor
   - Open `StudyHall.unity`
   - Press Play

### Step 3: Verify Data Flow

Check RPi Simulator logs:
```
Camera frame received from Unity (Rail_Back_001)
Ground truth detections: 2 objects
Mapped to 2 seats
Sent occupancy to Edge: 2 seats
```

Check Edge logs:
```
Occupancy from rpi_simulator [room_1]: 28 seats, 5 occupied
Published state for 28 seats to MQTT
```

Check Dashboard:
- Open http://localhost:3000
- Verify seats update in real-time

---

## Phase 6: Testing Scenarios

### Scenario 1: Ghost Creation

1. Unity: Student enters, sits at S1
2. Dashboard: S1 turns red
3. Unity: Student leaves bag, walks away
4. After 2 min: S1 turns yellow (suspected)
5. After 5 min: S1 turns purple (ghost)

### Scenario 2: Person Returns

1. S1 is purple (ghost state)
2. Student returns to seat
3. Unity: Motion detected
4. Dashboard: S1 immediately turns red
5. Alert: "Person returned to ghost seat"

---

## Troubleshooting

### Unity cannot connect to RPi Simulator

**Symptoms:** No frames received at port 5001

**Solutions:**
1. Verify RPi Simulator is running on port 5001
2. Check `DashboardBridge.cs` URL: `http://localhost:5001`
3. Check firewall settings

### Edge not receiving occupancy

**Symptoms:** RPi Simulator sends but Edge shows no data

**Solutions:**
1. Check Edge is running on port 5002
2. Verify RPi `EDGE_PROCESSOR_URL` in config
3. Check Edge logs for `/api/occupancy` requests

### Dashboard not updating

**Symptoms:** Seats stay gray/empty

**Solutions:**
1. Check MQTT connection (mosquitto logs)
2. Verify Edge is publishing to MQTT
3. Check browser console for WebSocket errors

---

## Next Steps

1. **Add more rooms** - Deploy more RPi Simulators
2. **Train YOLO** - Generate training data with YoloCapture
3. **Real hardware** - Replace simulation with RPi + camera + radar
4. **Mobile app** - Build student-facing mobile app

---

## Demo Script

### 5-Minute Demo Flow

**Slide 1: Introduction (30s)**
"Liberty Twin monitors library occupancy with privacy-preserving edge processing."

**Slide 2: Live Dashboard (30s)**
- Show empty library (all green)
- Point out 28 seats in 7 zones

**Demo 1: Student Enters (60s)**
1. Unity: Spawn student at S1
2. Dashboard: S1 turns red
3. Explain: RPi receives frames, runs YOLO, sends TEXT only

**Demo 2: Ghost Creation (90s)**
1. Student leaves bag
2. Wait 2 min → S1 turns yellow
3. Wait 5 min → S1 turns purple
4. Alert notification appears

**Demo 3: Person Returns (60s)**
1. Student returns to seat
2. S1 immediately turns red
3. Alert: "Person returned"

**Wrap-up (30s)**
- Privacy: Raw images never leave RPi
- Multi-room: Central aggregation
- Impact: Reduces seat hunting time
