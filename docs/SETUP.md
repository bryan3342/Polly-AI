# Setup

Local development, environment configuration and deployment.

## Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.10+ | 3.12 is what the Docker image uses |
| Node.js 18+ | for the Vite frontend |
| **ffmpeg** | required — decodes the browser's WebM/Opus recordings. `brew install ffmpeg` / `sudo apt install ffmpeg` |
| Gemini API key | optional; without it emotion and voice analysis still work, but there is no transcript and no coaching |

## Running locally

Two terminals. Backend:

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then add your GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

The first request that hits emotion detection downloads the DeepFace model
weights (a few hundred MB) — expect the first frame to take a while.

Frontend:

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

The database is created automatically on startup (`init_db()`); there is no
migration step. Delete `backend/debate_sessions.db` to start clean.

### Verifying it works

```bash
curl http://localhost:8000/api/health      # {"status":"ok"}
```

Then open the frontend, grant camera and microphone access, and check that the
emotion chip appears over the video within a second or two.

## Running the tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

The unit suite is headless: no ML stack, no network, no API key. The heavy
imports are stubbed in the test modules, which is why `requirements-dev.txt` is
so much smaller than `requirements.txt`. Tests that need ffmpeg skip themselves
if it is missing.

`backend/tests/demos/` contains interactive webcam scripts. They are excluded
from collection by `pytest.ini` and must never run in CI.

## Troubleshooting

| Symptom | Cause |
|---|---|
| Report says "Speech could not be transcribed" | No `GEMINI_API_KEY`, or ffmpeg is missing |
| Confidence shows "—" and tone reads "unavailable" | Voice analysis degraded — usually ffmpeg missing |
| Emotion chip never appears | No face detected: check lighting, and that the camera is not disabled in the toolbar |
| First frame takes ~30s | One-off DeepFace weight download |
| `Format not recognised` in logs | ffmpeg not on `PATH` |

## Secrets & environment

The backend reads configuration from environment variables via `python-dotenv`
(`backend/app/config.py`). In development these come from an **untracked** `backend/.env`
file; in production they come from Fly.io secrets. **Never commit a real `.env`** — it is
gitignored, and a template lives at `backend/.env.example`.

### 1. Create your local `.env`

```bash
cd backend
cp .env.example .env
# then edit .env and fill in real values
```

### 2. Required variables

| Variable | Used by | How to obtain |
|----------|---------|---------------|
| `GEMINI_API_KEY` | `chat_service.py` (Gemini calls) | Create a key at https://aistudio.google.com/apikey |
| `SECRET_KEY` | app secret | Generate: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URL` | `database.py` | Defaults to `sqlite:///./debate_sessions.db`; override for Postgres etc. |

The frontend uses `VITE_WS_URL` (see `frontend/.env.example`).

### 3. Production (Fly.io)

Set the same secrets on the deployed app — do **not** rely on a committed file:

```bash
fly secrets set GEMINI_API_KEY=... SECRET_KEY=...
```

### 4. Key rotation

If a key is ever committed or leaked, **rotate it at the provider first** (e.g. revoke the
Gemini key in Google AI Studio), then update your local `.env` and the Fly secrets. Rotation
is what neutralizes an exposed key — removing it from files or history afterward does not
un-leak a key that was already pushed.
