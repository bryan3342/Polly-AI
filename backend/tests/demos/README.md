# Manual camera demos

These scripts open a camera window and wait for keyboard input. They are **not**
automated tests, and `pytest.ini` restricts collection to `tests/unit`, so they are
never picked up in CI.

They previously lived under names that pytest *did* collect — `tests/test_camera_*.py`
and, in one case, `app/camera/test_camera.py` inside the shipped application package —
where a CI run would have blocked waiting for a keypress.

Run them by hand when validating camera behaviour on a new machine:

```bash
python tests/demos/camera_access_demo.py    # camera opens, resolution/FPS readout
python tests/demos/camera_face_demo.py      # face detection only
python tests/demos/camera_emotion_demo.py   # face detection + emotion classification
```

Press `q` to quit any window. These need the full runtime dependencies
(`requirements.txt`), not just `requirements-dev.txt`.

Automated tests live in `tests/unit/` and run under `pytest`.
