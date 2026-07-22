import { useState, useEffect, useRef, useCallback } from 'react';
import { Ctx } from './wsContext';

function getWsBase() {
    if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL;
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${proto}//${window.location.host}`;
}
const WS_BASE = getWsBase();
const SID = 'user-' + (crypto.randomUUID?.() ?? Math.random().toString(36).slice(2, 9));
const WS_URL = `${WS_BASE}/ws/${SID}`;
const FRAME_MS = 1000;

export function WebSocketProvider({ children }) {
    const [connected, setConnected]     = useState(false);
    const [emotion, setEmotion]         = useState(null);
    const [chat, setChat]               = useState([]);
    const [topic, setTopic]             = useState(null);
    const [processing, setProcessing]   = useState(false);
    const [error, setError]             = useState(null);
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
        catch { setError('Backend not reachable.'); return; }

        ws.current.onopen = () => { setConnected(true); setError(null); };

        ws.current.onmessage = (e) => {
            let m; try { m = JSON.parse(e.data); } catch { return; }
            switch (m.type) {
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
            if (!e.wasClean) { setError('Lost connection. Reconnecting...'); reco.current = setTimeout(connect, 3000); }
        };
        ws.current.onerror = () => { setError('Cannot reach backend.'); ws.current?.close(); };
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
        <Ctx.Provider value={{ connected, emotion, chat, topic, processing, error,
            sendFrame, sendChat, startRecording, stopRecording, sendAudio, newTopic, FRAME_MS }}>
            {children}
        </Ctx.Provider>
    );
}
