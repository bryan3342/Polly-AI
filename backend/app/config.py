import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    # Single source of truth for the DB URL; database.py reads it from here.
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./debate_sessions.db")
    SECRET_KEY = os.getenv("SECRET_KEY")
    # Comma-separated list of allowed browser origins. Defaults cover local dev
    # (Vite on 5173, CRA on 3000); in production the frontend is served from the
    # same origin, so extra origins are only needed for a separately hosted UI.
    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://localhost:3000"
        ).split(",")
        if origin.strip()
    ]

    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    FRAME_PROCESS_INTERVAL = 1.0        # Every second, process a video frame
    AUDIO_CHUNK_DURATION = 3.0          # Every 3 secs, audio processes

    # Bounds on per-session in-memory state. Without these a single long-lived
    # connection can grow the process heap without limit.
    MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", 25 * 1024 * 1024))   # 25 MB
    MAX_EMOTION_FRAMES = int(os.getenv("MAX_EMOTION_FRAMES", 3600))         # ~1 hr at 1 fps


config = Config()
