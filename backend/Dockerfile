FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_RETRIES=10 \
    PIP_DEFAULT_TIMEOUT=120 \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libglib2.0-0 \
        libsm6 \
        libxext6 \
        libxrender1 \
        libgl1 \
        libjpeg62-turbo \
        libpng16-16 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
# Install CPU-only PyTorch first from PyTorch's CPU index. ultralytics depends on
# torch, and the default PyPI torch wheel bundles ~3.5 GB of unused NVIDIA CUDA
# libraries. Installing CPU torch up front means the later `-r requirements.txt`
# sees torch already satisfied and skips the GPU stack.
#
# Each step is its own layer with a persistent pip cache mount, so a dropped
# download (the torch CPU wheel is ~190 MB) doesn't force a full re-download on
# retry — re-run `docker compose build` and it resumes from the cache. PIP_RETRIES
# / PIP_DEFAULT_TIMEOUT (set above) make pip tolerant of flaky connections.
RUN --mount=type=cache,target=/root/.cache/pip pip install --upgrade pip
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt \
    && pip install gunicorn==23.0.0

# Pre-download PaddleOCR models so cold starts on ephemeral hosts (Render/Fly/Railway)
# don't pay the download cost on every restart. Bakes models into the image layer.
RUN python -c "import os; os.environ['FLAGS_enable_pir_api']='0'; from paddleocr import PaddleOCR; PaddleOCR(lang='en', device='cpu', enable_mkldnn=False, use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)"

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py seed_data && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers ${GUNICORN_WORKERS:-2} --threads ${GUNICORN_THREADS:-4} --timeout 180"]
