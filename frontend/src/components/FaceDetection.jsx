import React, { useEffect, useRef } from "react";
import * as faceapi from "face-api.js";

export default function FaceDetection() {
  const containerRef = useRef(null);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    const MODEL_URL = "https://justadudewhohacks.github.io/face-api.js/models";
    let rafId;

    async function setupVideo() {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 1280, height: 720 },
      });
      const video = videoRef.current;
      video.srcObject = stream;
      await new Promise((res) => (video.onloadedmetadata = res));
      await video.play();
      requestAnimationFrame(syncOverlaySize);
    }

    function syncOverlaySize() {
      const container = containerRef.current;
      const canvas = canvasRef.current;
      const { width, height } = container.getBoundingClientRect();
      canvas.width = Math.round(width);
      canvas.height = Math.round(height);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
    }

    async function startDetection() {
      await faceapi.nets.tinyFaceDetector.loadFromUri(MODEL_URL);
      const video = videoRef.current;
      const canvas = canvasRef.current;

      const opts = new faceapi.TinyFaceDetectorOptions({
        inputSize: 320,
        scoreThreshold: 0.2,
      });

      const tick = async () => {
        const displaySize = { width: canvas.width, height: canvas.height };
        const dets = await faceapi.detectAllFaces(video, opts);
        const resized = faceapi.resizeResults(dets, displaySize);

        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        if (resized.length) {
          faceapi.draw.drawDetections(canvas, resized);
        }
        rafId = requestAnimationFrame(tick);
      };

      rafId = requestAnimationFrame(tick);
    }

    (async () => {
      await setupVideo();
      await startDetection();
      window.addEventListener("resize", syncOverlaySize);
    })();

    return () => {
      if (rafId) cancelAnimationFrame(rafId);
      window.removeEventListener("resize", syncOverlaySize);
      const v = videoRef.current;
      if (v?.srcObject) {
        v.srcObject.getTracks().forEach((t) => t.stop());
        v.srcObject = null;
      }
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{
        position: "relative",
        width: 899,
        height: 716,
        minWidth: 899,
        minHeight: 716,
        maxWidth: 899,
        maxHeight: 716,
        flex: "0 0 899px",
        overflow: "hidden",
        border: "3px solid rgba(148,163,184,0.6)",
        borderRadius: 8,
        background: "#000",
      }}
    >
      <video
        ref={videoRef}
        autoPlay
        muted
        playsInline
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover", // same “crop” look as your Figma
          display: "block",
        }}
      />
      <canvas
        ref={canvasRef}
        style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 9999 }}
      />
    </div>
  );
}
