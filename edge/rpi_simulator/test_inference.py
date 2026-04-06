#!/usr/bin/env python3
"""
Test YOLO inference on synthetic test images.
Can use either COCO pre-trained or our trained model.

Usage:
    python test_inference.py                          # Use COCO pretrained
    python test_inference.py --model best.pt          # Use trained model
    python test_inference.py --model best.pt --show  # Show results
"""
import argparse
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ultralytics import YOLO

# Test images
TEST_IMAGES = "/Users/agentswarm/Desktop/IotProject/edge/rpi_simulator/synthetic_data_v3/images"
TRAINED_MODEL = "/Users/agentswarm/Desktop/IotProject/edge/rpi_simulator/yolov8s_trained.pt"
VISDRONE_MODEL = "/Users/agentswarm/Desktop/IotProject/edge/rpi_simulator/yolov8s_visdrone.pt"


def test_model(model_path, show=False, limit=10):
    """Test YOLO model on test images."""

    print(f"\n{'='*60}")
    print(f"Testing: {model_path}")
    print(f"{'='*60}")

    if not os.path.exists(model_path):
        print(f"Model not found: {model_path}")
        return

    model = YOLO(model_path)

    # Get test images
    images = sorted([f for f in os.listdir(TEST_IMAGES) if f.endswith('.png')])[:limit]

    if not images:
        print(f"No images found in {TEST_IMAGES}")
        return

    print(f"Testing on {len(images)} images...\n")

    total_gt = 0
    total_detected = 0
    total_correct = 0

    for img_name in images:
        img_path = os.path.join(TEST_IMAGES, img_name)

        # Load label to get ground truth
        label_path = img_path.replace('.png', '.txt').replace('/images/', '/labels/')
        gt_count = 0
        if os.path.exists(label_path):
            with open(label_path) as f:
                lines = f.readlines()
            # Count person (class 0)
            gt_count = sum(1 for l in lines if l.strip() and l.split()[0] == '0')

        # Run inference
        results = model(img_path, verbose=False)

        # Count detections (person class = 0)
        detected = 0
        for r in results:
            if r.boxes is not None:
                for box in r.boxes:
                    if int(box.cls[0]) == 0:  # person
                        detected += 1

        # Calculate accuracy metrics
        tp = min(gt_count, detected)
        fp = max(0, detected - gt_count)
        fn = max(0, gt_count - detected)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0

        total_gt += gt_count
        total_detected += detected
        total_correct += tp

        print(f"{img_name}: GT={gt_count}, Detected={detected}, P={precision:.2f}, R={recall:.2f}")

        # Show results
        if show:
            results[0].show()
            results[0].save(str(img_path).replace('.png', '_result.png'))

    # Overall metrics
    print(f"\n{'='*60}")
    print("OVERALL METRICS")
    print(f"{'='*60}")
    print(f"Total Ground Truth: {total_gt}")
    print(f"Total Detected: {total_detected}")

    if total_gt > 0:
        print(f"Recall: {total_correct/total_gt:.2%}")
    if total_detected > 0:
        print(f"Precision: {total_correct/total_detected:.2%}")

    # mAP would require full validation run
    print(f"\nFor full mAP50, run: model.val()")


def main():
    parser = argparse.ArgumentParser(description="Test YOLO on synthetic images")
    parser.add_argument("--model", type=str, default=None,
                        help="Path to model weights (default: COCO pretrained)")
    parser.add_argument("--show", action="store_true",
                        help="Show detection results")
    parser.add_argument("--limit", type=int, default=10,
                        help="Number of images to test")
    args = parser.parse_args()

    # Use specified model or COCO pretrained
    if args.model:
        model_path = args.model
    else:
        # Use our trained model if exists, else COCO
        if os.path.exists(TRAINED_MODEL):
            model_path = TRAINED_MODEL
            print(f"Using trained model: {model_path}")
        elif os.path.exists(VISDRONE_MODEL):
            model_path = VISDRONE_MODEL
            print(f"Using VisDrone model: {model_path}")
        else:
            model_path = "yolov8s.pt"  # COCO pretrained
            print("Using COCO pretrained model")

    test_model(model_path, show=args.show, limit=args.limit)


if __name__ == "__main__":
    main()
