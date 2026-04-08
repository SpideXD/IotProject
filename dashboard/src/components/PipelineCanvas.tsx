import React, { useCallback, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  Edge,
  Node,
  NodeProps,
  Handle,
  Position,
  useNodesState,
  useEdgesState,
  MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { motion, AnimatePresence } from 'motion/react';
import { Box, Cpu, Cloud, Server, Activity, ArrowRight, Zap, Database, Shield, Wifi, MousePointer2 } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { OrbitControls, Environment } from '@react-three/drei';
import { UnityModel, RPiModel, EdgeModel, CloudModel } from './Models3D';

const CustomNode = ({ data, selected }: NodeProps) => {
  const Icon = data.icon as React.ElementType;
  
  return (
    <div className={`
      relative group rounded-xl border p-4 w-64 transition-all duration-300
      ${selected 
        ? 'bg-black/80 border-emerald-500/50 shadow-[0_0_30px_rgba(16,185,129,0.2)]' 
        : 'bg-black/40 border-white/10 hover:border-white/30 hover:bg-black/60 shadow-xl backdrop-blur-md'}
    `}>
      {/* Glow effect behind node */}
      <div className={`absolute inset-0 rounded-xl blur-xl -z-10 transition-opacity duration-300 ${selected ? 'opacity-100' : 'opacity-0 group-hover:opacity-50'}`} style={{ backgroundColor: data.color }} />
      
      <Handle type="target" position={Position.Left} className="w-2 h-4 rounded-sm bg-white/20 border-none" />
      
      <div className="flex items-start gap-4">
        <div className="w-16 h-16 rounded-lg overflow-hidden bg-black/50 border border-white/5 relative flex items-center justify-center pointer-events-none" style={{ boxShadow: `inset 0 0 20px ${data.color}20` }}>
          <Canvas camera={{ position: [0, 0, 4], fov: 45 }}>
            <ambientLight intensity={0.5} />
            <directionalLight position={[10, 10, 10]} intensity={1} />
            {data.modelType === 'unity' && <UnityModel />}
            {data.modelType === 'rpi' && <RPiModel />}
            {data.modelType === 'edge' && <EdgeModel />}
            {data.modelType === 'cloud' && <CloudModel />}
          </Canvas>
        </div>
        <div className="flex flex-col">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/50">{data.category}</span>
          <span className="font-display text-lg font-medium text-white mt-0.5">{data.label}</span>
        </div>
      </div>
      
      <div className="mt-4 pt-4 border-t border-white/10 flex justify-between items-center">
        <div className="flex items-center gap-1.5">
          <div className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: data.statusColor || '#10b981' }} />
          <span className="font-mono text-[9px] uppercase tracking-wider text-white/40">{data.status}</span>
        </div>
        <span className="font-mono text-[10px] text-white/30">{data.metric}</span>
      </div>

      <Handle type="source" position={Position.Right} className="w-2 h-4 rounded-sm bg-white/20 border-none" />
    </div>
  );
};

const nodeTypes = {
  custom: CustomNode,
};

const initialNodes: Node[] = [
  {
    id: 'unity',
    type: 'custom',
    position: { x: 50, y: 200 },
    data: { 
      label: 'Unity 3D Engine', 
      category: 'Simulation', 
      icon: Box, 
      modelType: 'unity',
      color: '#3b82f6', // blue
      status: 'Rendering',
      metric: '144 FPS',
      description: 'High-fidelity 3D digital twin of the physical space. Simulates human movement, thermal signatures, and environmental factors.',
      specs: [
        { label: 'Engine', value: 'Unity 2023.2 HDRP' },
        { label: 'Agents', value: '42 Active NavMesh' },
        { label: 'Resolution', value: '4K Native' }
      ]
    },
  },
  {
    id: 'rpi',
    type: 'custom',
    position: { x: 400, y: 200 },
    data: { 
      label: 'RPi Simulator', 
      category: 'Hardware Mock', 
      icon: Cpu, 
      modelType: 'rpi',
      color: '#f97316', // orange
      status: 'Transmitting',
      metric: '12ms Latency',
      description: 'Virtualizes Raspberry Pi 4 hardware to generate synthetic sensor data (mmWave, PIR, Thermal) based on the Unity simulation.',
      specs: [
        { label: 'Architecture', value: 'ARM Cortex-A72 (Sim)' },
        { label: 'Sensors', value: 'mmWave, Thermal, CO2' },
        { label: 'Protocol', value: 'MQTT over WSS' }
      ]
    },
  },
  {
    id: 'edge',
    type: 'custom',
    position: { x: 750, y: 200 },
    data: { 
      label: 'Edge Processing', 
      category: 'AI Inference', 
      icon: Server, 
      modelType: 'edge',
      color: '#a855f7', // purple
      status: 'Inferencing',
      metric: '45ms / frame',
      description: 'Local edge node running YOLOv8 for spatial detection and sensor fusion algorithms to combine mmWave and vision data.',
      specs: [
        { label: 'Model', value: 'YOLOv8-Nano + Custom' },
        { label: 'Accelerator', value: 'TensorRT / CUDA' },
        { label: 'Confidence', value: '94.2% Avg' }
      ]
    },
  },
  {
    id: 'cloud',
    type: 'custom',
    position: { x: 1100, y: 200 },
    data: { 
      label: 'Cloud Telemetry', 
      category: 'Dashboard', 
      icon: Cloud, 
      modelType: 'cloud',
      color: '#10b981', // emerald
      status: 'Synced',
      metric: '99.99% Uptime',
      description: 'Centralized cloud dashboard for real-time visualization, historical analytics, and predictive HVAC optimization.',
      specs: [
        { label: 'Database', value: 'Time-Series DB' },
        { label: 'Update Rate', value: '1Hz WebSocket' },
        { label: 'Clients', value: '12 Active' }
      ]
    },
  },
];

const initialEdges: Edge[] = [
  { 
    id: 'e1-2', 
    source: 'unity', 
    target: 'rpi', 
    animated: true, 
    style: { stroke: '#3b82f6', strokeWidth: 2, opacity: 0.5 },
    markerEnd: { type: MarkerType.ArrowClosed, color: '#3b82f6' }
  },
  { 
    id: 'e2-3', 
    source: 'rpi', 
    target: 'edge', 
    animated: true, 
    style: { stroke: '#f97316', strokeWidth: 2, opacity: 0.5 },
    markerEnd: { type: MarkerType.ArrowClosed, color: '#f97316' }
  },
  { 
    id: 'e3-4', 
    source: 'edge', 
    target: 'cloud', 
    animated: true, 
    style: { stroke: '#a855f7', strokeWidth: 2, opacity: 0.5 },
    markerEnd: { type: MarkerType.ArrowClosed, color: '#a855f7' }
  },
];

export default function PipelineCanvas() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);

  const onNodeClick = useCallback((event: React.MouseEvent, node: Node) => {
    setSelectedNode(node);
  }, []);

  const onPaneClick = useCallback(() => {
    setSelectedNode(null);
  }, []);

  return (
    <div className="absolute inset-0 bg-[#050505] overflow-hidden">
      {/* React Flow Canvas */}
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        className="bg-transparent"
        minZoom={0.5}
        maxZoom={1.5}
      >
        <Background color="#ffffff" gap={24} size={1} opacity={0.05} />
        <Controls className="bg-black/50 border border-white/10 fill-white !text-white rounded-lg overflow-hidden backdrop-blur-md" showInteractive={false} />
      </ReactFlow>

      {/* Overlay Details Panel */}
      <AnimatePresence>
        {selectedNode && (
          <motion.div
            initial={{ x: '100%', opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: '100%', opacity: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="absolute top-0 right-0 bottom-0 w-96 bg-black/80 backdrop-blur-2xl border-l border-white/10 p-6 flex flex-col z-50 shadow-2xl"
          >
            <button 
              onClick={() => setSelectedNode(null)}
              className="absolute top-6 right-6 w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors text-white/50 z-50"
            >
              ✕
            </button>

            {/* 3D Model Viewer */}
            <div className="h-48 w-full relative mb-6 rounded-xl overflow-hidden bg-gradient-to-b from-white/5 to-transparent border border-white/10 mt-12 shrink-0">
              <Canvas camera={{ position: [0, 0, 5], fov: 45 }}>
                <ambientLight intensity={0.5} />
                <directionalLight position={[10, 10, 10]} intensity={1} />
                <Environment preset="city" />
                <OrbitControls enableZoom={false} autoRotate autoRotateSpeed={2} />
                {selectedNode.data.modelType === 'unity' && <UnityModel />}
                {selectedNode.data.modelType === 'rpi' && <RPiModel />}
                {selectedNode.data.modelType === 'edge' && <EdgeModel />}
                {selectedNode.data.modelType === 'cloud' && <CloudModel />}
              </Canvas>
              <div className="absolute bottom-2 right-2 flex items-center gap-1 bg-black/50 px-2 py-1 rounded text-[8px] font-mono text-white/50 backdrop-blur-md">
                <MousePointer2 className="w-3 h-3" /> INTERACTIVE 3D
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="p-3 rounded-xl" style={{ backgroundColor: `${selectedNode.data.color}20`, color: selectedNode.data.color as string }}>
                {selectedNode.data.icon && React.createElement(selectedNode.data.icon as React.ElementType, { className: "w-6 h-6" })}
              </div>
              <div>
                <div className="font-mono text-xs uppercase tracking-widest text-white/40 mb-1">{selectedNode.data.category as string}</div>
                <h2 className="font-display text-2xl font-medium text-white">{selectedNode.data.label as string}</h2>
              </div>
            </div>

            <div className="mt-6 space-y-6 overflow-y-auto pr-2 custom-scrollbar">
              <div>
                <h3 className="font-mono text-[10px] uppercase tracking-widest text-white/30 mb-3 flex items-center gap-2">
                  <Activity className="w-3 h-3" /> System Status
                </h3>
                <div className="bg-white/5 border border-white/5 rounded-lg p-4 flex justify-between items-center">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: selectedNode.data.statusColor as string || '#10b981' }} />
                    <span className="text-sm text-white/80">{selectedNode.data.status as string}</span>
                  </div>
                  <span className="font-mono text-xs text-white/50">{selectedNode.data.metric as string}</span>
                </div>
              </div>

              <div>
                <h3 className="font-mono text-[10px] uppercase tracking-widest text-white/30 mb-3 flex items-center gap-2">
                  <Database className="w-3 h-3" /> Description
                </h3>
                <p className="text-sm text-white/60 leading-relaxed">
                  {selectedNode.data.description as string}
                </p>
              </div>

              <div>
                <h3 className="font-mono text-[10px] uppercase tracking-widest text-white/30 mb-3 flex items-center gap-2">
                  <Zap className="w-3 h-3" /> Specifications
                </h3>
                <div className="space-y-2">
                  {(selectedNode.data.specs as any[]).map((spec, i) => (
                    <div key={i} className="flex justify-between items-center py-2 border-b border-white/5 last:border-0">
                      <span className="text-xs text-white/40">{spec.label}</span>
                      <span className="font-mono text-xs text-white/80">{spec.value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <div className="mt-auto pt-6 border-t border-white/10">
              <button className="w-full py-3 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-sm font-medium transition-colors flex items-center justify-center gap-2">
                <Shield className="w-4 h-4 text-white/50" />
                View Detailed Logs
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
