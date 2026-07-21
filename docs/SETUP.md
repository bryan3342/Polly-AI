# Setup

> This page currently documents **secrets & environment configuration**. Full local/dev
> setup steps (install, run backend + frontend, DB init) are tracked in #18.

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
