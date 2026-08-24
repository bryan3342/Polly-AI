# API Reference

Polly AI exposes one HTTP health endpoint, one WebSocket endpoint, and the
static frontend. Everything interactive happens over the WebSocket.

Base URL in local development: `http://localhost:8000`.

---

## HTTP

### `GET /api/health`

Liveness probe, used by the Fly.io health check (`fly.toml`).

```json
{ "status": "ok" }
```

### `GET /{path}`

Serves the built React app. Any path that does not match a file on disk returns
`index.html` so client-side routing works. Paths are containment-checked
against the static root, so traversal attempts (`../../backend/.env`) return
`index.html` rather than the requested file.

> There is no REST API for sessions. Saved sessions are written to the database
> but not currently exposed over HTTP; see "Not implemented" below.

---

## WebSocket

### `WS /ws`

Opens a debate session. **The server assigns the session id** — it is not
supplied by the client. Connecting to `/ws/<anything>` is rejected with `403`.

On connect the server sends, in order: `session_assigned`, `topic_assigned`,
and a `chat_response` containing the welcome message.

Every frame is a JSON object with a `type` field. Unknown types get an `error`
reply; malformed JSON gets an `error` reply and the connection stays open.

---

### Client → server

#### `frame`
A video frame to analyse for facial emotion. The frontend sends one per second.

```json
{ "type": "frame", "data": "data:image/jpeg;base64,...", "timestamp": 1690000000.0 }
```

`timestamp` is accepted but not currently used; emotion results are stamped
server-side.

#### `start_recording`
Begins a recording. Clears any emotion timeline from a previous take.

```json
{ "type": "start_recording" }
```

#### `audio_complete`
The recorded audio, base64-encoded. The frontend sends this once, after
`MediaRecorder` stops — despite the name it is the whole recording, not a chunk.
Accepted only while the session is recording. Accumulated audio is capped at
`MAX_AUDIO_BYTES` (25 MB); beyond that the recording is truncated and the
result carries `audio_truncated: true`.

```json
{ "type": "audio_complete", "data": "data:audio/webm;base64,..." }
```

#### `stop_recording`
Ends the recording and runs the full analysis. A stop with no active recording
is answered with `recording_stopped` and otherwise ignored.

```json
{ "type": "stop_recording" }
```

#### `chat`
Ask the coach a question. Answered with `chat_response`.

```json
{ "type": "chat", "message": "How should I open my argument?" }
```

#### `request_new_topic`
Assign a different debate topic. Answered with `topic_assigned`.

```json
{ "type": "request_new_topic" }
```

---

### Server → client

#### `session_assigned`
Sent once on connect. Useful for correlating client logs with server logs; the
client does not send it back.

```json
{ "type": "session_assigned", "session_id": "L_5TbUWngdsg50A5lxA1hvyzyRUbZbr5" }
```

#### `topic_assigned`

```json
{
  "type": "topic_assigned",
  "topic": {
    "id": 6,
    "topic": "Climate change is the most pressing issue of our generation",
    "category": "Environment",
    "difficulty": "medium"
  }
}
```

#### `emotion_update`
One per analysed frame. `bounding_box` is `[x, y, width, height]` in source
frame pixels. When no face is found, every field is null/false and
`face_detected` is `false`.

```json
{
  "type": "emotion_update",
  "frame_number": 12,
  "data": {
    "emotions": { "happy": 0.98, "neutral": 0.01, "surprise": 0.0 },
    "dominant_emotion": "happy",
    "confidence": 0.98,
    "face_detected": true,
    "bounding_box": [177, 66, 94, 94],
    "timestamp": "2026-08-24T15:56:41.123456"
  }
}
```

#### `recording_started`

```json
{ "type": "recording_started", "timestamp": "2026-08-24T15:56:30.000000" }
```

#### `recording_stopped`
Acknowledges the stop. Analysis is still running at this point.

```json
{ "type": "recording_stopped", "message": "Processing your debate..." }
```

#### `chat_response`

```json
{ "type": "chat_response", "message": "Lead with your strongest claim...",
  "timestamp": "2026-08-24T15:56:45.000000" }
```

#### `analysis_complete`
The post-session report.

**Any component that could not be measured is omitted or null rather than
defaulted.** A number here means it was measured.

```json
{
  "type": "analysis_complete",
  "results": {
    "transcript": "Standardized testing measures preparation, not ability...",
    "transcript_is_mock": false,
    "transcript_error": null,
    "speech_analysis": {
      "word_count": 142,
      "words_per_minute": 138.4,
      "filler_word_count": 6,
      "filler_percentage": 4.2,
      "pause_count": 3,
      "average_pause_duration": 0.82,
      "total_speaking_time": 61.6,
      "is_mock": false
    },
    "voice_analysis": {
      "average_pitch": 170.18,
      "pitch_variance": 21.4,
      "average_energy": 0.0439,
      "energy_variance": 0.0102,
      "articulation_rate": 0.0185,
      "voice_brightness": 1842.3,
      "confidence_score": 78,
      "duration": 61.6
    },
    "voice_analysis_degraded": false,
    "tone_description": "confident, energetic, varied",
    "emotion_summary": {
      "session_duration": 94.2,
      "total_frames": 92,
      "emotion_summary": {
        "averages": { "happy": 0.41, "neutral": 0.52 },
        "dominant": "neutral",
        "total": 92,
        "frames_with_faces": 88,
        "confidence": 0.52,
        "detections": 0.956
      }
    },
    "feedback": "Your opening was clear and well-paced...",
    "duration": 61.6,
    "overall_score": 84.3,
    "audio_truncated": false
  }
}
```

Degradation flags, and what they mean for the numbers:

| Field | When set | Consequence |
|-------|----------|-------------|
| `transcript_is_mock` | No transcript could be produced. `transcript_error` says why (no API key, undecodable audio, API failure, no speech). | `transcript` is `""` and `speech_analysis` is `{}` — no pace, word count or filler numbers at all. |
| `voice_analysis_degraded` | Audio could not be decoded or analysed. | Every `voice_analysis` value is `null`; confidence is excluded from `overall_score`. |
| `audio_truncated` | Recording exceeded `MAX_AUDIO_BYTES`. | Analysis ran on the first 25 MB only. |

`overall_score` averages only the components that were measured, and is `null`
if none were.

#### `error`

```json
{ "type": "error", "message": "Unknown message type: foo" }
```

---

## Not implemented

Listed so the gaps are explicit rather than discovered:

- **No REST session history.** Sessions are persisted (`debate_sessions`) and
  `SessionModel.get_all_sessions` / `get_user_stats` exist, but nothing exposes
  them over HTTP. A dashboard needs endpoints added first.
- **No authentication.** Session ids are unguessable and server-minted, so one
  user cannot attach to another's session, but there are no accounts and no
  authorization on anything.
- **No video upload endpoint.** Analysis is live-only; see `docs/ARCHITECTURE.md`.
