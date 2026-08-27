# Manual camera demos

These scripts open a camera window and wait for keyboard input. They are **not**
automated tests, and `pytest.ini` restricts collection to `tests/unit`, so they are
never picked up in CI.

They previously lived under names that pytest *did* collect, `tests/test_camera_*.py`
and, in one case, `app/camera/test_camera.py` inside the shipped application package, where a CI run would have blocked waiting for a keypress.

Run them by hand when validating camera behaviour on a new machine:

```bash
python tests/demos/camera_access_demo.py       # camera opens, resolution/FPS readout
python tests/demos/camera_face_demo.py         # face detection only
python tests/demos/camera_emotion_demo.py      # face detection + emotion classification
python tests/demos/detection_tuning_demo.py    # pick DETECT_WIDTH from your own camera
```

Press `q` to quit any window. These need the full runtime dependencies
(`requirements.txt`), not just `requirements-dev.txt`.

`detection_tuning_demo.py` is the odd one out: it prints a table rather than
opening a window, and it is the one to run when tuning the server rather than
debugging a machine. The server searches a downscaled copy of each frame for a
face, because locating the face costs far more than classifying the emotion --
on a tenth of a shared core, 2231 ms against 166 ms. How far it can be
downscaled before faces start being missed depends on your camera, how far back
you sit, and how much you move, so it is measured rather than assumed. Move
normally while it runs; motion blur is what a Haar cascade handles worst.

Automated tests live in `tests/unit/` and run under `pytest`.
