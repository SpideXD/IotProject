import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'motion/react';
import { X, Cpu, Terminal, Layers, Activity, Database, Zap, Network, Server, ShieldAlert, Radio, Gauge, ActivitySquare, Camera } from 'lucide-react';
import { pipelineData } from '../lib/pipelineData';

interface RPiMetrics {
  frame: string | null;
  detections: Array<{
    class_name: string;
    confidence: number;
    bbox: { x1: number; y1: number; x2: number; y2: number };
  }>;
  timestamp: number;
  sensorId: string | null;
  zone: string | null;
  hasFrame: boolean;
}

const useRPiMetrics = () => {
  const [metrics, setMetrics] = useState<RPiMetrics>({
    frame: null,
    detections: [],
    timestamp: 0,
    sensorId: null,
    zone: null,
    hasFrame: false,
  });

  const PROTOCOL = window.location.protocol === 'https:' ? 'https:' : 'http:';
  const HOST = window.location.hostname;
  const API_BASE = `${PROTOCOL}//${HOST}:5002`;

  useEffect(() => {
    const fetchRPiData = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/live-frame`);
        if (res.ok) {
          const data = await res.json();
          setMetrics({
            frame: data.frame || null,
            detections: data.detections || [],
            timestamp: data.timestamp || 0,
            sensorId: data.sensor_id || null,
            zone: data.zone || null,
            hasFrame: data.frame && data.frame.length > 0,
          });
        }
      } catch (err) {
        console.warn('Failed to fetch RPi metrics:', err);
      }
    };

    fetchRPiData();
    const interval = setInterval(fetchRPiData, 1000);
    return () => clearInterval(interval);
  }, []);

  return metrics;
};

interface EdgeMetrics {
  occupancyCount: number;
  mqttPublishes: number;
  seatsOccupied: number;
  seatsEmpty: number;
  seatsGhost: number;
  uptime: number;
  msgsPerSec: number;
  lastOccupancyCount: number;
  lastMqttPublishes: number;
  lastTimestamp: number;
}

const useEdgeMetrics = () => {
  const [metrics, setMetrics] = useState<EdgeMetrics>({
    occupancyCount: 0,
    mqttPublishes: 0,
    seatsOccupied: 0,
    seatsEmpty: 0,
    seatsGhost: 0,
    uptime: 0,
    msgsPerSec: 0,
    lastOccupancyCount: 0,
    lastMqttPublishes: 0,
    lastTimestamp: Date.now(),
  });

  const PROTOCOL = window.location.protocol === 'https:' ? 'https:' : 'http:';
  const HOST = window.location.hostname;
  const API_BASE = `${PROTOCOL}//${HOST}:5002`;

  const fetchMetrics = useCallback(async () => {
    try {
      const [statusRes, metricsRes] = await Promise.all([
        fetch(`${API_BASE}/api/status`),
        fetch(`${API_BASE}/metrics`),
      ]);

      const status = await statusRes.json();
      const metricsText = await metricsRes.text();

      const parseMetric = (text: string, name: string): number => {
        const match = text.match(new RegExp(`^${name}\\s+([\\d.]+)`, 'm'));
        return match ? parseFloat(match[1]) : 0;
      };

      const occupancyCount = parseMetric(metricsText, 'liberty_occupancy_count');
      const mqttPublishes = parseMetric(metricsText, 'liberty_mqtt_publishes');
      const seatsOccupied = parseMetric(metricsText, 'liberty_seats_occupied');
      const seatsEmpty = parseMetric(metricsText, 'liberty_seats_empty');
      const seatsGhost = parseMetric(metricsText, 'liberty_seats_suspected_ghost') +
                         parseMetric(metricsText, 'liberty_seats_confirmed_ghost');
      const uptime = status.stats?.uptime_seconds || 0;

      const now = Date.now();
      const timeDelta = (now - metrics.lastTimestamp) / 1000;
      const mqttDelta = mqttPublishes - metrics.lastMqttPublishes;
      const msgsPerSec = timeDelta > 0 ? Math.round(mqttDelta / timeDelta) : 0;

      setMetrics({
        occupancyCount,
        mqttPublishes,
        seatsOccupied,
        seatsEmpty,
        seatsGhost,
        uptime,
        msgsPerSec,
        lastOccupancyCount: metrics.occupancyCount,
        lastMqttPublishes: metrics.mqttPublishes,
        lastTimestamp: now,
      });
    } catch (err) {
      console.warn('Failed to fetch edge metrics:', err);
    }
  }, []);

  useEffect(() => {
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 1000);
    return () => clearInterval(interval);
  }, [fetchMetrics]);

  return metrics;
};

const BoundingBox = ({ color, label, delay }: { color: string, label: string, delay: number }) => (
  <motion.div
    className="absolute border-2 flex flex-col justify-start items-start overflow-hidden shadow-[0_0_15px_rgba(0,0,0,0.5)]"
    style={{ borderColor: color, backgroundColor: `${color}15` }}
    initial={{ left: '10%', top: '10%', width: '20%', height: '30%' }}
    animate={{
      left: [`${10 + Math.random()*40}%`, `${40 + Math.random()*20}%`, `${20 + Math.random()*30}%`],
      top: [`${10 + Math.random()*30}%`, `${30 + Math.random()*30}%`, `${15 + Math.random()*30}%`],
      width: [`${15 + Math.random()*15}%`, `${10 + Math.random()*10}%`, `${20 + Math.random()*15}%`],
      height: [`${25 + Math.random()*20}%`, `${35 + Math.random()*15}%`, `${20 + Math.random()*20}%`],
    }}
    transition={{ duration: 8 + Math.random()*4, repeat: Infinity, repeatType: 'mirror', ease: 'easeInOut', delay }}
  >
    <div className="text-[9px] font-mono px-1.5 py-0.5 text-black font-bold whitespace-nowrap" style={{ backgroundColor: color }}>
      {label} {(Math.random() * 10 + 85).toFixed(1)}%
    </div>
  </motion.div>
);

const NeuralNet = () => {
  const layers = [4, 8, 8, 3];
  const width = 100;
  const height = 100;
  const xStep = width / (layers.length + 1);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full overflow-visible" preserveAspectRatio="none">
      {/* Edges */}
      {layers.map((nodeCount, layerIdx) => {
        if (layerIdx === layers.length - 1) return null;
        const nextNodeCount = layers[layerIdx + 1];
        const currentX = xStep * (layerIdx + 1);
        const nextX = xStep * (layerIdx + 2);
        
        return Array.from({ length: nodeCount }).map((_, i) => {
          const currentY = (height / (nodeCount + 1)) * (i + 1);
          return Array.from({ length: nextNodeCount }).map((_, j) => {
            const nextY = (height / (nextNodeCount + 1)) * (j + 1);
            return (
              <motion.line
                key={`edge-${layerIdx}-${i}-${j}`}
                x1={currentX} y1={currentY} x2={nextX} y2={nextY}
                stroke="rgba(168, 85, 247, 0.3)"
                strokeWidth="0.5"
                initial={{ strokeDasharray: "2 2", strokeDashoffset: 0 }}
                animate={{ strokeDashoffset: -10 }}
                transition={{ duration: 1 + Math.random(), repeat: Infinity, ease: "linear" }}
              />
            );
          });
        });
      })}
      {/* Nodes */}
      {layers.map((nodeCount, layerIdx) => {
        const x = xStep * (layerIdx + 1);
        return Array.from({ length: nodeCount }).map((_, i) => {
          const y = (height / (nodeCount + 1)) * (i + 1);
          return (
            <motion.circle
              key={`node-${layerIdx}-${i}`}
              cx={x} cy={y} r="1.5"
              fill="#c084fc"
              animate={{ r: [1.5, 2.5, 1.5], opacity: [0.6, 1, 0.6] }}
              transition={{ duration: 1.5 + Math.random(), repeat: Infinity }}
            />
          );
        });
      })}
    </svg>
  );
};

const AILogs = () => {
  const [logs, setLogs] = useState<string[]>([]);
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      const newLog = `[${new Date().toISOString().split('T')[1].slice(0, -1)}] YOLOv8_NANO: Detected ${Math.floor(Math.random() * 3) + 1} objects. Conf: ${(Math.random() * 0.2 + 0.8).toFixed(2)}. Inf_Time: ${(Math.random() * 5 + 10).toFixed(1)}ms`;
      setLogs(prev => [...prev.slice(-15), newLog]);
    }, 800);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  return (
    <div className="font-mono text-[10px] text-emerald-400/70 flex flex-col gap-1 h-full overflow-y-auto pb-4">
      {logs.map((log, i) => (
        <div key={i}>{log}</div>
      ))}
      <div ref={logsEndRef} />
    </div>
  );
};

interface EdgeStatusData {
  seatStates: Record<string, string>;
  stats: {
    occupancy_count: number;
    mqtt_publishes: number;
    duplicates_skipped: number;
    ghost_alerts: number;
    influx_writes: number;
    uptime_seconds: number;
    rpi_sources: string[];
    state_counts: {
      occupied: number;
      empty: number;
      suspected_ghost: number;
      confirmed_ghost: number;
    };
  };
  zoneBreakdown: Record<string, { occupied: number; empty: number; suspected_ghost: number; confirmed_ghost: number }>;
}

const useEdgeStatus = () => {
  const [status, setStatus] = useState<EdgeStatusData | null>(null);

  const PROTOCOL = window.location.protocol === 'https:' ? 'https:' : 'http:';
  const HOST = window.location.hostname;
  const API_BASE = `${PROTOCOL}//${HOST}:5002`;

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status`);
        const data = await res.json();

        const seatStates = data.seat_states || {};
        const stats = data.stats || {};

        const zoneBreakdown: Record<string, { occupied: number; empty: number; suspected_ghost: number; confirmed_ghost: number }> = {};
        const zoneRanges: Record<string, [number, number]> = {
          Z1: [1, 4], Z2: [5, 8], Z3: [9, 12], Z4: [13, 16],
          Z5: [17, 20], Z6: [21, 24], Z7: [25, 28]
        };

        for (const [zone, [start, end]] of Object.entries(zoneRanges)) {
          zoneBreakdown[zone] = { occupied: 0, empty: 0, suspected_ghost: 0, confirmed_ghost: 0 };
          for (let i = start; i <= end; i++) {
            const seat = `S${i}`;
            const state = seatStates[seat] || 'empty';
            if (zoneBreakdown[zone][state as keyof typeof zoneBreakdown[string] !== undefined]) {
              zoneBreakdown[zone][state as keyof typeof zoneBreakdown[string]]++;
            }
          }
        }

        setStatus({
          seatStates,
          stats: {
            occupancy_count: stats.occupancy_count || 0,
            mqtt_publishes: stats.mqtt_publishes || 0,
            duplicates_skipped: stats.duplicates_skipped || 0,
            ghost_alerts: stats.ghost_alerts || 0,
            influx_writes: stats.influx_writes || 0,
            uptime_seconds: stats.uptime_seconds || 0,
            rpi_sources: stats.rpi_sources || [],
            state_counts: stats.state_counts || { occupied: 0, empty: 0, suspected_ghost: 0, confirmed_ghost: 0 }
          },
          zoneBreakdown
        });
      } catch (err) {
        console.warn('Failed to fetch edge status:', err);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, []);

  return status;
};

const EdgeDeepDiveView = ({ color }: { color: string }) => {
  const metrics = useEdgeMetrics();
  const status = useEdgeStatus();

  const uptimeMinutes = Math.floor((status?.stats.uptime_seconds || 0) / 60);
  const uptimeHours = Math.floor(uptimeMinutes / 60);

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      {/* Zone Grid - Left Side */}
      <div className="col-span-8 grid grid-cols-4 gap-4 content-start">
        <div className="col-span-4 mb-2">
          <h3 className="font-mono text-xs uppercase tracking-widest text-white/50 flex items-center gap-2">
            <Layers className="w-4 h-4" /> Zone Occupancy Overview
          </h3>
        </div>

        {status ? Object.entries(status.zoneBreakdown).map(([zone, counts]) => {
          const total = counts.occupied + counts.empty + counts.suspected_ghost + counts.confirmed_ghost;
          const occupancyPct = total > 0 ? Math.round((counts.occupied / total) * 100) : 0;
          const hasGhost = counts.suspected_ghost > 0 || counts.confirmed_ghost > 0;

          return (
            <div key={zone} className="bg-white/5 rounded-xl border border-white/10 p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="font-mono text-sm text-white">{zone}</span>
                <span className={`font-mono text-xs ${hasGhost ? 'text-yellow-400' : counts.occupied > 0 ? 'text-emerald-400' : 'text-white/40'}`}>
                  {counts.occupied}/{total} occupied
                </span>
              </div>

              {/* Seat mini-grid */}
              <div className="grid grid-cols-4 gap-1 mb-3">
                {['S1', 'S2', 'S3', 'S4'].map(seat => {
                  const seatNum = seat.slice(1);
                  const actualSeat = `S${(parseInt(zone.slice(1)) - 1) * 4 + parseInt(seatNum)}`;
                  const state = status.seatStates[actualSeat] || 'empty';
                  return (
                    <div key={seat} className={`h-6 rounded-sm flex items-center justify-center text-[8px] font-mono ${
                      state === 'occupied' ? 'bg-emerald-500/40 text-emerald-300' :
                      state === 'suspected_ghost' ? 'bg-yellow-500/40 text-yellow-300' :
                      state === 'confirmed_ghost' ? 'bg-purple-500/40 text-purple-300' :
                      'bg-white/5 text-white/30'
                    }`}>
                      {seatNum}
                    </div>
                  );
                })}
              </div>

              {/* Occupancy bar */}
              <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                <div
                  className={`h-full transition-all ${hasGhost ? 'bg-yellow-500' : 'bg-emerald-500'}`}
                  style={{ width: `${occupancyPct}%` }}
                />
              </div>
            </div>
          );
        }) : (
          <div className="col-span-4 flex items-center justify-center h-32">
            <span className="font-mono text-sm text-white/40">Loading zone data...</span>
          </div>
        )}
      </div>

      {/* Right Side - Stats */}
      <div className="col-span-4 flex flex-col gap-4">
        {/* System Status */}
        <div className="bg-white/5 rounded-2xl border border-white/10 p-5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 block mb-3">Edge Processor Status</span>
          <div className="flex items-center gap-2 mb-2">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="font-display text-xl text-emerald-400">Online</span>
          </div>
          <span className="font-mono text-xs text-white/50">
            Uptime: {uptimeHours > 0 ? `${uptimeHours}h ${uptimeMinutes % 60}m` : `${uptimeMinutes}m`}
          </span>
        </div>

        {/* Seat Summary */}
        <div className="bg-white/5 rounded-2xl border border-white/10 p-5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 block mb-3">Seat Summary</span>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="font-display text-3xl text-emerald-400">{metrics.seatsOccupied}</div>
              <div className="font-mono text-[10px] text-white/40">Occupied</div>
            </div>
            <div>
              <div className="font-display text-3xl text-white/60">{metrics.seatsEmpty}</div>
              <div className="font-mono text-[10px] text-white/40">Empty</div>
            </div>
            <div>
              <div className="font-display text-3xl text-yellow-400">{metrics.seatsGhost}</div>
              <div className="font-mono text-[10px] text-white/40">Ghosts</div>
            </div>
            <div>
              <div className="font-display text-3xl text-white">{metrics.occupancyCount.toLocaleString()}</div>
              <div className="font-mono text-[10px] text-white/40">Total Events</div>
            </div>
          </div>
        </div>

        {/* MQTT Bridge */}
        <div className="bg-white/5 rounded-2xl border border-white/10 p-5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 block mb-3">MQTT Bridge</span>
          <div className="flex items-center justify-between">
            <div>
              <div className="font-display text-2xl text-white">{metrics.msgsPerSec} <span className="text-sm text-emerald-400">msg/s</span></div>
              <div className="font-mono text-[10px] text-white/40">Throughput</div>
            </div>
            <ActivitySquare className="w-8 h-8 text-emerald-400" />
          </div>
          <div className="mt-3 pt-3 border-t border-white/10">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] text-white/40">Total Published</span>
              <span className="font-mono text-xs text-white">{metrics.mqttPublishes.toLocaleString()}</span>
            </div>
            <div className="flex items-center justify-between mt-1">
              <span className="font-mono text-[10px] text-white/40">Duplicates Skipped</span>
              <span className="font-mono text-xs text-white/60">{status?.stats.duplicates_skipped.toLocaleString() || 0}</span>
            </div>
          </div>
        </div>

        {/* Data Sources */}
        <div className="bg-white/5 rounded-2xl border border-white/10 p-5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 block mb-3">RPi Sources</span>
          <div className="flex flex-wrap gap-1">
            {status?.stats.rpi_sources.map(source => (
              <span key={source} className="font-mono text-[9px] px-2 py-1 bg-white/10 rounded text-white/60">
                {source.replace('library_', '')}
              </span>
            )) || <span className="font-mono text-xs text-white/40">Loading...</span>}
          </div>
        </div>

        {/* InfluxDB Status */}
        <div className="bg-white/5 rounded-2xl border border-white/10 p-5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 block mb-3">InfluxDB Telemetry</span>
          <div className="flex items-center justify-between">
            <div>
              <div className={`font-display text-2xl ${(status?.stats.influx_writes || 0) > 0 ? 'text-cyan-400' : 'text-white/40'}`}>
                {status?.stats.influx_writes.toLocaleString() || 0}
              </div>
              <div className="font-mono text-[10px] text-white/40">Points Written</div>
            </div>
            <Database className="w-8 h-8 text-cyan-400/50" />
          </div>
        </div>
      </div>
    </div>
  );
};

const Seat = ({ seatId, state }: { seatId: string, state: string }) => {
  const getStateColor = () => {
    switch (state) {
      case 'occupied': return 'bg-emerald-500';
      case 'suspected_ghost': return 'bg-yellow-500';
      case 'confirmed_ghost': return 'bg-purple-500';
      default: return 'bg-white/20';
    }
  };

  return (
    <div className="relative group">
      {/* Chair */}
      <div className={`w-6 h-6 rounded-full ${getStateColor()} flex items-center justify-center transition-colors ${
        state === 'occupied' ? 'shadow-[0_0_8px_rgba(16,185,129,0.6)]' : ''
      }`}>
        {state !== 'empty' && (
          <motion.div
            className="absolute inset-0 rounded-full bg-white/30"
            animate={{ scale: [1, 1.3, 1], opacity: [0.5, 0, 0.5] }}
            transition={{ duration: 2, repeat: Infinity }}
          />
        )}
      </div>
      {/* Seat label */}
      <div className="absolute -bottom-4 left-1/2 -translate-x-1/2 font-mono text-[8px] text-white/40">
        {seatId}
      </div>
      {/* Tooltip */}
      <div className="absolute bottom-8 left-1/2 -translate-x-1/2 px-2 py-1 bg-black/80 rounded text-[10px] text-white whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity z-10">
        {seatId}: {state}
      </div>
    </div>
  );
};

const Desk = ({ children }: { children: React.ReactNode }) => (
  <div className="w-16 h-12 bg-white/5 border border-white/10 rounded-lg flex items-center justify-center">
    {children}
  </div>
);

const ZoneView = ({ zoneName, seats, seatStates }: { zoneName: string, seats: string[], seatStates: Record<string, string> }) => {
  const seatState = seats.map(s => seatStates[s] || 'empty');
  const occupiedCount = seatState.filter(s => s === 'occupied').length;
  const ghostCount = seatState.filter(s => s === 'suspected_ghost' || s === 'confirmed_ghost').length;

  return (
    <div className="bg-white/5 rounded-xl border border-white/10 p-3">
      {/* Zone header */}
      <div className="flex items-center justify-between mb-3">
        <span className="font-mono text-xs text-white">{zoneName}</span>
        <span className={`font-mono text-[10px] ${ghostCount > 0 ? 'text-yellow-400' : occupiedCount > 0 ? 'text-emerald-400' : 'text-white/40'}`}>
          {occupiedCount}/{seats.length}
        </span>
      </div>

      {/* 2x2 desk layout: seats on left/right, desks in middle */}
      <div className="flex items-center justify-center gap-2">
        {/* Left column: seats vertically stacked */}
        <div className="flex flex-col gap-3">
          <Seat seatId={seats[0]} state={seatState[0]} />
          <div className="h-6 w-1 bg-white/10" />
          <Seat seatId={seats[2]} state={seatState[2]} />
        </div>

        {/* Middle: two desks vertically stacked */}
        <div className="flex flex-col gap-3">
          <div className="w-10 h-8 bg-amber-900/30 border border-amber-500/20 rounded flex items-center justify-center">
            <span className="font-mono text-[8px] text-amber-400/60">D</span>
          </div>
          <div className="w-10 h-8 bg-amber-900/30 border border-amber-500/20 rounded flex items-center justify-center">
            <span className="font-mono text-[8px] text-amber-400/60">D</span>
          </div>
        </div>

        {/* Right column: seats vertically stacked */}
        <div className="flex flex-col gap-3">
          <Seat seatId={seats[1]} state={seatState[1]} />
          <div className="h-6 w-1 bg-white/10" />
          <Seat seatId={seats[3]} state={seatState[3]} />
        </div>
      </div>
    </div>
  );
};

const UnityDeepDiveView = ({ color }: { color: string }) => {
  const status = useEdgeStatus();

  const zoneSeats: Record<string, string[]> = {
    Z1: ['S1', 'S2', 'S3', 'S4'],
    Z2: ['S5', 'S6', 'S7', 'S8'],
    Z3: ['S9', 'S10', 'S11', 'S12'],
    Z4: ['S13', 'S14', 'S15', 'S16'],
    Z5: ['S17', 'S18', 'S19', 'S20'],
    Z6: ['S21', 'S22', 'S23', 'S24'],
    Z7: ['S25', 'S26', 'S27', 'S28'],
  };

  const zoneOrder = ['Z1', 'Z2', 'Z3', 'Z4', 'Z5', 'Z6', 'Z7'];
  const seatStates = status?.seatStates || {};

  const totalOccupied = Object.values(seatStates).filter(s => s === 'occupied').length;
  const totalGhosts = Object.values(seatStates).filter(s => s === 'suspected_ghost' || s === 'confirmed_ghost').length;

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      {/* Top-down Floor Plan - Left Side */}
      <div className="col-span-8 bg-black/40 rounded-2xl border border-white/10 p-6 relative overflow-hidden">
        <div className="absolute top-4 left-4 z-10 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span className="font-mono text-[10px] text-white uppercase tracking-widest">Top-Down View</span>
        </div>

        {/* Grid of zones */}
        <div className="grid grid-cols-4 gap-4 mt-8">
          {zoneOrder.map(zone => (
            <ZoneView
              key={zone}
              zoneName={zone}
              seats={zoneSeats[zone]}
              seatStates={seatStates}
            />
          ))}
        </div>

        {/* Legend */}
        <div className="absolute bottom-4 left-4 flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-emerald-500" />
            <span className="font-mono text-[10px] text-white/60">Occupied</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-yellow-500" />
            <span className="font-mono text-[10px] text-white/60">Suspected Ghost</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-purple-500" />
            <span className="font-mono text-[10px] text-white/60">Confirmed Ghost</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full bg-white/20" />
            <span className="font-mono text-[10px] text-white/60">Empty</span>
          </div>
        </div>
      </div>

      {/* Stats Panel - Right Side */}
      <div className="col-span-4 flex flex-col gap-4">
        {/* Unity Status */}
        <div className="bg-white/5 rounded-2xl border border-white/10 p-5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 block mb-3">Unity Simulation</span>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-red-500" />
            <span className="font-display text-xl text-red-400">Offline</span>
          </div>
          <p className="font-mono text-[10px] text-white/40 mt-2">Camera feed unavailable - simulation not running</p>
        </div>

        {/* Live Stats */}
        <div className="bg-white/5 rounded-2xl border border-white/10 p-5">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 block mb-3">Occupancy Summary</span>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <div className="font-display text-3xl text-emerald-400">{totalOccupied}</div>
              <div className="font-mono text-[10px] text-white/40">Occupied</div>
            </div>
            <div>
              <div className="font-display text-3xl text-white/60">{28 - totalOccupied - totalGhosts}</div>
              <div className="font-mono text-[10px] text-white/40">Empty</div>
            </div>
            <div>
              <div className="font-display text-3xl text-yellow-400">{totalGhosts}</div>
              <div className="font-mono text-[10px] text-white/40">Ghosts</div>
            </div>
            <div>
              <div className="font-display text-3xl text-white">{28}</div>
              <div className="font-mono text-[10px] text-white/40">Total Seats</div>
            </div>
          </div>
        </div>

        {/* Zone Utilization */}
        <div className="bg-white/5 rounded-2xl border border-white/10 p-5 flex-1">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 block mb-3">Zone Utilization</span>
          <div className="space-y-2">
            {zoneOrder.map(zone => {
              const seats = zoneSeats[zone];
              const occupied = seats.filter(s => seatStates[s] === 'occupied').length;
              const pct = Math.round((occupied / 4) * 100);
              return (
                <div key={zone} className="flex items-center gap-2">
                  <span className="font-mono text-xs text-white/60 w-6">{zone}</span>
                  <div className="flex-1 h-2 bg-white/10 rounded-full overflow-hidden">
                    <motion.div
                      className={`h-full ${pct > 0 ? 'bg-emerald-500' : 'bg-white/10'}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${pct}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                  <span className="font-mono text-[10px] text-white/40 w-8 text-right">{pct}%</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};

const RPiSimulatorView = ({ color, metrics }: { color: string, metrics: ReturnType<typeof useEdgeMetrics> }) => {
  const rpiMetrics = useRPiMetrics();

  const detectionCount = rpiMetrics.detections.length;
  const personCount = rpiMetrics.detections.filter(d => d.class_name === 'person').length;
  const bagCount = rpiMetrics.detections.filter(d => d.class_name === 'bag').length;

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      {/* Live Camera Feed */}
      <div className="col-span-8 row-span-10 bg-black rounded-2xl border border-white/10 relative overflow-hidden">
        {/* Header overlay */}
        <div className="absolute top-4 left-4 z-20 flex items-center gap-2 bg-black/70 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10">
          <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
          <span className="font-mono text-[10px] text-white uppercase tracking-widest">
            Live Feed {rpiMetrics.zone ? `/ ${rpiMetrics.zone}` : ''} {rpiMetrics.sensorId ? `/ ${rpiMetrics.sensorId}` : ''}
          </span>
        </div>

        {/* Detection count overlay */}
        <div className="absolute top-4 right-4 z-20 flex items-center gap-4 bg-black/70 backdrop-blur-md px-3 py-1.5 rounded-lg border border-white/10">
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            <span className="font-mono text-[10px] text-emerald-400">{personCount} Person</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-purple-500" />
            <span className="font-mono text-[10px] text-purple-400">{bagCount} Bag</span>
          </div>
        </div>

        {/* Camera feed or placeholder */}
        {rpiMetrics.hasFrame && rpiMetrics.frame ? (
          <img
            src={`data:image/jpeg;base64,${rpiMetrics.frame}`}
            alt="Live camera feed"
            className="w-full h-full object-contain"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <div className="text-center">
              <div className="w-16 h-16 rounded-full border-2 border-dashed border-white/20 mx-auto mb-4 flex items-center justify-center">
                <Camera className="w-8 h-8 text-white/20" />
              </div>
              <p className="font-mono text-xs text-white/40">Waiting for camera feed...</p>
              <p className="font-mono text-[10px] text-white/20 mt-1">Connect Unity to start streaming</p>
            </div>
          </div>
        )}

        {/* Scanning line animation */}
        <motion.div
          className="absolute left-0 right-0 h-[2px] bg-emerald-500/50 shadow-[0_0_15px_rgba(16,185,129,0.5)] z-10"
          animate={{ top: ['0%', '100%', '0%'] }}
          transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
        />
      </div>

      {/* Detection List */}
      <div className="col-span-4 row-span-10 bg-white/5 rounded-2xl border border-white/10 p-4 flex flex-col overflow-hidden">
        <h3 className="font-mono text-xs text-white/50 uppercase tracking-widest mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4" /> Detections ({detectionCount})
        </h3>

        <div className="flex-1 overflow-y-auto flex flex-col gap-2">
          {rpiMetrics.detections.map((det, i) => (
            <div key={i} className="bg-black/40 rounded-lg p-3 border border-white/5">
              <div className="flex items-center justify-between mb-2">
                <span className={`font-mono text-xs px-2 py-0.5 rounded ${
                  det.class_name === 'person' ? 'bg-emerald-500/20 text-emerald-400' :
                  det.class_name === 'bag' ? 'bg-purple-500/20 text-purple-400' :
                  'bg-white/10 text-white/60'
                }`}>
                  {det.class_name.toUpperCase()}
                </span>
                <span className="font-mono text-[10px] text-white/40">
                  {det.confidence.toFixed(2)}
                </span>
              </div>
              <div className="font-mono text-[9px] text-white/30">
                bbox: [{det.bbox.x1.toFixed(0)}, {det.bbox.y1.toFixed(0)}] → [{det.bbox.x2.toFixed(0)}, {det.bbox.y2.toFixed(0)}]
              </div>
            </div>
          ))}

          {detectionCount === 0 && (
            <div className="flex-1 flex items-center justify-center">
              <p className="font-mono text-xs text-white/30">No detections</p>
            </div>
          )}
        </div>

        {/* Zone info */}
        {rpiMetrics.zone && (
          <div className="mt-4 pt-4 border-t border-white/10">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] text-white/40">Current Zone</span>
              <span className="font-mono text-xs text-white">{rpiMetrics.zone}</span>
            </div>
            {rpiMetrics.sensorId && (
              <div className="flex items-center justify-between mt-1">
                <span className="font-mono text-[10px] text-white/40">Sensor</span>
                <span className="font-mono text-xs text-white">{rpiMetrics.sensorId}</span>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Bottom stats row */}
      <div className="col-span-12 row-span-2 grid grid-cols-4 gap-4">
        <div className="bg-white/5 rounded-xl border border-white/10 p-4 flex items-center justify-between">
          <div>
            <span className="font-mono text-[10px] text-white/40 uppercase">Camera Feed</span>
            <div className="font-display text-lg text-white mt-1">{rpiMetrics.hasFrame ? 'Active' : 'Offline'}</div>
          </div>
          <div className={`w-3 h-3 rounded-full ${rpiMetrics.hasFrame ? 'bg-emerald-500 animate-pulse' : 'bg-white/20'}`} />
        </div>
        <div className="bg-white/5 rounded-xl border border-white/10 p-4 flex items-center justify-between">
          <div>
            <span className="font-mono text-[10px] text-white/40 uppercase">YOLO Inferences</span>
            <div className="font-display text-lg text-white mt-1">{personCount + bagCount}</div>
          </div>
          <Cpu className="w-6 h-6 text-orange-400" />
        </div>
        <div className="bg-white/5 rounded-xl border border-white/10 p-4 flex items-center justify-between">
          <div>
            <span className="font-mono text-[10px] text-white/40 uppercase">MQTT Throughput</span>
            <div className="font-display text-lg text-white mt-1">{metrics.msgsPerSec} msg/s</div>
          </div>
          <Zap className="w-6 h-6 text-emerald-400" />
        </div>
        <div className="bg-white/5 rounded-xl border border-white/10 p-4 flex items-center justify-between">
          <div>
            <span className="font-mono text-[10px] text-white/40 uppercase">Processing</span>
            <div className="font-display text-lg text-white mt-1">~{metrics.msgsPerSec > 0 ? Math.round(1000 / metrics.msgsPerSec) : 0}ms</div>
          </div>
          <Gauge className="w-6 h-6 text-blue-400" />
        </div>
      </div>
    </div>
  );
};



const CloudTelemetryView = ({ color, metrics }: { color: string, metrics: ReturnType<typeof useEdgeMetrics> }) => {
  const uptimeMinutes = Math.floor(metrics.uptime / 60);
  const uptimeHours = Math.floor(uptimeMinutes / 60);

  return (
    <div className="grid grid-cols-12 gap-6 h-full">
      <div className="col-span-6 bg-black/40 rounded-2xl border border-white/10 p-6 flex flex-col items-center justify-center relative overflow-hidden">
        <motion.div
          className="w-64 h-64 rounded-full border border-cyan-500/30 border-dashed flex items-center justify-center"
          animate={{ rotate: 360 }}
          transition={{ duration: 20, repeat: Infinity, ease: 'linear' }}
        >
          <motion.div
            className="w-48 h-48 rounded-full border border-cyan-500/50 flex items-center justify-center"
            animate={{ rotate: -360 }}
            transition={{ duration: 15, repeat: Infinity, ease: 'linear' }}
          >
            <div className="w-32 h-32 rounded-full bg-cyan-500/20 shadow-[0_0_50px_rgba(6,182,212,0.5)] flex items-center justify-center backdrop-blur-md">
              <Network className="w-12 h-12 text-cyan-400" />
            </div>
          </motion.div>
        </motion.div>
      </div>
      <div className="col-span-6 flex flex-col gap-6">
        <div className="bg-white/5 rounded-2xl border border-white/10 p-6 flex-1 flex flex-col justify-center">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 mb-2">Edge Processor Status</span>
          <div className="font-display text-4xl text-emerald-400 mb-1">Online</div>
          <div className="text-cyan-400 font-mono text-sm">Uptime: {uptimeHours > 0 ? `${uptimeHours}h ${uptimeMinutes % 60}m` : `${uptimeMinutes}m`}</div>
        </div>
        <div className="bg-white/5 rounded-2xl border border-white/10 p-6 flex-1 flex flex-col justify-center">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 mb-2">Session Statistics</span>
          <div className="font-display text-4xl text-white mb-1">{metrics.occupancyCount.toLocaleString()}</div>
          <div className="text-cyan-400 font-mono text-sm">Total Occupancy Events</div>
        </div>
        <div className="bg-white/5 rounded-2xl border border-white/10 p-6 flex-1 flex flex-col justify-center">
          <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 mb-2">MQTT Bridge</span>
          <div className="font-display text-4xl text-white mb-1">{metrics.mqttPublishes.toLocaleString()}</div>
          <div className="text-cyan-400 font-mono text-sm">Total Messages Published</div>
        </div>
      </div>
    </div>
  );
};

export default function DeepDiveOverlay({ nodeId, onClose }: { nodeId: string, onClose: () => void }) {
  const node = pipelineData.find(n => n.id === nodeId) || pipelineData[0];
  const Icon = node.icon;
  const metrics = useEdgeMetrics();

  return (
    <motion.div
      initial={{ opacity: 0, backdropFilter: 'blur(0px)' }}
      animate={{ opacity: 1, backdropFilter: 'blur(20px)' }}
      exit={{ opacity: 0, backdropFilter: 'blur(0px)' }}
      className="absolute inset-0 z-[100] bg-black/60 flex items-center justify-center p-8"
    >
      <motion.div
        initial={{ scale: 0.9, y: 20, opacity: 0 }}
        animate={{ scale: 1, y: 0, opacity: 1 }}
        exit={{ scale: 0.9, y: 20, opacity: 0 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="w-full max-w-6xl h-full max-h-[800px] bg-[#0a0a0a] border border-white/10 rounded-3xl shadow-2xl flex flex-col overflow-hidden relative"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/10 bg-white/5">
          <div className="flex items-center gap-4">
            <div className="p-3 rounded-xl" style={{ backgroundColor: `${node.color}20`, color: node.color }}>
              <Icon className="w-6 h-6" />
            </div>
            <div>
              <div className="font-mono text-[10px] text-white/40 uppercase tracking-widest mb-1">Deep Dive Analysis</div>
              <h2 className="font-display text-2xl text-white font-medium">{node.title}</h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-3 rounded-xl bg-white/5 hover:bg-white/10 text-white/50 hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 p-6 overflow-hidden">
          {node.id === 'unity' && <UnityDeepDiveView color={node.color} />}
          {node.id === 'rpi' && <RPiSimulatorView color={node.color} metrics={metrics} />}
          {node.id === 'edge' && <EdgeDeepDiveView color={node.color} />}
          {node.id === 'cloud' && <CloudTelemetryView color={node.color} metrics={metrics} />}
        </div>
      </motion.div>
    </motion.div>
  );
}
