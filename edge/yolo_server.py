import io
import base64
import json
import logging
import threading
from flask import Flask, request, jsonify
from flask_cors import CORS
from PIL import Image
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

model = None

def load_model():
    global model
    try:
        from ultralytics import YOLO
        logger.info("Loading YOLOv8n model with MPS acceleration...")
        model = YOLO('yolov8n.pt')
        try:
            test_result = model.predict(np.zeros((640, 640, 3), dtype=np.uint8), device='mps', verbose=False)
            logger.info("MPS (Metal GPU) acceleration enabled!")
        except Exception as e:
            logger.warning(f"MPS not available, falling back to CPU: {e}")
            logger.info("Using CPU for inference")
        logger.info("YOLOv8n model loaded successfully!")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        try:
            logger.info("Downloading YOLOv8n model...")
            model = YOLO('yolov8n.pt')
        except:
            logger.warning("Could not load YOLOv8n, will use placeholder responses")

@app.route('/detect', methods=['POST'])
def detect():
    if model is None:
        return jsonify({'error': 'Model not loaded', 'detections': [], 'image': None}), 500

    try:
        data = request.get_json()
        if not data or 'image' not in data:
            return jsonify({'error': 'No image provided'}), 400

        image_data = base64.b64decode(data['image'].split(',')[1] if ',' in data['image'] else data['image'])
        image = Image.open(io.BytesIO(image_data)).convert('RGB')
        img_array = np.array(image)

        results = model(img_array, device='mps', verbose=False, conf=0.4, iou=0.45)

        detections = []
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                class_name = result.names[cls]

                allowed = ['person', 'chair', 'dining table', 'laptop', 'backpack', 'book', 'handbag', 'cell phone']
                if class_name in allowed:
                    detections.append({
                        'className': class_name,
                        'confidence': conf,
                        'bbox': {
                            'x1': float(x1),
                            'y1': float(y1),
                            'x2': float(x2),
                            'y2': float(y2)
                        }
                    })

        annotated_img = results[0].plot()
        annotated_pil = Image.fromarray(annotated_img)

        buffer = io.BytesIO()
        annotated_pil.save(buffer, format='JPEG', quality=85)
        annotated_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        return jsonify({
            'detections': detections,
            'count': len(detections),
            'image': f'data:image/jpeg;base64,{annotated_base64}'
        })

    except Exception as e:
        logger.error(f"Detection error: {e}")
        return jsonify({'error': str(e), 'detections': [], 'image': None}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'model_loaded': model is not None
    })

@app.route('/classes', methods=['GET'])
def classes():
    if model is None:
        return jsonify({'error': 'Model not loaded'}), 500
    return jsonify({
        'classes': list(model.names.values()),
        'filtered': ['person', 'chair', 'dining table', 'laptop', 'backpack', 'book', 'handbag', 'cell phone']
    })

if __name__ == '__main__':
    threading.Thread(target=load_model, daemon=True).start()

    logger.info("Starting YOLO Detection Server on port 5003...")
    app.run(host='0.0.0.0', port=5003, debug=False, threaded=True)