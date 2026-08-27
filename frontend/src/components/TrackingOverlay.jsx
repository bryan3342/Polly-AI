import { useRef, useEffect } from 'react';
import { coverTransform, projectBox, projectPoint } from './trackingProjection';

/**
 * Draws what the server is actually tracking, over the live video.
 *
 * This is a confirmation, not decoration. Everything drawn here comes back from
 * the server's own analysis of a frame it received — so if a box is around your
 * face and a skeleton is on your hands, those are the pixels being measured. If
 * nothing is drawn, nothing is being measured, and the report will say so.
 *
 * The coordinate mapping lives in ./trackingProjection.js, where it can be
 * tested without a canvas or a camera.
 */

const FACE_COLOR = '#10b981';   // green: the face the emotion score comes from
const HAND_COLOR = '#f59e0b';   // amber: hands
const TIP_COLOR = '#fbbf24';    // fingertips, drawn larger than the joints

export default function TrackingOverlay({ tracking, connections, active }) {
    const canvasRef = useRef(null);

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');

        // Match the backing store to the displayed size, at device pixel ratio,
        // or the strokes look soft on a retina display.
        const { width: cssW, height: cssH } = canvas.getBoundingClientRect();
        if (!cssW || !cssH) return;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = cssW * dpr;
        canvas.height = cssH * dpr;
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, cssW, cssH);

        if (!active || !tracking) return;

        const fw = tracking.frame_width;
        const fh = tracking.frame_height;
        if (!fw || !fh) return;

        const transform = coverTransform(fw, fh, cssW, cssH);
        if (!transform) return;
        const project = (p) => projectPoint(p, transform, fw, fh);

        // ── face ─────────────────────────────────────────────────────
        // Sent in frame pixels, unlike the hands, because it comes from the
        // Haar cascade which works in pixels.
        if (tracking.face_detected && tracking.bounding_box) {
            const { x: px, y: py, width: pw, height: ph } =
                projectBox(tracking.bounding_box, transform);

            ctx.strokeStyle = FACE_COLOR;
            ctx.lineWidth = 2;
            // Corner brackets rather than a full rectangle: it reads as a
            // tracking reticle and keeps the face itself unobscured.
            const c = Math.min(pw, ph) * 0.22;
            ctx.beginPath();
            ctx.moveTo(px, py + c); ctx.lineTo(px, py); ctx.lineTo(px + c, py);
            ctx.moveTo(px + pw - c, py); ctx.lineTo(px + pw, py); ctx.lineTo(px + pw, py + c);
            ctx.moveTo(px + pw, py + ph - c); ctx.lineTo(px + pw, py + ph); ctx.lineTo(px + pw - c, py + ph);
            ctx.moveTo(px + c, py + ph); ctx.lineTo(px, py + ph); ctx.lineTo(px, py + ph - c);
            ctx.stroke();
        }

        // ── hands ────────────────────────────────────────────────────
        // Normalised 0-1, so they need no knowledge of capture resolution.
        const bones = connections || [];
        for (const hand of tracking.hands || []) {
            const pts = hand.landmarks || [];
            if (!pts.length) continue;

            ctx.strokeStyle = HAND_COLOR;
            ctx.lineWidth = 2;
            ctx.beginPath();
            for (const [a, b] of bones) {
                if (!pts[a] || !pts[b]) continue;
                const from = project(pts[a]);
                const to = project(pts[b]);
                ctx.moveTo(from.x, from.y);
                ctx.lineTo(to.x, to.y);
            }
            ctx.stroke();

            const tips = new Set([4, 8, 12, 16, 20]);
            pts.forEach((point, i) => {
                const { x, y } = project(point);
                ctx.beginPath();
                ctx.arc(x, y, tips.has(i) ? 4 : 2.5, 0, Math.PI * 2);
                ctx.fillStyle = tips.has(i) ? TIP_COLOR : HAND_COLOR;
                ctx.fill();
            });
        }
    }, [tracking, connections, active]);

    return <canvas ref={canvasRef} className="tracking-overlay" aria-hidden="true" />;
}
