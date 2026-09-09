import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # ── Gemini models ───────────────────────────────────────────────
    #
    # Named here rather than in the services because they expire. Google retires
    # model versions, and the API answers a retired name with a 404 that this
    # app used to swallow into "I'm having trouble responding right now" -- a
    # message indistinguishable from a network blip, for a fault that needed a
    # one-word change. `scripts/check_gemini_models.py` reports what a key can
    # actually reach, and the server logs a loud error at startup if a model it
    # is configured to use has gone.
    #
    # gemini-2.0-flash and gemini-2.0-flash-lite were both retired; these are
    # their replacements, measured rather than assumed on a real recording:
    #
    #   transcription   flash-lite   999 ms, kept every filler word
    #                   flash       2619 ms, rewrote "Uh" as "Ah"
    #                   transcribe  1829 ms, returned nothing at all
    #
    # Filler preservation is not cosmetic here: speech-pattern analysis counts
    # those words, so a model that tidies them away silently flatters the
    # speaker's score.
    TRANSCRIPTION_MODEL = os.getenv("TRANSCRIPTION_MODEL", "gemini-3.5-flash-lite")

    # Coaching replies. flash-lite answers in ~800 ms against ~3.6 s for flash,
    # and this one is in a live conversation. Set CHAT_MODEL=gemini-3.5-flash
    # for somewhat richer feedback at that cost.
    CHAT_MODEL = os.getenv("CHAT_MODEL", "gemini-3.5-flash-lite")
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
    # These no longer set how fast tracking *looks*. The face box and hand
    # skeleton are tracked in the browser now, against the displayed video, and
    # redraw with the display -- a round trip could not put an indicator on
    # screen less than ~90 ms after the movement it described, which reads as
    # lag at any server speed.
    #
    # What still comes here is the emotion classification, which has no
    # browser equivalent and which the score depends on. Emotion moves at the
    # speed of an expression rather than a hand, so it is sampled far more
    # slowly than it was when the overlay was waiting on it: five frames a
    # second still gives ~600 samples across a two-minute recording, at a third
    # of the CPU.
    #
    # Hosted deployments override both; see render.yaml.
    FRAME_INTERVAL_MS = int(os.getenv("FRAME_INTERVAL_MS", 200))

    # The slower rate used when not recording, feeding only the live readout
    # beside the video. Still frequent enough to look responsive.
    IDLE_FRAME_INTERVAL_MS = int(os.getenv("IDLE_FRAME_INTERVAL_MS", 1000))

    # JPEG quality for captured frames, 0-1. The classifier sees these pixels,
    # so this is an input-fidelity setting, not just bandwidth.
    FRAME_JPEG_QUALITY = float(os.getenv("FRAME_JPEG_QUALITY", 0.85))

    # Width the browser downscales each frame to before sending it.
    #
    # The single biggest lever on how responsive tracking feels, because the
    # cost lands in three places at once: the browser encodes the JPEG on its
    # main thread, the frame crosses the socket, and the server decodes and
    # searches it. All three scale with pixel count. Measured end to end:
    #
    #   1280x720   53.8 ms server   907 KB   19 fps ceiling
    #    640x360   20.3 ms server   228 KB   49 fps ceiling
    #
    # Nothing downstream wants those pixels. The emotion model resamples its
    # face crop to 48x48 regardless, and a face fills enough of a 640px frame
    # for the cascade to find it comfortably. The *displayed* video is
    # untouched -- this is only the copy sent for analysis.
    #
    # 0 sends the frame at capture resolution.
    CAPTURE_WIDTH = int(os.getenv("CAPTURE_WIDTH", 640))

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
    # Two suits a developer machine: it absorbs bursts without oversubscribing
    # the CPU. A fractional-CPU host should set 1, where a second concurrent
    # inference splits the same sliver of CPU rather than adding throughput.
    MAX_CONCURRENT_INFERENCES = int(os.getenv("MAX_CONCURRENT_INFERENCES", 2))

    # Width, in pixels, of the copy the detector searches for a face.
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
    # is what the detector handles worst, and downscaling only compounds it.
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
