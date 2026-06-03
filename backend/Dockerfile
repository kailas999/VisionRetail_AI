FROM python:3.11-slim

# System deps for OpenCV, Shapely, psycopg2, and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1 \
    libpq-dev \
    gcc \
    g++ \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install CPU version of PyTorch and torchvision first to avoid heavy CUDA downloads (saves ~4GB)
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Pre-download YOLOv8m weights at build time
RUN python -c "from ultralytics import YOLO; YOLO('yolov8m.pt')" || true

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
