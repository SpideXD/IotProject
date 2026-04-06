#!/bin/bash

set -e
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
echo "======================================"
echo "  LIBERTY TWIN - Starting Services"
echo "  Project: $PROJECT_DIR"
echo "======================================"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "\n${YELLOW}[1/4] Starting MQTT Broker (Mosquitto)...${NC}"
mkdir -p /tmp/mosquitto
if command -v mosquitto &> /dev/null; then
    mosquitto -c "$PROJECT_DIR/broker/mosquitto.conf" -d
    echo -e "${GREEN}  ✓ Mosquitto running on port 1883 (TCP) + 9001 (WebSocket)${NC}"
else
    echo -e "${RED}  ✗ Mosquitto not installed. Install: brew install mosquitto${NC}"
    echo -e "${YELLOW}  → System will fall back to HTTP mode${NC}"
fi

echo -e "\n${YELLOW}[2/4] Checking InfluxDB...${NC}"
if command -v influxd &> /dev/null; then
    if ! pgrep -x influxd > /dev/null; then
        influxd &
        sleep 2
    fi
    echo -e "${GREEN}  ✓ InfluxDB running on port 8086${NC}"
else
    echo -e "${RED}  ✗ InfluxDB not installed. Install: brew install influxdb${NC}"
    echo -e "${YELLOW}  → Historical data storage disabled${NC}"
fi

echo -e "\n${YELLOW}[3/4] Starting Edge Processor...${NC}"
cd "$PROJECT_DIR/edge"
pip3 install -r requirements.txt -q 2>/dev/null
python3 processor.py &
EDGE_PID=$!
echo -e "${GREEN}  ✓ Edge Processor running (PID: $EDGE_PID) on port 5001${NC}"

echo -e "\n${YELLOW}[4/4] Starting Dashboard...${NC}"
cd "$PROJECT_DIR/dashboard"
pip3 install -r requirements.txt -q 2>/dev/null
python3 app.py &
DASH_PID=$!
echo -e "${GREEN}  ✓ Dashboard running (PID: $DASH_PID) on port 5000${NC}"

echo -e "\n${GREEN}======================================"
echo "  All services started!"
echo "  Dashboard: http://localhost:5000"
echo "  Edge API:  http://localhost:5001"
echo "  MQTT:      localhost:1883"
echo "======================================"
echo -e "${NC}"
echo "Press Ctrl+C to stop all services"

trap "echo 'Stopping...'; kill $EDGE_PID $DASH_PID 2>/dev/null; exit 0" SIGINT SIGTERM
wait
