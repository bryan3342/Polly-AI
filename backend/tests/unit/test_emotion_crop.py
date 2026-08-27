"""Face cropping geometry for emotion classification.

DeepFace was called with `detector_backend="skip"`, which means "this input is
already a cropped face" -- but it was handed the entire video frame. The
detected bounding box was used only to draw the overlay, so emotion scores were
computed over the whole room: wall colour, clothing, anything in shot (#26).
"""

import importlib
import sys
import threading
import time
import types

import numpy as np
import pytest


def _stub(name, **attrs):
    if name in sys.modules:
        return sys.modules[name]
    try:
        return importlib.import_module(name)
    except ImportError:
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module
        return module


def _fake_resize(img, size, interpolation=None):
    """Enough of cv2.resize for the geometry: produce an array of `size`."""
    width, height = size
    return np.zeros((height, width) + img.shape[2:], dtype=img.dtype)


_stub("cv2", data=types.SimpleNamespace(haarcascades=""),
      CascadeClassifier=lambda *a, **k: None, cvtColor=lambda img, code: img,
      COLOR_BGR2GRAY=0, COLOR_BGR2RGB=1, INTER_AREA=3, resize=_fake_resize,
      imencode=lambda ext, img: (True, types.SimpleNamespace(tobytes=lambda: b"jpeg")))
_stub("deepface", DeepFace=types.SimpleNamespace(
    analyze=lambda *a, **k: [], build_model=lambda *a, **k: object()))
_pil_image = _stub("PIL.Image", Image=type("Image", (), {}), open=lambda *a, **k: None)
_stub("PIL", Image=_pil_image)

from app.services.emotion_service import (  # noqa: E402
    DETECT_WIDTH,
    FACE_MARGIN,
    EmotionService,
)

crop_face = EmotionService.crop_face


def _frame(height=480, width=640):
    return np.zeros((height, width, 3), dtype=np.uint8)


def test_crop_is_much_smaller_than_the_frame():
    """The regression: the classifier used to receive the entire frame."""
    frame = _frame()
    crop = crop_face(frame, [280, 200, 80, 80])

    assert crop.shape[:2] != frame.shape[:2]
    assert crop.size < frame.size / 10


def test_crop_covers_the_detected_box_plus_margin():
    frame = _frame()
    crop = crop_face(frame, [280, 200, 80, 80], margin=0.25)

    # 80px box + 25% on each side = 120px.
    assert crop.shape[0] == 120
    assert crop.shape[1] == 120


def test_crop_contains_the_face_pixels():
    frame = _frame()
    frame[200:280, 280:360] = 255          # mark the face region
    crop = crop_face(frame, [280, 200, 80, 80])

    # Every marked pixel must survive the crop.
    assert int((crop == 255).sum()) == 80 * 80 * 3


def test_crop_excludes_distant_background():
    frame = _frame()
    frame[0:50, 0:50] = 200                # a bright object in the corner
    crop = crop_face(frame, [280, 200, 80, 80])

    assert not (crop == 200).any(), "background leaked into the classifier input"


def test_box_at_the_frame_edge_is_clamped():
    frame = _frame()
    crop = crop_face(frame, [0, 0, 60, 60])

    assert crop.shape[0] > 0 and crop.shape[1] > 0
    assert crop.shape[0] <= frame.shape[0]
    assert crop.shape[1] <= frame.shape[1]


def test_box_overflowing_the_bottom_right_is_clamped():
    frame = _frame()
    crop = crop_face(frame, [600, 440, 80, 80])

    assert crop.shape[0] <= 40 + int(80 * FACE_MARGIN)
    assert crop.size > 0


def test_degenerate_box_falls_back_to_the_frame():
    """An empty array would make DeepFace raise; the frame is a safe fallback."""
    frame = _frame()
    crop = crop_face(frame, [5000, 5000, 10, 10])

    assert crop.size > 0


def test_default_margin_is_applied():
    frame = _frame()
    crop = crop_face(frame, [280, 200, 100, 100])
    expected = 100 + 2 * int(100 * FACE_MARGIN)

    assert crop.shape[0] == expected


class TestLargestFaceSelection:
    """detectMultiScale returns boxes in no meaningful order, so faces[0] could
    jump to a bystander in the background from one frame to the next."""

    def test_largest_box_wins(self):
        faces = [(10, 10, 30, 30), (200, 100, 120, 120), (400, 300, 45, 45)]
        chosen = max(faces, key=lambda b: int(b[2]) * int(b[3]))

        assert chosen == (200, 100, 120, 120)


def _bare_service():
    """An EmotionService without the OpenCV/TensorFlow constructor.

    `__init__` loads a Haar cascade from disk, which these tests neither need
    nor have. Only the warm-up concurrency state is set up by hand.
    """
    service = EmotionService.__new__(EmotionService)
    service.face_cascade = None
    service._model_lock = threading.Lock()
    service._model_ready = False
    return service


class TestWarmUp:
    """The model is built before a user's first frame, not during it.

    Lazily constructing it meant the first frame of the first session paid for
    the graph trace, the Haar cascade's first run and the JPEG decode path —
    measured at 130ms, which reads to that user as the app stalling.

    Warm-up runs on a background thread now (so the server can bind its port
    without waiting for TensorFlow), which means it can overlap with the first
    frames arriving on worker threads. These cover that overlap.
    """

    def test_warm_up_reports_success(self, monkeypatch):
        service = _bare_service()
        monkeypatch.setattr(service, "analyze_encoded_frame", lambda data: {}, raising=False)

        assert service.warm_up() is True

    def test_warm_up_failure_does_not_stop_startup(self, monkeypatch):
        """Every other feature still works without emotion detection, so a
        failure here is logged and left to the per-frame error handling."""
        import app.services.emotion_service as module

        service = _bare_service()
        monkeypatch.setattr(
            module.DeepFace, "build_model",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no network")),
        )

        assert service.warm_up() is False

    def test_a_failed_warm_up_is_retried(self, monkeypatch):
        """A failure must not latch. The next frame gets another attempt."""
        import app.services.emotion_service as module

        service = _bare_service()
        monkeypatch.setattr(service, "analyze_encoded_frame", lambda data: {}, raising=False)

        attempts = []

        def flaky(*a, **k):
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("no network")

        monkeypatch.setattr(module.DeepFace, "build_model", flaky)

        assert service.warm_up() is False
        assert service.warm_up() is True
        assert len(attempts) == 2

    def test_the_model_is_built_once_however_many_callers(self, monkeypatch):
        """Repeat calls are free: every frame calls warm_up before analysing."""
        import app.services.emotion_service as module

        service = _bare_service()
        monkeypatch.setattr(service, "analyze_encoded_frame", lambda data: {}, raising=False)
        builds = []
        monkeypatch.setattr(module.DeepFace, "build_model",
                            lambda *a, **k: builds.append(1))

        for _ in range(5):
            assert service.warm_up() is True

        assert len(builds) == 1

    def test_concurrent_warm_ups_build_the_model_only_once(self, monkeypatch):
        """The race this guards: the background warm-up thread and a worker
        thread handling an early frame both reaching an unbuilt model.
        DeepFace's model cache is not thread-safe, so one must wait."""
        import app.services.emotion_service as module

        service = _bare_service()
        monkeypatch.setattr(service, "analyze_encoded_frame", lambda data: {}, raising=False)

        builds = []
        start = threading.Barrier(8)

        def slow_build(*a, **k):
            builds.append(1)
            time.sleep(0.05)          # widen the window a racy version would lose

        monkeypatch.setattr(module.DeepFace, "build_model", slow_build)

        results = []

        def worker():
            start.wait()              # maximise the overlap
            results.append(service.warm_up())

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert results == [True] * 8
        assert len(builds) == 1


class _RecordingCascade:
    """A Haar cascade that records the image it was asked to search."""

    def __init__(self, boxes):
        self._boxes = boxes
        self.searched_shape = None

    def detectMultiScale(self, image, *args, **kwargs):
        self.searched_shape = image.shape[:2]
        return self._boxes


class TestDetectionDownscaling:
    """Faces are located on a downscaled copy, and reported at full scale.

    Detection dominates the per-frame cost and scales with pixel count. Measured
    on a tenth of a shared core -- the smallest free instance this deploys to --
    searching a 640x480 frame took 2231 ms against a 1000 ms frame interval,
    while the emotion classification behind it took 166 ms. Searching a 320px
    copy took 435 ms, which fits.

    What must not change is the coordinate space callers see: the overlay the
    client draws and the crop the classifier receives are both in full-frame
    terms.
    """

    def _service(self, boxes):
        service = EmotionService.__new__(EmotionService)
        service.face_cascade = _RecordingCascade(boxes)
        return service

    def test_the_search_runs_on_a_downscaled_copy(self):
        service = self._service([])
        service.detect_faces(_frame(height=480, width=640))

        assert service.face_cascade.searched_shape == (240, DETECT_WIDTH), (
            "detection should search a 320px-wide copy, not the full frame"
        )

    def test_boxes_come_back_in_full_frame_coordinates(self):
        """The regression this guards: an overlay drawn at half scale, and a
        crop taken from the wrong part of the frame."""
        # A box found on the 320px copy of a 640px frame is half-scale.
        service = self._service([(50, 40, 60, 60)])

        boxes = service.detect_faces(_frame(height=480, width=640))

        assert boxes == [[100, 80, 120, 120]], "boxes must be scaled back up"

    def test_a_small_frame_is_not_upscaled(self):
        """Nothing is gained by searching more pixels than were captured."""
        service = self._service([(10, 10, 20, 20)])

        boxes = service.detect_faces(_frame(height=180, width=240))

        assert service.face_cascade.searched_shape == (180, 240)
        assert boxes == [[10, 10, 20, 20]], "coordinates must pass through unchanged"

    def test_the_crop_is_still_taken_from_the_full_resolution_frame(self):
        """Downscaling is a search optimisation only. The classifier must still
        receive real pixels, not a blown-up thumbnail."""
        service = self._service([(50, 40, 60, 60)])
        frame = _frame(height=480, width=640)
        frame[80:200, 100:220] = 255              # mark the full-scale face region

        box = service.detect_faces(frame)[0]
        crop = EmotionService.crop_face(frame, box)

        assert (crop == 255).any(), "the crop missed the face it was pointed at"
        assert crop.shape[0] == 120 + 2 * int(120 * FACE_MARGIN)
