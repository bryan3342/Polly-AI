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
const FRAME_MS = 1000;

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
        try { ws.current = new WebSocket(WS_URL); }
        catch { setError(UNREACHABLE); return; }

        ws.current.onopen = () => {
            everConnected.current = true;
            setConnected(true);
            setError(null);
        };

        ws.current.onmessage = (e) => {
            let m; try { m = JSON.parse(e.data); } catch { return; }
            switch (m.type) {
                case 'session_assigned':  setSessionId(m.session_id); break;
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

        ws.current.onclose = (e) => {
            setConnected(false);
            if (e.wasClean) return;
            setError(everConnected.current ? 'Lost connection. Reconnecting…' : UNREACHABLE);
            reco.current = setTimeout(connect, 3000);
        };
        ws.current.onerror = () => {
            setError(everConnected.current ? 'Lost connection. Reconnecting…' : UNREACHABLE);
            ws.current?.close();
        };
    }, []);

    useEffect(() => {
        connect();
        return () => {
            clearTimeout(reco.current);
            const sock = ws.current;
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
        if (ws.current?.readyState !== WebSocket.OPEN) return false;
        ws.current.send(JSON.stringify(msg));
        return true;
    }, []);

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
            sendFrame, sendChat, startRecording, stopRecording, sendAudio, newTopic, FRAME_MS }}>
            {children}
        </Ctx.Provider>
    );
}
