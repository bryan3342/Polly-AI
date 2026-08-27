import { useRef, useEffect, useState } from 'react';
import { useWS } from '../context/wsContext';
import { FaVideoSlash } from 'react-icons/fa';

export default function VideoBox({ isRecording, cameraOn, muted, onAudioReady }) {
    const { sendFrame, emotion, connected, FRAME_MS, IDLE_FRAME_MS } = useWS();
    const videoRef   = useRef(null);
    const canvasRef  = useRef(null);
    const streamRef  = useRef(null);
    const recRef     = useRef(null);
    const chunksRef  = useRef([]);
    const cbRef      = useRef(onAudioReady);
    const [ready, setReady]      = useState(false);
    const [camErr, setCamErr]    = useState(null);
    cbRef.current = onAudioReady;

    /* ── get stream ──────────────────────────────── */
    useEffect(() => {
        let dead = false;
        (async () => {
            try {
                const s = await navigator.mediaDevices.getUserMedia({
                    video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' },
                    audio: true,
                });
                if (dead) { s.getTracks().forEach(t => t.stop()); return; }
                streamRef.current = s;
                if (videoRef.current) videoRef.current.srcObject = s;
                setReady(true);
            } catch { setCamErr('Camera / mic access denied.'); }
        })();
        return () => { dead = true; streamRef.current?.getTracks().forEach(t => t.stop()); };
    }, []);

    /* ── camera / mute toggles ───────────────────── */
    useEffect(() => { streamRef.current?.getVideoTracks().forEach(t => { t.enabled = cameraOn; }); }, [cameraOn, ready]);
    useEffect(() => { streamRef.current?.getAudioTracks().forEach(t => { t.enabled = !muted; }); },  [muted, ready]);

    /* ── send frames ─────────────────────────────── */
    // Full rate while recording, slower while idle: every frame costs a
    // DeepFace inference server-side, and only the recorded ones end up in the
    // report.
    const frameInterval = isRecording ? FRAME_MS : IDLE_FRAME_MS;
    useEffect(() => {
        const id = setInterval(() => {
            // Send nothing at all while the tab is in the background. This is
            // what lets the server's idle timeout actually fire: browsers still
            // run this timer in a hidden tab, just throttled to roughly once a
            // minute, and one frame a minute is enough to keep a connection
            // looking busy forever.
            if (document.hidden) return;
            const v = videoRef.current, c = canvasRef.current;
            if (!v || !c || v.readyState < v.HAVE_CURRENT_DATA || !cameraOn || !connected) return;
            const ctx = c.getContext('2d');
            c.width = v.videoWidth; c.height = v.videoHeight;
            ctx.drawImage(v, 0, 0);
            sendFrame(c.toDataURL('image/jpeg', 0.6));
        }, frameInterval);
        return () => clearInterval(id);
    }, [frameInterval, sendFrame, cameraOn, connected]);

    /* ── audio recording ─────────────────────────── */
    useEffect(() => {
        if (!ready) return;
        if (isRecording) {
            const as = new MediaStream(streamRef.current.getAudioTracks());
            const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm';
            chunksRef.current = [];
            const r = new MediaRecorder(as, { mimeType: mime });
            r.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data); };
            r.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: mime });
                const rd = new FileReader();
                // Always notify, even on read failure -- the callback is what tells
                // the backend the recording ended, so swallowing an error here
                // would strand the session in "recording" forever.
                rd.onload  = () => cbRef.current?.(rd.result);
                rd.onerror = () => { console.error('Audio read failed', rd.error); cbRef.current?.(null); };
                rd.readAsDataURL(blob);
            };
            r.start(1000);
            recRef.current = r;
        } else if (recRef.current?.state === 'recording') {
            recRef.current.stop();
            recRef.current = null;
        }
    }, [isRecording, ready]);

    const dom = emotion?.dominant_emotion;
    const conf = emotion?.confidence;

    return (
        <div className={`video-panel ${!cameraOn ? 'camera-off' : ''}`}>
            {/* camera off overlay */}
            {!cameraOn && (
                <div className="camera-off-msg">
                    <FaVideoSlash />
                    <span>Camera off</span>
                </div>
            )}

            {/* error */}
            {camErr && (
                <div className="camera-off-msg">
                    <span style={{ color: '#f87171' }}>{camErr}</span>
                </div>
            )}

            <video ref={videoRef} autoPlay playsInline muted />
            <canvas ref={canvasRef} hidden />

            {/* REC badge */}
            {isRecording && (
                <div className="video-overlay rec-badge">
                    <div className="rec-dot" />
                    <span>Rec</span>
                </div>
            )}

            {/* connection dot */}
            <div className="video-overlay conn-dot"
                 style={{ background: connected ? '#10b981' : '#ef4444' }}
                 title={connected ? 'Connected' : 'Disconnected'} />

            {/* emotion */}
            {cameraOn && emotion?.face_detected && dom && (
                <div className="video-overlay emotion-chip">
                    <div className="label">{dom}</div>
                    {conf != null && <div className="conf">{(conf * 100).toFixed(0)}%</div>}
                </div>
            )}
        </div>
    );
}
