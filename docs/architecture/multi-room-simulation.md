# Liberty Twin - Multi-Room Simulation Architecture

## Overview

This document describes the architecture for simulating multiple library rooms using a single Unity instance combined with mock data for prototype development.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LIBERTY TWIN DATA FLOW                              │
└─────────────────────────────────────────────────────────────────────────────┘

                        ┌─────────────────────────────────────────────────────┐
                        │              MULTI-ROOM PROTOTYPE                   │
                        │                                                      │
                        │   ┌───────────────┐     ┌─────────────────────┐    │
                        │   │ Unity Engine  │────▶│  DashboardBridge   │    │
                        │   │ (1 Instance)  │     │  (sends to :5001)  │    │
                        │   └───────────────┘     └─────────┬───────────┘    │
                        │                                    │                 │
                        │   ┌──────────────────────────────▼───────────┐    │
                        │   │         RPi Simulator (:5001)             │    │
                        │   │  - Receives sensor data from Unity        │    │
                        │   │  - Runs YOLOv8 inference on camera frames  │    │
                        │   │  - Sensor fusion (vision + mmWave radar)  │    │
                        │   │  - Ghost detection FSM                    │    │
                        │   └──────────────────────┬────────────────────┘    │
                        │                          │ MQTT                     │
                        └──────────────────────────┼──────────────────────────┘
                                                 │
                         ┌────────────────────────┼────────────────────────┐
                         │                        ▼                         │
                         │              ┌──────────────────┐                │
                         │              │ Edge Processor   │                │
                         │              │    (:5002)       │                │
                         │              │                  │                │
                         │              │ - Aggregates all │                │
                         │              │   room data      │                │
                         │              │ - Cross-room    │                │
                         │              │   correlation    │                │
                         │              └────────┬─────────┘                │
                         │                       │                           │
                         │                       ▼                           │
                         │   ┌─────────────────────────────────────────┐    │
                         │   │         multi_rpi_simulator.py            │    │
                         │   │                                          │    │
                         │   │  Simulates 6 additional rooms:          │    │
                         │   │  library_z1, library_z2, ..., library_z7 │    │
                         │   │                                          │    │
                         │   │  - Probabilistic occupancy patterns      │    │
                         │   │  - Time-based ghost FSM                   │    │
                         │   │  - Direct MQTT to Edge                    │    │
                         │   └─────────────────────────────────────────┘    │
                         │                                                       │
                         │                                                       │
                         │   ┌─────────────────────────────────────────┐    │
                         │   │         Dashboard (:3000)                  │    │
                         │   │                                          │    │
                         │   │  - Shows all 7 zones (Z1-Z7)            │    │
                         │   │  - Real + simulated data aggregated      │    │
                         │   └─────────────────────────────────────────┘    │
                         │                                                       │
                         └───────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                       PRODUCTION ARCHITECTURE                                 │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │ Unity Room 1 │────▶│ RPi Room 1   │────▶│              │
    └──────────────┘     └──────────────┘     │              │
    ┌──────────────┐     ┌──────────────┐     │              │
    │ Unity Room 2 │────▶│ RPi Room 2   │────▶│   Edge       │────▶ Dashboard
    └──────────────┘     └──────────────┘     │   Processor  │
    ┌──────────────┐     ┌──────────────┐     │   (:5002)    │
    │ Unity Room 3 │────▶│ RPi Room 3   │────▶│              │
    └──────────────┘     └──────────────┘     └──────────────┘
         ...                  ...
    ┌──────────────┐     ┌──────────────┐
    │ Unity Room 7 │────▶│ RPi Room 7   │
    └──────────────┘     └──────────────┘
```

## Data Sources Comparison

| Aspect | Unity + RPi (:5001) | multi_rpi_simulator.py |
|--------|---------------------|------------------------|
| **Purpose** | Real sensor simulation | Multi-room mock data |
| **Data Source** | YOLOv8 on camera frames | Probabilistic generation |
| **Input** | RenderTexture from Unity cameras | Random seed + patterns |
| **Sensor Fusion** | Vision + mmWave radar (simulated) | None |
| **Confidence** | Real inference confidence (0.5-0.99) | Fixed 0.95 |
| **Ghost Detection** | Image differencing + FSM | Time-based FSM only |
| **YOLO BBoxes** | Actual bounding boxes | Not included |
| **Processing** | ~100-200ms per frame | Instant |
| **RPi Source ID** | `library_z1` through `library_z7` | Same format |

## Room ID Mapping

Both sources use the same room ID format to publish to Edge:

| Zone | Room ID | Seats |
|------|---------|-------|
| Z1 | library_z1 | S1-S4 |
| Z2 | library_z2 | S5-S8 |
| Z3 | library_z3 | S9-S12 |
| Z4 | library_z4 | S13-S16 |
| Z5 | library_z5 | S17-S20 |
| Z6 | library_z6 | S21-S24 |
| Z7 | library_z7 | S25-S28 |

## Data Flow Details

### Path 1: Unity → RPi Simulator → Edge

```
1. Unity renders 3D scene
2. RailSensorController captures camera RenderTexture
3. DashboardBridge POSTs to :5001/api/v1/sensor/capture
4. RPi Simulator receives JSON:
   {
     "sensor": "RailSensor_Z1",
     "zone": "Z1",
     "frame": "<base64 JPEG>",
     "occupancy": { "S1": {...}, ... }
   }
5. RPi runs YOLOv8 inference on frame
6. Sensor fusion combines vision + simulated radar
7. GhostDetector applies image differencing + FSM
8. Result published via MQTT to liberty_twin/sensor/Z1/occupancy
9. Edge receives, processes, and aggregates
```

### Path 2: multi_rpi_simulator → Edge

```
1. multi_rpi_simulator runs independently
2. For each zone (Z1-Z7), generates:
   - Random occupancy based on zone pattern
   - Time-based ghost FSM updates
3. Publishes via MQTT to liberty_twin/sensor/{zone}/occupancy
4. Edge receives, processes, and aggregates
```

## Key Difference: How Ghost Detection Works

### RPi Simulator (with YOLO)
```python
# Uses image differencing between consecutive frames
diff = cv2.absdiff(current_frame, previous_frame)
if diff.mean() > THRESHOLD:
    # Motion detected
    ghost_state = "occupied"
else:
    # No motion - apply time thresholds
    if time_since_motion > CONFIRM_PERIOD:
        ghost_state = "confirmed_ghost"
    elif time_since_motion > GRACE_PERIOD:
        ghost_state = "suspected_ghost"
```

### multi_rpi_simulator
```python
# Simple probabilistic model
if random.random() < occupied_prob:
    ghost_state = "occupied"
elif random.random() < ghost_prob:
    ghost_state = "suspected_ghost"  # No actual time tracking
else:
    ghost_state = "empty"
```

## Managing the Simulation

### Stop multi_rpi_simulator (when running Unity)
```bash
pkill -f multi_rpi_simulator
```

### Check which sources are feeding Edge
```bash
curl -s http://localhost:5002/api/status | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('RPi Sources:', d['stats']['rpi_sources'])
print('Messages/min:', d['stats']['messages_per_minute'])
"
```

### View MQTT traffic
```bash
# Subscribe to all Liberty Twin topics
mosquitto_sub -t "liberty_twin/#" -v
```

## Limitations of multi_rpi_simulator

1. **No Real Sensor Data**: Uses probability instead of actual YOLO/radar
2. **Independent Ghost Detection**: Each zone's ghost detection is independent, not correlated across rooms
3. **Fixed Patterns**: Zone patterns (occupied_prob, ghost_prob) are static
4. **No Camera Frames**: Cannot test vision-based detection edge cases
5. **Same Room ID Conflict**: Cannot distinguish from Unity data in Edge

## Recommendations for Prototype

1. **Use multi_rpi_simulator for**:
   - UI/UX dashboard development
   - Layout and visualization testing
   - API integration testing
   - Basic functionality demos

2. **Use Unity + RPi for**:
   - Accurate ghost detection testing
   - Sensor fusion validation
   - Real-world scenario testing
   - Performance profiling

## Future Enhancements

1. Add source tagging to distinguish Unity vs simulator data
2. Implement scene change detection to pause simulator when Unity is active
3. Add option to run multi_rpi_simulator for specific zones only
4. Create visual indicator in dashboard showing data source per zone
