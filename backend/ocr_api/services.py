from __future__ import annotations

import base64
import io
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

# Disable experimental PIR engine which is unstable on some Windows environments
os.environ['FLAGS_enable_pir_api'] = '0'

from paddleocr import PaddleOCR
from ultralytics import YOLO


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_YOLO_MODEL_PATH = PROJECT_ROOT / 'models' / 'license_plate_detector.pt'
PLATE_CLASS_HINTS = {
    'license_plate',
    'licence_plate',
    'plate',
    'number_plate',
    'registration_plate',
    'car_plate',
}


@lru_cache(maxsize=1)
def get_ocr_engine() -> PaddleOCR:
    return PaddleOCR(
        lang='en',
        device='cpu',
        enable_mkldnn=False,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
    )


@lru_cache(maxsize=1)
def get_plate_detector() -> YOLO:
    model_path = Path(os.environ.get('YOLO_MODEL_PATH', str(DEFAULT_YOLO_MODEL_PATH))).expanduser()
    if not model_path.exists():
        raise FileNotFoundError(
            'YOLO plate detector model was not found. '
            f'Expected a local model at "{model_path}" or set YOLO_MODEL_PATH to your trained plate model.'
        )
    return YOLO(str(model_path))


@lru_cache(maxsize=1)
def get_plate_class_names() -> set[str]:
    raw_value = os.environ.get('YOLO_PLATE_CLASS_NAMES', '')
    if not raw_value.strip():
        return set(PLATE_CLASS_HINTS)
    return {item.strip().lower() for item in raw_value.split(',') if item.strip()}


@lru_cache(maxsize=1)
def get_yolo_confidence_threshold() -> float:
    raw_value = os.environ.get('YOLO_CONFIDENCE', '0.25')
    try:
        parsed = float(raw_value)
    except ValueError as exc:
        raise ValueError('YOLO_CONFIDENCE must be a valid float.') from exc
    return min(max(parsed, 0.0), 1.0)


@lru_cache(maxsize=1)
def get_crop_padding_ratio() -> float:
    raw_value = os.environ.get('YOLO_CROP_PADDING_RATIO', '0.08')
    try:
        parsed = float(raw_value)
    except ValueError as exc:
        raise ValueError('YOLO_CROP_PADDING_RATIO must be a valid float.') from exc
    return max(parsed, 0.0)


@lru_cache(maxsize=1)
def get_max_crop_dimension() -> int:
    raw_value = os.environ.get('OCR_MAX_CROP_DIMENSION', '1200')
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ValueError('OCR_MAX_CROP_DIMENSION must be a valid integer.') from exc
    return max(parsed, 256)


@lru_cache(maxsize=1)
def get_output_image_quality() -> int:
    raw_value = os.environ.get('OCR_OUTPUT_IMAGE_QUALITY', '90')
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ValueError('OCR_OUTPUT_IMAGE_QUALITY must be a valid integer.') from exc
    return min(max(parsed, 50), 95)


@lru_cache(maxsize=1)
def get_preprocess_scale_factor() -> float:
    raw_value = os.environ.get('OCR_PREPROCESS_SCALE_FACTOR', '2.0')
    try:
        parsed = float(raw_value)
    except ValueError as exc:
        raise ValueError('OCR_PREPROCESS_SCALE_FACTOR must be a valid float.') from exc
    return max(parsed, 1.0)


@lru_cache(maxsize=1)
def should_use_grayscale_preprocess() -> bool:
    return os.environ.get('OCR_USE_GRAYSCALE_PREPROCESS', '1').strip().lower() not in {'0', 'false', 'no'}


@lru_cache(maxsize=1)
def should_auto_invert_dark_plate() -> bool:
    return os.environ.get('OCR_AUTO_INVERT_DARK_PLATE', '1').strip().lower() not in {'0', 'false', 'no'}


@lru_cache(maxsize=1)
def get_invert_threshold() -> float:
    raw_value = os.environ.get('OCR_INVERT_THRESHOLD', '90')
    try:
        parsed = float(raw_value)
    except ValueError as exc:
        raise ValueError('OCR_INVERT_THRESHOLD must be a valid float.') from exc
    return min(max(parsed, 0.0), 255.0)


@lru_cache(maxsize=1)
def should_return_annotated_image() -> bool:
    return os.environ.get('RETURN_ANNOTATED_IMAGE', '1').strip().lower() not in {'0', 'false', 'no'}


@lru_cache(maxsize=1)
def should_return_crop_image() -> bool:
    return os.environ.get('RETURN_CROP_IMAGE', '1').strip().lower() not in {'0', 'false', 'no'}


@lru_cache(maxsize=1)
def should_return_preprocessed_crop() -> bool:
    return os.environ.get('RETURN_PREPROCESSED_CROP_IMAGE', '1').strip().lower() not in {'0', 'false', 'no'}


@lru_cache(maxsize=1)
def should_force_single_plate() -> bool:
    return os.environ.get('YOLO_FORCE_SINGLE_PLATE', '1').strip().lower() not in {'0', 'false', 'no'}


@lru_cache(maxsize=1)
def get_yolo_image_size() -> int | None:
    raw_value = os.environ.get('YOLO_IMAGE_SIZE', '').strip()
    if not raw_value:
        return None
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ValueError('YOLO_IMAGE_SIZE must be a valid integer when provided.') from exc
    return max(parsed, 320)


@lru_cache(maxsize=1)
def get_allowed_plate_classes() -> set[str]:
    return get_plate_class_names()


@lru_cache(maxsize=1)
def get_default_detection_limit() -> int:
    raw_value = os.environ.get('YOLO_MAX_DETECTIONS', '5')
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ValueError('YOLO_MAX_DETECTIONS must be a valid integer.') from exc
    return max(parsed, 1)


@lru_cache(maxsize=1)
def _image_jpeg_format() -> str:
    return 'JPEG'


@lru_cache(maxsize=1)
def _image_output_extension() -> str:
    return 'jpeg'


def _to_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if hasattr(value, 'tolist'):
        return value.tolist()
    if isinstance(value, list):
        return value
    return list(value)


def _clamp_box(box: tuple[float, float, float, float], width: int, height: int, padding_ratio: float) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = box
    box_width = max(x2 - x1, 1.0)
    box_height = max(y2 - y1, 1.0)
    pad_x = box_width * padding_ratio
    pad_y = box_height * padding_ratio

    left = max(int(round(x1 - pad_x)), 0)
    top = max(int(round(y1 - pad_y)), 0)
    right = min(int(round(x2 + pad_x)), width)
    bottom = min(int(round(y2 + pad_y)), height)

    if right <= left:
        right = min(left + 1, width)
    if bottom <= top:
        bottom = min(top + 1, height)

    return left, top, right, bottom


def _encode_image_base64(image: Image.Image) -> str:
    buffer = io.BytesIO()
    image.save(buffer, format=_image_jpeg_format(), quality=get_output_image_quality())
    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
    return f'data:image/{_image_output_extension()};base64,{encoded}'


def _select_candidate_indexes(result: Any) -> list[int]:
    boxes = getattr(result, 'boxes', None)
    if boxes is None or boxes.xyxy is None:
        return []

    confidences = _to_list(getattr(boxes, 'conf', []))
    classes = _to_list(getattr(boxes, 'cls', []))
    names = getattr(result, 'names', {}) or {}
    allowed_class_names = get_allowed_plate_classes()

    candidate_indexes: list[int] = []
    fallback_indexes: list[int] = []

    for index, score in enumerate(confidences):
        confidence_value = float(score)
        if confidence_value < get_yolo_confidence_threshold():
            continue

        fallback_indexes.append(index)

        class_name = None
        if index < len(classes):
            class_id = int(classes[index])
            class_name = str(names.get(class_id, class_id)).strip().lower()

        if class_name is None or class_name in allowed_class_names:
            candidate_indexes.append(index)

    return candidate_indexes or fallback_indexes


def detect_license_plate(image_path: str) -> dict[str, Any]:
    detector = get_plate_detector()
    image_size = get_yolo_image_size()
    prediction_kwargs: dict[str, Any] = {
        'conf': get_yolo_confidence_threshold(),
        'verbose': False,
        'max_det': get_default_detection_limit(),
    }
    if image_size is not None:
        prediction_kwargs['imgsz'] = image_size

    predictions = detector.predict(source=image_path, **prediction_kwargs)
    if not predictions:
        return {
            'detected': False,
            'message': 'The detector returned no prediction results.',
        }

    result = predictions[0]
    boxes = getattr(result, 'boxes', None)
    if boxes is None or boxes.xyxy is None or len(boxes.xyxy) == 0:
        return {
            'detected': False,
            'message': 'No license plate was detected in the uploaded image.',
        }

    candidate_indexes = _select_candidate_indexes(result)
    if not candidate_indexes:
        return {
            'detected': False,
            'message': 'No license plate detection met the configured confidence threshold.',
        }

    image = Image.open(image_path).convert('RGB')
    image_width, image_height = image.size
    padding_ratio = get_crop_padding_ratio()

    candidate_boxes: list[dict[str, Any]] = []
    for index in candidate_indexes:
        raw_box = tuple(float(value) for value in boxes.xyxy[index].tolist())
        left, top, right, bottom = _clamp_box(raw_box, image_width, image_height, padding_ratio)
        width = max(right - left, 1)
        height = max(bottom - top, 1)
        area = width * height
        confidence = float(boxes.conf[index]) if boxes.conf is not None else None

        class_id = int(boxes.cls[index]) if boxes.cls is not None else None
        class_name = None
        if class_id is not None:
            class_name = str((getattr(result, 'names', {}) or {}).get(class_id, class_id))

        candidate_boxes.append(
            {
                'index': index,
                'bbox': {'x1': left, 'y1': top, 'x2': right, 'y2': bottom},
                'width': width,
                'height': height,
                'area': area,
                'confidence': confidence,
                'class_id': class_id,
                'class_name': class_name,
                'score': (confidence or 0.0) * area,
            }
        )

    candidate_boxes.sort(key=lambda item: item['score'], reverse=True)
    selected = candidate_boxes[0]
    crop_box = selected['bbox']
    crop = image.crop((crop_box['x1'], crop_box['y1'], crop_box['x2'], crop_box['y2']))

    annotated_image_base64 = None
    if should_return_annotated_image():
        annotated_bgr = result.plot()
        if annotated_bgr is not None:
            annotated_rgb = Image.fromarray(annotated_bgr[:, :, ::-1])
            annotated_image_base64 = _encode_image_base64(annotated_rgb)

    return {
        'detected': True,
        'selected_box': selected,
        'candidate_boxes': candidate_boxes if not should_force_single_plate() else [selected],
        'crop': crop,
        'crop_image_base64': _encode_image_base64(crop) if should_return_crop_image() else None,
        'annotated_image_base64': annotated_image_base64,
        'message': 'License plate detected successfully.',
    }


def preprocess_plate_crop(image: Image.Image) -> Image.Image:
    processed = image.convert('RGB')

    if should_use_grayscale_preprocess():
        grayscale = ImageOps.grayscale(processed)
        if should_auto_invert_dark_plate():
            histogram = grayscale.histogram()
            pixel_count = sum(histogram) or 1
            brightness = sum(index * count for index, count in enumerate(histogram)) / pixel_count
            if brightness < get_invert_threshold():
                grayscale = ImageOps.invert(grayscale)
        processed = grayscale

    scale_factor = get_preprocess_scale_factor()
    if scale_factor > 1.0:
        width, height = processed.size
        resized = processed.resize(
            (
                min(int(round(width * scale_factor)), get_max_crop_dimension()),
                min(int(round(height * scale_factor)), get_max_crop_dimension()),
            ),
            Image.Resampling.LANCZOS,
        )
        processed = resized

    return processed


def extract_text_from_image(image_path: str) -> dict[str, Any]:
    engine = get_ocr_engine()
    output = engine.predict(image_path)

    items: list[dict[str, Any]] = []
    joined_parts: list[str] = []

    for result in output:
        payload = getattr(result, 'res', result)
        rec_texts = [str(text).strip() for text in _to_list(payload.get('rec_texts'))]
        rec_scores = [float(score) for score in _to_list(payload.get('rec_scores'))]

        if rec_texts:
            for index, text in enumerate(rec_texts):
                if not text:
                    continue
                score = rec_scores[index] if index < len(rec_scores) else None
                joined_parts.append(text)
                items.append(
                    {
                        'text': text,
                        'score': score,
                    }
                )
            continue

        single_text = str(payload.get('rec_text', '')).strip()
        single_score = payload.get('rec_score')
        if single_text:
            score_value = float(single_score) if single_score is not None else None
            joined_parts.append(single_text)
            items.append(
                {
                    'text': single_text,
                    'score': score_value,
                }
            )

    average_score = None
    valid_scores = [item['score'] for item in items if item['score'] is not None]
    if valid_scores:
        average_score = sum(valid_scores) / len(valid_scores)

    return {
        'joined_text': ' '.join(joined_parts).strip(),
        'items': items,
        'average_score': average_score,
        'item_count': len(items),
    }


def detect_plate_and_extract_text(image_path: str) -> dict[str, Any]:
    detection_result = detect_license_plate(image_path)
    if not detection_result['detected']:
        return {
            'plate_detected': False,
            'selected_text': '',
            'ocr': {
                'joined_text': '',
                'items': [],
                'average_score': None,
                'item_count': 0,
            },
            'detection': {
                'message': detection_result['message'],
                'selected_box': None,
                'candidate_boxes': [],
                'crop_image_base64': None,
                'annotated_image_base64': None,
            },
        }

    crop = detection_result['crop']
    processed_crop = preprocess_plate_crop(crop)

    with io.BytesIO() as buffer:
        processed_crop.save(buffer, format=_image_jpeg_format(), quality=get_output_image_quality())
        buffer.seek(0)
        with Image.open(buffer) as normalized_crop:
            temp_input = io.BytesIO()
            normalized_crop.save(temp_input, format=_image_jpeg_format(), quality=get_output_image_quality())
            temp_input.seek(0)
            # PaddleOCR expects a file path, so persist a small temporary file.
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_file.write(temp_input.read())
                temp_file_path = temp_file.name

    try:
        ocr_result = extract_text_from_image(temp_file_path)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    return {
        'plate_detected': True,
        'selected_text': ocr_result['joined_text'],
        'ocr': ocr_result,
        'detection': {
            'message': detection_result['message'],
            'selected_box': detection_result['selected_box'],
            'candidate_boxes': detection_result['candidate_boxes'],
            'crop_image_base64': detection_result['crop_image_base64'],
            'preprocessed_crop_image_base64': _encode_image_base64(processed_crop) if should_return_preprocessed_crop() else None,
            'annotated_image_base64': detection_result['annotated_image_base64'],
        },
    }
