# Polly AI

## Description

A full-stack debate and public-speaking coach. A React client sends camera frames, audio, and session messages over one WebSocket connection to a FastAPI service that returns tracking updates, transcription, feedback, and a scored report.

## Dependencies

- Python 3.11, 3.12, or 3.13 for the local launcher; the project documentation uses Python 3.12 in its container.
- Node.js 18+ and npm.
- ffmpeg for browser audio decoding.
- Camera and microphone permissions.
- Internet access for the initial vision-model download.
- A Gemini API key for transcription and coaching. Tracking and local voice measurements can run without it.

## Technologies

Python, FastAPI, WebSockets, React 19, Vite 7, OpenCV DNN, YuNet, FER+, MediaPipe, librosa, ffmpeg, Gemini, SQLAlchemy, SQLite, Vitest, and pytest.

## Setup

```bash
git clone https://github.com/bryan3342/Polly-AI.git
cd Polly-AI
cp backend/.env.example backend/.env
```

Set `GEMINI_API_KEY` and replace `SECRET_KEY` in `backend/.env` if using Gemini features. Then run:

```bash
./run-local.sh
```

The launcher creates a virtual environment, installs dependencies, downloads the vision models, and starts the backend and frontend. Open `http://localhost:5173`.

Manual setup, deployment choices, environment variables, and architecture details are in [setup](docs/SETUP.md), [architecture](docs/ARCHITECTURE.md), and [API documentation](docs/API.md).

## Features

- Real-time face detection and FER+ emotion classification.
- MediaPipe hand landmarks and gesture metrics.
- Server-supplied capture settings and live tracking overlays.
- Gemini transcription with filler words preserved.
- Pitch, energy, articulation, stability, speaking-rate, filler, and pause analysis.
- Debate topics, conversational coaching, multi-part scoring, and report cards.
- SQLite session persistence.
- Model evaluation fixtures and interactive camera demos.

Emotion support is strongest for happy, angry, surprise, and neutral in the repository's evaluation. Disgust and fear are documented as unreliable. The scores are coaching signals, not medical or psychological assessments.

## Commands to run

| Location | Command | Purpose |
| --- | --- | --- |
| Root | `./run-local.sh` | Prepare and run the local app. |
| `backend/` | `uvicorn app.main:app --reload --port 8000` | Run a manually prepared backend. |
| `backend/` | `pytest` | Run headless unit tests after installing `requirements-dev.txt`. |
| `frontend/` | `npm run dev` | Run Vite at `http://localhost:5173`. |
| `frontend/` | `npm run build` | Build the React app. |
| `frontend/` | `npm test` | Run Vitest. |
| `frontend/` | `npm run lint` | Run ESLint. |

`backend/tests/demos/` contains manual webcam programs and is excluded from pytest collection.

## Contributors

- [Bryan Mejia (@bryan3342)](https://github.com/bryan3342)
- Sharlyn, recorded as `[Sharlyn]` and Sharlyn8 in Git history.
- [Giancarlo Forero (@gianca2020)](https://github.com/gianca2020)

Credit follows human authors in Git history.
