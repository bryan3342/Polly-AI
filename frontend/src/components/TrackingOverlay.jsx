import { useRef, useEffect } from 'react';
import { coverTransform } from './trackingProjection';

/**
 * Draws what is being tracked, over the live video, at the video's own rate.
 *
 * Two things keep this immediate. It reads tracking from a ref rather than from
 * props, so new positions never go through React — nothing re-renders, at any
 * frame rate. And it runs its own animation loop, so it redraws in step with
 * the display rather than whenever a message happens to arrive.
 *
 * Everything drawn comes from the frame currently on screen, so an indicator
 * sitting on your hand means that hand is being tracked right now.
 */

const FACE_COLOR = '#10b981';   // green: the face
const HAND_COLOR = '#f59e0b';   // amber: hands
const TIP_COLOR = '#fbbf24';    // fingertips, drawn larger than the joints
const FINGERTIPS = new Set([4, 8, 12, 16, 20]);

export default function TrackingOverlay({ trackingRef, videoRef, active, onPresence }) {
    const canvasRef = useRef(null);
    // Last reported presence, so the status chip is only told when it changes
    // rather than sixty times a second.
    const presenceRef = useRef({ face: false, hands: 0 });

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return undefined;
        const ctx = canvas.getContext('2d');
        let raf = 0;
        let sized = { w: 0, h: 0, dpr: 0 };

        const draw = () => {
            raf = requestAnimationFrame(draw);

            const { width: cssW, height: cssH } = canvas.getBoundingClientRect();
            if (!cssW || !cssH) return;

            // Resizing a canvas clears it, so only do it when it actually
            // changed; every frame would blank the drawing half the time.
            const dpr = window.devicePixelRatio || 1;
            if (sized.w !== cssW || sized.h !== cssH || sized.dpr !== dpr) {
                canvas.width = cssW * dpr;
                canvas.height = cssH * dpr;
                sized = { w: cssW, h: cssH, dpr };
            }
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            ctx.clearRect(0, 0, cssW, cssH);

            const video = videoRef?.current;
            const tracking = trackingRef?.current;
            if (!active || !video || !tracking) return;

            const fw = video.videoWidth;
            const fh = video.videoHeight;
            const transform = coverTransform(fw, fh, cssW, cssH);
            if (!transform) return;
            const { scale, offsetX, offsetY } = transform;
            const toX = (nx) => offsetX + nx * fw * scale;
            const toY = (ny) => offsetY + ny * fh * scale;

            // ── face ─────────────────────────────────────────────────
            const face = tracking.face;
            if (face) {
                const px = toX(face.x);
                const py = toY(face.y);
                const pw = face.width * fw * scale;
                const ph = face.height * fh * scale;

                ctx.strokeStyle = FACE_COLOR;
                ctx.lineWidth = 2;
                // Corner brackets rather than a closed rectangle: it reads as a
                // tracking reticle and leaves the face itself unobscured.
                const c = Math.min(pw, ph) * 0.22;
                ctx.beginPath();
                ctx.moveTo(px, py + c); ctx.lineTo(px, py); ctx.lineTo(px + c, py);
                ctx.moveTo(px + pw - c, py); ctx.lineTo(px + pw, py); ctx.lineTo(px + pw, py + c);
                ctx.moveTo(px + pw, py + ph - c); ctx.lineTo(px + pw, py + ph); ctx.lineTo(px + pw - c, py + ph);
                ctx.moveTo(px + c, py + ph); ctx.lineTo(px, py + ph); ctx.lineTo(px, py + ph - c);
                ctx.stroke();
            }

            // ── hands ────────────────────────────────────────────────
            const bones = tracking.connections || [];
            for (const points of tracking.hands || []) {
                if (!points.length) continue;

                ctx.strokeStyle = HAND_COLOR;
                ctx.lineWidth = 2;
                ctx.beginPath();
                for (const [a, b] of bones) {
                    if (!points[a] || !points[b]) continue;
                    ctx.moveTo(toX(points[a][0]), toY(points[a][1]));
                    ctx.lineTo(toX(points[b][0]), toY(points[b][1]));
                }
                ctx.stroke();

                points.forEach(([nx, ny], i) => {
                    const tip = FINGERTIPS.has(i);
                    ctx.beginPath();
                    ctx.arc(toX(nx), toY(ny), tip ? 4 : 2.5, 0, Math.PI * 2);
                    ctx.fillStyle = tip ? TIP_COLOR : HAND_COLOR;
                    ctx.fill();
                });
            }

            // Tell the status chip only on a change of state.
            const now = { face: !!face, hands: (tracking.hands || []).length };
            const before = presenceRef.current;
            if (now.face !== before.face || now.hands !== before.hands) {
                presenceRef.current = now;
                onPresence?.(now);
            }
        };

        raf = requestAnimationFrame(draw);
        return () => cancelAnimationFrame(raf);
    }, [trackingRef, videoRef, active, onPresence]);

    return <canvas ref={canvasRef} className="tracking-overlay" aria-hidden="true" />;
}
