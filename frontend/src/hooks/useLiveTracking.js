import { useEffect, useRef, useState } from 'react';

/**
 * Face and hand tracking that runs in this browser, on every video frame.
 *
 * Tracking used to happen on the server: each frame was encoded to JPEG, sent
 * over the socket, decoded, searched, and the coordinates sent back. Even with
 * everything tuned -- 640px frames, 20 ms of server work, a 26 ms round trip --
 * an indicator could not appear less than about 90 ms after the movement it
 * described, and refreshed only as often as frames were sent. Hands move faster
 * than that, so it read as lag no matter how fast either end got.
 *
 * The fix is not to make the round trip faster but to stop making one. MediaPipe
 * ships a WASM build of the same models the server was running, which can be
 * pointed straight at the video element -- so the overlay is drawn from the very
 * frame being displayed. There is no network in the loop and nothing to be
 * behind.
 *
 * Results are written to a ref rather than to state, deliberately. Tracking
 * updates ~60 times a second, and this app keeps its WebSocket data in a context
 * that four components read; putting tracking there re-rendered the entire app
 * on every frame. The overlay reads this ref from its own animation loop, so the
 * React tree never re-renders for tracking at all.
 *
 * The server still receives frames, at a much lower rate, for the DeepFace
 * emotion classification that has no browser equivalent and that the score
 * depends on.
 */

const WASM_PATH = '/mediapipe/wasm';
const HAND_MODEL = '/mediapipe/models/hand_landmarker.task';
const FACE_MODEL = '/mediapipe/models/blaze_face_short_range.tflite';

export function useLiveTracking(videoRef, enabled) {
    // { face: {x, y, width, height} | null, hands: [[[x, y], ...]], connections }
    const resultRef = useRef({ face: null, hands: [], connections: [] });
    const [status, setStatus] = useState('loading');   // loading | ready | unavailable

    useEffect(() => {
        if (!enabled) return undefined;

        let cancelled = false;
        let raf = 0;
        let handLandmarker = null;
        let faceDetector = null;
        let lastTimestamp = -1;

        (async () => {
            let vision;
            try {
                vision = await import('@mediapipe/tasks-vision');
                const fileset = await vision.FilesetResolver.forVisionTasks(WASM_PATH);

                // GPU where the browser offers it: this runs on every displayed
                // frame, so it has to be cheap enough to leave the main thread
                // free for the rest of the page.
                const base = (modelAssetPath) => ({
                    baseOptions: { modelAssetPath, delegate: 'GPU' },
                    runningMode: 'VIDEO',
                });

                [handLandmarker, faceDetector] = await Promise.all([
                    vision.HandLandmarker.createFromOptions(fileset, {
                        ...base(HAND_MODEL), numHands: 2,
                    }),
                    vision.FaceDetector.createFromOptions(fileset, {
                        ...base(FACE_MODEL), minDetectionConfidence: 0.5,
                    }),
                ]);

                if (cancelled) return;
                resultRef.current.connections =
                    (vision.HandLandmarker.HAND_CONNECTIONS || [])
                        .map((c) => [c.start, c.end]);
                setStatus('ready');
            } catch (error) {
                // Tracking is an indicator, not the app. Recording, emotion,
                // transcription and scoring all work without it.
                console.warn('Live tracking unavailable:', error);
                if (!cancelled) setStatus('unavailable');
                return;
            }

            const tick = () => {
                raf = requestAnimationFrame(tick);
                const video = videoRef.current;
                if (!video || video.readyState < video.HAVE_CURRENT_DATA) return;

                // VIDEO mode requires strictly increasing timestamps and rejects
                // a repeat, which happens whenever this loop runs faster than the
                // camera produces frames.
                const timestamp = video.currentTime * 1000;
                if (timestamp <= lastTimestamp) return;
                lastTimestamp = timestamp;

                try {
                    const hands = handLandmarker.detectForVideo(video, timestamp);
                    const faces = faceDetector.detectForVideo(video, timestamp);

                    resultRef.current.hands = (hands.landmarks || [])
                        .map((points) => points.map((p) => [p.x, p.y]));

                    const box = faces.detections?.[0]?.boundingBox;
                    // Normalised against the video's own dimensions, so the
                    // overlay never needs to know the capture resolution.
                    resultRef.current.face = box ? {
                        x: box.originX / video.videoWidth,
                        y: box.originY / video.videoHeight,
                        width: box.width / video.videoWidth,
                        height: box.height / video.videoHeight,
                    } : null;
                } catch {
                    // One dropped frame is not worth tearing the loop down; the
                    // next arrives in ~16 ms.
                }
            };
            raf = requestAnimationFrame(tick);
        })();

        return () => {
            cancelled = true;
            cancelAnimationFrame(raf);
            handLandmarker?.close?.();
            faceDetector?.close?.();
            resultRef.current = { face: null, hands: [], connections: [] };
        };
    }, [videoRef, enabled]);

    return { resultRef, status };
}
