"""Download the model files this app needs but does not vendor.

Three models are fetched at runtime rather than committed: MediaPipe's hand
landmarker (~7.5 MB), YuNet face detection (~0.2 MB) and the FER+ emotion
classifier (~35 MB). None belongs in git -- they are large binaries the code can
fetch for itself -- but none should be downloaded during a user's first session
either, so this runs at setup time and the Dockerfile bakes them into the image.

    python scripts/fetch_models.py
"""

import sys
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

HAND_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)
HAND_MODEL_PATH = BACKEND / ".models" / "hand_landmarker.task"

# OpenCV's YuNet. Replaced the Haar cascade for face detection: measured on 175
# labelled photographs it found 174 against Haar's 159, and did it in less time
# per frame (2.8 ms against 3.8 ms).
YUNET_URL = (
    "https://github.com/opencv/opencv_zoo/raw/main/models/"
    "face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_PATH = BACKEND / ".models" / "face_detection_yunet.onnx"

# FER+ from the ONNX model zoo. Replaced DeepFace's classifier, which was
# trained on the original FER2013 labels; FER+ is the same images relabelled by
# ten annotators each, and it measured 13 points more accurate on the same
# crops at the same speed. See backend/tests/eval/README.md.
EMOTION_URL = (
    "https://github.com/onnx/models/raw/main/validated/vision/body_analysis/"
    "emotion_ferplus/model/emotion-ferplus-8.onnx"
)
EMOTION_PATH = BACKEND / ".models" / "emotion_ferplus.onnx"


def fetch_hand_model() -> bool:
    if HAND_MODEL_PATH.exists():
        size = HAND_MODEL_PATH.stat().st_size / 1e6
        print(f"OK    hand landmarker already present ({size:.1f} MB)")
        return True

    HAND_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    print(f"...   downloading hand landmarker from {HAND_MODEL_URL}")
    try:
        urllib.request.urlretrieve(HAND_MODEL_URL, HAND_MODEL_PATH)
    except Exception as exc:
        print(f"FAIL  could not download the hand landmarker: {exc}")
        print("      Hand and finger tracking will be unavailable; everything")
        print("      else still works.")
        return False
    print(f"OK    hand landmarker ({HAND_MODEL_PATH.stat().st_size / 1e6:.1f} MB)")
    return True


def fetch_onnx(name: str, url: str, path: Path, consequence: str) -> bool:
    if path.exists():
        print(f"OK    {name} already present ({path.stat().st_size / 1e6:.1f} MB)")
        return True

    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"...   downloading {name} from {url}")
    try:
        urllib.request.urlretrieve(url, path)
    except Exception as exc:
        print(f"FAIL  could not download {name}: {exc}")
        print(f"      {consequence}")
        # A partial file is worse than none: it would be loaded and fail per
        # frame rather than at startup, where this message is.
        path.unlink(missing_ok=True)
        return False
    print(f"OK    {name} ({path.stat().st_size / 1e6:.1f} MB)")
    return True


def main() -> int:
    ok = fetch_hand_model()
    ok = fetch_onnx(
        "YuNet face detector", YUNET_URL, YUNET_PATH,
        "Face detection falls back to the Haar cascade, which finds ~91% of "
        "faces against YuNet's ~99%.",
    ) and ok
    ok = fetch_onnx(
        "FER+ emotion classifier", EMOTION_URL, EMOTION_PATH,
        "Emotion detection will be unavailable; everything else still works.",
    ) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
