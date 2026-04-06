"""
Accuracy monitor for YOLO training.
Tracks mAP metrics over time and logs progress.
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from rpi_simulator.config import METRICS_LOG, OUTPUT_DIR


class AccuracyMonitor:
    """Monitors and displays YOLO training accuracy metrics."""

    def __init__(self):
        self.history: List[Dict] = []
        self.current_run = 0
        self._load_history()

    def _load_history(self):
        """Load previous metrics history."""
        if Path(METRICS_LOG).exists():
            with open(METRICS_LOG, 'r') as f:
                for line in f:
                    try:
                        self.history.append(json.loads(line.strip()))
                    except Exception:
                        pass

    def add_metrics(self, metrics: Dict):
        """Add new metrics from a training run."""
        self.current_run += 1
        metrics["run"] = self.current_run
        self.history.append(metrics)

    def get_improvement(self) -> Optional[Dict]:
        """Calculate improvement between first and latest run."""
        if len(self.history) < 2:
            return None

        first = self.history[0]
        latest = self.history[-1]

        if "error" in first or "error" in latest:
            return None

        def get_map(m):
            return m.get("metrics/mAP50(B)") or m.get("metrics/mAP50-95(B)", 0)

        first_map = get_map(first)
        latest_map = get_map(latest)

        if first_map is None or latest_map is None:
            return None

        return {
            "first_mAP50": first_map,
            "latest_mAP50": latest_map,
            "absolute_improvement": latest_map - first_map,
            "relative_improvement_pct": ((latest_map - first_map) / (first_map + 1e-6)) * 100,
            "total_runs": len(self.history),
        }

    def print_summary(self):
        """Print a formatted summary of all training runs."""
        print("\n" + "=" * 70)
        print("YOLO TRAINING ACCURACY SUMMARY")
        print("=" * 70)

        if not self.history:
            print("No training runs recorded yet.")
            print("=" * 70)
            return

        print(f"{'Run':<6} {'Timestamp':<22} {'mAP50':<10} {'mAP50-95':<10} {'Time(s)':<10} {'Device':<8}")
        print("-" * 70)

        for m in self.history:
            if "error" in m:
                print(f"{m.get('run', '?'):<6} {m.get('timestamp', 'N/A')[:22]:<22} ERROR")
                continue

            ts = m.get('timestamp', 'N/A')
            if isinstance(ts, str) and len(ts) > 22:
                ts = ts[:22]

            map50 = m.get("metrics/mAP50(B)", m.get("metrics/mAP50-95(B)", "N/A"))
            map50_95 = m.get("metrics/mAP50-95(B)", "N/A")
            train_time = m.get("training_time_seconds", "N/A")
            device = m.get("device", "N/A")

            if isinstance(map50, float):
                map50 = f"{map50:.4f}"
            if isinstance(map50_95, float):
                map50_95 = f"{map50_95:.4f}"
            if isinstance(train_time, float):
                train_time = f"{train_time:.1f}s"

            print(f"{m.get('run', '?'):<6} {ts:<22} {map50:<10} {map50_95:<10} {train_time:<10} {device:<8}")

        # Print improvement
        improvement = self.get_improvement()
        if improvement:
            print("-" * 70)
            print(f"Improvement: {improvement['absolute_improvement']:+.4f} mAP50 "
                  f"({improvement['relative_improvement_pct']:+.1f}%) "
                  f"over {improvement['total_runs']} runs")

        # Per-class performance
        latest = self.history[-1]
        if "per_class_ap50" in latest and "error" not in latest:
            print("-" * 70)
            print("Per-Class AP50:")
            from config import CLASS_NAMES
            per_class = latest["per_class_ap50"]
            for i, ap in enumerate(per_class):
                cls_name = CLASS_NAMES[i] if i < len(CLASS_NAMES) else f"class_{i}"
                bar = "█" * int(ap * 20) + "░" * (20 - int(ap * 20))
                print(f"  {cls_name:<12}: {bar} {ap:.3f}")

        print("=" * 70)

    def print_current_status(self):
        """Print current status (run number, latest mAP, training state)."""
        latest = self.history[-1] if self.history else {}

        if "error" in latest:
            print(f"[MONITOR] Run #{self.current_run} - ERROR: {latest['error']}")
            return

        map50 = latest.get("metrics/mAP50(B)", "N/A")
        map50_95 = latest.get("metrics/mAP50-95(B)", "N/A")

        if isinstance(map50, float):
            map50 = f"{map50:.4f}"
        if isinstance(map50_95, float):
            map50_95 = f"{map50_95:.4f}"

        print(f"[MONITOR] Run #{self.current_run} | mAP50: {map50} | mAP50-95: {map50_95}")

    def should_continue_training(self, target_map: float = 0.75, max_runs: int = 10) -> bool:
        """Simple heuristic: should we train more?"""
        if self.current_run >= max_runs:
            return False

        if len(self.history) < 2:
            return True

        latest = self.history[-1]
        if "error" in latest:
            return True

        map50 = latest.get("metrics/mAP50(B)", 0)
        if map50 >= target_map:
            return False

        # Check if improving
        improvement = self.get_improvement()
        if improvement and improvement["relative_improvement_pct"] < 1.0:
            # Not improving much, might be saturating
            if map50 > 0.6:
                return False

        return True
