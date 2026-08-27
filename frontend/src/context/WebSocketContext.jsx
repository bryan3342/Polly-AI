import { useState, useEffect, useRef, useCallback } from 'react';
import { Ctx } from './wsContext';

function getWsBase() {
    if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}`;
}
const WS_BASE = getWsBase();
// The server mints the session id and announces it in a `session_assigned`
// message. It used to be generated here and passed in the URL, which the server
// trusted verbatim: connecting with somebody else's id attached you to their
// live session (issue #21).
const WS_URL = `${WS_BASE}/ws`;
// Capture defaults, used only until the server states its own on connect (see
// the `capture_settings` message). The right frame rate depends on the machine
// running inference, which the browser cannot know: a laptop measures ~39 ms per
// frame at full resolution while a fractional-CPU instance measures ~600 ms.
// Baking a single number in here meant one of those two was always wrong.
//
// These are the conservative fallback, not the intended values.
const DEFAULT_FRAME_MS = 1000;
const DEFAULT_IDLE_FRAME_MS = 5000;
const DEFAULT_JPEG_QUALITY = 0.6;

// How often to tell the server we are still here while the tab is visible but
// no frames are flowing -- the camera is off, or the user is reading their
// report. Without this the server would reap them mid-read: it cannot tell
// "user sitting on the page with the camera off" from "tab abandoned", and both
// look like silence. Comfortably under WS_IDLE_TIMEOUT_SECONDS (120).
const KEEPALIVE_MS = 45000;

// The server closes inactive connections with this code to let a
// per-request-billed host scale to zero; see Config.WS_IDLE_TIMEOUT_SECONDS.
// It is an expected, benign close, so it must not surface as a lost-connection
// error or trigger the reconnect backoff.
const WS_CLOSE_IDLE = 4000;

// Shown when the socket never opened at all — almost always the analysis
// backend not running, or a static-only deployment with no VITE_WS_URL set.
// Says which half is missing rather than reporting a generic failure, because
// the camera and the rest of the interface are working fine at this point.
const UNREACHABLE =
    "Can't reach the analysis server, so coaching and scoring are unavailable. "
    + 'The camera still works. Retrying…';

export function WebSocketProvider({ children }) {
    const [connected, setConnected]     = useState(false);
    const [emotion, setEmotion]         = useState(null);
    const [chat, setChat]               = useState([]);
    const [topic, setTopic]             = useState(null);
    const [processing, setProcessing]   = useState(false);
    const [error, setError]             = useState(null);
    const [sessionId, setSessionId]     = useState(null);
    // Replaced by whatever the server reports it can keep up with.
    const [capture, setCapture]         = useState({
        frameMs: DEFAULT_FRAME_MS,
        idleFrameMs: DEFAULT_IDLE_FRAME_MS,
        jpegQuality: DEFAULT_JPEG_QUALITY,
    });
    // Distinguishes "never reached the server" from "was connected and dropped".
    // They need different explanations: the first is usually a backend that is
    // not running or not configured, the second is a blip worth waiting out.
    const everConnected = useRef(false);
    const ws   = useRef(null);
    const reco = useRef(null);

    /* ── connect ─────────────────────────────────── */
    const connect = useCallback(() => {
        // CONNECTING counts as live too. Checking only for OPEN let StrictMode's
        // double-invoked effect open a second socket while the first was still
        // connecting, leaving an orphaned socket whose handlers duplicated every
        // message (the welcome text appeared twice) and whose eventual close tore
        // down the live session server-side.
        const state = ws.current?.readyState;
        if (state === WebSocket.OPEN || state === WebSocket.CONNECTING) return;

        let sock;
        try { sock = new WebSocket(WS_URL); }
        catch { setError(UNREACHABLE); return; }
        ws.current = sock;

        // Every handler below ignores events from a socket that is no longer
        // the current one. Without this, a socket being torn down reports its
        // own close as a lost connection and clears state that now belongs to
        // its replacement.
        const isCurrent = () => ws.current === sock;

        sock.onopen = () => {
            if (!isCurrent()) return;
            everConnected.current = true;
            setConnected(true);
            setError(null);
        };

        sock.onmessage = (e) => {
            if (!isCurrent()) return;
            let m; try { m = JSON.parse(e.data); } catch { return; }
            switch (m.type) {
                case 'session_assigned':  setSessionId(m.session_id); break;
                case 'capture_settings':
                    setCapture({
                        frameMs: m.frame_interval_ms ?? DEFAULT_FRAME_MS,
                        idleFrameMs: m.idle_frame_interval_ms ?? DEFAULT_IDLE_FRAME_MS,
                        jpegQuality: m.jpeg_quality ?? DEFAULT_JPEG_QUALITY,
                    }); break;
                case 'emotion_update':    setEmotion(m.data); break;
                case 'topic_assigned':    setTopic(m.topic); break;
                case 'recording_started': break;
                case 'recording_stopped': setProcessing(true);
                    setChat(p => [...p, { role: 'system', content: 'Analyzing your performance...' }]); break;
                case 'analysis_complete':
                    setProcessing(false);
                    setChat(p => [...p, m.results
                        ? { role: 'report', results: m.results }
                        : { role: 'assistant', content: 'Analysis complete.' }]); break;
                case 'chat_response':
                    setChat(p => [...p, { role: 'assistant', content: m.message }]); break;
                case 'error': setError(m.message); break;
            }
        };

        sock.onclose = (e) => {
            if (!isCurrent()) return;
            setConnected(false);
            // Reaped for inactivity. Reconnection is deliberately left until
            // something needs the socket again -- `send` reopens it, and the
            // frame loop calls `send` -- because reconnecting straight away
            // would just wake the server back up and defeat the timeout.
            if (e.code === WS_CLOSE_IDLE) { setError(null); return; }
            if (e.wasClean) return;
            setError(everConnected.current ? 'Lost connection. Reconnecting…' : UNREACHABLE);
            reco.current = setTimeout(connect, 3000);
        };
        sock.onerror = () => {
            if (!isCurrent()) return;
            setError(everConnected.current ? 'Lost connection. Reconnecting…' : UNREACHABLE);
            sock.close();
        };
    }, []);

    // Keepalive. Gated on visibility, which is the whole point: a visible tab is
    // a present user and worth keeping a connection open for, while a hidden one
    // should be allowed to lapse so the server can scale to zero.
    useEffect(() => {
        const id = setInterval(() => {
            if (document.hidden) return;
            if (ws.current?.readyState === WebSocket.OPEN) {
                ws.current.send(JSON.stringify({ type: 'ping' }));
            }
        }, KEEPALIVE_MS);
        return () => clearInterval(id);
    }, []);

    useEffect(() => {
        connect();
        // Coming back to a backgrounded tab should feel instant rather than
        // waiting for the next frame tick to notice the socket is gone.
        const onVisibility = () => { if (!document.hidden) connect(); };
        document.addEventListener('visibilitychange', onVisibility);
        return () => {
            document.removeEventListener('visibilitychange', onVisibility);
            clearTimeout(reco.current);
            const sock = ws.current;
            // Released *before* the close is arranged, so that the immediate
            // re-mount StrictMode performs in development builds a fresh socket
            // instead of finding this one still CONNECTING and returning early.
            // That early return left the app with a socket already scheduled to
            // close, and a clean close does not trigger the reconnect path -- so
            // it sat on "Connecting to server…" indefinitely.
            ws.current = null;
            if (!sock) return;
            // Close whether OPEN or still CONNECTING; the old check skipped
            // CONNECTING sockets and leaked them.
            if (sock.readyState === WebSocket.OPEN) {
                sock.close(1000);
            } else if (sock.readyState === WebSocket.CONNECTING) {
                sock.onopen = () => sock.close(1000);
            }
        };
    }, [connect]);

    /* ── senders ─────────────────────────────────── */
    const send = useCallback((msg) => {
        if (ws.current?.readyState !== WebSocket.OPEN) {
            // Reopen on demand. After an idle close this is what brings the
            // socket back: the caller's message is dropped (it reports false,
            // and the frame loop simply sends another one shortly), but the
            // connection is live again for the next one.
            connect();
            return false;
        }
        ws.current.send(JSON.stringify(msg));
        return true;
    }, [connect]);

    const sendFrame      = useCallback((b64) => send({ type: 'frame', data: b64, timestamp: Date.now() / 1000 }), [send]);
    // Only echo the user's message once the socket has actually accepted it,
    // otherwise a closed connection silently shows the message as sent.
    const sendChat       = useCallback((txt) => {
        if (send({ type: 'chat', message: txt })) {
            setChat(p => [...p, { role: 'user', content: txt }]);
            return true;
        }
        setError('Not connected — your message was not sent.');
        return false;
    }, [send]);
    const startRecording = useCallback(() => send({ type: 'start_recording' }), [send]);
    const stopRecording  = useCallback(() => send({ type: 'stop_recording' }),  [send]);
    const sendAudio      = useCallback((b64) => send({ type: 'audio_complete', data: b64 }), [send]);
    const newTopic       = useCallback(() => send({ type: 'request_new_topic' }), [send]);

    return (
        <Ctx.Provider value={{ connected, emotion, chat, topic, processing, error, sessionId,
            sendFrame, sendChat, startRecording, stopRecording, sendAudio, newTopic,
            capture }}>
            {children}
        </Ctx.Provider>
    );
}
