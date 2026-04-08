import React, { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'motion/react';
import { Camera, Cpu, Activity, X, AlertCircle } from 'lucide-react';

interface Detection {
  className: string;
  confidence: number;
  bbox: { x1: number; y1: number; x2: number; y2: number };
}

export default function YoloLive() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const animationRef = useRef<number>(0);

  const [isModelLoading, setIsModelLoading] = useState(true);
  const [modelError, setModelError] = useState<string | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);
  const [annotatedImage, setAnnotatedImage] = useState<string | null>(null);
  const [fps, setFps] = useState(0);

  const YOLO_SERVER_URL = 'https://scott-feel-matter-occasional.trycloudflare.com';
  const API_BASE = YOLO_SERVER_URL;

  const startCamera = useCallback(() => {
    console.log('START_CAMERA: clicked');
    if (!videoRef.current) {
      setTimeout(() => startCamera(), 100);
      return;
    }

    navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } }
    }).then((stream) => {
      console.log('START_CAMERA: got stream');
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        streamRef.current = stream;

        if (videoRef.current.readyState >= 2) {
          videoRef.current.play().then(() => {
            setCameraActive(true);
            setCameraError(null);
          });
        } else {
          videoRef.current.onloadedmetadata = () => {
            videoRef.current?.play().then(() => {
              setCameraActive(true);
              setCameraError(null);
            });
          };
        }
      }
    }).catch((err: any) => {
      console.error('START_CAMERA: getUserMedia failed:', err);
      setCameraError(err.message || 'Failed to access camera');
    });
  }, []);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
    setCameraActive(false);
  }, []);

  useEffect(() => {
    const checkServer = async () => {
      try {
        const res = await fetch(`${API_BASE}/health`);
        const data = await res.json();
        if (data.model_loaded) {
          setIsModelLoading(false);
        } else {
          setModelError('Model loading on server...');
        }
      } catch (err) {
        setModelError('Detection server unavailable');
        setIsModelLoading(false);
      }
    };
    checkServer();
  }, [API_BASE]);

  const runDetection = useCallback(async () => {
    if (!videoRef.current || !cameraActive) return;

    const video = videoRef.current;

    if (video.readyState < 2) {
      animationRef.current = requestAnimationFrame(runDetection);
      return;
    }

    try {
      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth || 640;
      canvas.height = video.videoHeight || 480;
      const ctx = canvas.getContext('2d');
      if (!ctx) {
        animationRef.current = requestAnimationFrame(runDetection);
        return;
      }

      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

      const imageData = canvas.toDataURL('image/jpeg', 0.8);


      const res = await fetch(`${API_BASE}/detect`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image: imageData })
      });

      if (!res.ok) throw new Error('Detection failed');

      const data = await res.json();

      if (data.image) {
        setAnnotatedImage(data.image);
      }
      setDetections(data.detections || []);
      setFps(prev => prev === 0 ? 10 : (prev + 10) / 2);

    } catch (err) {
      console.error('Detection error:', err);
    } finally {
      animationRef.current = requestAnimationFrame(runDetection);
    }
  }, [cameraActive, API_BASE]);

  useEffect(() => {
    if (cameraActive) {
      runDetection();
    } else {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    }

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [cameraActive, runDetection]);

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, [stopCamera]);

  return (
    <div className="flex-1 flex flex-col bg-black/40 rounded-2xl border border-white/10 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${cameraActive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/10 text-white/40'}`}>
            {cameraActive ? <Camera className="w-5 h-5" /> : <Camera className="w-5 h-5" />}
          </div>
          <div>
            <h2 className="font-display text-lg text-white">Server-side YOLO Detection</h2>
            <p className="font-mono text-[10px] text-white/40">
              {cameraActive ? `Camera active - ${detections.length} objects` : cameraError || 'Click Start to begin'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {cameraActive && (
            <div className="flex items-center gap-4 font-mono text-xs">
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4 text-emerald-400" />
                <span className="text-white">{fps} FPS</span>
              </div>
              <div className="flex items-center gap-2">
                <Cpu className="w-4 h-4 text-blue-400" />
                <span className="text-white">{detections.length} objects</span>
              </div>
            </div>
          )}

          {!cameraActive ? (
            <button
              onClick={startCamera}
              disabled={isModelLoading}
              className="px-4 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 font-mono text-xs uppercase tracking-wider disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            >
              <Camera className="w-4 h-4" />
              Start Camera
            </button>
          ) : (
            <button
              onClick={stopCamera}
              className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white font-mono text-xs uppercase tracking-wider flex items-center gap-2"
            >
              <X className="w-4 h-4" />
              Stop
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="relative bg-black overflow-hidden" style={{ height: 'calc(100vh - 180px)' }}>
        {isModelLoading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="w-12 h-12 border-2 border-white/20 border-t-emerald-500 rounded-full animate-spin mx-auto mb-4" />
              <p className="font-mono text-sm text-white/60">Connecting to YOLO server...</p>
              <p className="font-mono text-[10px] text-white/40 mt-2">{API_BASE}/health</p>
            </div>
          </div>
        ) : modelError ? (
          <div className="absolute inset-0 flex items-center justify-center p-8">
            <div className="text-center">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
              <p className="font-mono text-sm text-red-400 mb-2">Server Error</p>
              <p className="font-mono text-xs text-white/40">{modelError}</p>
              <p className="font-mono text-xs text-white/40 mt-2">Start: python yolo_server.py</p>
            </div>
          </div>
        ) : (
          <>
            <video ref={videoRef} className="hidden" playsInline muted autoPlay />

            {/* Display annotated image from server with boxes already drawn */}
            {annotatedImage ? (
              <img
                src={annotatedImage}
                alt="YOLO Detection"
                className="max-w-full max-h-full object-contain mx-auto"
                style={{ maxHeight: 'calc(100vh - 200px)' }}
              />
            ) : (
              <div className="flex items-center justify-center h-full">
                <div className="text-center">
                  <div className="w-20 h-20 rounded-full border-2 border-dashed border-white/20 flex items-center justify-center mx-auto mb-4">
                    <Camera className="w-8 h-8 text-white/20" />
                  </div>
                  <p className="font-mono text-sm text-white/60 mb-2">Camera Starting...</p>
                </div>
              </div>
            )}

            {!cameraActive && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/80">
                <div className="text-center">
                  <div className="w-20 h-20 rounded-full border-2 border-dashed border-white/20 flex items-center justify-center mx-auto mb-4">
                    <Camera className="w-8 h-8 text-white/20" />
                  </div>
                  <p className="font-mono text-sm text-white/60 mb-2">Camera Starting...</p>
                  {cameraError && <p className="font-mono text-xs text-red-400 mt-4 max-w-md">{cameraError}</p>}
                </div>
              </div>
            )}

            {cameraActive && detections.length > 0 && (
              <div className="absolute top-4 left-4 z-20 bg-black/70 backdrop-blur-sm px-3 py-1.5 rounded-full border border-white/10">
                <span className="font-mono text-xs text-white">
                  <span className="text-emerald-400">{detections.length}</span> objects detected
                </span>
              </div>
            )}

            {cameraActive && (
              <motion.div
                className="absolute left-0 right-0 h-[2px] bg-emerald-500/50 shadow-[0_0_15px_rgba(16,185,129,0.5)] z-20 pointer-events-none"
                animate={{ top: ['0%', '100%', '0%'] }}
                transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}
