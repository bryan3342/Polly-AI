"""Prove the trimmed stack runs, in the image, before anyone records into it.

Two jobs, deliberately in one build step:

1. Check no substituted wheel got reinstalled alongside its replacement.
2. Exercise the real inference path end to end, models and all.

(2) exists because the unit suite cannot cover it: CI deliberately installs none
of the ML stack, so nothing else in the tree would notice a missing model file,
an OpenCV build without the DNN module, or an ONNX file that downloaded as a
GitHub error page. All three fail identically at runtime, on the first frame of
someone's first session, and all three are caught here instead.

Run by the Dockerfile. A non-zero exit fails the build, which is the point.
"""

import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2
import numpy as np


def _installed(name: str) -> bool:
    try:
        distribution(name)
        return True
    except PackageNotFoundError:
        return False


def check_no_duplicate_wheels() -> int:
    """Fail if a substituted wheel got reinstalled alongside its replacement.

    mediapipe declares `opencv-contrib-python` with no upper bound. Installed
    normally it resolves to OpenCV 5 and lands a second cv2 on top of the pinned
    opencv-python-headless, so --no-deps is what keeps the substitution.

    Also fails if tensorflow comes back. Nothing needs it any more, emotion
    classification runs on an ONNX model through cv2.dnn, and it weighed 1.1 GB
    installed. A new dependency quietly pulling it back in would undo that
    without breaking anything, which is exactly the kind of regression nothing
    else here would notice.
    """
    problems = []

    for name in ("tensorflow", "tensorflow-cpu", "deepface", "tf-keras"):
        if _installed(name):
            problems.append(
                f"`{name}` is installed. Emotion classification runs on ONNX "
                f"through cv2.dnn; nothing should be pulling the TensorFlow "
                f"stack back in (it was 1.1 GB). Find what depends on it and "
                f"install that with --no-deps, or drop it"
            )

    # Any other distribution that also ships `cv2`. They install over each
    # other rather than beside each other -- measured: with
    # opencv-contrib-python present, `import cv2` reported 5.0.0 despite the 4.x
    # pin, and removing either one left cv2 with no cvtColor at all. OpenCV 5 is
    # what the pin at the top of requirements.txt exists to keep out.
    for name in ("opencv-python", "opencv-contrib-python",
                 "opencv-contrib-python-headless"):
        if _installed(name):
            problems.append(
                f"`{name}` is installed alongside opencv-python-headless. Both "
                f"ship cv2 and overwrite each other, so the effective OpenCV "
                f"version is whichever landed last. Install whatever pulled it "
                f"in with --no-deps; see requirements-nodeps.txt"
            )

    # The version actually in effect, which is the thing the pin is about.
    try:
        import cv2

        if int(cv2.__version__.split(".")[0]) >= 5:
            problems.append(
                f"OpenCV {cv2.__version__} is active. 5.x dropped "
                f"cv2.CascadeClassifier, which the emotion service falls back "
                f"to when YuNet is unavailable; requirements.txt pins below it "
                f"for that reason"
            )
    except Exception as exc:
        problems.append(f"could not determine the OpenCV version: {exc}")

    for problem in problems:
        print(f"FAIL: {problem}", file=sys.stderr)
    return 1 if problems else 0


def main() -> int:
    if check_no_duplicate_wheels() != 0:
        return 1

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

    # The real service, so both ONNX models are loaded the way a session loads
    # them. warm_up() swallows its own failures by design -- a broken model must
    # not stop the server booting -- so its return value is the signal here.
    from app.services.emotion_service import (
        EMOTION_PATH, EMOTIONS, YUNET_PATH, EmotionService, empty_result,
    )

    for path in (YUNET_PATH, EMOTION_PATH):
        if not path.exists():
            print(f"FAIL: {path} is missing; run scripts/fetch_models.py",
                  file=sys.stderr)
            return 1

    service = EmotionService()
    if not service.warm_up():
        print("FAIL: the emotion models did not load; see the logged traceback",
              file=sys.stderr)
        return 1

    if service._detector is None:
        print("FAIL: YuNet did not load, so detection would silently fall back "
              "to the Haar cascade in production", file=sys.stderr)
        return 1

    # A blank frame has no face in it, so this asserts the shape of the answer
    # rather than its content: the path ran and produced the payload the
    # transport layer expects.
    result = service.analyze_frame(frame)
    if set(result) != set(empty_result()):
        print(f"FAIL: unexpected result shape: {sorted(result)}", file=sys.stderr)
        return 1

    print(f"OK: cv2 {cv2.__version__}, YuNet + FER+ ready "
          f"({len(EMOTIONS)} classes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
