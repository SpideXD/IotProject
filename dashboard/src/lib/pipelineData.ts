import { Activity, Database, Zap, Cpu, Network, Server, Cloud } from 'lucide-react';

export interface PipelineNode {
  id: string;
  title: string;
  category: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  status: string;
  metric: string;
  description: string;
  specs: Array<{ label: string; value: string }>;
}

export const pipelineData: PipelineNode[] = [
  {
    id: 'unity',
    title: 'Unity 3D',
    category: 'Simulation',
    icon: Activity,
    color: '#22c55e',
    status: 'Running',
    metric: '60 FPS',
    description: '3D digital twin simulation of the library environment. Captures camera frames and radar telemetry from virtual sensors mounted on rail system.',
    specs: [
      { label: 'Sensors', value: 'Camera + Radar' },
      { label: 'Zones', value: '7 Active' },
      { label: 'Frame Rate', value: '60 FPS' },
    ],
  },
  {
    id: 'rpi',
    title: 'RPi Simulator',
    category: 'Edge Node',
    icon: Cpu,
    color: '#3b82f6',
    status: 'Processing',
    metric: '5001',
    description: 'Local edge processing node simulating Raspberry Pi hardware. Runs YOLO inference for object detection and applies ghost detection FSM for chair/bag classification.',
    specs: [
      { label: 'YOLO Model', value: 'best.pt' },
      { label: 'Detection', value: 'person, bag, chair' },
      { label: 'Port', value: '5001' },
    ],
  },
  {
    id: 'edge',
    title: 'Edge Processor',
    category: 'Central Hub',
    icon: Network,
    color: '#a855f7',
    status: 'Active',
    metric: '5002',
    description: 'Central edge processor aggregating data from all RPi nodes. Performs sensor fusion, manages occupancy state, forwards data to cloud.',
    specs: [
      { label: 'Rooms', value: '1 Active' },
      { label: 'MQTT', value: 'Connected' },
      { label: 'Port', value: '5002' },
    ],
  },
  {
    id: 'cloud',
    title: 'Cloud Services',
    category: 'Cloud',
    icon: Cloud,
    color: '#06b6d4',
    status: 'Connected',
    metric: 'Connected',
    description: 'Cloud backend for data persistence, analytics, and dashboard visualization. Receives processed occupancy data via MQTT.',
    specs: [
      { label: 'MQTT Broker', value: '1883' },
      { label: 'InfluxDB', value: 'Writing' },
      { label: 'Dashboard', value: 'Port 3000' },
    ],
  },
];