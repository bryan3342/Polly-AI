import numpy as np

from app.utils.serialization import sanitize


def test_numpy_scalars_become_native():
    result = sanitize({"i": np.int64(3), "f": np.float32(1.5), "b": np.bool_(True)})
    assert result == {"i": 3, "f": 1.5, "b": True}
    assert all(type(v) in (int, float, bool) for v in result.values())


def test_arrays_become_lists():
    assert sanitize(np.array([1, 2, 3])) == [1, 2, 3]


def test_nested_structures_are_walked():
    payload = {"outer": [{"inner": np.float64(2.0)}, (np.int32(1),)]}
    assert sanitize(payload) == {"outer": [{"inner": 2.0}, [1]]}


def test_none_and_plain_values_pass_through():
    assert sanitize({"a": None, "b": "text", "c": 5}) == {"a": None, "b": "text", "c": 5}


def test_output_is_json_serializable():
    import json
    import pytest

    payload = {"emotions": {"happy": np.float32(0.9)}, "box": np.array([1, 2, 3, 4])}
    roundtripped = json.loads(json.dumps(sanitize(payload)))

    # float32 -> float widening is lossy, so compare approximately.
    assert roundtripped["emotions"]["happy"] == pytest.approx(0.9, abs=1e-6)
    assert roundtripped["box"] == [1, 2, 3, 4]
