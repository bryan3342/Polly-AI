import { useState, useEffect, useCallback } from 'react';
import { useWS } from './context/WebSocketContext';
import VideoBox from './components/VideoBox';
import Chatbox  from './components/Chatbox';
import Toolbar  from './components/Toolbar';

export default function App() {
    const { connected, error, startRecording, stopRecording, sendAudio } = useWS();

    const [recording, setRecording] = useState(false);
    const [cameraOn, setCameraOn]   = useState(true);
    const [muted, setMuted]         = useState(false);
    const [time, setTime]           = useState(0);

    /* timer */
    useEffect(() => {
        if (!recording) return;
        setTime(0);
        const id = setInterval(() => setTime(t => t + 1), 1000);
        return () => clearInterval(id);
    }, [recording]);

    /* handlers */
    const handleRecord = useCallback(() => { setRecording(true);  startRecording(); }, [startRecording]);
    const handleStop   = useCallback(() => { setRecording(false); }, []);
    const handleAudio  = useCallback((b64) => { sendAudio(b64); stopRecording(); }, [sendAudio, stopRecording]);

    return (
        <div className="app">
            {error && <div className="error-banner">{error}</div>}

            {/* ── header ─────────────────────── */}
            <header className="header">
                <div className="header-brand">
                    <h1>Polly AI</h1>
                    <span className="header-badge">Debate Coach</span>
                </div>
                <div className="header-status">
                    <span className={`status-dot ${connected ? 'on' : 'off'}`} />
                    {connected ? 'Connected' : 'Offline'}
                </div>
            </header>

            {/* ── main: video + chat ─────────── */}
            <main className="main">
                <VideoBox
                    isRecording={recording}
                    cameraOn={cameraOn}
                    muted={muted}
                    onAudioReady={handleAudio}
                />
                <Chatbox />
            </main>

            {/* ── toolbar ────────────────────── */}
            <Toolbar
                isRecording={recording}
                cameraOn={cameraOn}
                muted={muted}
                time={time}
                onRecord={handleRecord}
                onStop={handleStop}
                onCam={() => setCameraOn(v => !v)}
                onMic={() => setMuted(v => !v)}
            />
        </div>
    );
}
