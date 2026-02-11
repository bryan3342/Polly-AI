# Polly AI

**AI-Powered Debate Coach with Real-Time Multimodal Analysis**

## Overview

Polly AI is a fullstack web application that helps users improve their **debate and public speaking skills** through real-time AI feedback. It combines **computer vision, voice analysis, and conversational AI** to deliver actionable coaching — all streamed over a single WebSocket connection.

Record a debate response, and Polly AI analyzes your **facial expressions, vocal tone, speech patterns, and argument quality** simultaneously, then returns a comprehensive performance report.

---

## Features

- **Facial Emotion Detection** — Real-time emotion tracking (happy, sad, angry, neutral, surprised, etc.) using DeepFace + OpenCV, streamed at 1 frame/second
- **Voice & Tone Analysis** — Evaluates pitch, energy, confidence, articulation, and vocal stability using librosa
- **Speech Pattern Analysis** — Measures words-per-minute, filler word usage, pause frequency
- **AI Debate Coaching** — Conversational Gemini AI agent that assigns debate topics, answers questions, and provides detailed feedback
- **Performance Scoring** — Overall score (0-100) combining speech, voice confidence, and emotional composure
- **Session Persistence** — All sessions saved to SQLite with full analysis history

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
- **Google Gemini 1.5 Flash** — Debate coaching, argument evaluation, and feedback generation
- **DeepFace + TensorFlow** — Facial emotion classification from video frames
- **librosa** — Audio feature extraction (pitch, energy, spectral analysis)
- **SQLAlchemy + SQLite** — Session storage and analytics
- **OpenCV** — Image preprocessing for face detection

### Architecture
```
Browser ←→ WebSocket ←→ FastAPI
                          ├── EmotionService (DeepFace)
                          ├── VoiceAnalysisService (librosa)
                          ├── SpeechService (transcription)
                          ├── ChatService (Gemini AI)
                          ├── TopicService (debate topics)
                          └── SQLite (session data)
```

---

## Local Development

### Prerequisites
- **Python 3.10+**
- **Node.js 18+**
- **Google Gemini API key** — [Get one here](https://aistudio.google.com/apikey)

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

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# Start the server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend will be running at `http://localhost:8000`. You can verify at `http://localhost:8000/health`.

### 3. Frontend setup
```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

The frontend will be running at `http://localhost:5173`. Open it in your browser, grant camera/mic access, and start debating.

---

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
- `WS /ws/{session_id}` → WebSocket for real-time data
- `GET /api/health` → Health check

The frontend auto-detects the WebSocket URL from `window.location`, so no configuration is needed.

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
│   │   ├── main.py                     # FastAPI app + WebSocket endpoint
│   │   ├── config.py                   # Environment configuration
│   │   ├── database.py                 # SQLAlchemy models + session
│   │   ├── api/
│   │   │   └── websocket.py            # ConnectionManager (all WS logic)
│   │   ├── services/
│   │   │   ├── emotion_service.py      # DeepFace emotion detection
│   │   │   ├── chat_service.py         # Gemini AI integration
│   │   │   ├── speech_service.py       # Speech transcription
│   │   │   ├── voice_analysis_service.py  # librosa audio analysis
│   │   │   └── topic_service.py        # Debate topic management
│   │   ├── models/
│   │   │   └── session.py              # Database operations
│   │   └── data/
│   │       └── topics.json             # 15 debate topics
│   └── requirements.txt
└── README.md
```

---

## Future Enhancements

- Real speech-to-text transcription (Google Cloud Speech / Gemini Audio)
- Gesture and body language analysis
- Performance analytics dashboard with historical trends
- Multi-language support
- Real-time counter-argument generation

---

## License

MIT
