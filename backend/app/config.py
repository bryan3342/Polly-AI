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

    AUDIO_CHUNK_DURATION = 3.0          # Every 3 secs, audio processes

    # ── Capture rate ────────────────────────────────────────────────
    #
    # How often the browser should send a frame, in milliseconds. These are
    # served to the client when it connects rather than compiled into it,
    # because the right rate is a property of the machine doing the inference,
    # and only this side knows what that machine is. A hosted instance and a
    # laptop want very different numbers, and the client should not have to be
    # rebuilt to move between them.
    #
    # The defaults target a developer machine, which is where this now runs.
    # Measured per frame on an Apple M4: face detection and emotion
    # classification together cost far less than 100 ms, so 10 frames a second
    # leaves real headroom -- and emotion is a signal that moves at the speed of
    # a face, so sampling it once a second throws most of it away.
    #
    # Hosted deployments override both; see render.yaml, where a tenth of a core
    # measured ~600 ms per frame and 1 fps is the ceiling.
    FRAME_INTERVAL_MS = int(os.getenv("FRAME_INTERVAL_MS", 100))

    # The slower rate used when not recording, feeding only the live readout
    # beside the video. Still frequent enough to look responsive.
    IDLE_FRAME_INTERVAL_MS = int(os.getenv("IDLE_FRAME_INTERVAL_MS", 500))

    # JPEG quality for captured frames, 0-1. The classifier sees these pixels,
    # so this is an input-fidelity setting, not just bandwidth. 0.6 was chosen
    # when every byte crossed the public internet; on a loopback connection
    # there is no reason not to hand the model a better image.
    FRAME_JPEG_QUALITY = float(os.getenv("FRAME_JPEG_QUALITY", 0.85))

    # Bounds on per-session in-memory state. Without these a single long-lived
    # connection can grow the process heap without limit.
    MAX_AUDIO_BYTES = int(os.getenv("MAX_AUDIO_BYTES", 25 * 1024 * 1024))   # 25 MB
    MAX_EMOTION_FRAMES = int(os.getenv("MAX_EMOTION_FRAMES", 3600))         # ~1 hr at 1 fps
    # How many emotion inferences may run concurrently on worker threads.
    #
    # Frames that arrive while every slot is busy are dropped, not queued (see
    # ConnectionManager.process_frame), so this sets how much work is attempted
    # at once, not how far behind the server may fall. More slots means fewer
    # dropped frames when several arrive together.
    #
    # Two suits a developer machine: it absorbs bursts without letting the
    # TensorFlow graph -- which is not safely reentrant -- be entered from many
    # threads at once. A fractional-CPU host should set 1, where a second
    # concurrent inference splits the same sliver of CPU rather than adding
    # throughput.
    MAX_CONCURRENT_INFERENCES = int(os.getenv("MAX_CONCURRENT_INFERENCES", 2))

    # Width, in pixels, of the copy the Haar cascade searches for a face.
    #
    # Locating the face dominates the per-frame cost, and it scales with pixel
    # count. Measured on a tenth of a shared core: searching a 640x480 frame
    # took 2231 ms against a 1000 ms frame interval, while the emotion
    # classification behind it took 166 ms. Searching a 320px copy took 435 ms.
    #
    # Lower is faster but detects smaller faces less reliably, which matters for
    # someone sitting further back or moving quickly.
    #
    # 0 disables downscaling and searches the frame as captured, which is the
    # default here: on a developer machine full-resolution detection measured
    # ~30 ms, so there is nothing to buy by trading accuracy away. Motion blur
    # is what a Haar cascade handles worst, and downscaling only compounds it.
    #
    # Hosted deployments set a width; see render.yaml, where searching full
    # resolution measured 2231 ms against a 1000 ms frame budget. Use
    # tests/demos/detection_tuning_demo.py to pick one from a live camera.
    DETECT_WIDTH = int(os.getenv("DETECT_WIDTH", 0))

    # Close connections that have gone silent.
    #
    # Disabled by default. It exists to stop a per-request-billed host charging
    # for abandoned browser tabs; running locally there is nothing to save, and
    # no reason to make someone lose their topic and coaching history for
    # stepping away from the machine.
    #
    # Where it is enabled, "silent" is defined by the client, and deliberately:
    # it sends frames while its tab is visible, and a keepalive when the tab is
    # visible but frames are not flowing (camera off, or reading the report). A
    # hidden tab sends nothing at all, so a short window reaps *abandoned* tabs
    # rather than idle users. That distinction matters, because reconnecting
    # starts a new session -- the server mints session ids and never accepts one
    # from the client -- so a reaped session loses its history.
    #
    # render.yaml sets it, and records the billing arithmetic behind the value.
    WS_IDLE_TIMEOUT_SECONDS = float(os.getenv("WS_IDLE_TIMEOUT_SECONDS", 0))


config = Config()
