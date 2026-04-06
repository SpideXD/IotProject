"""
YOLO trainer with incremental learning support.
Fine-tunes YOLOv8 on synthetic Unity data with MPS (M2 GPU) support.
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import torch
from ultralytics import YOLO

from rpi_simulator.config import (
    YOLO_MODEL, BATCH_SIZE, IMAGE_SIZE, NUM_EPOCHS, PATIENCE,
    MODEL_PATH, OUTPUT_DIR, DATA_YAML, CLASS_NAMES, NUM_CLASSES,
    METRICS_LOG, SYNTHETIC_DATA_ROOT
)


class YOLOTrainer:
    """Handles YOLO training with metrics tracking."""

    def __init__(self, model_name: str = YOLO_MODEL):
        self.model_name = model_name
        self.model: Optional[YOLO] = None
        self.best_model_path: Optional[str] = None
        self.metrics_history: List[Dict] = []
        self.device = self._get_device()
        self.is_training = False
        self.last_train_time: Optional[float] = None

    def _get_device(self) -> str:
        """Determine best available device."""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        else:
            return "cpu"

    def load_or_create_model(self, weights_path: Optional[str] = None) -> YOLO:
        """Load existing model or create new from pretrained."""
        if weights_path and Path(weights_path).exists():
            self.model = YOLO(weights_path)
            print(f"[YOLO] Loaded model from {weights_path}")
        else:
            self.model = YOLO(self.model_name)
            print(f"[YOLO] Created new model from {self.model_name}")

        self.model.to(self.device)
        return self.model

    def train(
        self,
        data_yaml: str,
        epochs: int = NUM_EPOCHS,
        batch: int = BATCH_SIZE,
        imgsz: int = IMAGE_SIZE,
        patience: int = PATIENCE,
        project: str = OUTPUT_DIR,
        name: str = "train",
        exist_ok: bool = True,
    ) -> Dict:
        """
        Train YOLO model. Returns metrics dictionary.
        """
        if self.model is None:
            self.load_or_create_model()

        self.is_training = True
        start_time = time.time()

        print(f"[YOLO] Starting training on {self.device}")
        print(f"[YOLO] Dataset: {data_yaml}")
        print(f"[YOLO] Epochs: {epochs}, Batch: {batch}, Image size: {imgsz}")
        print(f"[YOLO] Classes: {CLASS_NAMES}")

        try:
            results = self.model.train(
                data=data_yaml,
                epochs=epochs,
                batch=batch,
                imgsz=imgsz,
                patience=patience,
                project=project,
                name=name,
                exist_ok=exist_ok,
                device=self.device,
                verbose=True,
                # YOLO args
                optimizer="AdamW",
                lr0=0.001,
                lrf=0.01,
                warmup_epochs=3,
                close_mosaic=10,
                amp=True,  # Automatic Mixed Precision for M2 MPS
                save=True,
                save_period=10,
                plots=True,
            )

            # Extract metrics
            metrics = self._extract_metrics(results)
            self.last_train_time = time.time() - start_time
            metrics["training_time_seconds"] = self.last_train_time
            metrics["device"] = self.device

            # Find best model path
            runs_dir = Path(project) / name
            best_pt = runs_dir / "weights" / "best.pt"
            last_pt = runs_dir / "weights" / "last.pt"

            if best_pt.exists():
                self.best_model_path = str(best_pt)
                # Copy to standard path
                import shutil
                shutil.copy2(best_pt, MODEL_PATH)
                print(f"[YOLO] Best model saved to {MODEL_PATH}")
            elif last_pt.exists():
                self.best_model_path = str(last_pt)
                import shutil
                shutil.copy2(last_pt, MODEL_PATH)

            self.metrics_history.append(metrics)
            self._save_metrics(metrics)

            print(f"[YOLO] Training complete in {self.last_train_time:.1f}s")
            print(f"[YOLO] Best mAP50: {metrics.get('metrics/mAP50(B)', 'N/A'):.4f}")
            print(f"[YOLO] Best mAP50-95: {metrics.get('metrics/mAP50-95(B)', 'N/A'):.4f}")

        except Exception as e:
            print(f"[YOLO] Training error: {e}")
            metrics = {"error": str(e), "training_time_seconds": time.time() - start_time}
            self.metrics_history.append(metrics)

        finally:
            self.is_training = False

        return metrics

    def _extract_metrics(self, results) -> Dict:
        """Extract metrics from training results."""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "epochs_trained": NUM_EPOCHS,
        }

        try:
            # From results.metrics
            if hasattr(results, 'metrics'):
                m = results.metrics
                metrics["metrics/mAP50(B)"] = getattr(m, 'map50', None) or getattr(m, 'mAP50', None)
                metrics["metrics/mAP50-95(B)"] = getattr(m, 'map', None) or getattr(m, 'mAP50-95', None)
                metrics["metrics/precision(B)"] = getattr(m, 'precision', None)
                metrics["metrics/recall(B)"] = getattr(m, 'recall', None)

            # From results.results_dict
            if hasattr(results, 'results_dict') and results.results_dict:
                rd = results.results_dict
                metrics["metrics/mAP50(B)"] = rd.get('metrics/mAP50(B)', metrics.get("metrics/mAP50(B)"))
                metrics["metrics/mAP50-95(B)"] = rd.get('metrics/mAP50-95(B)', metrics.get("metrics/mAP50-95(B)"))

            # Per-class AP if available
            if hasattr(results, 'box'):
                box = results.box
                if hasattr(box, 'ap50'):
                    metrics["per_class_ap50"] = box.ap50.tolist()
                if hasattr(box, 'ap'):
                    metrics["per_class_ap"] = box.ap.tolist()

            # Clean None values
            metrics = {k: v for k, v in metrics.items() if v is not None}

        except Exception as e:
            print(f"[YOLO] Error extracting metrics: {e}")

        return metrics

    def _save_metrics(self, metrics: Dict):
        """Append metrics to log file."""
        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        with open(METRICS_LOG, 'a') as f:
            f.write(json.dumps(metrics) + "\n")

    def load_metrics_history(self) -> List[Dict]:
        """Load all previous metrics from log."""
        if not Path(METRICS_LOG).exists():
            return []
        history = []
        with open(METRICS_LOG, 'r') as f:
            for line in f:
                try:
                    history.append(json.loads(line.strip()))
                except Exception:
                    pass
        return history

    def validate(self, data_yaml: str = DATA_YAML) -> Dict:
        """Run validation on current model."""
        if self.model is None:
            self.load_or_create_model()

        results = self.model.val(data=data_yaml, device=self.device, verbose=False)
        return self._extract_metrics(results)

    def export(self, format: str = "onnx") -> str:
        """Export model to different format."""
        if self.model is None:
            self.load_or_create_model()

        export_path = self.model.export(format=format)
        return export_path

    def get_model_info(self) -> Dict:
        """Return current model information."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "best_weights": self.best_model_path,
            "is_training": self.is_training,
            "last_train_time": self.last_train_time,
            "total_runs": len(self.metrics_history),
            "classes": CLASS_NAMES,
            "num_classes": NUM_CLASSES,
        }
