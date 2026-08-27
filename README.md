<p align="center">
  <img src="frontend/public/polly-mark.svg" width="96" alt="Polly AI" />
</p>

<h1 align="center">Polly AI</h1>

<p align="center"><strong>AI-Powered Debate Coach with Real-Time Multimodal Analysis</strong></p>

## Overview

Polly AI is a fullstack web application that helps users improve their **debate and public speaking skills** through real-time AI feedback. It combines **computer vision, voice analysis, and conversational AI** to deliver actionable coaching, all streamed over a single WebSocket connection.

Record a debate response and Polly AI analyses your **facial expressions, hand gestures, vocal tone, speech patterns and argument quality** at once, then returns a scored report.

---

## Features

- **Facial Emotion Detection**: Real-time emotion tracking (happy, sad, angry, neutral, surprised, etc.). OpenCV locates the face, DeepFace classifies the cropped region
- **Hand & Finger Tracking**: 21 landmarks per hand via MediaPipe, feeding gesture metrics into the score. OpenCV has no hand model; the cascades that exist give a box, not fingers
- **Live tracking indicators**: the face box and hand skeleton are drawn from the server's own analysis, so an indicator appearing is evidence that frame was measured
- **Speech-to-Text**: Recordings are transcribed by Gemini, verbatim, with filler words preserved
- **Voice & Tone Analysis**: Pitch, energy, confidence, articulation and vocal stability via librosa
- **Speech Pattern Analysis**: Words-per-minute and filler-word usage from the transcript; pauses measured from the waveform itself
- **AI Debate Coaching**: Conversational Gemini agent that assigns topics, answers questions and writes the post-session report
- **Performance Scoring**: Overall score (0-100) from speech, voice confidence and emotional composure. Components that could not be measured are left out rather than defaulted, so a number always means it was measured
- **Session Persistence**: Sessions saved to SQLite with full analysis history

---

## Tech Stack

### Frontend
- **React 19** + **Vite 7**: Fast SPA with hot reload
- **WebSocket Context**: Single persistent connection for all real-time data
- **MediaRecorder API**: Browser-native audio capture (WebM/Opus)
- **Canvas API**: Video frame capture at 1fps for emotion analysis
- **Pure CSS**: Hand-written CSS Grid layout (no framework dependencies)

### Backend
- **FastAPI**: Async Python web framework with WebSocket support
- **Google Gemini**: Transcription (`gemini-2.0-flash`) plus coaching and feedback (`gemini-2.0-flash-lite`), via the `google-genai` SDK
- **DeepFace + TensorFlow**: Facial emotion classification from video frames
- **librosa + ffmpeg**: ffmpeg transcodes the browser's WebM/Opus recording to PCM; librosa extracts pitch, energy and spectral features
- **SQLAlchemy + SQLite**: Session storage
- **OpenCV**: Image preprocessing for face detection

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

## Running it

Polly runs **on your machine**. The browser holds the camera and microphone, and
frames cross a loopback WebSocket to a local Python process that does the OpenCV
face detection and DeepFace emotion work right there.

```bash
./run-local.sh
```

First run creates the virtualenv, installs everything, caches the emotion model
weights and starts both processes. After that it just starts them. `Ctrl-C`
stops both. Add `GEMINI_API_KEY` to `backend/.env` for the transcript and
coaching replies; everything else works without it.

TensorFlow publishes no wheels for Python 3.14, so the script looks for 3.13,
3.12 or 3.11 rather than whatever `python3` happens to be. `brew install
python@3.13` if it cannot find one.

### What running locally buys

Every capture and inference setting is sized for the machine doing the work.
Measured per frame on an Apple M4, at 1280x720:

| | Local (default) | A free hosted instance |
|---|---|---|
| Face detection | **full resolution**, 37 ms | 320px copy, 435 ms |
| Emotion classification | 2.3 ms | 166 ms |
| Frame rate | **10 fps** | 1 fps |
| JPEG quality | **0.85** | 0.6 |
| Ceiling | ~26 fps at full resolution | ~1.6 fps |

That is roughly a **tenfold increase in temporal resolution at full spatial
resolution**, which matters, because emotion moves at the speed of a face.
Sampling once a second throws most of the signal away, and downscaling before
detection compounds the motion blur a Haar cascade already handles worst.

Verified end to end: 720p frames at the configured rate, **100% analysed, none
dropped**.

### The client is told what rate to use

The capture rate is a property of the machine running inference, and the browser
cannot know what that is, the two numbers above differ by more than an order of
magnitude. So the server sends `frame_interval_ms`, `idle_frame_interval_ms` and
`jpeg_quality` in a `capture_settings` message when the socket opens, and the
client follows them. Moving between a laptop and a small instance needs no
frontend rebuild.

Tune any of them by environment variable, see `backend/app/config.py`, where
each carries the measurement behind its default:

```bash
FRAME_INTERVAL_MS=66 DETECT_WIDTH=0 ./run-local.sh   # ~15 fps, full resolution
```

Use `backend/tests/demos/detection_tuning_demo.py` to pick `DETECT_WIDTH` from
your own camera, moving the way you actually move.

### Deploying it somewhere, if you ever want to

The whole app is still **one container**: API, WebSocket and the built SPA from
one URL, and `Dockerfile`, `render.yaml` and `deploy/cloudrun/` are all still
here and working. Memory was never the obstacle (292 MB against a 512 MB free
instance); CPU is, and `render.yaml` carries the overrides that make a tenth of
a core survivable. Frames that arrive while inference is busy are **dropped, not
queued**, so a slow host produces a sparser readout rather than one that falls
further behind all session.

| Host | Free? | Card needed? | Notes |
|---|---|---|---|
| **Local** | Yes | No | **How this runs.** Full resolution, 10 fps |
| Render | Yes, 512 MB | No | `render.yaml` committed. 0.1 CPU; sleeps after 15 min |
| Cloud Run | Yes, within quota | Yes | [`deploy/cloudrun/`](deploy/cloudrun/README.md). 1 vCPU |
| Fly.io | No | Yes | `fly.toml` retained; free allowances ended in 2024 |
| Hugging Face Spaces | No | Yes | Docker Spaces require a paid plan |

The container reads `PORT` (default 8080), so it runs unchanged on Render, Fly
(8080), Spaces (7860) and Cloud Run (injected).

## Local Development

`./run-local.sh` does everything below in one command, see
[Running it](#running-it). These are the same steps by hand, for when you want
to run the two processes separately.

### Prerequisites
- **Python 3.11-3.13** (TensorFlow publishes no 3.14 wheels yet)
- **Node.js 18+**
- **ffmpeg**: required to decode browser audio. `brew install ffmpeg` (macOS) or
  `sudo apt install ffmpeg` (Debian/Ubuntu). Without it, transcription and voice
  analysis report themselves unavailable. Already present in the Docker image.
- **Google Gemini API key**: [Get one here](https://aistudio.google.com/apikey).
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

# Stage MediaPipe's WASM runtime and models. Face and hand tracking runs in
# the browser, against the displayed video, so the runtime has to be served
# over HTTP; none of it is committed.
./scripts/stage-mediapipe.sh

# Start dev server
npm run dev
```

The frontend will be running at `http://localhost:5173`. Open it in your browser, grant camera/mic access, and start debating.

The Vite dev server proxies `/ws` and `/api` to the backend on port 8000, so the client
sees a single origin in development just as it does in production. No extra configuration
is needed; set `VITE_WS_URL` only if your backend runs somewhere other than
`localhost:8000`.

---

## Deployment Guide

Polly runs locally by default; see [Running it](#running-it).

To put it on a server, the whole app builds as one container from the
`Dockerfile`, FastAPI serves the built React files and handles WebSocket
connections from the same process, so it is one image and one URL:

- **Render**: `render.yaml` is committed, needs no payment method. Blueprint
  deploy: **New → Blueprint** → point at this repository. It carries the
  overrides that make 0.1 CPU survivable.
- **Cloud Run**: a full vCPU; see [`deploy/cloudrun/README.md`](deploy/cloudrun/README.md).
- **Fly.io**: `fly.toml` is retained and works (`fly deploy`), but Fly ended its
  free allowances in 2024. The GitHub Actions workflow for it is gated behind a
  `FLY_ENABLED` repository variable.

Whichever host, remember to lower the capture settings for it: the defaults
assume a developer machine, and `render.yaml` shows what a small instance needs.

Full message protocol: [`docs/API.md`](docs/API.md).

---

## How It Works

1. **User opens the app**: WebSocket connects and a random debate topic is assigned
2. **User clicks Record**: MediaRecorder captures audio; video frames are sent at 1fps
3. **Real-time emotion tracking**: Each frame is analyzed by DeepFace, results stream back instantly
4. **User clicks Stop**: Audio blob is sent to the backend for processing
5. **Backend analyzes everything:**
   - Transcribes speech
   - Analyzes vocal tone (pitch, energy, confidence)
   - Summarizes emotional patterns
   - Gemini writes the feedback
6. **Results appear in chat**: Strengths, weaknesses, and actionable tips
7. **User can also chat directly**: Ask Polly AI for debate tips, practice arguments, or get coaching

---

## Repository & Branches

This repository is a **single consolidated tree**: one FastAPI `backend/`, one React/Vite
`frontend/`, and shared `docs/`, all committed on **`main`, which is the single source of
truth**. There are no nested or duplicate app copies.

Older branches (`Napoli`, `demo-ready-branch`, `final`, `feature/frontend-fixes`,
`backup/local-main-*`) predate this consolidation (last active 2025-10) and are being
archived/removed, do not branch from them. Start all new work from `main`:

```bash
git switch -c my-feature origin/main
```

---

## Project Structure

```
Polly-AI/
├── run-local.sh                        # Start backend + frontend on this machine
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

The unit suite runs headless and does not need the ML stack, a network
connection or an API key; anything heavy is stubbed. `backend/tests/demos/`
holds interactive webcam scripts and is excluded from collection.

---

## Roadmap

- Gesture and body-language analysis
- Performance analytics dashboard with historical trends (needs REST endpoints
  over the stored sessions, see `docs/API.md`)
- Multi-language transcription and coaching
- Real-time counter-argument generation
- User accounts, so history belongs to a person (see the auth note in
  `docs/ARCHITECTURE.md`)

**Not planned:** video file upload. Analysis is live-capture only; the
reasoning is recorded in `docs/ARCHITECTURE.md`.

---

## License

MIT
