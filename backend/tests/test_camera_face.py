import argparse
import time
import threading
import queue
import sys

import cv2

# Test script for camera access and face detection using OpenCV.

class FrameGrabber(threading.Thread):

    def __init__(self, cap, out_q: queue.Queue, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.cap = cap
        self.q = out_q
        self.stop_event = stop_event

    def run(self):
        while not self.stop_event.is_set():
            ret, frame = self.cap.read()
            if not ret:
                # brief sleep to avoid tight loop if camera fails
                time.sleep(0.01)
                continue
            try:
                # keep only the latest frame
                if self.q.full():
                    try:
                        self.q.get_nowait()
                    except queue.Empty:
                        pass
                self.q.put_nowait((ret, frame))
            except queue.Full:
                # unlikely because we popped when full, but ignore if it happens
                pass


def run_camera(target_fps: float = 10.0, use_threaded: bool = False):
    print("Testing Camera Access with target FPS:", target_fps)
    print("Press 'q' to quit the camera feed.")

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not open camera.")
        sys.exit(1)

    # Setting Camera FPS
    cap.set(cv2.CAP_PROP_FPS, target_fps)

    print("Camera opened successfully.")
    print(f" Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f" Driver FPS: {cap.get(cv2.CAP_PROP_FPS)}\n")

    frame_interval = 1.0 / float(target_fps)

    q = queue.Queue(maxsize=1)
    stop_event = threading.Event()
    grabber = None
    if use_threaded:
        grabber = FrameGrabber(cap, q, stop_event)
        grabber.start()

    frame_count = 0
    face_detected_count = 0

    measure_frames = 0
    measure_start = time.perf_counter()

    try:
        while True:
            frame_start = time.perf_counter()

            if use_threaded:
                try:
                    ret, frame = q.get(timeout=1.0)
                except queue.Empty:
                    # no frame available from thread - try direct read as fallback
                    ret, frame = cap.read()
            else:
                ret, frame = cap.read()

            if not ret:
                print("Warning: Could not read frame (skipping).")
                # small sleep to avoid hammering when camera temporarily fails
                time.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)

            frame_count += 1

            faces = face_cascade.detectMultiScale(
                frame,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30),
            )

            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 4)
                cv2.putText(
                    frame,
                    "Face Detected",
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (0, 255, 0),
                    2,
                )

            if len(faces) > 0:
                face_detected_count += 1

            status_text = f"Faces: {len(faces)} | Frame Detections: {frame_count}"
            cv2.putText(
                frame,
                status_text,
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 0, 0),
                2,
            )

            cv2.imshow("Face Detection Feed", frame)

            # Performance measurement
            measure_frames += 1
            if measure_frames >= 30:
                now = time.perf_counter()
                actual_fps = measure_frames / (now - measure_start)
                print(f"Actual FPS: {actual_fps:.2f} | Frames: {frame_count} | Detection Rate: {(face_detected_count / frame_count) * 100:.2f}%")
                measure_frames = 0
                measure_start = now

            # throttle to target_fps using elapsed processing time
            elapsed = time.perf_counter() - frame_start
            remaining = frame_interval - elapsed

            # cv2.waitKey expects milliseconds;
            wait_ms = int(max(1, remaining * 1000))
            key = cv2.waitKey(wait_ms) & 0xFF
            if key == ord("q"):
                break

    finally:
        # cleanup
        if grabber is not None:
            stop_event.set()
            grabber.join(timeout=1.0)
        cap.release()
        cv2.destroyAllWindows()
        print("Camera released and all windows closed.")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--target-fps", type=float, default=60.0, help="Target frames per second to aim for (software throttle)")
    p.add_argument("--threaded", action="store_true", help="Use background capture thread to keep frames fresh")
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run_camera(target_fps=args.target_fps, use_threaded=args.threaded)
