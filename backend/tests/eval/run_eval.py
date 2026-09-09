"""Measure the emotion pipeline's accuracy against the labelled fixture set.

This drives the real `EmotionService.analyze_frame`, not a reimplementation of
it, so detection, the margin crop and classification are all exercised the way
a live frame exercises them. What it reports:

  detection rate    fraction of fixtures where a face was found at all. A miss
                    here is a Haar cascade failure, not a classifier failure,
                    and the two are worth separating: they have different fixes.
  top-1 accuracy    dominant_emotion == label, over the frames with a face.
  top-2 accuracy    label is in the two highest-scoring emotions. Included
                    because the product ranks emotions for feedback rather than
                    asserting a single one, so a near-miss is not a total loss.
  confusion         which label the model reaches for when it is wrong. This is
                    the part that says whether the errors are systematic.

Run:  python backend/tests/eval/run_eval.py [--json out.json]
"""
import argparse
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent.parent
sys.path.insert(0, str(BACKEND))

import cv2  # noqa: E402

from app.services.emotion_service import EmotionService  # noqa: E402

CLASSES = ["angry", "disgust", "fear", "happy", "sad", "surprise", "neutral"]


def load_cases() -> list[dict]:
    manifest = json.loads((HERE / "fixtures.json").read_text())
    return manifest["cases"]


def load_annotator() -> dict:
    """The independent blind labelling of the same fixtures, if present."""
    path = HERE / "annotator_labels.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text()).get("labels", {})


def run() -> dict:
    service = EmotionService()
    service.warm_up()

    results = []
    for case in load_cases():
        path = HERE / "fixtures" / case["image"]
        frame = cv2.imread(str(path))
        if frame is None:
            raise SystemExit(f"could not read fixture {path}")

        started = time.perf_counter()
        analysis = service.analyze_frame(frame)
        elapsed_ms = (time.perf_counter() - started) * 1000

        scores = analysis.get("emotions") or {}
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)

        results.append({
            "id": case["id"],
            "image": case["image"],
            "label": case["label"],
            "face_detected": analysis["face_detected"],
            "predicted": analysis["dominant_emotion"],
            "confidence": round(analysis["confidence"], 4),
            "top2": [name for name, _ in ranked[:2]],
            "scores": {name: round(value, 4) for name, value in ranked},
            "ms": round(elapsed_ms, 1),
        })

    return summarise(results, load_cases())


def summarise(results: list[dict], cases: list[dict]) -> dict:
    detected = [r for r in results if r["face_detected"]]
    correct = [r for r in detected if r["predicted"] == r["label"]]
    top2 = [r for r in detected if r["label"] in r["top2"]]

    per_class: dict[str, dict] = {}
    for result in results:
        bucket = per_class.setdefault(
            result["label"], {"total": 0, "detected": 0, "correct": 0}
        )
        bucket["total"] += 1
        if result["face_detected"]:
            bucket["detected"] += 1
            if result["predicted"] == result["label"]:
                bucket["correct"] += 1

    confusion: dict[str, dict[str, int]] = {}
    for result in detected:
        row = confusion.setdefault(result["label"], {})
        predicted = result["predicted"]
        row[predicted] = row.get(predicted, 0) + 1

    latencies = sorted(r["ms"] for r in results)

    return {
        "agreement": agreement(results),
        "results": results,
        "summary": {
            "total": len(results),
            "faces_detected": len(detected),
            "detection_rate": round(len(detected) / len(results), 4) if results else 0.0,
            # Scored over the frames that produced a face. A frame with no face
            # is a detection failure and is already counted as one above;
            # folding it into accuracy too would charge the classifier for it.
            "top1_accuracy": round(len(correct) / len(detected), 4) if detected else 0.0,
            "top2_accuracy": round(len(top2) / len(detected), 4) if detected else 0.0,
            "top1_accuracy_end_to_end": round(len(correct) / len(results), 4) if results else 0.0,
            "median_ms": latencies[len(latencies) // 2] if latencies else 0.0,
            "max_ms": latencies[-1] if latencies else 0.0,
        },
        "per_class": per_class,
        "confusion": confusion,
    }


def agreement(results: list[dict]) -> dict:
    """Score against the blind second opinion as well as the source labels.

    The source labels are the weak part of this benchmark, not the model: they
    are crowd-sourced and they disagree with an independent pass often enough
    that a raw accuracy figure against them understates what the pipeline does.
    The subset where both agree is small but is the one number here worth
    trusting.
    """
    annotator = load_annotator()
    if not annotator:
        return {}

    detected = [r for r in results if r["face_detected"]]

    both_agree = [
        r for r in results
        if annotator.get(r["image"], {}).get("first") == r["label"]
    ]
    trusted_detected = [r for r in both_agree if r["face_detected"]]
    trusted_correct = [r for r in trusted_detected if r["predicted"] == r["label"]]

    return {
        "label_agreement": len(both_agree),
        "label_agreement_rate": round(len(both_agree) / len(results), 4),
        "model_vs_annotator": round(sum(
            1 for r in detected
            if r["predicted"] == annotator.get(r["image"], {}).get("first")
        ) / len(detected), 4) if detected else 0.0,
        "trusted_n": len(both_agree),
        "trusted_detected": len(trusted_detected),
        "trusted_correct": len(trusted_correct),
        "trusted_accuracy": round(
            len(trusted_correct) / len(trusted_detected), 4
        ) if trusted_detected else 0.0,
    }


def report(data: dict) -> None:
    summary = data["summary"]
    print("\n=== Emotion pipeline accuracy ===")
    print(f"fixtures            {summary['total']}")
    print(f"faces detected      {summary['faces_detected']}/{summary['total']}"
          f"  ({summary['detection_rate']:.0%})")
    print(f"top-1 (of detected) {summary['top1_accuracy']:.0%}")
    print(f"top-2 (of detected) {summary['top2_accuracy']:.0%}")
    print(f"top-1 end to end    {summary['top1_accuracy_end_to_end']:.0%}")
    print(f"latency             median {summary['median_ms']}ms, max {summary['max_ms']}ms")

    print("\nper class:")
    for label in CLASSES:
        bucket = data["per_class"].get(label)
        if not bucket:
            continue
        print(f"  {label:9s} {bucket['correct']}/{bucket['detected']} correct"
              f"  ({bucket['detected']}/{bucket['total']} detected)")

    print("\ncase by case:")
    for result in data["results"]:
        mark = "ok  " if result["predicted"] == result["label"] else "MISS"
        predicted = result["predicted"] or "no-face"
        print(f"  {mark} {result['id']}  {result['label']:9s} -> {predicted:9s}"
              f"  conf {result['confidence']:.2f}  {result['image']}")

    pact = data.get("agreement") or {}
    if pact:
        print("\nagainst the blind second opinion:")
        print(f"  source label == annotator   {pact['label_agreement']}/{summary['total']}"
              f"  ({pact['label_agreement_rate']:.0%})   <- label-quality ceiling")
        print(f"  model == annotator          {pact['model_vs_annotator']:.0%} of detected")
        print(f"  TRUSTED subset (both agree) {pact['trusted_correct']}/{pact['trusted_detected']}"
              f" correct ({pact['trusted_accuracy']:.0%}), from {pact['trusted_n']} fixtures")

    print("\nconfusion (label -> predictions):")
    for label, row in data["confusion"].items():
        pairs = ", ".join(f"{k} x{v}" for k, v in sorted(row.items(), key=lambda kv: -kv[1]))
        print(f"  {label:9s} {pairs}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, help="also write the full result as JSON")
    args = parser.parse_args()

    data = run()
    report(data)

    if args.json:
        args.json.write_text(json.dumps(data, indent=2) + "\n")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
