"""Download the larger pool the tuning decisions were measured on.

`build_fixtures.py` produces 20 images, which is enough for a smoke test and far
too few to choose between pipelines: at n=20 a single image is five points, so
every candidate looked the same. This produces 175, stratified the same way and
under the same 200px floor, and it is the set the detector and classifier swaps
were actually decided on. See README.md for the numbers.

Not committed as images: 175 photographs is 4 MB of binaries that a script can
fetch. The labels are committed, in pool_labels.json, because the blind
annotation pass is the expensive half and cannot be regenerated deterministically.

Run:  python backend/tests/eval/build_pool.py
"""
import csv
import io
import json
import random
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

REPO = "https://raw.githubusercontent.com/muxspace/facial_expressions/master"
HERE = Path(__file__).resolve().parent
POOL_DIR = HERE / "pool"
LABELS = HERE / "pool_labels.json"

LABEL_MAP = {
    "anger": "angry", "disgust": "disgust", "fear": "fear",
    "happiness": "happy", "sadness": "sad", "surprise": "surprise",
    "neutral": "neutral",
}
# 30 per class where the source has them. Fear and disgust run out well short of
# that (the source holds 21 and 208 respectively, and the 200px floor takes more
# out), which is why their per-class figures in the README carry a warning.
QUOTA = {k: 30 for k in ["angry", "disgust", "fear", "sad", "surprise", "happy", "neutral"]}
MIN_DIM = 200
SEED = 7


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def big_enough(data: bytes) -> bool:
    image = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    return image is not None and min(image.shape[:2]) >= MIN_DIM


def main() -> int:
    legend = fetch(f"{REPO}/data/legend.csv").decode("utf-8", "replace")
    by_class: dict[str, list[str]] = {}
    for row in csv.DictReader(io.StringIO(legend)):
        target = LABEL_MAP.get(row["emotion"].strip().lower())
        if target:
            by_class.setdefault(target, []).append(row["image"].strip())

    POOL_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)

    def grab(name):
        path = POOL_DIR / name
        if path.exists():
            return name, path.read_bytes()
        try:
            return name, fetch(f"{REPO}/images/{name}")
        except Exception:
            return name, None

    manifest = []
    for label, quota in QUOTA.items():
        candidates = sorted(set(by_class.get(label, [])))
        rng.shuffle(candidates)
        # Oversampled because the resolution floor rejects a good fraction, and
        # a second pass over the network is slower than fetching a few spares.
        candidates = candidates[:quota * 4]

        taken = 0
        with ThreadPoolExecutor(max_workers=16) as pool:
            for name, data in pool.map(grab, candidates):
                if taken >= quota or not data or not big_enough(data):
                    continue
                (POOL_DIR / name).write_bytes(data)
                manifest.append({"image": name, "label": label})
                taken += 1
        print(f"  {label:9s} {taken}")

    manifest.sort(key=lambda entry: entry["image"])
    for index, entry in enumerate(manifest, start=1):
        entry["id"] = f"P{index:03d}"

    if LABELS.exists():
        known = json.loads(LABELS.read_text())
        missing = [e["image"] for e in manifest if e["image"] not in known["annotator"]]
        if missing:
            print(f"\n  ! {len(missing)} images have no blind label; "
                  f"the trusted-subset figure will not be comparable")

    (HERE / "pool.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"\n{len(manifest)} images -> {POOL_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
