import os

from dotenv import load_dotenv

load_dotenv()


def _csv_env(name: str, default: list) -> list:
    """Read a comma-separated env var into a list, falling back to `default`."""
    raw = os.getenv(name)
    if not raw:
        return default
    return [item.strip() for item in raw.split(",") if item.strip()]


class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    # Single source of truth for the DB URL; database.py reads it from here.
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./debate_sessions.db")
    SECRET_KEY = os.getenv("SECRET_KEY")

    # Explicit allow-list. A wildcard cannot be combined with credentialed
    # requests, so the origins are named. Override via CORS_ORIGINS env var.
    CORS_ORIGINS = _csv_env(
        "CORS_ORIGINS",
        ["http://localhost:5173", "http://localhost:3000"],
    )

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    FRAME_PROCESS_INTERVAL = 1.0        # Every second, process a video frame
    AUDIO_CHUNK_DURATION = 3.0          # Every 3 secs, audio processes

    # Bounds on per-session in-memory state. Without these a single long-lived
    # connection can grow the process heap without limit.
    MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", 25 * 1024 * 1024))   # 25 MB
    MAX_EMOTION_FRAMES = int(os.getenv("MAX_EMOTION_FRAMES", 3600))         # ~1 hr at 1 fps


config = Config()
