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
from importlib.metadata import PackageNotFoundError, distribution

import cv2
import numpy as np
from deepface import DeepFace


def _installed(name: str) -> bool:
    try:
        distribution(name)
        return True
    except PackageNotFoundError:
        return False


def check_no_duplicate_wheels() -> int:
    """Fail if a substituted wheel got reinstalled alongside its replacement.

    Several packages in this tree declare hard requirements on `tensorflow` and
    `opencv-python` -- deepface does, and so does tf-keras, which is the easy one
    to miss. Installing any of them normally pulls the originals back in *on top
    of* the -cpu/-headless variants, leaving the image larger than it was before
    the substitution rather than smaller. Nothing fails at runtime when that
    happens; the image just quietly grows by ~1.8 GB.

    Worth asserting here specifically because it is architecture-dependent: on
    aarch64 plain `tensorflow` is the correct package, so this class of mistake
    is invisible until the image is built for the x86_64 that Cloud Run runs.
    """
    problems = []

    if _installed("tensorflow") and _installed("tensorflow-cpu"):
        problems.append(
            "both `tensorflow` and `tensorflow-cpu` are installed -- something "
            "depends on `tensorflow` and was not installed with --no-deps"
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
                f"cv2.CascadeClassifier, which the emotion service detects "
                f"faces with; requirements.txt pins below it for that reason"
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
