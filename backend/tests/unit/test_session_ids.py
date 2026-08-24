"""Session ids must be minted by the server, not taken from the URL.

The endpoint was `/ws/{session_id}` and used whatever the client put in the
path. Connecting to another user's id attached you to their live session: their
topic and coaching replies were delivered to you, and frames, audio and
analysis requests you sent were applied to their session (issue #21).

Ids were also generated client-side, so they were neither unguessable nor
guaranteed unique.
"""

import importlib
import os
import sys
import types

import pytest

os.environ.setdefault("DATABASE_URL", "sqlite://")   # in-memory; no file on disk


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


_stub("cv2", data=types.SimpleNamespace(haarcascades=""), CascadeClassifier=lambda *a, **k: None,
      cvtColor=lambda *a, **k: None, COLOR_BGR2GRAY=0, COLOR_BGR2RGB=0, COLOR_RGB2BGR=0,
      imdecode=lambda *a, **k: None, IMREAD_COLOR=1)
_stub("deepface", DeepFace=types.SimpleNamespace(analyze=lambda *a, **k: []))
_stub("librosa", load=lambda *a, **k: (None, None),
      feature=types.SimpleNamespace(), effects=types.SimpleNamespace())
_pil_image = _stub("PIL.Image", Image=type("Image", (), {}), open=lambda *a, **k: None)
_stub("PIL", Image=_pil_image)

main = pytest.importorskip("app.main")


def _websocket_paths():
    return [
        route.path for route in main.app.routes
        if route.__class__.__name__ == "APIWebSocketRoute"
    ]


def test_the_websocket_route_takes_no_client_supplied_id():
    """The regression: `/ws/{session_id}` trusted the path segment."""
    paths = _websocket_paths()

    assert "/ws" in paths
    assert not any("{" in path for path in paths), (
        f"a websocket route still accepts a client-supplied parameter: {paths}"
    )


def test_ids_are_long_enough_to_be_unguessable():
    import secrets

    generated = secrets.token_urlsafe(main.SESSION_ID_BYTES)

    # 24 bytes of entropy; the old ids were 7 characters of Math.random().
    assert main.SESSION_ID_BYTES >= 16
    assert len(generated) >= 20


def test_generated_ids_do_not_collide():
    import secrets

    ids = {secrets.token_urlsafe(main.SESSION_ID_BYTES) for _ in range(2000)}
    assert len(ids) == 2000
