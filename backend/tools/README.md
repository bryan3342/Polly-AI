# Manual verification tools

These scripts open a camera window and wait for keyboard input. They are **not**
automated tests — they were previously named `test_camera_*.py` under `tests/`,
where pytest would collect them and block CI waiting for a keypress.

Run them by hand when validating camera/emotion behaviour on a new machine:

```bash
python tools/manual_camera_access.py    # camera opens, resolution/FPS readout
python tools/manual_camera_face.py      # face detection only
python tools/manual_camera_emotion.py   # face detection + emotion classification
```

`manual_camera_access.py` previously lived at `app/camera/test_camera.py` — an
interactive script inside the shipped application package.

Press `q` to quit either window.

Automated tests live in `tests/` and run under `pytest`.
