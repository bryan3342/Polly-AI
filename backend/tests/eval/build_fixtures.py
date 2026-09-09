"""Download the labelled fixture set the emotion accuracy eval runs against.

Ground truth comes from muxspace/facial_expressions: ~13.7k real photographs
labelled by hand, as opposed to the 48x48 crops the DeepFace emotion model was
trained on. Real photographs matter here because the thing under test is the
whole pipeline -- Haar detection, the margin crop, then classification -- and a
pre-cropped thumbnail would skip the first two stages entirely.

The sample is stratified rather than natural: the source is 92% neutral and
happy, and a natural draw of 20 would say almost nothing about the five other
classes. A balanced draw measures per-class behaviour at the cost of making the
headline number pessimistic against real session footage. Both numbers are
reported.

Run:  python backend/tests/eval/build_fixtures.py
"""
import csv
import io
import json
import random
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

REPO = "https://raw.githubusercontent.com/muxspace/facial_expressions/master"
LEGEND = f"{REPO}/data/legend.csv"
IMAGES = f"{REPO}/images"

HERE = Path(__file__).resolve().parent
FIXTURE_DIR = HERE / "fixtures"
MANIFEST = HERE / "fixtures.json"

# Source label -> the DeepFace class it should produce. "contempt" has no
# DeepFace equivalent (the model has seven classes and that is not one of
# them), so those nine rows are dropped rather than scored as failures.
LABEL_MAP = {
    "anger": "angry",
    "disgust": "disgust",
    "fear": "fear",
    "happiness": "happy",
    "sadness": "sad",
    "surprise": "surprise",
    "neutral": "neutral",
}

# 20 tests, weighted towards the classes that are hard and rare. Neutral and
# happy get fewer slots precisely because they dominate the source: they are
# the easy, well-represented cases and spending the budget there would hide
# whatever the model does with anger, disgust and fear.
QUOTA = {
    "angry": 3,
    "disgust": 3,
    "fear": 3,
    "sad": 3,
    "surprise": 3,
    "happy": 3,
    "neutral": 2,
}

SEED = 20260908

# A face has to be big enough to be a fair test of the pipeline. The source
# mixes 350x350 portraits with thumbnails as small as 47x68, and the small ones
# fail Haar detection for reasons a webcam frame never reproduces -- counting
# them would understate detection against the only input the product ever sees.
MIN_DIM = 200


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def big_enough(data: bytes) -> bool:
    """True if the JPEG is at least MIN_DIM on both sides."""
    array = np.frombuffer(data, dtype=np.uint8)
    image = cv2.imdecode(array, cv2.IMREAD_COLOR)
    if image is None:
        return False
    height, width = image.shape[:2]
    return min(height, width) >= MIN_DIM


def main() -> int:
    rng = random.Random(SEED)

    legend = fetch(LEGEND).decode("utf-8", errors="replace")
    rows = list(csv.DictReader(io.StringIO(legend)))

    by_class: dict[str, list[str]] = {}
    for row in rows:
        target = LABEL_MAP.get(row["emotion"].strip().lower())
        if target:
            by_class.setdefault(target, []).append(row["image"].strip())

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    manifest = []
    for label, count in QUOTA.items():
        pool = sorted(set(by_class.get(label, [])))
        rng.shuffle(pool)

        taken = 0
        for name in pool:
            if taken == count:
                break
            destination = FIXTURE_DIR / name
            if destination.exists():
                data = destination.read_bytes()
            else:
                data = fetch(f"{IMAGES}/{name}")
                if not big_enough(data):
                    continue
                destination.write_bytes(data)
            if not big_enough(data):
                continue
            manifest.append({
                "image": name,
                "label": label,
                "source_label": next(
                    key for key, value in LABEL_MAP.items() if value == label
                ),
            })
            taken += 1
            print(f"  {label:9s} {name}")

        if taken < count:
            print(f"  ! only {taken} images of {label} met the {MIN_DIM}px floor")

    manifest.sort(key=lambda entry: entry["image"])
    for index, entry in enumerate(manifest, start=1):
        entry["id"] = f"T{index:02d}"

    MANIFEST.write_text(json.dumps({
        "source": "muxspace/facial_expressions",
        "seed": SEED,
        "cases": manifest,
    }, indent=2) + "\n")

    print(f"\n{len(manifest)} fixtures -> {FIXTURE_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
