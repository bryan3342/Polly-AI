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
    # TensorFlow graph behind DeepFace is not safely reentrant, and the target
    # host (Render's free instance) is a tenth of a shared core, so a second
    # concurrent inference there does not add throughput -- it just splits the
    # same sliver of CPU two ways and makes both slower.
    #
    # Frames that arrive while every slot is busy are dropped, not queued (see
    # ConnectionManager.process_frame), so raising this raises how much work is
    # attempted at once, not how far behind the server is allowed to fall.
    # Raise it on a host with whole cores to spare.
    MAX_CONCURRENT_INFERENCES = int(os.getenv("MAX_CONCURRENT_INFERENCES", 1))

    # Width, in pixels, of the copy the Haar cascade searches for a face.
    #
    # Locating the face dominates the per-frame cost, and it scales with pixel
    # count. Measured on a tenth of a shared core: searching a 640x480 frame
    # took 2231 ms against a 1000 ms frame interval, while the emotion
    # classification behind it took 166 ms. Searching a 320px copy took 435 ms.
    #
    # Lower is faster but detects smaller faces less reliably, which matters for
    # someone sitting further back or moving quickly. With the cascade's 30px
    # minimum, 320 means a face must fill ~9% of the frame width -- a webcam
    # portrait is typically 25-40%, so there is real margin. Raise it if faces
    # are being missed; tests/demos/detection_tuning_demo.py measures both the
    # speed and the hit rate against a live camera.
    DETECT_WIDTH = int(os.getenv("DETECT_WIDTH", 320))

    # How long a connection may go without sending anything before the server
    # closes it.
    #
    # This exists for cost, not for hygiene. On a per-request-billed host
    # (Cloud Run) an open WebSocket counts as a request for its entire life, so
    # a browser tab left open in the background bills for CPU and memory around
    # the clock while doing nothing at all. Closing idle sockets is what lets
    # the instance scale back to zero.
    #
    # "Silent" is defined by the client, and deliberately: it sends frames while
    # its tab is visible, and a keepalive when the tab is visible but frames are
    # not flowing (camera off, or reading the report). A hidden tab sends
    # nothing at all. So this reaps *abandoned* tabs, not idle users -- which is
    # what makes a window this short safe.
    #
    # It has to be short to be worth anything: the waste being reclaimed is the
    # gap between the user leaving and the socket closing, so a ten-minute
    # window reclaims almost nothing.
    #
    # It still matters that reconnecting starts a *new* session: the server
    # mints session ids and never accepts one from the client (see the /ws
    # handler), so a reaped session loses its topic and coaching history. The
    # keepalive is what keeps that from happening to someone still at the page.
    #
    # Set to 0 to disable, which is the right thing on an always-on host.
    WS_IDLE_TIMEOUT_SECONDS = float(os.getenv("WS_IDLE_TIMEOUT_SECONDS", 120))


config = Config()
