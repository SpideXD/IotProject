import React, { useState, useEffect, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Activity, Clock, Users, Ghost, CheckCircle2,
  Cpu, Wifi, Map as MapIcon, BarChart3, 
  Flame, Radar, Camera, Crosshair, AlertTriangle,
  Thermometer, Wind, Droplets, Zap, TrendingUp
} from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, ResponsiveContainer, Tooltip as RechartsTooltip, CartesianGrid } from 'recharts';
import PipelineIsometric from './PipelineIsometric';
import YoloLive from './YoloLive';

type SeatState = 'empty' | 'occupied' | 'suspected_ghost' | 'confirmed_ghost';

interface Seat {
  id: string;
  zoneId: string;
  state: SeatState;
  occupancyScore: number;
  timeSinceMotion: number;
  ghostDuration?: number;
}

const ZONES = [
  { id: 'Z1', name: 'Study Zone 1', seats: ['S1', 'S2', 'S3', 'S4'] },
  { id: 'Z2', name: 'Study Zone 2', seats: ['S5', 'S6', 'S7', 'S8'] },
  { id: 'Z3', name: 'Study Zone 3', seats: ['S9', 'S10', 'S11', 'S12'] },
  { id: 'Z4', name: 'Study Zone 4', seats: ['S13', 'S14', 'S15', 'S16'] },
  { id: 'Z5', name: 'Study Zone 5', seats: ['S17', 'S18', 'S19', 'S20'] },
  { id: 'Z6', name: 'Study Zone 6', seats: ['S21', 'S22', 'S23', 'S24'] },
  { id: 'Z7', name: 'Study Zone 7', seats: ['S25', 'S26', 'S27', 'S28'] },
];

const generateInitialSeats = (): Record<string, Seat> => {
  const seats: Record<string, Seat> = {};
  ZONES.forEach(zone => {
    zone.seats.forEach(seatId => {
      const rand = Math.random();
      let state: SeatState = 'empty';
      if (rand > 0.85) state = 'confirmed_ghost';
      else if (rand > 0.75) state = 'suspected_ghost';
      else if (rand > 0.4) state = 'occupied';

      seats[seatId] = {
        id: seatId,
        zoneId: zone.id,
        state,
        occupancyScore: state === 'empty' ? 0 : Math.random() * 0.5 + 0.5,
        timeSinceMotion: state === 'empty' ? 0 : (state === 'occupied' ? Math.random() * 60 : Math.random() * 300 + 120),
        ghostDuration: state === 'confirmed_ghost' ? Math.random() * 600 + 300 : (state === 'suspected_ghost' ? Math.random() * 120 + 120 : 0)
      };
    });
  });
  return seats;
};

const generateChartData = () => {
  const data = [];
  const now = new Date();
  for (let i = 24; i >= 0; i--) {
    const time = new Date(now.getTime() - i * 5 * 60000);
    data.push({
      time: time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      occupied: Math.floor(Math.random() * 15) + 5,
      ghosts: Math.floor(Math.random() * 5),
    });
  }
  return data;
};

const getSeatStyles = (state: SeatState) => {
  switch (state) {
    case 'empty': return {
      bg: 'bg-white/5',
      border: 'border-white/10',
      text: 'text-white/30',
      glow: 'shadow-none'
    };
    case 'occupied': return {
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/50',
      text: 'text-emerald-400',
      glow: 'shadow-[0_0_15px_rgba(16,185,129,0.15)]'
    };
    case 'suspected_ghost': return {
      bg: 'bg-amber-500/10',
      border: 'border-amber-500/50',
      text: 'text-amber-400',
      glow: 'shadow-[0_0_15px_rgba(245,158,11,0.15)]'
    };
    case 'confirmed_ghost': return {
      bg: 'bg-purple-500/10',
      border: 'border-purple-500/50',
      text: 'text-purple-400',
      glow: 'shadow-[0_0_15px_rgba(168,85,247,0.25)]'
    };
  }
};

export default function Dashboard() {
  const [mainView, setMainView] = useState<'dashboard' | 'pipeline' | 'yolo'>('dashboard');
  const [seats, setSeats] = useState<Record<string, Seat>>(generateInitialSeats());
  const [chartData, setChartData] = useState(generateChartData());
  const [selectedSeat, setSelectedSeat] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'blueprint' | 'heatmap'>('blueprint');
  const [envData, setEnvData] = useState({ temp: 22.1, co2: 420, humidity: 45 });
  const [edgeStats, setEdgeStats] = useState<Record<string, number>>({});

  const PROTOCOL = window.location.protocol === 'https:' ? 'https:' : 'http:';
  const HOST = window.location.hostname;
  const API_BASE = `${PROTOCOL}//${HOST}:5002`;

  useEffect(() => {
    const fetchEdgeData = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/status`);
        if (!res.ok) throw new Error('API unavailable');
        const data = await res.json();

        if (data.seat_states) {
          setSeats(prev => {
            const next = { ...prev };
            Object.entries(data.seat_states).forEach(([seatId, state]) => {
              if (next[seatId]) {
                next[seatId] = {
                  ...next[seatId],
                  state: state as SeatState,
                  timeSinceMotion: 0
                };
              }
            });
            return next;
          });
        }

        if (data.stats) {
          setEdgeStats({
            occupied: data.stats.state_counts?.occupied || 0,
            empty: data.stats.state_counts?.empty || 0,
            ghosts: (data.stats.state_counts?.suspected_ghost || 0) + (data.stats.state_counts?.confirmed_ghost || 0),
            total: data.total_seats || 28,
            messagesPerMin: data.stats.messages_per_minute || 0,
            uptime: data.stats.uptime_seconds || 0
          });
        }

        setChartData(prev => {
          const next = [...prev.slice(1)];
          const now = new Date();
          const occupied = data.stats?.state_counts?.occupied || 0;
          const ghosts = (data.stats?.state_counts?.suspected_ghost || 0) + (data.stats?.state_counts?.confirmed_ghost || 0);
          next.push({
            time: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            occupied,
            ghosts
          });
          return next;
        });

      } catch (err) {
        console.warn('Edge API unavailable, using simulation:', err);
      }
    };

    fetchEdgeData();


    const interval = setInterval(fetchEdgeData, 3000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const interval = setInterval(() => {
      setSeats(prev => {
        let occupiedCount = 0;
        (Object.values(prev) as Seat[]).forEach(s => {
          if (s.state !== 'empty') occupiedCount++;
        });
        const currentUtil = occupiedCount / Object.keys(prev).length;

        setEnvData(prev => {
          const targetTemp = 21 + (currentUtil) * 4;
          const targetCo2 = 400 + (currentUtil) * 600;
          const targetHum = 40 + (currentUtil) * 20;

          return {
            temp: prev.temp + (targetTemp - prev.temp) * 0.1 + (Math.random() * 0.2 - 0.1),
            co2: prev.co2 + (targetCo2 - prev.co2) * 0.1 + (Math.random() * 10 - 5),
            humidity: prev.humidity + (targetHum - prev.humidity) * 0.1 + (Math.random() * 1 - 0.5)
          };
        });

        return prev;
      });
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  const stats = useMemo(() => (Object.values(seats) as Seat[]).reduce<{ total: number, empty: number, occupied: number, suspected: number, ghosts: number }>((acc, seat) => {
    acc.total++;
    if (seat.state === 'empty') acc.empty++;
    else if (seat.state === 'occupied') acc.occupied++;
    else if (seat.state === 'suspected_ghost') acc.suspected++;
    else if (seat.state === 'confirmed_ghost') acc.ghosts++;
    return acc;
  }, { total: 0, empty: 0, occupied: 0, suspected: 0, ghosts: 0 }), [seats]);

  const utilization = ((stats.occupied + stats.suspected + stats.ghosts) / stats.total) * 100;

  const zoneStats = useMemo(() => {
    return ZONES.map(zone => {
      const zoneSeats = zone.seats.map(id => seats[id]);
      const occupiedCount = zoneSeats.filter(s => s.state !== 'empty').length;
      const ghostCount = zoneSeats.filter(s => s.state === 'confirmed_ghost' || s.state === 'suspected_ghost').length;
      const util = (occupiedCount / zone.seats.length) * 100;
      return { ...zone, utilization: util, occupied: occupiedCount, ghosts: ghostCount, total: zone.seats.length };
    }).sort((a, b) => b.utilization - a.utilization);
  }, [seats]);

  const activeGhosts = useMemo(() => {
    return (Object.values(seats) as Seat[])
      .filter(s => s.state === 'suspected_ghost' || s.state === 'confirmed_ghost')
      .sort((a, b) => b.timeSinceMotion - a.timeSinceMotion);
  }, [seats]);

  return (
    <div className="min-h-screen bg-[#050505] text-white font-sans selection:bg-purple-500/30 flex flex-col">
      
      {/* HUD Header */}
      <header className="px-6 py-4 border-b border-white/10 flex justify-between items-center bg-black/50 backdrop-blur-md sticky top-0 z-50">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <div className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
            </div>
            <span className="font-mono text-[10px] tracking-[0.2em] text-white/50 uppercase">
              {mainView === 'dashboard' ? 'Live Telemetry' : mainView === 'pipeline' ? 'System Pipeline' : 'Live YOLO'}
            </span>
          </div>
          <div className="h-4 w-px bg-white/20" />
          <h1 className="font-display text-xl font-medium tracking-tight flex items-center gap-2">
            LIBERTY TWIN <span className="text-white/30 font-light">/ EDGE</span>
          </h1>
          <div className="ml-8 flex bg-black/50 rounded-md border border-white/10 p-1">
            <button 
              onClick={() => setMainView('dashboard')}
              className={`px-3 py-1 rounded text-[10px] font-mono uppercase tracking-wider transition-colors ${mainView === 'dashboard' ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/70'}`}
            >
              Telemetry
            </button>
            <button
              onClick={() => setMainView('pipeline')}
              className={`px-3 py-1 rounded text-[10px] font-mono uppercase tracking-wider transition-colors ${mainView === 'pipeline' ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/70'}`}
            >
              Pipeline
            </button>
            <button
              onClick={() => setMainView('yolo')}
              className={`px-3 py-1 rounded text-[10px] font-mono uppercase tracking-wider transition-colors ${mainView === 'yolo' ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/70'}`}
            >
              Live YOLO
            </button>
          </div>
        </div>
        <div className="flex items-center gap-6 font-mono text-xs text-white/50">
          <div className="flex items-center gap-2">
            <Users className="w-3 h-3 text-emerald-500" />
            <span>DENSITY: {utilization.toFixed(1)}%</span>
          </div>
          <div className="flex items-center gap-2">
            <Wifi className="w-3 h-3 text-emerald-500" />
            <span>NODE_01_ONLINE</span>
          </div>
          <div className="flex items-center gap-2">
            <Cpu className="w-3 h-3 text-emerald-500" />
            <span>YOLO_V8_NANO</span>
          </div>
          <div className="flex items-center gap-2 text-white/80">
            <Clock className="w-3 h-3" />
            {new Date().toLocaleTimeString([], { hour12: false })}
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      {mainView === 'pipeline' ? (
        <main className="flex-1 relative">
          <PipelineIsometric />
        </main>
      ) : mainView === 'yolo' ? (
        <main className="flex-1 p-6">
          <YoloLive />
        </main>
      ) : (
        <main className="flex-1 p-6 grid grid-cols-12 gap-6 overflow-y-auto items-start">
          
          {/* Left Column: Stats & Analytics (3 cols) */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-6">
          
          {/* Big Stats Bento */}
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-2 gap-4">
            <div className="glass-panel rounded-xl p-5 flex flex-col justify-between min-h-[140px]">
              <div className="flex justify-between items-start">
                <span className="font-mono text-[10px] uppercase tracking-widest text-white/40">Total Seats</span>
                <MapIcon className="w-4 h-4 text-white/20" />
              </div>
              <div className="mt-4">
                <span className="font-display text-5xl font-light tracking-tighter">{stats.total}</span>
              </div>
            </div>
            
            <div className="glass-panel rounded-xl p-5 flex flex-col justify-between min-h-[140px] relative overflow-hidden">
              <div className="absolute inset-0 bg-emerald-500/5" />
              <div className="relative flex justify-between items-start">
                <span className="font-mono text-[10px] uppercase tracking-widest text-emerald-400/70">Available</span>
                <CheckCircle2 className="w-4 h-4 text-emerald-500/50" />
              </div>
              <div className="relative mt-4">
                <span className="font-display text-5xl font-light tracking-tighter text-emerald-400">{stats.empty}</span>
              </div>
            </div>

            <div className="glass-panel rounded-xl p-5 flex flex-col justify-between min-h-[140px] relative overflow-hidden">
              <div className="absolute inset-0 bg-purple-500/5" />
              <div className="relative flex justify-between items-start">
                <span className="font-mono text-[10px] uppercase tracking-widest text-purple-400/70">Ghosts</span>
                <Ghost className="w-4 h-4 text-purple-500/50" />
              </div>
              <div className="relative mt-4">
                <span className="font-display text-5xl font-light tracking-tighter text-purple-400">{stats.ghosts}</span>
                <div className="font-mono text-[10px] text-purple-400/50 mt-1">+{stats.suspected} SUSPECTED</div>
              </div>
            </div>

            <div className="glass-panel rounded-xl p-5 flex flex-col justify-between min-h-[140px]">
              <div className="flex justify-between items-start">
                <span className="font-mono text-[10px] uppercase tracking-widest text-white/40">Utilization</span>
                <Activity className="w-4 h-4 text-white/20" />
              </div>
              <div className="mt-4">
                <span className="font-display text-4xl font-light tracking-tighter">{utilization.toFixed(0)}%</span>
                <div className="w-full h-1 bg-white/10 rounded-full mt-3 overflow-hidden">
                  <motion.div 
                    className="h-full bg-white/50" 
                    initial={{ width: 0 }}
                    animate={{ width: `${utilization}%` }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Mini Chart */}
          <div className="glass-panel rounded-xl p-5 flex flex-col h-[280px]">
            <div className="flex justify-between items-center mb-6">
              <span className="font-mono text-[10px] uppercase tracking-widest text-white/40">Trend Analysis</span>
              <BarChart3 className="w-4 h-4 text-white/20" />
            </div>
            <div className="flex-1 w-full -ml-4">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData}>
                  <defs>
                    <linearGradient id="colorOcc" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#10b981" stopOpacity={0.2}/>
                      <stop offset="95%" stopColor="#10b981" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorGho" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#a855f7" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#a855f7" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="rgba(255,255,255,0.05)" />
                  <XAxis dataKey="time" axisLine={false} tickLine={false} tick={{ fontSize: 10, fill: 'rgba(255,255,255,0.3)', fontFamily: 'JetBrains Mono' }} dy={10} />
                  <RechartsTooltip 
                    contentStyle={{ backgroundColor: 'rgba(10,10,10,0.9)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: '8px', fontFamily: 'JetBrains Mono', fontSize: '12px' }}
                    itemStyle={{ color: '#fff' }}
                  />
                  <Area type="monotone" dataKey="occupied" stroke="#10b981" strokeWidth={2} fill="url(#colorOcc)" />
                  <Area type="monotone" dataKey="ghosts" stroke="#a855f7" strokeWidth={2} fill="url(#colorGho)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Environmental Sensors */}
          <div className="glass-panel rounded-xl p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-widest text-white/40">Environment</span>
              <Thermometer className="w-4 h-4 text-emerald-500" />
            </div>
            <div className="grid grid-cols-3 gap-2">
              <div className="bg-white/5 rounded-lg p-3 flex flex-col items-center justify-center gap-1">
                <Thermometer className="w-4 h-4 text-orange-400 mb-1" />
                <span className="font-display text-lg">{envData.temp.toFixed(1)}°</span>
                <span className="font-mono text-[8px] text-white/40">TEMP</span>
              </div>
              <div className="bg-white/5 rounded-lg p-3 flex flex-col items-center justify-center gap-1">
                <Wind className="w-4 h-4 text-blue-400 mb-1" />
                <span className="font-display text-lg">{Math.round(envData.co2)}</span>
                <span className="font-mono text-[8px] text-white/40">CO2 PPM</span>
              </div>
              <div className="bg-white/5 rounded-lg p-3 flex flex-col items-center justify-center gap-1">
                <Droplets className="w-4 h-4 text-cyan-400 mb-1" />
                <span className="font-display text-lg">{Math.round(envData.humidity)}%</span>
                <span className="font-mono text-[8px] text-white/40">HUMIDITY</span>
              </div>
            </div>
          </div>
        </div>

        {/* Center Column: Digital Twin Map (5 cols) */}
        <div className="col-span-12 lg:col-span-5 flex flex-col">
          <div className="glass-panel rounded-xl p-1 relative overflow-hidden flex flex-col">
            <div className="absolute top-6 left-6 right-6 z-20 flex justify-between items-center">
              <span className="font-mono text-[10px] uppercase tracking-widest text-white/40 flex items-center gap-2">
                <div className="w-1.5 h-1.5 rounded-full bg-white/20 animate-pulse" />
                Floor Plan Schematic
              </span>
              <div className="flex bg-black/50 rounded-md border border-white/10 p-1">
                <button 
                  onClick={() => setViewMode('blueprint')}
                  className={`px-3 py-1 rounded text-[10px] font-mono uppercase tracking-wider transition-colors ${viewMode === 'blueprint' ? 'bg-white/10 text-white' : 'text-white/40 hover:text-white/70'}`}
                >
                  Blueprint
                </button>
                <button 
                  onClick={() => setViewMode('heatmap')}
                  className={`px-3 py-1 rounded text-[10px] font-mono uppercase tracking-wider transition-colors ${viewMode === 'heatmap' ? 'bg-orange-500/20 text-orange-400' : 'text-white/40 hover:text-white/70'}`}
                >
                  Heatmap
                </button>
              </div>
            </div>
            
            {/* The Blueprint Map */}
            <div className="flex-1 bg-grid-pattern relative flex items-center justify-center p-8 rounded-lg overflow-hidden border border-white/5 mt-12">
              {/* Scanline */}
              {viewMode === 'blueprint' && (
                <motion.div
                  className="absolute inset-0 w-full h-[1px] bg-white/20 shadow-[0_0_15px_rgba(255,255,255,0.3)] z-0 pointer-events-none"
                  animate={{ top: ['-10%', '110%'] }}
                  transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
                />
              )}

              <div className="relative z-10 w-full max-w-lg grid grid-cols-2 gap-x-16 gap-y-12">
                {/* Section A (Left) */}
                <div className="space-y-12">
                  {['Z1', 'Z2', 'Z3', 'Z4'].map(zoneId => {
                    const zone = ZONES.find(z => z.id === zoneId)!;
                    const zStats = zoneStats.find(z => z.id === zoneId)!;
                    
                    return (
                      <div key={zoneId} className="relative">
                        <div className="absolute -left-12 top-1/2 -translate-y-1/2 text-[10px] font-mono tracking-widest text-white/30 -rotate-90 whitespace-nowrap">
                          {zone.name}
                        </div>
                        
                        {/* Heatmap Overlay */}
                        <AnimatePresence>
                          {viewMode === 'heatmap' && (
                            <motion.div 
                              initial={{ opacity: 0, scale: 0.8 }}
                              animate={{ opacity: 1, scale: [1, 1.05, 1] }}
                              exit={{ opacity: 0, scale: 0.8 }}
                              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                              className="absolute inset-[-40px] rounded-full blur-[40px] -z-10 pointer-events-none"
                              style={{
                                background: `radial-gradient(circle at center, ${
                                  zStats.utilization > 75 ? 'rgba(249, 115, 22, 0.5)' : 
                                  zStats.utilization > 40 ? 'rgba(234, 179, 8, 0.3)' : 
                                  zStats.utilization > 10 ? 'rgba(59, 130, 246, 0.2)' : 'transparent'
                                } 0%, transparent 70%)`
                              }}
                            />
                          )}
                        </AnimatePresence>

                        <div className="grid grid-cols-2 gap-4">
                          {zone.seats.map(seatId => {
                            const seat = seats[seatId];
                            const styles = getSeatStyles(seat.state);
                            const isSelected = selectedSeat === seatId;
                            
                            return (
                              <motion.div 
                                key={seatId}
                                layoutId={`seat-${seatId}`}
                                onClick={() => setSelectedSeat(seatId === selectedSeat ? null : seatId)}
                                className={`
                                  relative h-12 rounded-md border flex items-center justify-center cursor-pointer transition-colors duration-500
                                  ${viewMode === 'heatmap' ? 
                                    (seat.state !== 'empty' ? 'bg-orange-500/20 border-orange-500/30 shadow-[0_0_15px_rgba(249,115,22,0.2)]' : 'bg-white/5 border-white/5') 
                                    : `${styles.bg} ${styles.border} ${styles.glow}`}
                                  ${isSelected ? 'ring-2 ring-white/50 scale-105 z-20' : ''}
                                `}
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                              >
                                <span className={`font-mono text-[10px] font-medium ${viewMode === 'heatmap' ? 'text-white/20' : styles.text}`}>
                                  {seatId}
                                </span>
                                
                                {seat.state === 'suspected_ghost' && viewMode === 'blueprint' && (
                                  <motion.div 
                                    className="absolute -top-1 -right-1 w-2 h-2 bg-amber-500 rounded-full"
                                    animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
                                    transition={{ duration: 2, repeat: Infinity }}
                                  />
                                )}
                              </motion.div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Section B (Right) */}
                <div className="space-y-12">
                  {['Z5', 'Z6', 'Z7'].map(zoneId => {
                    const zone = ZONES.find(z => z.id === zoneId)!;
                    const zStats = zoneStats.find(z => z.id === zoneId)!;

                    return (
                      <div key={zoneId} className="relative">
                        <div className="absolute -right-12 top-1/2 -translate-y-1/2 text-[10px] font-mono tracking-widest text-white/30 rotate-90 whitespace-nowrap">
                          {zone.name}
                        </div>

                        {/* Heatmap Overlay */}
                        <AnimatePresence>
                          {viewMode === 'heatmap' && (
                            <motion.div 
                              initial={{ opacity: 0, scale: 0.8 }}
                              animate={{ opacity: 1, scale: [1, 1.05, 1] }}
                              exit={{ opacity: 0, scale: 0.8 }}
                              transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                              className="absolute inset-[-40px] rounded-full blur-[40px] -z-10 pointer-events-none"
                              style={{
                                background: `radial-gradient(circle at center, ${
                                  zStats.utilization > 75 ? 'rgba(249, 115, 22, 0.5)' : 
                                  zStats.utilization > 40 ? 'rgba(234, 179, 8, 0.3)' : 
                                  zStats.utilization > 10 ? 'rgba(59, 130, 246, 0.2)' : 'transparent'
                                } 0%, transparent 70%)`
                              }}
                            />
                          )}
                        </AnimatePresence>

                        <div className="grid grid-cols-2 gap-4">
                          {zone.seats.map(seatId => {
                            const seat = seats[seatId];
                            const styles = getSeatStyles(seat.state);
                            const isSelected = selectedSeat === seatId;
                            
                            return (
                              <motion.div 
                                key={seatId}
                                layoutId={`seat-${seatId}`}
                                onClick={() => setSelectedSeat(seatId === selectedSeat ? null : seatId)}
                                className={`
                                  relative h-12 rounded-md border flex items-center justify-center cursor-pointer transition-colors duration-500
                                  ${viewMode === 'heatmap' ? 
                                    (seat.state !== 'empty' ? 'bg-orange-500/20 border-orange-500/30 shadow-[0_0_15px_rgba(249,115,22,0.2)]' : 'bg-white/5 border-white/5') 
                                    : `${styles.bg} ${styles.border} ${styles.glow}`}
                                  ${isSelected ? 'ring-2 ring-white/50 scale-105 z-20' : ''}
                                `}
                                whileHover={{ scale: 1.05 }}
                                whileTap={{ scale: 0.95 }}
                              >
                                <span className={`font-mono text-[10px] font-medium ${viewMode === 'heatmap' ? 'text-white/20' : styles.text}`}>
                                  {seatId}
                                </span>
                                
                                {seat.state === 'suspected_ghost' && viewMode === 'blueprint' && (
                                  <motion.div 
                                    className="absolute -top-1 -right-1 w-2 h-2 bg-amber-500 rounded-full"
                                    animate={{ scale: [1, 1.5, 1], opacity: [1, 0.5, 1] }}
                                    transition={{ duration: 2, repeat: Infinity }}
                                  />
                                )}
                              </motion.div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                  {/* Lounge Area Placeholder */}
                  <div className="h-[112px] border border-dashed border-white/10 rounded-lg flex items-center justify-center bg-white/[0.02]">
                    <span className="font-mono text-[10px] tracking-widest text-white/20 uppercase">Lounge Area</span>
                  </div>
                </div>
              </div>
            </div>
            
            {/* Selected Seat Details Panel */}
            <AnimatePresence>
              {selectedSeat && (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 20 }}
                  className="absolute bottom-6 left-6 right-6 bg-black/80 backdrop-blur-xl border border-white/10 rounded-lg p-4 flex items-center justify-between shadow-2xl z-30"
                >
                  <div className="flex items-center gap-6">
                    <div className="w-12 h-12 rounded-md bg-white/5 border border-white/10 flex items-center justify-center font-display text-xl">
                      {selectedSeat}
                    </div>
                    <div>
                      <div className="font-mono text-[10px] text-white/40 uppercase tracking-widest mb-1">
                        {ZONES.find(z => z.seats.includes(selectedSeat))?.name}
                      </div>
                      <div className="flex items-center gap-3 font-mono text-xs">
                        <span className="text-white/70">STATE:</span>
                        <span className={`uppercase ${getSeatStyles(seats[selectedSeat].state).text}`}>
                          {seats[selectedSeat].state.replace('_', ' ')}
                        </span>
                      </div>
                    </div>
                  </div>
                  
                  <div className="flex gap-8 font-mono text-xs">
                    <div className="flex flex-col gap-1">
                      <span className="text-white/40">CONFIDENCE</span>
                      <span className="text-white">{(seats[selectedSeat].occupancyScore * 100).toFixed(1)}%</span>
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-white/40">IDLE TIME</span>
                      <span className="text-white">{Math.floor(seats[selectedSeat].timeSinceMotion)}s</span>
                    </div>
                    {seats[selectedSeat].state === 'suspected_ghost' && (
                      <div className="flex flex-col gap-1">
                        <span className="text-amber-500/70">GHOST IN</span>
                        <span className="text-amber-400">{Math.max(0, 300 - Math.floor(seats[selectedSeat].timeSinceMotion))}s</span>
                      </div>
                    )}
                  </div>
                  
                  <button 
                    onClick={() => setSelectedSeat(null)}
                    className="w-8 h-8 rounded-full bg-white/5 hover:bg-white/10 flex items-center justify-center transition-colors"
                  >
                    <span className="text-white/50 text-xs">✕</span>
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Right Column: Analytics & Features (4 cols) */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-6">
          
          {/* Zone Heatmap Widget */}
          <div className="glass-panel rounded-xl p-5 flex flex-col gap-5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-widest text-white/40">Zone Heatmap</span>
              <Flame className="w-4 h-4 text-orange-500" />
            </div>
            <div className="space-y-4">
              {zoneStats.map(zone => (
                <div key={zone.id} className="space-y-1.5">
                  <div className="flex justify-between items-center font-mono text-[10px]">
                    <span className="text-white/70">{zone.id} - {zone.name}</span>
                    <div className="flex items-center gap-3">
                      {zone.ghosts > 0 && (
                        <span className="text-purple-400 flex items-center gap-1"><Ghost className="w-3 h-3"/> {zone.ghosts}</span>
                      )}
                      <span className={zone.utilization > 75 ? 'text-orange-400 font-bold' : 'text-white/50'}>
                        {zone.utilization.toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden flex">
                    <motion.div
                      className={`h-full ${zone.utilization > 75 ? 'bg-orange-500' : zone.utilization > 25 ? 'bg-emerald-500' : 'bg-blue-500'}`}
                      initial={{ width: 0 }}
                      animate={{ width: `${zone.utilization}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Predictive Insights */}
          <div className="glass-panel rounded-xl p-5 flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-widest text-white/40">AI Insights</span>
              <Zap className="w-4 h-4 text-yellow-400" />
            </div>
            <div className="space-y-3">
              <div className="flex items-start gap-3 bg-white/5 p-3 rounded-lg border border-white/5">
                <TrendingUp className="w-4 h-4 text-emerald-400 mt-0.5" />
                <div>
                  <div className="font-mono text-[10px] text-white/70 mb-1">PEAK PREDICTION</div>
                  <div className="text-xs text-white/50">Expected 85% utilization at 14:30 based on historical patterns.</div>
                </div>
              </div>
              <div className="flex items-start gap-3 bg-white/5 p-3 rounded-lg border border-white/5">
                <Flame className="w-4 h-4 text-orange-400 mt-0.5" />
                <div>
                  <div className="font-mono text-[10px] text-white/70 mb-1">HVAC OPTIMIZATION</div>
                  <div className="text-xs text-white/50">Zone 1 & 2 cooling increased due to rising heat density.</div>
                </div>
              </div>
            </div>
          </div>

          {/* Sensor Fusion Telemetry */}
          <div className="glass-panel rounded-xl p-5 flex flex-col gap-5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[10px] uppercase tracking-widest text-white/40">Sensor Fusion Engine</span>
              <Crosshair className="w-4 h-4 text-blue-400" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-white/5 border border-white/10 rounded-lg p-3 flex flex-col gap-2">
                <div className="flex items-center gap-2 text-white/50 font-mono text-[10px]">
                  <Camera className="w-3 h-3" /> YOLOv8 Vision
                </div>
                <div className="font-display text-2xl text-white">94<span className="text-sm text-white/30">%</span></div>
                <div className="text-[9px] font-mono text-emerald-400 uppercase tracking-wider">Weight: 60%</div>
              </div>
              <div className="bg-white/5 border border-white/10 rounded-lg p-3 flex flex-col gap-2">
                <div className="flex items-center gap-2 text-white/50 font-mono text-[10px]">
                  <Radar className="w-3 h-3" /> mmWave Radar
                </div>
                <div className="font-display text-2xl text-white">88<span className="text-sm text-white/30">%</span></div>
                <div className="text-[9px] font-mono text-blue-400 uppercase tracking-wider">Weight: 40%</div>
              </div>
            </div>
          </div>

          {/* Active Ghost Tracker */}
          <div className="glass-panel rounded-xl flex flex-col min-h-[200px] max-h-[300px] overflow-hidden">
            <div className="p-5 border-b border-white/10 flex items-center justify-between shrink-0">
              <span className="font-mono text-[10px] uppercase tracking-widest text-white/40">Ghost Tracker</span>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] text-purple-400">{activeGhosts.length} ACTIVE</span>
                <AlertTriangle className="w-4 h-4 text-amber-500" />
              </div>
            </div>
            <div className="p-2 overflow-y-auto flex-1 space-y-1">
              <AnimatePresence>
                {activeGhosts.length === 0 ? (
                  <div className="h-full flex items-center justify-center font-mono text-xs text-white/20">
                    NO GHOSTS DETECTED
                  </div>
                ) : (
                  activeGhosts.map(ghost => (
                    <motion.div 
                      key={ghost.id}
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -20 }}
                      className="p-3 rounded-lg bg-white/[0.02] hover:bg-white/[0.05] transition-colors border border-transparent hover:border-white/5 flex items-center justify-between group cursor-pointer"
                      onClick={() => setSelectedSeat(ghost.id)}
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full ${ghost.state === 'confirmed_ghost' ? 'bg-purple-500 shadow-[0_0_10px_rgba(168,85,247,0.5)]' : 'bg-amber-500 animate-pulse'}`} />
                        <div className="flex flex-col">
                          <span className="font-mono text-xs font-bold text-white">{ghost.id}</span>
                          <span className="font-mono text-[9px] text-white/40">{ZONES.find(z => z.id === ghost.zoneId)?.name}</span>
                        </div>
                      </div>
                      
                      <div className="flex flex-col items-end gap-1">
                        <span className={`font-mono text-[10px] ${ghost.state === 'confirmed_ghost' ? 'text-purple-400' : 'text-amber-400'}`}>
                          {ghost.state === 'confirmed_ghost' ? 'CONFIRMED' : 'SUSPECTED'}
                        </span>
                        {ghost.state === 'suspected_ghost' && (
                          <div className="w-16 h-1 bg-white/10 rounded-full overflow-hidden">
                            <div 
                              className="h-full bg-amber-500" 
                              style={{ width: `${Math.min(100, (ghost.timeSinceMotion / 300) * 100)}%` }} 
                            />
                          </div>
                        )}
                      </div>
                    </motion.div>
                  ))
                )}
              </AnimatePresence>
            </div>
          </div>

        </div>

      </main>
      )}
    </div>
  );
}
