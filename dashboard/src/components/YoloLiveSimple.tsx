import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Camera, X, AlertCircle } from 'lucide-react';
// @ts-ignore
import * as ort from 'onnxruntime-web';

interface Detection {
  className: string;
  confidence: number;
  bbox: { x1: number; y1: number; x2: number; y2: number };
}

const COCO_CLASSES = [
  'person', 'bicycle', 'car', 'motorcycle', 'airplane', 'bus', 'train', 'truck', 'boat',
  'traffic light', 'fire hydrant', 'stop sign', 'parking meter', 'bench', 'bird', 'cat',
  'dog', 'horse', 'sheep', 'cow', 'elephant', 'bear', 'zebra', 'giraffe', 'backpack',
  'umbrella', 'handbag', 'tie', 'suitcase', 'frisbee', 'skis', 'snowboard', 'sports ball',
  'kite', 'baseball bat', 'baseball glove', 'skateboard', 'surfboard', 'tennis racket',
  'bottle', 'wine glass', 'cup', 'fork', 'knife', 'spoon', 'bowl', 'banana', 'apple',
  'sandwich', 'orange', 'broccoli', 'carrot', 'hot dog', 'pizza', 'donut', 'cake', 'chair',
  'couch', 'potted plant', 'bed', 'dining table', 'toilet', 'tv', 'laptop', 'mouse',
  'remote', 'keyboard', 'cell phone', 'microwave', 'oven', 'toaster', 'sink', 'refrigerator',
  'book', 'clock', 'vase', 'scissors', 'teddy bear', 'hair drier', 'toothbrush'
];

const ALLOWED_CLASSES = ['person', 'chair', 'dining table', 'laptop', 'backpack', 'book', 'handbag', 'cell phone'];

export default function YoloLiveSimple() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sessionRef = useRef<ort.InferenceSession | null>(null);
  const animationRef = useRef<number>(0);
  const streamRef = useRef<MediaStream | null>(null);

  const [isModelLoading, setIsModelLoading] = useState(true);
  const [modelError, setModelError] = useState<string | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [detections, setDetections] = useState<Detection[]>([]);

  useEffect(() => {
    const loadModel = async () => {
      try {
        console.log('Loading ONNX model...');
        ort.env.wasm.numThreads = 4;
        sessionRef.current = await ort.InferenceSession.create('/yolov8n.onnx');
        console.log('Model loaded successfully!');
        setIsModelLoading(false);
      } catch (err) {
        console.error('Failed to load model:', err);
        setModelError('Failed to load detection model');
        setIsModelLoading(false);
      }
    };
    loadModel();
  }, []);

  const runInference = useCallback(async () => {
    if (!videoRef.current || !canvasRef.current || !sessionRef.current || !cameraActive) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    if (video.readyState < 2) {
      animationRef.current = requestAnimationFrame(runInference);
      return;
    }

    try {
      const vidWidth = video.videoWidth || 640;
      const vidHeight = video.videoHeight || 480;
      canvas.width = vidWidth;
      canvas.height = vidHeight;

      ctx.drawImage(video, 0, 0, vidWidth, vidHeight);

      const inputSize = 640;
      const inputTensor = new Float32Array(1 * 3 * inputSize * inputSize);
      const tempCanvas = document.createElement('canvas');
      tempCanvas.width = inputSize;
      tempCanvas.height = inputSize;
      const tempCtx = tempCanvas.getContext('2d')!;
      tempCtx.drawImage(video, 0, 0, inputSize, inputSize);
      const imgData = tempCtx.getImageData(0, 0, inputSize, inputSize);
      const pixels = imgData.data;

      for (let i = 0; i < inputSize * inputSize; i++) {
        const r = pixels[i * 4] / 255;
        const g = pixels[i * 4 + 1] / 255;
        const b = pixels[i * 4 + 2] / 255;
        inputTensor[i] = r;
        inputTensor[inputSize * inputSize + i] = g;
        inputTensor[2 * inputSize * inputSize + i] = b;
      }

      const feeds: Record<string, ort.Tensor> = {
        'images': new ort.Tensor('float32', inputTensor, [1, 3, inputSize, inputSize])
      };
      const results = await sessionRef.current.run(feeds);
      const output = results[0].data as Float32Array;

      const numAnchors = 8400;
      const numClasses = 80;
      const detectionResults: Detection[] = [];

      const scaleX = vidWidth / inputSize;
      const scaleY = vidHeight / inputSize;

      for (let i = 0; i < numAnchors; i++) {
        const offset = i * (numClasses + 4);
        let maxScore = 0;
        let maxClass = 0;
        for (let c = 0; c < numClasses; c++) {
          const score = output[offset + 4 + c];
          if (score > maxScore) {
            maxScore = score;
            maxClass = c;
          }
        }

        const confidence = 1 / (1 + Math.exp(-maxScore));
        if (confidence > 0.4) {
          const className = COCO_CLASSES[maxClass] || 'unknown';
          if (ALLOWED_CLASSES.includes(className)) {
            const bx = output[offset];
            const by = output[offset + 1];
            const bw = output[offset + 2];
            const bh = output[offset + 3];

            const x1 = (bx - bw / 2) * scaleX;
            const y1 = (by - bh / 2) * scaleY;
            const x2 = (bx + bw / 2) * scaleX;
            const y2 = (by + bh / 2) * scaleY;

            detectionResults.push({
              className,
              confidence: 1 / (1 + Math.exp(-confidence)),
              bbox: { x1: Math.max(0, x1), y1: Math.max(0, y1), x2: Math.min(vidWidth, x2), y2: Math.min(vidHeight, y2) }
            });
          }
        }
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(video, 0, 0, vidWidth, vidHeight);

      detectionResults.forEach((det) => {
        const { x1, y1, x2, y2 } = det.bbox;
        const width = x2 - x1;
        const height = y2 - y1;

        ctx.strokeStyle = '#FF0000';
        ctx.lineWidth = 3;
        ctx.strokeRect(x1, y1, width, height);

        const label = `${det.className} ${(det.confidence * 100).toFixed(0)}%`;
        ctx.font = 'bold 16px Arial';
        ctx.fillStyle = '#FF0000';
        ctx.fillRect(x1, y1 - 22, 140, 22);
        ctx.fillStyle = '#FFFFFF';
        ctx.fillText(label, x1 + 4, y1 - 6);
      });

      setDetections(detectionResults);

    } catch (err) {
      console.error('Inference error:', err);
    }

    animationRef.current = requestAnimationFrame(runInference);
  }, [cameraActive]);

  const startCamera = useCallback(() => {
    navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } }
    }).then((stream) => {
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
        setCameraActive(true);
        setCameraError(null);
      }
    }).catch((err) => {
      setCameraError(err.message);
    });
  }, []);

  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
    }
    setCameraActive(false);
  }, []);

  useEffect(() => {
    if (cameraActive) {
      runInference();
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
  }, [cameraActive, runInference]);

  return (
    <div className="flex-1 flex flex-col bg-black/40 rounded-2xl border border-white/10 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-white/10 bg-white/5">
        <div className="flex items-center gap-3">
          <div className={`p-2 rounded-lg ${cameraActive ? 'bg-emerald-500/20 text-emerald-400' : 'bg-white/10 text-white/40'}`}>
            <Camera className="w-5 h-5" />
          </div>
          <div>
            <h2 className="font-display text-lg text-white">Client-side YOLO Detection</h2>
            <p className="font-mono text-[10px] text-white/40">
              {cameraActive ? `${detections.length} objects` : 'Click Start'}
            </p>
          </div>
        </div>

        {!cameraActive ? (
          <button onClick={startCamera} disabled={isModelLoading}
            className="px-4 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 font-mono text-xs uppercase">
            <Camera className="w-4 h-4 inline mr-2" />Start
          </button>
        ) : (
          <button onClick={stopCamera}
            className="px-4 py-2 rounded-lg bg-white/10 hover:bg-white/20 text-white font-mono text-xs uppercase">
            <X className="w-4 h-4 inline mr-2" />Stop
          </button>
        )}
      </div>

      {/* Content */}
      <div className="relative bg-black" style={{ height: 'calc(100vh - 180px)' }}>
        {isModelLoading ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <div className="w-12 h-12 border-2 border-white/20 border-t-emerald-500 rounded-full animate-spin mx-auto mb-4" />
              <p className="font-mono text-sm text-white/60">Loading ONNX model...</p>
            </div>
          </div>
        ) : modelError ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="text-center">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-4" />
              <p className="font-mono text-sm text-red-400">{modelError}</p>
            </div>
          </div>
        ) : (
          <>
            <video ref={videoRef} className="hidden" playsInline muted autoPlay />
            <canvas ref={canvasRef} className="max-w-full max-h-full object-contain mx-auto" style={{ maxHeight: 'calc(100vh - 200px)' }} />
            {!cameraActive && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/80">
                <div className="text-center">
                  <Camera className="w-16 h-16 text-white/20 mx-auto mb-4" />
                  <p className="font-mono text-sm text-white/60">Click Start to begin</p>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
