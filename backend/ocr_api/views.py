from __future__ import annotations

import os
import tempfile

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST


@require_GET
def health_check(request):
    return JsonResponse({'status': 'ok'})


@csrf_exempt
@require_POST
def run_ocr(request):
    # Imported lazily so the YOLO/PaddleOCR stack only loads when OCR is actually run,
    # keeping Django startup and migrations free of the heavy ML dependencies.
    from .services import detect_plate_and_extract_text

    uploaded_file = request.FILES.get('image')
    if uploaded_file is None:
        return JsonResponse({'error': 'No image file was uploaded under the field name "image".'}, status=400)

    _, extension = os.path.splitext(uploaded_file.name)
    suffix = extension if extension else '.jpg'
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
            temp_path = temp_file.name

        result = detect_plate_and_extract_text(temp_path)

        return JsonResponse(
            {
                'filename': uploaded_file.name,
                'plate_detected': result['plate_detected'],
                'selected_text': result['selected_text'],
                'joined_text': result['ocr']['joined_text'],
                'items': result['ocr']['items'],
                'average_score': result['ocr']['average_score'],
                'item_count': result['ocr']['item_count'],
                'detection': result['detection'],
            }
        )
    except Exception as exc:
        return JsonResponse(
            {
                'error': 'Plate detection/OCR processing failed.',
                'details': str(exc),
            },
            status=500,
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
