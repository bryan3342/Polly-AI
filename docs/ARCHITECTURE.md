# System Architecture — Polly AI

## Overview

Polly AI analyses a live webcam and microphone stream to coach debate and
public-speaking practice. Facial emotion, vocal tone and speech patterns are
measured, combined into a score, and turned into written feedback by a language
model.

The whole app — API, WebSocket and the built frontend — runs as **one process**.
FastAPI serves the React bundle and handles WebSocket traffic from the same
server, so there is one URL, one deploy and no CORS in production.

---

## Technology stack

This section describes what is actually installed and running. It previously
described a much larger system (Whisper, GPT-4, PostgreSQL, Redis, S3,
Socket.IO, WebRTC, Tailwind, Nginx) that was never built — see issue #18.

### Frontend
| Concern | Choice |
|---|---|
| Framework | React 19 |
| Build | Vite 7 |
| Language | JavaScript (JSX), no TypeScript |
| Realtime | Native `WebSocket`, one persistent connection |
| Capture | `getUserMedia`, `MediaRecorder` (audio), `<canvas>` (video frames) |
| State | React Context + hooks |
| Styling | Hand-written CSS (`src/index.css`), CSS Grid |
| Icons | `react-icons` |
| Charts | None |

### Backend
| Concern | Choice |
|---|---|
| Framework | FastAPI |
| Server | Uvicorn |
| Python | 3.10+ (3.12 in the image) |
| Realtime | FastAPI native WebSockets |
| Async | `asyncio`, `asyncio.to_thread` for blocking work |

### AI / analysis
| Concern | Choice |
|---|---|
| Speech-to-text | Gemini audio understanding (`gemini-2.0-flash`) |
| Coaching & feedback | Gemini (`gemini-2.0-flash-lite`) via `google-genai` |
| Facial emotion | OpenCV Haar cascade for detection, DeepFace for classification |
| Voice/tone | librosa |
| Audio decoding | ffmpeg |

### Data
| Concern | Choice |
|---|---|
| Database | SQLite via SQLAlchemy |
| Cache | None |
| File storage | None — audio and video are analysed in memory and discarded |

### Infrastructure
| Concern | Choice |
|---|---|
| Container | Single multi-stage `Dockerfile` |
| Hosting | Fly.io (`fly.toml`) |
| CI | GitHub Actions — unit tests, frontend lint & build |

---

## Request flow

```
Browser                                  Server (one process)
───────                                  ────────────────────
getUserMedia
   │
   ├── canvas frame, 1/sec ──▶ WS ──▶ process_frame
   │                                    └─▶ to_thread ──▶ Haar detect
   │                                                       └─▶ crop face
   │                                                            └─▶ DeepFace
   │   ◀── emotion_update ──────────────────────────────────────────┘
   │
   ├── MediaRecorder ──▶ audio_complete (whole recording, base64)
   │
   └── stop_recording ──▶ ffmpeg decode ──┬─▶ Gemini  ──▶ transcript
                                          ├─▶ librosa ──▶ pitch/energy/confidence
                                          ├─▶ energy framing ──▶ pauses
                                          └─▶ emotion timeline ──▶ summary
                                                     │
                                              scoring_service
                                                     │
                                              Gemini feedback
                                                     │
                            ◀── analysis_complete ───┘  + row in SQLite
```

---

## Design decisions

### Everything on one WebSocket
Frames, audio, chat and results share a single connection. It keeps the client
simple and means one thing to reconnect. The cost is that a large audio payload
and the frame stream contend for the same socket.

### Blocking work runs on worker threads
DeepFace inference, librosa feature extraction and both Gemini calls are
synchronous. Run inline they froze the event loop — and therefore *every*
connected session — for the duration of each call. They all go through
`asyncio.to_thread`. Emotion inference is additionally bounded by a semaphore
(`MAX_CONCURRENT_INFERENCES`, default 2) because the TensorFlow graph behind
DeepFace is not safely reentrant and the default VM has one shared CPU.

### Unmeasured components are omitted, never defaulted
A failed voice analysis returns nulls and a `degraded` flag rather than a
mid-range score; a missing transcript yields no speech metrics rather than
metrics derived from placeholder text. `overall_score` averages only what was
actually measured. A number in a result means it was measured.

### Session ids are server-minted
`/ws` assigns `secrets.token_urlsafe(24)`. The endpoint used to be
`/ws/{session_id}` and trusted the client's value, which let anyone attach to
another user's live session.

### Audio decoded with ffmpeg before analysis
Browsers record WebM/Opus (MP4/AAC on Safari). libsndfile, and therefore
librosa, cannot demux either, so uploads are transcoded to PCM WAV first.

---

## Open decisions

Recorded here so they stay decisions rather than drift.

### WebRTC vs WebSocket frames (issue #16) — staying with WebSocket
Sending base64 JPEG frames at 1/sec over the existing socket is inefficient
(~33% base64 overhead, no inter-frame compression) but analysis only needs one
frame per second, and DeepFace inference — not transport — is the bottleneck.
WebRTC would add signalling, TURN and a media pipeline for no gain at this
frame rate. Revisit if frame rate needs to rise or per-frame latency becomes
user-visible.

### Video file upload (issue #15) — not planned
The README once implied MP4 upload. Analysis is live-capture only. Supporting
uploads means a file endpoint, size/duration limits, storage, and a job queue,
because a long video cannot be analysed inside a request. Not worth it until
someone asks for it; the claim has been removed from the README rather than
left as an implied feature.

### pyAudioAnalysis (issue #17) — dropped
It appeared in the old architecture doc but was never imported and is not in
`requirements.txt`. librosa covers the features actually used. Nothing to
remove; the reference is gone from this document.

### Authentication — not implemented
There are no user accounts. Server-minted session ids stop one user attaching
to another's session, but there is no identity, no authorization, and session
history cannot be attributed to a person. Real auth means accounts, a session
store keyed by user, and access control on the persisted rows — a larger change
than the id fix.

### SQLite
Fine for one machine. Fly.io volumes are per-machine, so scaling past one
instance requires moving to Postgres; nothing in the code assumes SQLite beyond
the connection URL.
