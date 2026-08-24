"""Face cropping geometry for emotion classification.

DeepFace was called with `detector_backend="skip"`, which means "this input is
already a cropped face" -- but it was handed the entire video frame. The
detected bounding box was used only to draw the overlay, so emotion scores were
computed over the whole room: wall colour, clothing, anything in shot (#26).
"""

import importlib
import sys
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


_stub("cv2", data=types.SimpleNamespace(haarcascades=""),
      CascadeClassifier=lambda *a, **k: None, cvtColor=lambda img, code: img,
      COLOR_BGR2GRAY=0, COLOR_BGR2RGB=1)
_stub("deepface", DeepFace=types.SimpleNamespace(analyze=lambda *a, **k: []))
_pil_image = _stub("PIL.Image", Image=type("Image", (), {}), open=lambda *a, **k: None)
_stub("PIL", Image=_pil_image)

from app.services.emotion_service import FACE_MARGIN, EmotionService  # noqa: E402

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
