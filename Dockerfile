# ── Stage 1: Build frontend ──────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python backend + built frontend ─────────
FROM python:3.12-slim
WORKDIR /app

# System deps for OpenCV, librosa
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the emotion model weights into the image.
#
# DeepFace fetches them from a remote host the first time a frame is analysed.
# In a fresh container that made the first user wait for a download, and made
# emotion detection depend on a third-party host being reachable at request
# time — a runtime failure mode for something that is really a build input.
RUN python -c "from deepface import DeepFace; DeepFace.build_model('Emotion', task='facial_attribute')"

# Backend code
COPY backend/ .

# Frontend build output
COPY --from=frontend-build /build/dist /app/static

# Tell FastAPI where the static files are
ENV STATIC_DIR=/app/static

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
