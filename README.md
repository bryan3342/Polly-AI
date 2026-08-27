<p align="center">
  <img src="frontend/public/polly-mark.svg" width="96" alt="Polly AI" />
</p>

<h1 align="center">Polly AI</h1>

<p align="center"><strong>AI-Powered Debate Coach with Real-Time Multimodal Analysis</strong></p>

## Overview

Polly AI is a fullstack web application that helps users improve their **debate and public speaking skills** through real-time AI feedback. It combines **computer vision, voice analysis, and conversational AI** to deliver actionable coaching — all streamed over a single WebSocket connection.

Record a debate response, and Polly AI analyzes your **facial expressions, vocal tone, speech patterns, and argument quality** simultaneously, then returns a comprehensive performance report.

---

## Features

- **Facial Emotion Detection** — Real-time emotion tracking (happy, sad, angry, neutral, surprised, etc.). OpenCV locates the face, DeepFace classifies the cropped region, at 1 frame/second
- **Speech-to-Text** — Recordings are transcribed by Gemini, verbatim, with filler words preserved
- **Voice & Tone Analysis** — Pitch, energy, confidence, articulation and vocal stability via librosa
- **Speech Pattern Analysis** — Words-per-minute and filler-word usage from the transcript; pauses measured from the waveform itself
- **AI Debate Coaching** — Conversational Gemini agent that assigns topics, answers questions and writes the post-session report
- **Performance Scoring** — Overall score (0-100) from speech, voice confidence and emotional composure. Components that could not be measured are left out rather than defaulted, so a number always means it was measured
- **Session Persistence** — Sessions saved to SQLite with full analysis history

---

## Tech Stack

### Frontend
- **React 19** + **Vite 7** — Fast SPA with hot reload
- **WebSocket Context** — Single persistent connection for all real-time data
- **MediaRecorder API** — Browser-native audio capture (WebM/Opus)
- **Canvas API** — Video frame capture at 1fps for emotion analysis
- **Pure CSS** — Hand-written CSS Grid layout (no framework dependencies)

### Backend
- **FastAPI** — Async Python web framework with WebSocket support
- **Google Gemini** — Transcription (`gemini-2.0-flash`) plus coaching and feedback (`gemini-2.0-flash-lite`), via the `google-genai` SDK
- **DeepFace + TensorFlow** — Facial emotion classification from video frames
- **librosa + ffmpeg** — ffmpeg transcodes the browser's WebM/Opus recording to PCM; librosa extracts pitch, energy and spectral features
- **SQLAlchemy + SQLite** — Session storage
- **OpenCV** — Image preprocessing for face detection

### Architecture
```
Browser ←→ WebSocket ←→ FastAPI
                          ├── EmotionService (OpenCV + DeepFace)
                          ├── VoiceAnalysisService (ffmpeg + librosa)
                          ├── SpeechService (Gemini transcription)
                          ├── ChatService (Gemini coaching)
                          ├── ScoringService (rubric)
                          ├── TopicService (debate topics)
                          └── SQLite (session data)
```

---

## Local Development

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **ffmpeg** — required to decode browser audio. `brew install ffmpeg` (macOS) or
  `sudo apt install ffmpeg` (Debian/Ubuntu). Without it, transcription and voice
  analysis report themselves unavailable. Already present in the Docker image.
- **Google Gemini API key** — [Get one here](https://aistudio.google.com/apikey).
  Without it the app still runs: the camera, emotion detection and voice analysis
  all work, but there is no transcript and no coaching.

### 1. Clone the repository
```bash
git clone https://github.com/YOUR_USERNAME/Polly-AI.git
cd Polly-AI
```

### 2. Backend setup
```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate   # macOS/Linux
# venv\Scripts\activate    # Windows

# Install dependencies. Two files: deepface must be installed without its
# dependency closure so it does not pull in the full tensorflow and
# opencv-python wheels on top of the -cpu/-headless ones. See
# requirements-nodeps.txt for why.
pip install -r requirements.txt
pip install --no-deps -r requirements-nodeps.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will be running at `http://localhost:8000`. You can verify at `http://localhost:8000/api/health`.

### 3. Frontend setup
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

The frontend will be running at `http://localhost:5173`. Open it in your browser, grant camera/mic access, and start debating.

The Vite dev server proxies `/ws` and `/api` to the backend on port 8000, so the client
sees a single origin in development just as it does in production. No extra configuration
is needed; set `VITE_WS_URL` only if your backend runs somewhere other than
`localhost:8000`.

---

## Deployment

The whole app — API, WebSocket and the built frontend — runs as **one process**,
so a single container host serves everything from one URL.

Measured footprint: **231 MB after startup, 292 MB after inference** — small
enough for a 512 MB free instance.

**Google Cloud Run is the deployment target.** See
[`deploy/cloudrun/README.md`](deploy/cloudrun/README.md).

CPU, not memory, is what this app is short of: emotion inference runs once per
video frame. Cloud Run's free tier provides a full vCPU and **50 hours of
connected time a month**, and the app already depends on Google for the Gemini
API, so keeping compute in the same project keeps credentials and billing in one
place.

| Host | Free? | Status |
|---|---|---|
| **Cloud Run** | Yes, within quota | **In use.** 1 vCPU, scales to zero |
| Render | Yes, 512 MB | Dropped — **0.1 CPU** is too little for per-frame inference |
| Fly.io | No | `fly.toml` retained; free allowances ended in 2024 |
| Hugging Face Spaces | No | Docker Spaces require a paid plan |
| Cloudflare Pages | Yes | Frontend only, and only if egress ever becomes a limit |

The SPA, API and WebSocket are all served by the one container from a single
origin, so there is no CORS to configure and one URL to deploy.

The container reads `PORT` (default 8080), so it runs unchanged on Fly (8080),
Spaces (7860) and Cloud Run (injected).

### Cost-shaped behaviour

Two behaviours exist because hosts bill for an open WebSocket as though it were
a request in flight for its whole life:

- Frames are sent at 1/second while recording and 1/5s otherwise, and **not at
  all while the browser tab is hidden**. Every frame costs a DeepFace inference.
- The server closes connections silent for `WS_IDLE_TIMEOUT_SECONDS` (default
  120; `0` disables). Reconnecting starts a new session, so a reaped session
  loses its topic and coaching history — which is why the client sends a
  keepalive every 45s **whenever its tab is visible**. Silence therefore means
  the tab is hidden, not that the user is sitting still.

On an always-on host set `WS_IDLE_TIMEOUT_SECONDS=0`.

### Image size

The runtime image installs `tensorflow-cpu` and `opencv-python-headless` instead
of the default wheels. Measured on x86_64, `tensorflow` unpacks to 1873 MB
against `tensorflow-cpu`'s 1273 MB — 600 MB on disk, 299 MB in a registry. deepface declares hard
requirements on the originals, so the Dockerfile installs it with `--no-deps`
and `backend/requirements.txt` carries its real imports; see
[`backend/requirements-nodeps.txt`](backend/requirements-nodeps.txt). Because
pip no longer checks those imports, the build runs
`backend/scripts/verify_emotion_stack.py` — a real `DeepFace.analyze()` call —
so a missing import fails the build rather than a user's first frame.

## Deployment Guide (Fly.io — Single Deploy, Free Tier)

The entire app (frontend + backend) deploys as **one service** on Fly.io. FastAPI serves the built React files and handles WebSocket connections from the same process. One URL, always on.

### Prerequisites

1. **Install the Fly CLI:**
   ```bash
   # macOS
   brew install flyctl

   # Linux / WSL
   curl -L https://fly.io/install.sh | sh
   ```

2. **Create a free account:**
   ```bash
   fly auth signup
   ```

### Deploy (3 commands)

```bash
# From the project root (Polly-AI/)

# 1. Create the app (first time only)
fly launch --name polly-ai --region iad --no-deploy

# 2. Set your Gemini API key as a secret
fly secrets set GEMINI_API_KEY=your_key_here

# 3. Deploy
fly deploy
```

That's it. Fly.io will:
- Build the frontend (Node stage)
- Install Python dependencies
- Copy the built React app into the server
- Deploy and give you a URL like `https://polly-ai.fly.dev`

### After deployment

- **View your app:** `fly open`
- **Check logs:** `fly logs`
- **Redeploy after changes:** `fly deploy`
- **Scale up if needed:** edit `fly.toml` → change `memory` or `cpus`

### How the single-server deploy works

The `Dockerfile` uses a multi-stage build:
1. **Stage 1 (Node):** Builds the React frontend → produces `dist/`
2. **Stage 2 (Python):** Installs backend deps, copies `dist/` into the server

FastAPI serves everything:
- `GET /` → React SPA (index.html)
- `GET /assets/*` → JS/CSS bundles
- `WS /ws` → WebSocket for real-time data (the server assigns the session id)
- `GET /api/health` → Health check

The frontend auto-detects the WebSocket URL from `window.location`, so no configuration is needed.

Full message protocol: [`docs/API.md`](docs/API.md).

---

## How It Works

1. **User opens the app** — WebSocket connects, a random debate topic is assigned
2. **User clicks Record** — MediaRecorder captures audio; video frames are sent at 1fps
3. **Real-time emotion tracking** — Each frame is analyzed by DeepFace, results stream back instantly
4. **User clicks Stop** — Audio blob is sent to the backend for processing
5. **Backend analyzes everything:**
   - Transcribes speech
   - Analyzes vocal tone (pitch, energy, confidence)
   - Summarizes emotional patterns
   - Gemini AI generates comprehensive feedback
6. **Results appear in chat** — Strengths, weaknesses, and actionable tips
7. **User can also chat directly** — Ask Polly AI for debate tips, practice arguments, or get coaching

---

## Repository & Branches

This repository is a **single consolidated tree** — one FastAPI `backend/`, one React/Vite
`frontend/`, and shared `docs/`, all committed on **`main`, which is the single source of
truth**. There are no nested or duplicate app copies.

Older branches (`Napoli`, `demo-ready-branch`, `final`, `feature/frontend-fixes`,
`backup/local-main-*`) predate this consolidation (last active 2025-10) and are being
archived/removed — do not branch from them. Start all new work from `main`:

```bash
git switch -c my-feature origin/main
```

---

## Project Structure

```
Polly-AI/
├── frontend/
│   ├── src/
│   │   ├── main.jsx                    # Entry point
│   │   ├── App.jsx                     # Root component + state
│   │   ├── index.css                   # All styles (CSS Grid layout)
│   │   ├── context/
│   │   │   └── WebSocketContext.jsx     # WebSocket provider + hooks
│   │   └── components/
│   │       ├── VideoBox.jsx            # Camera + frame capture + audio recording
│   │       ├── Chatbox.jsx             # AI chat + topic display
│   │       └── Toolbar.jsx             # Record/Stop/Timer/Camera/Mic controls
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── __init__.py                 # Configures logging before submodules load
│   │   ├── main.py                     # FastAPI app, routing, static file serving
│   │   ├── config.py                   # Environment configuration (single source)
│   │   ├── logging_config.py           # Structured stdout logging setup
│   │   ├── database.py                 # SQLAlchemy models + session
│   │   ├── api/
│   │   │   └── websocket.py            # ConnectionManager (transport only)
│   │   ├── services/
│   │   │   ├── emotion_service.py      # DeepFace emotion detection
│   │   │   ├── chat_service.py         # Gemini AI integration
│   │   │   ├── speech_service.py       # Speech transcription (mock)
│   │   │   ├── voice_analysis_service.py  # librosa audio analysis
│   │   │   ├── scoring_service.py      # Performance scoring rules
│   │   │   └── topic_service.py        # Debate topic management
│   │   ├── models/
│   │   │   └── session.py              # Database operations
│   │   ├── utils/
│   │   │   ├── imaging.py              # base64 -> BGR frame decoding
│   │   │   ├── paths.py                # Static-path containment check
│   │   │   └── serialization.py        # numpy -> JSON sanitization
│   │   └── data/
│   │       └── topics.json             # Debate topics (single source of truth)
│   ├── tests/
│   │   ├── unit/                       # Automated pytest suite
│   │   └── demos/                      # Interactive camera scripts (manual only)
│   ├── scripts/
│   │   └── verify_emotion_stack.py     # Build-time check of the trimmed ML install
│   ├── requirements.txt
│   ├── requirements-nodeps.txt         # Installed with --no-deps (see the file)
│   └── requirements-dev.txt
└── README.md
```

---

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

The suite covers scoring rules, speech-pattern analysis, topic loading, session
statistics, JSON sanitization, and static-path traversal containment.

`requirements-dev.txt` deliberately excludes the heavy runtime dependencies
(TensorFlow, DeepFace, librosa, OpenCV) — the unit suite must not need them, which
keeps CI to a few seconds. Install `requirements.txt` as well if you want to run the
camera demos.

Scripts in `backend/tests/demos/` open a camera window and wait for a keypress — they
are manual diagnostics, not tests, and `pytest.ini` limits collection to `tests/unit`.

Frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

Both backend and frontend checks run in CI on every push and pull request
(`.github/workflows/test.yml`).

---

## Testing

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

The unit suite runs headless and does not need the ML stack, a network
connection or an API key — anything heavy is stubbed. `backend/tests/demos/`
holds interactive webcam scripts and is excluded from collection.

---

## Roadmap

- Gesture and body-language analysis
- Performance analytics dashboard with historical trends (needs REST endpoints
  over the stored sessions — see `docs/API.md`)
- Multi-language transcription and coaching
- Real-time counter-argument generation
- User accounts, so history belongs to a person (see the auth note in
  `docs/ARCHITECTURE.md`)

**Not planned:** video file upload. Analysis is live-capture only; the
reasoning is recorded in `docs/ARCHITECTURE.md`.

---

## License

MIT
