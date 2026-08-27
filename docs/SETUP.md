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
pip install --no-deps -r requirements-nodeps.txt
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

## Deploying

The app is one process in production: FastAPI serves the built SPA *and* handles
WebSockets, so a single host runs everything (see `Dockerfile` and `fly.toml`).

### Choosing a host

The app is one container: API, WebSocket and the built SPA from a single URL.
Measured footprint is **231 MB after startup and warm-up, 292 MB after
inference**, so it fits a 512 MB instance — which is what makes a free tier
possible at all.

| Host | Free? | Notes |
|---|---|---|
| **Render** | Yes, 512 MB | Fits. Sleeps after ~15 min idle; first request after that is a cold start. `render.yaml` is committed. |
| **Fly.io** | No | Needs a card. 1 GB machine; `fly.toml` is committed. |
| **Hugging Face Spaces** | **No — see below** | Docker Spaces require PRO. |
| Cloudflare Pages | Yes | **Frontend only.** Workers cannot run TensorFlow, librosa or ffmpeg. |

Whatever the host, the container reads `PORT` and needs no other configuration.

#### Render

```bash
# Blueprint deploy: New → Blueprint → point at this repository.
# render.yaml provisions a free Docker web service with a health check.
```

Add `GEMINI_API_KEY` in the dashboard for transcription and coaching. Without
it the camera, face detection, emotion tracking and voice measurement still
work.

#### Hugging Face Spaces — requires PRO

`deploy/huggingface/deploy.sh` works, but Hugging Face no longer runs Docker
Spaces on the free tier:

> Static Spaces are free for everyone, but hosting Gradio and Docker Spaces on
> free cpu-basic requires a PRO subscription.

The script exits with that explanation on HTTP 402. It remains useful for
anyone who has PRO — the free CPU tier there is 2 vCPU and 16 GB.

```bash
# Only prerequisite: a write token from https://huggingface.co/settings/tokens
HF_TOKEN=hf_... ./deploy/huggingface/deploy.sh <your-hf-username> polly-ai
```

The script creates the Space if it does not exist and updates it if it does, so
it is safe to re-run for every deploy.

The first build takes roughly ten minutes — the TensorFlow layer dominates.
Afterwards the app is at `https://<username>-polly-ai.hf.space`.

For transcription and coaching, add `GEMINI_API_KEY` under the Space's
**Settings → Variables and secrets**. Without it the camera, face detection,
emotion tracking and voice measurement still work.

Storage on a Space is ephemeral: saved sessions do not survive a restart.

### Splitting the frontend onto Cloudflare Pages

The frontend can be hosted separately — Cloudflare Pages serves it free — but
**the backend cannot run there**. Pages runs static assets plus Workers (V8
isolates, 128 MB, no arbitrary binaries); this backend needs TensorFlow,
OpenCV, librosa and an `ffmpeg` binary. Python Workers run on Pyodide and
support none of them. The backend needs a container host.

Frontend, on Cloudflare Pages:

| Setting | Value |
|---|---|
| Root directory | `frontend` |
| Build command | `npm run build` |
| Output directory | `dist` |
| Environment variable | `VITE_WS_URL` = `wss://your-backend-host` |

`public/_redirects` provides the SPA fallback and `public/_headers` sets the
security and caching headers; both are picked up automatically.

`VITE_WS_URL` is baked in at **build time**, not read at runtime — changing it
requires a rebuild. Without it the client derives the WebSocket URL from
`window.location`, which is correct for the single-host deploy and wrong for a
split one.

From the CLI:

```bash
cd frontend
npx wrangler login
npx wrangler pages deploy dist --project-name polly-ai
```

Backend hosts that can actually run it: Fly.io (`fly.toml` is committed),
Render, Railway, Hugging Face Spaces, or any Docker host with ~2 GB of RAM.

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
