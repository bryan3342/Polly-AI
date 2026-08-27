"""Bake the emotion weights into the image, and prove the trimmed stack runs.

Two jobs, deliberately in one build step:

1. Build the DeepFace emotion model so its weights are baked into the image
   rather than downloaded during a user's first frame.
2. Exercise the real inference path end to end.

(2) exists because deepface is installed with ``--no-deps`` (see
requirements-nodeps.txt). That substitution is what keeps tensorflow-cpu and
opencv-python-headless in place, but it also means pip is no longer checking
deepface's imports for us -- and the unit suite cannot cover the gap, since CI
deliberately installs none of the ML stack. Without this script a new eager
import inside deepface would sail through the build and fail on the first frame
of the first real session.

Run by the Dockerfile. A non-zero exit fails the build, which is the point.
"""

import sys

import cv2
import numpy as np
from deepface import DeepFace


def main() -> int:
    # Headless OpenCV must work with no libGL/X11 present; the Dockerfile no
    # longer installs them.
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    if cascade.empty():
        print("FAIL: Haar cascade did not load", file=sys.stderr)
        return 1

    frame = np.zeros((128, 128, 3), dtype=np.uint8)
    cascade.detectMultiScale(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), 1.1, 5,
                             minSize=(30, 30))

    # Downloads and caches the weights under DEEPFACE_HOME.
    DeepFace.build_model("Emotion", task="facial_attribute")

    # The same call EmotionService.analyze_frame makes, including
    # detector_backend="skip" -- the path that decides which of deepface's
    # optional imports are actually reachable.
    result = DeepFace.analyze(
        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
        actions=["emotion"],
        enforce_detection=False,
        detector_backend="skip",
        silent=True,
    )
    analysis = result[0] if isinstance(result, list) else result

    if "emotion" not in analysis or not analysis.get("dominant_emotion"):
        print(f"FAIL: unexpected DeepFace result: {analysis}", file=sys.stderr)
        return 1

    print(f"OK: cv2 {cv2.__version__}, emotion model ready "
          f"({len(analysis['emotion'])} classes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
