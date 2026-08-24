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

# Keep the model cache at a fixed, world-readable path. DeepFace defaults to
# $HOME/.deepface, and build-time and run-time users differ on some hosts
# (Hugging Face Spaces runs as uid 1000), which would silently re-download the
# weights on first request — the exact failure this bake exists to prevent.
ENV DEEPFACE_HOME=/app

# Bake the emotion model weights into the image.
#
# DeepFace fetches them from a remote host the first time a frame is analysed.
# In a fresh container that made the first user wait for a download, and made
# emotion detection depend on a third-party host being reachable at request
# time — a runtime failure mode for something that is really a build input.
RUN python -c "from deepface import DeepFace; DeepFace.build_model('Emotion', task='facial_attribute')" \
    && chmod -R a+rX /app/.deepface

# Backend code
COPY backend/ .

# Frontend build output
COPY --from=frontend-build /build/dist /app/static

# Tell FastAPI where the static files are
ENV STATIC_DIR=/app/static

# The listening port is host-supplied: Fly.io expects 8080, Hugging Face Spaces
# 7860, Cloud Run injects $PORT. Defaulting keeps `docker run` working with no
# configuration while letting any host override it.
ENV PORT=8080
EXPOSE 8080

# Writable location for the SQLite file. Container filesystems are ephemeral on
# every host targeted here, so sessions do not survive a restart; mount a volume
# and override DATABASE_URL to keep them.
ENV DATABASE_URL=sqlite:////app/data/debate_sessions.db
RUN mkdir -p /app/data && chmod 777 /app/data

# Shell form so $PORT is expanded at container start rather than baked in.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
