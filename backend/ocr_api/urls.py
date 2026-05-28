from django.urls import path

from .views import health_check, run_ocr

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('ocr/', run_ocr, name='run_ocr'),
]
