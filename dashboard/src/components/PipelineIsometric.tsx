import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence, useMotionValue, useSpring, useAnimationFrame } from 'motion/react';
import { pipelineData } from '../lib/pipelineData';
import { Activity, Database, Zap, Cpu, Network, Move3d, RefreshCw, Play, Pause, Maximize2 } from 'lucide-react';
import DeepDiveOverlay from './DeepDiveOverlay';

export default function PipelineIsometric() {
  const [activeIndex, setActiveIndex] = useState(0);
  const [mounted, setMounted] = useState(false);
  const [autoRotate, setAutoRotate] = useState(true);
  const [deepDiveNode, setDeepDiveNode] = useState<string | null>(null);

  useEffect(() => {
    setMounted(true);
  }, []);

  const rotX = useMotionValue(60);
  const rotZ = useMotionValue(-45);
  const smoothRotX = useSpring(rotX, { stiffness: 300, damping: 40 });
  const smoothRotZ = useSpring(rotZ, { stiffness: 300, damping: 40 });

  useAnimationFrame((t, delta) => {
    if (autoRotate) {
      rotZ.set(rotZ.get() + delta * 0.01);
    }
  });

  const handlePan = (e: any, info: any) => {
    setAutoRotate(false);
    rotZ.set(rotZ.get() + info.delta.x * 0.5);
    rotX.set(Math.max(10, Math.min(85, rotX.get() - info.delta.y * 0.5)));
  };

  const resetCamera = () => {
    rotX.set(60);
    rotZ.set(-45);
    setAutoRotate(true);
  };

  const getZOffset = (index: number) => {
    let z = (pipelineData.length - index - 1) * 160;
    if (index < activeIndex) z += 120;
    if (index > activeIndex) z -= 120;
    return z;
  };

  const getXOffset = (index: number) => (index % 2 === 0 ? -90 : 90);
  const getYOffset = (index: number) => (index % 2 === 0 ? -45 : 45);

  return (
    <motion.div 
      className="absolute inset-0 bg-[#050505] overflow-hidden flex items-center justify-center cursor-grab active:cursor-grabbing"
      onPan={handlePan}
    >
      {/* Ambient Background Glow */}
      <div className="absolute inset-0 bg-grid-pattern opacity-20 pointer-events-none" />
      <div 
        className="absolute inset-0 opacity-30 transition-colors duration-1000 pointer-events-none"
        style={{ 
          background: `radial-gradient(circle at 40% 50%, ${pipelineData[activeIndex].color}40, transparent 60%)` 
        }}
      />
      
      {/* Floating Particles */}
      {mounted && [...Array(20)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-1 h-1 rounded-full bg-white/20 pointer-events-none"
          initial={{ 
            x: Math.random() * window.innerWidth, 
            y: Math.random() * window.innerHeight,
            scale: Math.random() * 0.5 + 0.5
          }}
          animate={{ 
            y: [null, Math.random() * -100 - 50],
            opacity: [0, 0.5, 0]
          }}
          transition={{ 
            duration: Math.random() * 5 + 5, 
            repeat: Infinity, 
            ease: "linear",
            delay: Math.random() * 5
          }}
        />
      ))}

      {/* 3D Scene Container */}
      <div 
        className="relative w-full h-full flex items-center justify-center lg:pr-[400px] pointer-events-none"
        style={{ perspective: '2000px' }}
      >
        <motion.div 
          className="relative w-[350px] h-[350px]"
          style={{ 
            rotateX: smoothRotX,
            rotateZ: smoothRotZ,
            transformStyle: 'preserve-3d'
          }}
        >
          {/* Holographic Projector Base */}
          <motion.div 
            className="absolute inset-[-100%] rounded-full border border-white/10 flex items-center justify-center pointer-events-none"
            style={{ 
              background: 'radial-gradient(circle at center, rgba(255,255,255,0.03) 0%, transparent 60%)',
            }}
            animate={{ translateZ: getZOffset(pipelineData.length - 1) - 200 }}
            transition={{ duration: 0.8, type: 'spring', bounce: 0.3 }}
          >
            <div className="absolute w-[80%] h-[80%] rounded-full border border-white/5 border-dashed animate-[spin_20s_linear_infinite]" />
            <div className="absolute w-[60%] h-[60%] rounded-full border border-white/5 animate-[spin_15s_linear_infinite_reverse]" />
            <div className="absolute w-[40%] h-[40%] rounded-full border border-white/10 border-dashed animate-[spin_10s_linear_infinite]" />
            
            {/* Center projector lens */}
            <div className="absolute w-16 h-16 rounded-full bg-white/5 backdrop-blur-md border border-white/20 flex items-center justify-center shadow-[0_0_50px_rgba(255,255,255,0.1)]">
              <div className="w-8 h-8 rounded-full bg-white/20 animate-pulse" />
            </div>
          </motion.div>

          {/* Floor Reflection/Shadow */}
          <motion.div 
            className="absolute inset-[-50%] bg-black/80 blur-3xl rounded-full"
            animate={{ translateZ: getZOffset(pipelineData.length - 1) - 150 }}
            transition={{ duration: 0.8, type: 'spring', bounce: 0.3 }}
          />

          {pipelineData.map((node, index) => {
            const Icon = node.icon;
            const isActive = index === activeIndex;
            const zOffset = getZOffset(index);
            const xOffset = getXOffset(index);
            const yOffset = getYOffset(index);
            
            const nextXOffset = index < pipelineData.length - 1 ? getXOffset(index + 1) : 0;
            const nextYOffset = index < pipelineData.length - 1 ? getYOffset(index + 1) : 0;
            const dx = nextXOffset - xOffset;
            const dy = nextYOffset - yOffset;
            const distXY = Math.sqrt(dx * dx + dy * dy);
            const angleXY = Math.atan2(dy, dx) * (180 / Math.PI);
            const dz = index < pipelineData.length - 1 ? getZOffset(index) - getZOffset(index + 1) : 0;
            
            return (
              <motion.div
                key={node.id}
                className="absolute inset-0 cursor-pointer pointer-events-auto"
                style={{ transformStyle: 'preserve-3d' }}
                animate={{
                  translateX: xOffset,
                  translateY: yOffset,
                  translateZ: zOffset,
                  scale: isActive ? 1.1 : 1,
                }}
                transition={{ duration: 0.8, type: 'spring', bounce: 0.3 }}
                onClick={() => setActiveIndex(index)}
              >
                {/* The Glass Plate */}
                <div 
                  className={`w-full h-full rounded-2xl border backdrop-blur-md flex flex-col items-center justify-center transition-all duration-500 overflow-hidden relative group
                    ${isActive ? 'bg-black/80' : 'bg-black/40 hover:bg-black/60'}
                  `}
                  style={{ 
                    borderColor: isActive ? node.color : 'rgba(255,255,255,0.15)',
                    boxShadow: isActive 
                      ? `0 30px 60px rgba(0,0,0,0.6), 0 0 50px ${node.color}40, inset 0 0 30px ${node.color}30` 
                      : '0 15px 35px rgba(0,0,0,0.5)',
                  }}
                >
                  {/* Corner Brackets */}
                  <div className="absolute top-0 left-0 w-6 h-6 border-t-2 border-l-2 rounded-tl-2xl transition-colors duration-500" style={{ borderColor: isActive ? node.color : 'rgba(255,255,255,0.2)' }} />
                  <div className="absolute top-0 right-0 w-6 h-6 border-t-2 border-r-2 rounded-tr-2xl transition-colors duration-500" style={{ borderColor: isActive ? node.color : 'rgba(255,255,255,0.2)' }} />
                  <div className="absolute bottom-0 left-0 w-6 h-6 border-b-2 border-l-2 rounded-bl-2xl transition-colors duration-500" style={{ borderColor: isActive ? node.color : 'rgba(255,255,255,0.2)' }} />
                  <div className="absolute bottom-0 right-0 w-6 h-6 border-b-2 border-r-2 rounded-br-2xl transition-colors duration-500" style={{ borderColor: isActive ? node.color : 'rgba(255,255,255,0.2)' }} />

                  {/* Layer Number */}
                  <div className="absolute top-4 right-5 font-mono text-[10px] font-bold tracking-widest transition-colors duration-500" style={{ color: isActive ? node.color : 'rgba(255,255,255,0.2)' }}>
                    {String(index + 1).padStart(2, '0')}
                  </div>

                  {/* Specular Highlight (Top Edge) */}
                  <div className="absolute top-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-white/50 to-transparent opacity-50" />
                  
                  {/* Inner Glow */}
                  <div 
                    className="absolute inset-0 opacity-20 transition-opacity duration-500 group-hover:opacity-40"
                    style={{ background: `radial-gradient(circle at center, ${node.color}, transparent 70%)` }}
                  />

                  <Icon 
                    className="w-16 h-16 mb-4 relative z-10 transition-all duration-500" 
                    style={{ 
                      color: isActive ? node.color : 'rgba(255,255,255,0.4)',
                      filter: isActive ? `drop-shadow(0 0 15px ${node.color})` : 'none',
                      transform: isActive ? 'scale(1.1)' : 'scale(1)'
                    }} 
                  />
                  <div className="font-mono text-xs tracking-widest uppercase mb-2 relative z-10 transition-colors duration-500" style={{ color: isActive ? 'rgba(255,255,255,0.8)' : 'rgba(255,255,255,0.4)' }}>
                    {node.category}
                  </div>
                  <div className={`font-display text-3xl font-bold relative z-10 transition-colors duration-500 ${isActive ? 'text-white' : 'text-white/50'}`}>
                    {node.title}
                  </div>
                </div>

                {/* 3-Segment Data Bus */}
                {index < pipelineData.length - 1 && (
                  <div className="absolute left-1/2 top-1/2 pointer-events-none" style={{ transformStyle: 'preserve-3d' }}>
                    {/* Segment 1: Down */}
                    <motion.div 
                      className="absolute left-0 top-0"
                      style={{ 
                        width: '4px', 
                        marginLeft: '-2px',
                        background: `linear-gradient(to bottom, ${node.color}80, ${pipelineData[index+1].color}80)`,
                        transform: 'rotateX(-90deg)',
                        transformOrigin: 'top center',
                        boxShadow: `0 0 10px ${node.color}40`
                      }}
                      animate={{ height: dz / 2 }}
                      transition={{ duration: 0.8, type: 'spring', bounce: 0.3 }}
                    />
                    {/* Segment 2: Across */}
                    <motion.div 
                      className="absolute left-0 top-0"
                      style={{ 
                        height: '4px',
                        marginTop: '-2px',
                        background: pipelineData[index+1].color,
                        opacity: 0.8,
                        transformOrigin: 'left center',
                        boxShadow: `0 0 10px ${pipelineData[index+1].color}40`
                      }}
                      animate={{ 
                        width: distXY,
                        transform: `translateZ(-${dz / 2}px) rotateZ(${angleXY}deg)`
                      }}
                      transition={{ duration: 0.8, type: 'spring', bounce: 0.3 }}
                    />
                    {/* Segment 3: Down */}
                    <motion.div 
                      className="absolute left-0 top-0"
                      style={{ 
                        width: '4px', 
                        marginLeft: '-2px',
                        background: `linear-gradient(to bottom, ${pipelineData[index+1].color}80, ${pipelineData[index+1].color}80)`,
                        transformOrigin: 'top center',
                        boxShadow: `0 0 10px ${pipelineData[index+1].color}40`
                      }}
                      animate={{ 
                        height: dz / 2,
                        transform: `translateX(${dx}px) translateY(${dy}px) translateZ(-${dz / 2}px) rotateX(-90deg)`
                      }}
                      transition={{ duration: 0.8, type: 'spring', bounce: 0.3 }}
                    />
                  </div>
                )}
              </motion.div>
            );
          })}
        </motion.div>
      </div>

      {/* Camera Controls */}
      <div className="absolute bottom-8 left-8 flex items-center gap-4 z-50">
        <div className="flex items-center gap-3 text-white/40 font-mono text-xs uppercase tracking-widest pointer-events-none bg-black/40 backdrop-blur-md px-4 py-3 rounded-xl border border-white/10">
          <Move3d className="w-4 h-4" />
          <span>Drag to rotate</span>
        </div>
        
        <button 
          onClick={() => setAutoRotate(!autoRotate)}
          className={`p-3 rounded-xl border transition-colors flex items-center justify-center ${autoRotate ? 'bg-white/10 border-white/20 text-white' : 'bg-black/40 border-white/10 text-white/40 hover:text-white/70'}`}
          title="Toggle Auto-Rotate"
        >
          {autoRotate ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        </button>

        <button 
          onClick={resetCamera}
          className="p-3 bg-black/40 backdrop-blur-md border border-white/10 rounded-xl text-white/40 hover:text-white/70 transition-colors flex items-center justify-center"
          title="Reset Camera"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Side Details Panel (Bento Style) */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeIndex}
          initial={{ opacity: 0, x: 50, filter: 'blur(10px)' }}
          animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
          exit={{ opacity: 0, x: 50, filter: 'blur(10px)' }}
          transition={{ duration: 0.5, type: 'spring', damping: 25 }}
          onPointerDown={(e) => e.stopPropagation()}
          className="absolute right-6 top-6 bottom-6 w-[420px] bg-black/40 backdrop-blur-2xl border border-white/10 rounded-3xl p-6 flex flex-col z-50 shadow-2xl overflow-y-auto cursor-auto"
        >
          {/* Header */}
          <div className="flex items-center gap-5 mb-8">
            <div 
              className="p-4 rounded-2xl border border-white/10 shadow-inner" 
              style={{ 
                backgroundColor: `${pipelineData[activeIndex].color}15`, 
                color: pipelineData[activeIndex].color,
                boxShadow: `inset 0 0 20px ${pipelineData[activeIndex].color}20`
              }}
            >
              {React.createElement(pipelineData[activeIndex].icon, { className: "w-8 h-8" })}
            </div>
            <div>
              <div className="font-mono text-[10px] uppercase tracking-[0.2em] text-white/40 mb-1">
                {pipelineData[activeIndex].category}
              </div>
              <h2 className="font-display text-2xl font-medium text-white tracking-tight">
                {pipelineData[activeIndex].title}
              </h2>
            </div>
          </div>

          {/* Bento Grid */}
          <div className="grid grid-cols-2 gap-4 mb-4">
            {/* Status Card */}
            <div className="col-span-2 bg-white/5 border border-white/5 rounded-2xl p-5 relative overflow-hidden group">
              <div className="absolute inset-0 opacity-0 group-hover:opacity-10 transition-opacity duration-500" style={{ backgroundColor: pipelineData[activeIndex].color }} />
              <h3 className="font-mono text-[10px] uppercase tracking-widest text-white/40 mb-4 flex items-center gap-2">
                <Activity className="w-3 h-3" /> Live Status
              </h3>
              <div className="flex justify-between items-end">
                <div className="flex items-center gap-3">
                  <div className="relative flex h-3 w-3">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full opacity-75" style={{ backgroundColor: pipelineData[activeIndex].color }}></span>
                    <span className="relative inline-flex rounded-full h-3 w-3" style={{ backgroundColor: pipelineData[activeIndex].color }}></span>
                  </div>
                  <span className="text-lg text-white font-medium">{pipelineData[activeIndex].status}</span>
                </div>
                <span className="font-mono text-sm" style={{ color: pipelineData[activeIndex].color }}>
                  {pipelineData[activeIndex].metric}
                </span>
              </div>
            </div>

            {/* Description Card */}
            <div className="col-span-2 bg-white/5 border border-white/5 rounded-2xl p-5">
              <h3 className="font-mono text-[10px] uppercase tracking-widest text-white/40 mb-3 flex items-center gap-2">
                <Database className="w-3 h-3" /> Overview
              </h3>
              <p className="text-sm text-white/70 leading-relaxed font-light">
                {pipelineData[activeIndex].description}
              </p>
            </div>

            {/* Specs Mini-Cards */}
            {pipelineData[activeIndex].specs.map((spec, i) => (
              <div key={i} className={`bg-white/5 border border-white/5 rounded-2xl p-4 flex flex-col justify-center ${i === 2 ? 'col-span-2' : 'col-span-1'}`}>
                <span className="font-mono text-[9px] uppercase tracking-widest text-white/40 mb-2">{spec.label}</span>
                <span className="font-display text-sm text-white/90">{spec.value}</span>
              </div>
            ))}

            {/* Deep Dive Button */}
            <div className="col-span-2 mt-2">
              <button
                onClick={() => setDeepDiveNode(pipelineData[activeIndex].id)}
                className="w-full py-4 rounded-2xl bg-white/10 hover:bg-white/20 border border-white/10 text-white font-mono text-xs uppercase tracking-widest transition-all flex items-center justify-center gap-3 group"
              >
                <Maximize2 className="w-4 h-4 group-hover:scale-110 transition-transform" />
                Initialize Deep Dive
              </button>
            </div>
          </div>
        </motion.div>
      </AnimatePresence>

      {/* Deep Dive Fullscreen Overlay */}
      <AnimatePresence>
        {deepDiveNode && (
          <DeepDiveOverlay 
            nodeId={deepDiveNode} 
            onClose={() => setDeepDiveNode(null)} 
          />
        )}
      </AnimatePresence>
    </motion.div>
  );
}
