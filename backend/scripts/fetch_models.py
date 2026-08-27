"""Download the model files this app needs but does not vendor.

Two models are fetched at runtime rather than committed: DeepFace's emotion
weights (~6 MB) and MediaPipe's hand landmarker (~7.5 MB). Neither belongs in
git -- they are large binaries the code can fetch for itself -- but neither
should be downloaded during a user's first session either, so this runs at
setup time and the Dockerfile bakes them into the image.

    python scripts/fetch_models.py
"""

import os
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


def fetch_emotion_model() -> bool:
    """DeepFace fetches its own weights; this just triggers it once, here,
    instead of during someone's first recorded frame."""
    os.environ.setdefault("DEEPFACE_HOME", str(BACKEND))
    try:
        from deepface import DeepFace

        DeepFace.build_model("Emotion", task="facial_attribute")
    except Exception as exc:
        print(f"FAIL  could not cache the emotion model: {exc}")
        return False
    print("OK    emotion model cached")
    return True


def main() -> int:
    ok = fetch_hand_model()
    ok = fetch_emotion_model() and ok
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
