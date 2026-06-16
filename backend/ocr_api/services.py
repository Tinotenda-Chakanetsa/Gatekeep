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
DEFAULT_CHAR_MODEL_PATH = PROJECT_ROOT / 'models' / 'plate_char_detector.pt'
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
def get_char_detector() -> YOLO | None:
    """Optional second-stage YOLO that detects A-Z/0-9 *characters* on a plate crop.

    Returns None when the model file is absent so the backend keeps booting in
    Paddle-only mode. Train the weights with the Colab notebook in
    ``Lisence plate detector prototype/char_detector_trainer_package``.
    """
    model_path = Path(os.environ.get('CHAR_OCR_MODEL_PATH', str(DEFAULT_CHAR_MODEL_PATH))).expanduser()
    if not model_path.exists():
        return None
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
def get_preprocess_mode() -> str:
    """'color' (default, new) preserves colour and CLAHE-normalises luminance.

    'legacy' keeps the original greyscale+auto-invert+upscale pipeline.
    Custom Zimbabwe plates (government, diplomatic, personalised) read better
    in colour mode because the auto-invert step destroys the colour cue and
    forces PaddleOCR to read a stylised font on a now-unfamiliar inverted bg.
    """
    raw = os.environ.get('OCR_PREPROCESS_MODE', 'color').strip().lower()
    return raw if raw in {'color', 'colour', 'legacy'} else 'color'


@lru_cache(maxsize=1)
def get_clahe_clip_limit() -> float:
    raw_value = os.environ.get('OCR_CLAHE_CLIP_LIMIT', '2.0')
    try:
        return max(float(raw_value), 0.5)
    except ValueError as exc:
        raise ValueError('OCR_CLAHE_CLIP_LIMIT must be a valid float.') from exc


@lru_cache(maxsize=1)
def get_char_detector_confidence() -> float:
    raw_value = os.environ.get('CHAR_OCR_CONFIDENCE', '0.25')
    try:
        parsed = float(raw_value)
    except ValueError as exc:
        raise ValueError('CHAR_OCR_CONFIDENCE must be a valid float.') from exc
    return min(max(parsed, 0.0), 1.0)


@lru_cache(maxsize=1)
def get_char_detector_max_chars() -> int:
    raw_value = os.environ.get('CHAR_OCR_MAX_CHARS', '24')
    try:
        return max(int(raw_value), 1)
    except ValueError as exc:
        raise ValueError('CHAR_OCR_MAX_CHARS must be a valid integer.') from exc


@lru_cache(maxsize=1)
def get_char_row_tolerance_ratio() -> float:
    """Two char boxes belong to the same row when their y-centres differ by
    less than this fraction of their average height. Multi-line plates (e.g.
    motorbike-style) get split into rows top-to-bottom."""
    raw_value = os.environ.get('CHAR_OCR_ROW_TOLERANCE', '0.5')
    try:
        return max(float(raw_value), 0.0)
    except ValueError as exc:
        raise ValueError('CHAR_OCR_ROW_TOLERANCE must be a valid float.') from exc


@lru_cache(maxsize=1)
def get_char_detector_bias() -> float:
    """When both readers run, the char detector is preferred if
    char_score + bias >= paddle_score. The char detector is purpose-built for
    plate fonts so we tilt the tie-break in its favour by a small margin."""
    raw_value = os.environ.get('CHAR_OCR_PREFERENCE_BIAS', '0.05')
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError('CHAR_OCR_PREFERENCE_BIAS must be a valid float.') from exc


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


def _upscale_for_ocr(image: Image.Image) -> Image.Image:
    scale_factor = get_preprocess_scale_factor()
    if scale_factor <= 1.0:
        return image
    width, height = image.size
    return image.resize(
        (
            min(int(round(width * scale_factor)), get_max_crop_dimension()),
            min(int(round(height * scale_factor)), get_max_crop_dimension()),
        ),
        Image.Resampling.LANCZOS,
    )


def _preprocess_color(image: Image.Image) -> Image.Image:
    # CLAHE-normalise the luminance channel so contrast is consistent across plates
    # without losing colour. Keeps coloured / government / diplomatic plates readable.
    import cv2  # ultralytics already pulls in opencv-python
    import numpy as np

    arr = np.array(image.convert('RGB'))
    lab = cv2.cvtColor(arr, cv2.COLOR_RGB2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=get_clahe_clip_limit(), tileGridSize=(8, 8))
    l_eq = clahe.apply(l_channel)
    merged = cv2.merge((l_eq, a_channel, b_channel))
    normalized = cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)
    return _upscale_for_ocr(Image.fromarray(normalized))


def _preprocess_legacy(image: Image.Image) -> Image.Image:
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
    return _upscale_for_ocr(processed)


def preprocess_plate_crop(image: Image.Image) -> Image.Image:
    if get_preprocess_mode() == 'legacy':
        return _preprocess_legacy(image)
    return _preprocess_color(image)


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


def _empty_reader_result(available: bool = True) -> dict[str, Any]:
    return {
        'available': available,
        'joined_text': '',
        'items': [],
        'average_score': None,
        'item_count': 0,
    }


def extract_text_with_char_detector(image_path: str) -> dict[str, Any]:
    """Read a plate crop with the YOLO character detector.

    Detects every A-Z/0-9 box, groups them into rows by y-centre proximity (so
    rare multi-line plates work), sorts each row left-to-right, and
    concatenates rows top-to-bottom. Format-agnostic by design — works on
    personalised, government, diplomatic, and standard plates equally.
    """
    detector = get_char_detector()
    if detector is None:
        return _empty_reader_result(available=False)

    predictions = detector.predict(
        source=image_path,
        conf=get_char_detector_confidence(),
        verbose=False,
        max_det=get_char_detector_max_chars(),
    )
    if not predictions:
        return _empty_reader_result()

    result = predictions[0]
    boxes = getattr(result, 'boxes', None)
    if boxes is None or boxes.xyxy is None or len(boxes.xyxy) == 0:
        return _empty_reader_result()

    names = getattr(result, 'names', {}) or {}
    raw_chars: list[dict[str, Any]] = []
    for xyxy, cls, conf in zip(
        boxes.xyxy.tolist(),
        boxes.cls.tolist() if boxes.cls is not None else [],
        boxes.conf.tolist() if boxes.conf is not None else [],
    ):
        char = str(names.get(int(cls), '')).strip().upper()
        if not char:
            continue
        x1, y1, x2, y2 = xyxy
        raw_chars.append({
            'char': char,
            'cx': (x1 + x2) / 2,
            'cy': (y1 + y2) / 2,
            'h': max(y2 - y1, 1.0),
            'conf': float(conf),
            'bbox': [round(x1, 1), round(y1, 1), round(x2, 1), round(y2, 1)],
        })

    if not raw_chars:
        return _empty_reader_result()

    # Group into rows top-to-bottom.
    raw_chars.sort(key=lambda r: r['cy'])
    row_tolerance = get_char_row_tolerance_ratio()
    rows: list[dict[str, Any]] = []
    for char_info in raw_chars:
        if rows:
            last = rows[-1]
            tolerance = row_tolerance * max(char_info['h'], last['h_avg'])
            if abs(char_info['cy'] - last['cy_avg']) <= tolerance:
                last['items'].append(char_info)
                items = last['items']
                last['cy_avg'] = sum(it['cy'] for it in items) / len(items)
                last['h_avg'] = sum(it['h'] for it in items) / len(items)
                continue
        rows.append({'items': [char_info], 'cy_avg': char_info['cy'], 'h_avg': char_info['h']})

    parts: list[str] = []
    items_out: list[dict[str, Any]] = []
    for row in rows:
        row['items'].sort(key=lambda r: r['cx'])
        parts.append(''.join(r['char'] for r in row['items']))
        for char_info in row['items']:
            items_out.append({
                'text': char_info['char'],
                'score': char_info['conf'],
                'bbox': char_info['bbox'],
            })

    joined = ''.join(parts)
    average = (sum(it['score'] for it in items_out) / len(items_out)) if items_out else None

    return {
        'available': True,
        'joined_text': joined,
        'items': items_out,
        'average_score': average,
        'item_count': len(items_out),
    }


def _write_temp_image(image: Image.Image) -> str:
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
        image.save(temp_file, format=_image_jpeg_format(), quality=get_output_image_quality())
        return temp_file.name


def detect_plate_and_extract_text(image_path: str) -> dict[str, Any]:
    detection_result = detect_license_plate(image_path)
    if not detection_result['detected']:
        return {
            'plate_detected': False,
            'selected_text': '',
            'selected_source': None,
            'ocr': {
                'joined_text': '',
                'items': [],
                'average_score': None,
                'item_count': 0,
                'paddle': _empty_reader_result(),
                'char_detector': _empty_reader_result(available=get_char_detector() is not None),
            },
            'detection': {
                'message': detection_result['message'],
                'selected_box': None,
                'candidate_boxes': [],
                'crop_image_base64': None,
                'preprocessed_crop_image_base64': None,
                'annotated_image_base64': None,
            },
        }

    crop = detection_result['crop']
    processed_crop = preprocess_plate_crop(crop)

    # Paddle reads the contrast-normalised crop (its strength is clean printed text).
    # Char detector reads the *original colour* crop because it was trained on coloured
    # plates and CLAHE-shifted hues would push it off-distribution.
    color_temp = _write_temp_image(crop)
    paddle_temp = _write_temp_image(processed_crop)

    paddle_result: dict[str, Any] = _empty_reader_result()
    char_result: dict[str, Any] = _empty_reader_result(available=False)
    try:
        paddle_raw = extract_text_from_image(paddle_temp)
        paddle_result = {'available': True, **paddle_raw}
        char_result = extract_text_with_char_detector(color_temp)
    finally:
        for path in (color_temp, paddle_temp):
            if path and os.path.exists(path):
                os.remove(path)

    paddle_score = paddle_result.get('average_score') or 0.0
    paddle_text = paddle_result.get('joined_text') or ''
    char_score = char_result.get('average_score') or 0.0
    char_text = char_result.get('joined_text') or ''
    char_usable = char_result.get('available') and char_result.get('item_count', 0) > 0

    if char_usable and (char_score + get_char_detector_bias() >= paddle_score or not paddle_text):
        selected_text = char_text
        selected_source = 'char_detector'
        winning_items = char_result['items']
        winning_score = char_score or None
        winning_count = char_result['item_count']
    else:
        selected_text = paddle_text
        selected_source = 'paddle' if paddle_text else None
        winning_items = paddle_result.get('items', [])
        winning_score = paddle_score or None
        winning_count = paddle_result.get('item_count', 0)

    return {
        'plate_detected': True,
        'selected_text': selected_text,
        'selected_source': selected_source,
        'ocr': {
            'joined_text': selected_text,
            'items': winning_items,
            'average_score': winning_score,
            'item_count': winning_count,
            'paddle': paddle_result,
            'char_detector': char_result,
        },
        'detection': {
            'message': detection_result['message'],
            'selected_box': detection_result['selected_box'],
            'candidate_boxes': detection_result['candidate_boxes'],
            'crop_image_base64': detection_result['crop_image_base64'],
            'preprocessed_crop_image_base64': _encode_image_base64(processed_crop) if should_return_preprocessed_crop() else None,
            'annotated_image_base64': detection_result['annotated_image_base64'],
        },
    }
