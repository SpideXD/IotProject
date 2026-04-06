"""
Manages synthetic images and YOLO format labels.
Handles conversion from Unity ground truth to YOLO format.
"""
import json
import os
import shutil
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from rpi_simulator.config import (
    IMAGES_DIR, LABELS_DIR, DATA_YAML, NUM_CLASSES,
    CLASS_NAMES, CLASS_TO_ID, MAX_TRAINING_IMAGES
)


class UnityLabelFormat:
    """
    Expected Unity label format (exported from Unity C# script):
    {
        "frame_id": "Rail_Back_001",
        "timestamp": 1234567890.123,
        "width": 256,
        "height": 256,
        "objects": [
            {
                "class": "person",
                "bbox": [x_min, y_min, x_max, y_max],  # normalized 0-1
                "seat_id": "S1"
            },
            ...
        ]
    }
    """

    @classmethod
    def parse_file(cls, label_path: Path) -> Optional[Dict]:
        try:
            with open(label_path, 'r') as f:
                return json.load(f)
        except Exception:
            return None

    @classmethod
    def to_yolo_format(cls, unity_data: Dict, img_width: int, img_height: int) -> List[str]:
        """Convert Unity label to YOLO .txt format (class x_center y_center width height)"""
        yolo_lines = []
        for obj in unity_data.get("objects", []):
            cls_name = obj.get("cls", "")
            if cls_name not in CLASS_TO_ID:
                continue  # Skip unknown classes

            cls_id = CLASS_TO_ID[cls_name]
            x_min, y_min, x_max, y_max = obj["bbox"]

            # Convert to YOLO format (normalized 0-1)
            x_center = (x_min + x_max) / 2.0
            y_center = (y_min + y_max) / 2.0
            width = x_max - x_min
            height = y_max - y_min

            yolo_lines.append(f"{cls_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")

        return yolo_lines


class DatasetManager:
    """Manages the synthetic dataset for YOLO training."""

    def __init__(self):
        self.images_dir = Path(IMAGES_DIR)
        self.labels_dir = Path(LABELS_DIR)
        self._ensure_dirs()
        self._processed_files: set = set()

    def _ensure_dirs(self):
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.labels_dir.mkdir(parents=True, exist_ok=True)

    def get_image_count(self) -> int:
        """Returns count of processed images."""
        return len(self._processed_files)

    def get_pending_count(self) -> int:
        """Returns count of unprocessed label files."""
        label_files = list(self.labels_dir.glob("*.json"))
        return len([f for f in label_files if f.stem not in self._processed_files])

    def process_pending_labels(self) -> int:
        """
        Process any pending Unity label JSON files and convert to YOLO format.
        Returns number of newly processed files.
        """
        label_files = list(self.labels_dir.glob("*.json"))
        new_count = 0

        for label_path in label_files:
            if label_path.stem in self._processed_files:
                continue

            unity_data = UnityLabelFormat.parse_file(label_path)
            if unity_data is None:
                continue

            # Check if corresponding image exists
            img_name = label_path.stem
            img_extensions = ['.png', '.jpg', '.jpeg']
            img_found = any((self.images_dir / f"{img_name}{ext}").exists() for ext in img_extensions)

            if not img_found:
                continue

            # Convert to YOLO format
            width = unity_data.get("width", 640)
            height = unity_data.get("height", 640)
            yolo_lines = UnityLabelFormat.to_yolo_format(unity_data, width, height)

            # Write YOLO label file
            yolo_path = self.labels_dir / f"{img_name}.txt"
            with open(yolo_path, 'w') as f:
                f.write('\n'.join(yolo_lines))

            self._processed_files.add(label_path.stem)
            new_count += 1

        return new_count

    @staticmethod
    def merge_datasets(source_folders: list, output_folder: str) -> dict:
        """
        Merge multiple dataset folders into one combined dataset.
        Returns stats about the merged dataset.
        """
        import shutil

        merged_images_dir = Path(output_folder) / "images"
        merged_labels_dir = Path(output_folder) / "labels"
        merged_images_dir.mkdir(parents=True, exist_ok=True)
        merged_labels_dir.mkdir(parents=True, exist_ok=True)

        total_images = 0
        total_labels = 0
        skipped = 0

        for source_folder in source_folders:
            src_images = Path(source_folder) / "images"
            src_labels = Path(source_folder) / "labels"

            if not src_images.exists():
                continue

            for img_path in src_images.glob("*"):
                if img_path.suffix.lower() not in ['.png', '.jpg', '.jpeg']:
                    continue

                stem = img_path.stem
                txt_path = src_labels / f"{stem}.txt"
                json_path = src_labels / f"{stem}.json"

                # Check if we have labels
                if not txt_path.exists() and not json_path.exists():
                    skipped += 1
                    continue

                # Copy image
                dest_img = merged_images_dir / img_path.name
                if not dest_img.exists():
                    shutil.copy2(img_path, dest_img)
                    total_images += 1

                # Copy label
                if json_path.exists():
                    dest_json = merged_labels_dir / json_path.name
                    if not dest_json.exists():
                        shutil.copy2(json_path, dest_json)
                        total_labels += 1
                if txt_path.exists():
                    dest_txt = merged_labels_dir / f"{stem}.txt"
                    if not dest_txt.exists():
                        shutil.copy2(txt_path, dest_txt)
                        total_labels += 1

        return {
            "total_images": total_images,
            "total_labels": total_labels,
            "skipped": skipped,
            "output_folder": output_folder
        }

    def create_dataset_yaml(self, train_split: float = 0.8) -> str:
        """
        Creates dataset.yaml for YOLO training.
        Splits images into train/val sets.
        """
        image_files = []
        for ext in ['.png', '.jpg', '.jpeg']:
            image_files.extend(list(self.images_dir.glob(f"*{ext}")))

        # Filter to only images that have corresponding label files
        valid_images = []
        for img_path in image_files:
            label_path = self.labels_dir / f"{img_path.stem}.txt"
            if label_path.exists():
                valid_images.append(img_path)

        if len(valid_images) == 0:
            raise ValueError("No valid image-label pairs found!")

        # Limit dataset size (remove oldest if too large)
        if len(valid_images) > MAX_TRAINING_IMAGES:
            # Sort by modification time, keep newest
            valid_images.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            valid_images = valid_images[:MAX_TRAINING_IMAGES]

        # Shuffle and split
        random.shuffle(valid_images)
        split_idx = int(len(valid_images) * train_split)
        train_images = valid_images[:split_idx]
        val_images = valid_images[split_idx:]

        # Create symlinks or copy to train/val folders
        train_dir = self.images_dir.parent / "images" / "train"
        val_dir = self.images_dir.parent / "images" / "val"
        train_labels_dir = self.labels_dir.parent / "labels" / "train"
        val_labels_dir = self.labels_dir.parent / "labels" / "val"

        for d in [train_dir, val_dir, train_labels_dir, val_labels_dir]:
            d.mkdir(parents=True, exist_ok=True)

        self._link_or_copy(train_images, train_dir, train_labels_dir)
        self._link_or_copy(val_images, val_dir, val_labels_dir)

        # Write dataset.yaml
        yaml_content = f"""
path: {self.images_dir.parent}
train: images/train
val: images/val
names:
"""
        for i, name in enumerate(CLASS_NAMES):
            yaml_content += f"  {i}: {name}\n"

        with open(DATA_YAML, 'w') as f:
            f.write(yaml_content.strip())

        return DATA_YAML

    def _link_or_copy(self, image_paths: List[Path], dest_img_dir: Path, dest_lbl_dir: Path):
        """Link or copy images and their corresponding labels."""
        for img_path in image_paths:
            # Link image
            dest_img = dest_img_dir / img_path.name
            if not dest_img.exists():
                try:
                    os.link(img_path, dest_img)  # Hard link (fast)
                except OSError:
                    shutil.copy2(img_path, dest_img)  # Copy if link fails

            # Link label
            lbl_path = self.labels_dir / f"{img_path.stem}.txt"
            if lbl_path.exists():
                dest_lbl = dest_lbl_dir / lbl_path.name
                if not dest_lbl.exists():
                    try:
                        os.link(lbl_path, dest_lbl)
                    except OSError:
                        shutil.copy2(lbl_path, dest_lbl)

    def get_stats(self) -> Dict:
        """Returns dataset statistics."""
        image_files = []
        for ext in ['.png', '.jpg', '.jpeg']:
            image_files.extend(list(self.images_dir.glob(f"*{ext}")))
        return {
            "total_images": len(image_files),
            "processed_labels": len(self._processed_files),
            "pending_labels": self.get_pending_count(),
        }
