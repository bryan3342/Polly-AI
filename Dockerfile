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

# System deps.
#
# libgl1, libsm6, libxext6 and libxrender1 used to be listed here for OpenCV.
# They are gone for two reasons: opencv-python-headless does not link against
# them, and ffmpeg already pulls that whole Mesa/LLVM tree in transitively, so
# naming them bought nothing. Measured: identical install size either way.
#
# ffmpeg is the largest single item in this image at ~409 MB installed. It stays
# because it is the only thing that decodes the browser's WebM/Opus and MP4/AAC
# recordings (see backend/app/utils/audio.py).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Python deps, in two passes.
#
# Pass 1 installs everything normally. Pass 2 installs mediapipe with --no-deps,
# which is what stops pip from re-installing opencv-contrib-python on top of the
# pinned opencv-python-headless. See requirements-nodeps.txt for the reasoning.
#
# This used to be a much bigger deal: tensorflow, deepface, mtcnn, retina-face
# and tf-keras all needed the same treatment. Emotion classification runs on an
# ONNX model through cv2.dnn now, so all of that is gone.
COPY backend/requirements.txt backend/requirements-nodeps.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-deps -r requirements-nodeps.txt

# Backend code. Before the model fetch, because both scripts below live in it
# and verify_emotion_stack.py imports the real service.
COPY backend/ .

# Bake the models into the image, then prove the trimmed install runs.
#
# The models (YuNet face detection, the FER+ emotion classifier, the MediaPipe
# hand landmarker) are downloaded rather than vendored. Fetching them here makes
# them a build input: a fresh container would otherwise make the first user wait
# for the download, and would leave the feature depending on a third-party host
# being reachable at request time.
#
# The verify step is the one that has to run *after* the fetch. mediapipe is
# installed with --no-deps, so a missing transitive import surfaces only when
# the code path runs, and CI never runs it because the unit suite deliberately
# excludes the ML stack. It also fails the build if a model downloaded as an
# error page, or if YuNet is missing and detection would quietly fall back to
# the Haar cascade in production.
#
# World-readable because build-time and run-time users differ on some hosts
# (Hugging Face Spaces runs as uid 1000), which would otherwise re-download the
# models on first request: the exact failure this bake exists to prevent.
RUN python scripts/fetch_models.py \
    && python scripts/verify_emotion_stack.py \
    && chmod -R a+rX /app/.models

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
