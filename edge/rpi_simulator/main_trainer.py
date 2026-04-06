#!/usr/bin/env python3
"""
Main training orchestrator for YOLO on synthetic Unity data.
Watches for new images, triggers training, monitors accuracy.

Usage:
    python main_trainer.py                    # Start monitoring + training
    python main_trainer.py --once            # Train once with current data
    python main_trainer.py --status          # Show current status
    python main_trainer.py --validate        # Validate current model
"""
import argparse
import os
import sys
import time
import signal
import threading
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rpi_simulator.config import (
    IMAGES_DIR, LABELS_DIR, WATCH_INTERVAL,
    MIN_NEW_IMAGES_TO_TRAIN, TRAIN_EVERY_N_IMAGES,
    MODEL_PATH, NUM_EPOCHS, YOLO_MODEL
)
from rpi_simulator.dataset_manager import DatasetManager
from rpi_simulator.yolo_trainer import YOLOTrainer
from rpi_simulator.monitor import AccuracyMonitor


class TrainingOrchestrator:
    """Orchestrates continuous YOLO training on synthetic data."""

    def __init__(self):
        self.dataset = DatasetManager()
        self.trainer = YOLOTrainer()
        self.monitor = AccuracyMonitor()
        self.running = False
        self.train_thread: threading.Thread = None
        self.last_trained_count = 0

        # Load existing model if available
        if os.path.exists(MODEL_PATH):
            self.trainer.load_or_create_model(MODEL_PATH)

    def train_once(self) -> bool:
        """Run one training session with current dataset."""
        print(f"\n[TRAINER] Processing pending labels...")
        new_count = self.dataset.process_pending_labels()
        print(f"[TRAINER] New labels processed: {new_count}")

        stats = self.dataset.get_stats()
        print(f"[TRAINER] Dataset stats: {stats}")

        total_images = stats["total_images"]
        if total_images < MIN_NEW_IMAGES_TO_TRAIN:
            print(f"[TRAINER] Not enough images ({total_images}/{MIN_NEW_IMAGES_TO_TRAIN}). "
                  f"Need more Unity samples first.")
            return False

        # Check if we have enough NEW images since last training
        if total_images <= self.last_trained_count and self.last_trained_count > 0:
            print(f"[TRAINER] No new images since last training. "
                  f"(Total: {total_images}, Last trained: {self.last_trained_count})")
            return False

        print(f"[TRAINER] Creating dataset YAML...")
        try:
            yaml_path = self.dataset.create_dataset_yaml()
        except ValueError as e:
            print(f"[TRAINER] Dataset error: {e}")
            return False

        print(f"[TRAINER] Starting YOLO training...")
        metrics = self.trainer.train(
            data_yaml=yaml_path,
            epochs=NUM_EPOCHS,
            name=f"run_{int(time.time())}",
        )

        self.monitor.add_metrics(metrics)
        self.last_trained_count = total_images

        print(f"\n[TRAINER] Training complete!")
        self.monitor.print_summary()

        return "error" not in metrics

    def validate(self) -> bool:
        """Validate current model on dataset."""
        self.dataset.process_pending_labels()
        stats = self.dataset.get_stats()

        if stats["total_images"] < 10:
            print(f"[VALIDATE] Not enough images ({stats['total_images']}/10)")
            return False

        try:
            yaml_path = self.dataset.create_dataset_yaml()
        except ValueError as e:
            print(f"[VALIDATE] Dataset error: {e}")
            return False

        print(f"[VALIDATE] Running validation...")
        metrics = self.trainer.validate(yaml_path)

        print(f"\n[VALIDATE] Validation Results:")
        map50 = metrics.get("metrics/mAP50(B)", "N/A")
        map50_95 = metrics.get("metrics/mAP50-95(B)", "N/A")
        if isinstance(map50, float):
            map50 = f"{map50:.4f}"
        if isinstance(map50_95, float):
            map50_95 = f"{map50_95:.4f}"
        print(f"  mAP50: {map50}")
        print(f"  mAP50-95: {map50_95}")

        return True

    def watch_loop(self):
        """Main loop: watch for new images and train when ready."""
        print(f"[WATCHER] Starting training watcher...")
        print(f"[WATCHER] Watching: {IMAGES_DIR}")
        print(f"[WATCHER] Will train every {TRAIN_EVERY_N_IMAGES} new images")
        print(f"[WATCHER] Min images to train: {MIN_NEW_IMAGES_TO_TRAIN}")
        print(f"[WATCHER] Press Ctrl+C to stop")
        print()

        self.monitor.print_summary()

        while self.running:
            try:
                # Process any new labels
                new_labels = self.dataset.process_pending_labels()
                if new_labels > 0:
                    print(f"[WATCHER] Processed {new_labels} new labels")

                stats = self.dataset.get_stats()
                pending = stats["pending_labels"]

                # Calculate new images since last training
                new_since_train = stats["total_images"] - self.last_trained_count

                print(f"[WATCHER] Total: {stats['total_images']} images, "
                      f"{pending} pending, "
                      f"{new_since_train} new since last train | "
                      f"Model: {'Ready' if os.path.exists(MODEL_PATH) else 'Not trained yet'}")

                # Check if we should train
                should_train = (
                    stats["total_images"] >= MIN_NEW_IMAGES_TO_TRAIN and
                    new_since_train >= TRAIN_EVERY_N_IMAGES
                )

                if should_train and not self.trainer.is_training:
                    print(f"\n[WATCHER] Triggering training ({new_since_train} new images)...")
                    success = self.train_once()

                    if not success:
                        print(f"[WATCHER] Training failed or not enough data")

                # Show accuracy trend every loop
                if os.path.exists(MODEL_PATH):
                    self.monitor.print_current_status()

                time.sleep(WATCH_INTERVAL)

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[WATCHER] Error in watch loop: {e}")
                time.sleep(WATCH_INTERVAL)

        print(f"[WATCHER] Stopped.")

    def start_background_training(self):
        """Start training in background thread."""
        self.running = True
        self.train_thread = threading.Thread(target=self.watch_loop, daemon=True)
        self.train_thread.start()
        print(f"[ORCHESTRATOR] Background training started")

    def stop(self):
        """Stop background training."""
        self.running = False
        if self.train_thread:
            self.train_thread.join(timeout=5)
        print(f"[ORCHESTRATOR] Stopped.")


def main():
    parser = argparse.ArgumentParser(description="YOLO Training Orchestrator")
    parser.add_argument("--once", action="store_true", help="Train once with current data and exit")
    parser.add_argument("--status", action="store_true", help="Show training status and exit")
    parser.add_argument("--validate", action="store_true", help="Validate current model and exit")
    parser.add_argument("--watch", action="store_true", help="Watch for new images and train continuously")
    args = parser.parse_args()

    orchestrator = TrainingOrchestrator()

    # Handle signals for graceful shutdown
    def signal_handler(sig, frame):
        print("\n[ORCHESTRATOR] Received shutdown signal...")
        orchestrator.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    if args.status:
        orchestrator.monitor.print_summary()
        stats = orchestrator.dataset.get_stats()
        print(f"\nDataset: {stats['total_images']} images")
        print(f"Model: {'Trained' if os.path.exists(MODEL_PATH) else 'Not trained yet'}")
        return

    if args.validate:
        orchestrator.validate()
        return

    if args.once:
        success = orchestrator.train_once()
        sys.exit(0 if success else 1)

    # Default: watch mode
    print("""
╔══════════════════════════════════════════════════════════════╗
║     YOLO Training Orchestrator - Synthetic Unity Data        ║
╠══════════════════════════════════════════════════════════════╣
║  Unity generates images ─► Training triggers automatically   ║
║  MPS GPU acceleration (Apple M2)                             ║
║  Metrics tracked over time                                    ║
╚══════════════════════════════════════════════════════════════╝
""")
    orchestrator.start_background_training()

    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        orchestrator.stop()


if __name__ == "__main__":
    main()
