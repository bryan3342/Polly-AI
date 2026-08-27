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
    # How many emotion inferences may run concurrently on worker threads. The
    # TensorFlow graph behind DeepFace is not safely reentrant and the default
    # Fly VM is a single shared CPU, so this stays low; raise it alongside cpus
    # in fly.toml if frames start queueing.
    MAX_CONCURRENT_INFERENCES = int(os.getenv("MAX_CONCURRENT_INFERENCES", 2))

    # How long a connection may go without sending anything before the server
    # closes it.
    #
    # This exists for cost, not for hygiene. On a per-request-billed host
    # (Cloud Run) an open WebSocket counts as a request for its entire life, so
    # a browser tab left open in the background bills for CPU and memory around
    # the clock while doing nothing at all. Closing idle sockets is what lets
    # the instance scale back to zero.
    #
    # The client stops sending frames when its tab is hidden and reconnects when
    # the tab is next shown, so in practice this reaps abandoned tabs. It is set
    # generously because reconnecting starts a *new* session: the server mints
    # session ids and never accepts one from the client (see the /ws handler),
    # so a reaped session loses its topic and coaching history. Ten minutes of
    # complete silence means the user has gone.
    #
    # Set to 0 to disable, which is the right thing on an always-on host.
    WS_IDLE_TIMEOUT_SECONDS = float(os.getenv("WS_IDLE_TIMEOUT_SECONDS", 600))


config = Config()
