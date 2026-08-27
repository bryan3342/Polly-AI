import { useRef, useEffect, useState, useCallback } from 'react';
import { useWS } from '../context/wsContext';
import { FaVideoSlash } from 'react-icons/fa';
import TrackingOverlay from './TrackingOverlay';
import { useLiveTracking } from '../hooks/useLiveTracking';

export default function VideoBox({ isRecording, cameraOn, muted, onAudioReady }) {
    const { sendFrame, emotion, connected, capture } = useWS();
    const videoRef   = useRef(null);
    const canvasRef  = useRef(null);
    const streamRef  = useRef(null);
    const recRef     = useRef(null);
    const chunksRef  = useRef([]);
    const cbRef      = useRef(onAudioReady);
    const [ready, setReady]      = useState(false);
    const [camErr, setCamErr]    = useState(null);
    // Presence only — the coordinates never enter React state, or every frame
    // would re-render the app. See useLiveTracking.
    const [presence, setPresence] = useState({ face: false, hands: 0 });
    cbRef.current = onAudioReady;

    // Tracking runs here, against the displayed video, rather than on the
    // server: a per-frame round trip could not put an indicator on screen less
    // than ~90 ms after the movement it described.
    const { resultRef, status: trackStatus } = useLiveTracking(videoRef, ready && cameraOn);
    const onPresence = useCallback((p) => setPresence(p), []);

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
    // report. Both rates come from the server, which is the only side that
    // knows how fast it can actually analyse them.
    const frameInterval = isRecording ? capture.frameMs : capture.idleFrameMs;
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
            // Downscale before encoding. toDataURL runs synchronously on the
            // main thread and its cost scales with pixel count, so encoding the
            // full 720p frame fifteen times a second was the largest single
            // source of the delay — before a byte had even left the browser.
            // Analysis gains nothing from those pixels; the display keeps them.
            const target = capture.captureWidth || v.videoWidth;
            const scale = v.videoWidth > target ? target / v.videoWidth : 1;
            c.width = Math.round(v.videoWidth * scale);
            c.height = Math.round(v.videoHeight * scale);
            const ctx = c.getContext('2d');
            ctx.drawImage(v, 0, 0, c.width, c.height);
            sendFrame(c.toDataURL('image/jpeg', capture.jpegQuality));
        }, frameInterval);
        return () => clearInterval(id);
    }, [frameInterval, capture.jpegQuality, capture.captureWidth, sendFrame, cameraOn, connected]);

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
    const handLabel = presence.hands === 1 ? '1 hand' : 'Hands';

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

            {/* What the server is measuring, drawn over the video it measured.
                Its coordinates come back from the analysis itself, so an
                indicator appearing is evidence the frame was received and
                understood — not a local guess about where a face might be. */}
            <TrackingOverlay trackingRef={resultRef} videoRef={videoRef}
                             active={cameraOn} onPresence={onPresence} />

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

            {/* Tracking status, top right. States what is being tracked right
                now, so an absent indicator is distinguishable from a broken
                one. Driven by the overlay's own loop, which reports only on a
                change of state rather than every frame. */}
            {cameraOn && (
                <div className="video-overlay track-status">
                    {trackStatus === 'unavailable' ? (
                        <span className="off" title="Tracking could not start; everything else still works">
                            <i /> Tracking off
                        </span>
                    ) : (
                        <>
                            <span className={presence.face ? 'on face' : 'off'}>
                                <i /> Face
                            </span>
                            <span className={presence.hands ? 'on hands' : 'off'}>
                                <i /> {handLabel}
                            </span>
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
