"""Measure face detection against a live webcam, at several search widths.

Why this exists: the server downscales each frame before searching it for a
face, because locating the face -- not classifying the emotion -- dominates the
per-frame cost. On a tenth of a shared core, searching a 640x480 frame measured
2231 ms against a 1000 ms frame interval, while the emotion classification
behind it took 166 ms. Searching a 320px copy took 435 ms.

That trade only holds if detection still *finds* the face. How small a copy is
small enough depends on things no synthetic benchmark can tell you: your camera,
how far back you sit, your lighting, and how fast you move -- motion blur is
what a Haar cascade handles worst, and a debate practice session is full of it.

So this measures both halves against your actual camera:

    hit rate   -- how often a face is found, relative to full resolution
    speed      -- milliseconds per frame at each width

Run it, sit as you would while practising, and *move the way you actually move*
-- lean in, turn your head, gesture, talk. The number to pick is the smallest
width whose hit rate stays close to full resolution while you are moving.

    python tests/demos/detection_tuning_demo.py [seconds]

Then set it for the server:

    DETECT_WIDTH=<value>

Manual only: it needs a camera, so it is not part of the automated suite.
"""

import sys
import time
from collections import defaultdict

import cv2

# Full resolution is included as the baseline every other width is judged
# against; it is what the server did before downscaling.
WIDTHS = [None, 480, 400, 320, 240]
DEFAULT_SECONDS = 20


def label(width):
    return "full res" if width is None else f"{width}px"


def detect(cascade, frame, width):
    """Search `frame` for faces, downscaled to `width`. Returns (boxes, seconds)."""
    height, original_width = frame.shape[:2]
    scale = width / original_width if width and original_width > width else 1.0

    started = time.monotonic()
    if scale < 1.0:
        search = cv2.resize(
            frame, (int(original_width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA,
        )
    else:
        search = frame
    gray = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
    boxes = cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
    elapsed = time.monotonic() - started

    return [[int(v / scale) for v in box] for box in boxes], elapsed


def main(seconds):
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("Could not open the camera. Grant camera access and try again.")
        return 1

    hits = defaultdict(int)
    total_time = defaultdict(float)
    sizes = []
    frames = 0

    print(f"Recording for {seconds}s — move the way you would while debating: "
          f"lean in, turn your head, gesture, talk.\n")
    deadline = time.monotonic() + seconds

    try:
        while time.monotonic() < deadline:
            ok, frame = camera.read()
            if not ok:
                continue
            frames += 1

            for width in WIDTHS:
                boxes, elapsed = detect(cascade, frame, width)
                total_time[width] += elapsed
                if boxes:
                    hits[width] += 1
                    if width is None:
                        # How much of the frame the face fills, at full res.
                        biggest = max(boxes, key=lambda b: b[2] * b[3])
                        sizes.append(biggest[2] / frame.shape[1])

            remaining = int(deadline - time.monotonic())
            print(f"\r  {frames} frames, {remaining}s left…", end="", flush=True)
    finally:
        camera.release()

    if not frames:
        print("\nNo frames captured.")
        return 1

    baseline = hits[None]
    print(f"\n\n{frames} frames captured. Face found in {baseline} of them at full resolution.\n")
    print(f"  {'width':>9}  {'hit rate':>9}  {'vs full':>8}  {'ms/frame':>9}   verdict")
    print(f"  {'-'*9}  {'-'*9}  {'-'*8}  {'-'*9}   {'-'*7}")

    for width in WIDTHS:
        rate = hits[width] / frames
        relative = (hits[width] / baseline) if baseline else 0.0
        ms = total_time[width] / frames * 1000
        if width is None:
            verdict = "baseline"
        elif relative >= 0.98:
            verdict = "no measurable loss"
        elif relative >= 0.90:
            verdict = "slight loss"
        else:
            verdict = "MISSES FACES — too small"
        print(f"  {label(width):>9}  {rate:>8.0%}  {relative:>7.0%}  {ms:>8.0f}   {verdict}")

    if sizes:
        smallest = min(sizes)
        print(f"\nYour face filled {min(sizes):.0%}-{max(sizes):.0%} of the frame width.")
        # The cascade's 30px floor is what sets the limit at a given width.
        print(f"At its smallest, a search width below ~{int(30 / smallest)}px "
              f"could not have found it at all.")

    print("\nThese timings are on this machine. The deployed instance is slower — a\n"
          "tenth of a core measured roughly 70x this — so read the hit rates here and\n"
          "the relative speeds, not the absolute milliseconds.")
    print("\nPick the smallest width with no measurable loss, then set DETECT_WIDTH to it.")
    return 0


if __name__ == "__main__":
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SECONDS
    raise SystemExit(main(seconds))
