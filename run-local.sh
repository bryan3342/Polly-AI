#!/usr/bin/env bash
#
# Run Polly AI on this machine: FastAPI backend and Vite frontend, together.
#
# Everything runs locally and nothing is deployed. The browser holds the camera
# and microphone; frames cross a loopback WebSocket to the Python process, which
# does the OpenCV face detection and DeepFace emotion work here rather than on a
# rented CPU. That is why the defaults are what they are -- full-resolution
# detection at 10 frames a second, where a free hosted instance managed one
# frame a second at a third of the resolution.
#
#   ./run-local.sh              start both, open the browser
#   ./run-local.sh --setup      (re)create the virtualenv and install everything
#
set -euo pipefail
cd "$(dirname "$0")"

BACKEND_PORT=${BACKEND_PORT:-8000}
FRONTEND_PORT=${FRONTEND_PORT:-5173}
VENV=backend/venv

# macOS ships a python3 that is often newer than the ML wheels support, so pick
# a version known to work rather than failing halfway through an install.
#
# TensorFlow used to set this ceiling. It is gone, and the whole requirements
# set now resolves on 3.14 as well, but resolving is not running: 3.14 is left
# out until someone has actually run a session on it.
find_python() {
    for candidate in python3.13 python3.12 python3.11; do
        if command -v "$candidate" >/dev/null 2>&1; then echo "$candidate"; return; fi
    done
    echo ""
}

setup() {
    local py; py=$(find_python)
    if [ -z "$py" ]; then
        echo "Need Python 3.11-3.13." >&2
        echo "  brew install python@3.13" >&2
        exit 1
    fi
    echo "==> Creating $VENV with $py"
    rm -rf "$VENV"
    "$py" -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --upgrade pip

    echo "==> Installing backend dependencies"
    "$VENV/bin/pip" install --quiet -r backend/requirements.txt
    # mediapipe must skip its dependency closure or it reinstalls
    # opencv-contrib-python over the pinned headless build.
    "$VENV/bin/pip" install --quiet --no-deps -r backend/requirements-nodeps.txt

    echo "==> Caching models (face detection, emotion, hand landmarker)"
    (cd backend && "../$VENV/bin/python" scripts/fetch_models.py)

    echo "==> Installing frontend dependencies"
    (cd frontend && npm install --silent)

    # Face and hand tracking runs in the browser, so MediaPipe's WASM runtime
    # and models have to be reachable over HTTP. Neither is committed.
    echo "==> Staging the in-browser tracking runtime"
    (cd frontend && ./scripts/stage-mediapipe.sh)

    echo "==> Setup complete."
}

if [ "${1:-}" = "--setup" ]; then setup; exit 0; fi

if [ ! -x "$VENV/bin/python" ]; then
    echo "No virtualenv yet, running setup first."
    setup
fi

if [ ! -f backend/.env ]; then
    echo "note: backend/.env not found. The camera, face detection, emotion"
    echo "      tracking and voice measurement all still work; the transcript"
    echo "      and coaching replies will report themselves unavailable."
    echo "      Add GEMINI_API_KEY to backend/.env to enable them."
    echo
fi

cleanup() { echo; echo "Stopping..."; kill 0 2>/dev/null || true; }
trap cleanup EXIT INT TERM

echo "==> Backend  http://localhost:$BACKEND_PORT"
(cd backend && "../$VENV/bin/python" -m uvicorn app.main:app \
    --host 127.0.0.1 --port "$BACKEND_PORT" --reload) &

echo "==> Frontend http://localhost:$FRONTEND_PORT"
(cd frontend && VITE_WS_URL="ws://localhost:$BACKEND_PORT" \
    npm run dev -- --port "$FRONTEND_PORT" --strictPort) &

# Give uvicorn time to load the models before pointing a browser at it.
for _ in $(seq 1 60); do
    if curl -sf "http://localhost:$BACKEND_PORT/api/health" >/dev/null 2>&1; then break; fi
    sleep 1
done

echo
echo "==> Open http://localhost:$FRONTEND_PORT   (Ctrl-C to stop both)"
command -v open >/dev/null 2>&1 && open "http://localhost:$FRONTEND_PORT" || true

wait
