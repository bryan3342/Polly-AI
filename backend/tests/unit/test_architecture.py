"""Architectural boundaries, enforced.

The dependency rule this project follows: inner layers (transport, domain
services, value objects) must not depend on outer ones (the ML stack, the
database driver, the Gemini SDK). Those are wired in exactly one place,
`app.container`.

This was not always true. The transport layer used to construct its own
services, so importing it pulled in TensorFlow, OpenCV, librosa and the Gemini
SDK, which is why its tests had to inject fake modules into `sys.modules`
before importing anything.

These run in a fresh interpreter per check, because once any test has imported
a heavy module it stays in `sys.modules` for the rest of the session and the
assertion would be meaningless.
"""

import subprocess
import sys
import textwrap

import pytest

HEAVY_DEPENDENCIES = ("tensorflow", "cv2", "deepface", "librosa", "google.genai", "PIL")


def _import_in_clean_interpreter(import_target: str):
    """Import `import_target` in a fresh interpreter.

    Returns (ok, heavy_modules_loaded, error). A failed import is reported
    rather than skipped: in the lean CI environment the ML stack is not
    installed at all, so "it imported successfully" *is* the proof that it did
    not reach for one. Skipping there would turn a real regression into a
    silent pass.
    """
    script = textwrap.dedent(f"""
        import sys
        import {import_target}
        heavy = {HEAVY_DEPENDENCIES!r}
        found = [m for m in heavy
                 if any(k == m or k.startswith(m + ".") for k in sys.modules)]
        print(",".join(found))
    """)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, cwd=".",
    )
    loaded = [m for m in result.stdout.strip().split(",") if m]
    return result.returncode == 0, loaded, result.stderr.strip()[-300:]


def _assert_independent_of_ml_stack(import_target: str):
    ok, loaded, error = _import_in_clean_interpreter(import_target)

    assert ok, (
        f"{import_target} could not be imported on its own:\n{error}\n"
        f"It must depend on app.services.protocols, not on a concrete "
        f"implementation. Concrete services are wired in app.container."
    )
    assert loaded == [], (
        f"{import_target} pulled in {loaded}. Transport and domain layers must "
        f"depend on protocols; implementations are wired in app.container."
    )


class TestDependencyRule:
    def test_transport_layer_does_not_depend_on_the_ml_stack(self):
        """The regression this guards: transport constructing its own services."""
        _assert_independent_of_ml_stack("app.api.websocket")

    def test_analysis_service_does_not_depend_on_the_ml_stack(self):
        """The analysis sequence orchestrates collaborators; it never imports them."""
        _assert_independent_of_ml_stack("app.services.analysis_service")

    def test_protocols_are_free_of_heavy_imports(self):
        """Depending on an interface must never cost an implementation."""
        _assert_independent_of_ml_stack("app.services.protocols")

    def test_scoring_is_pure_domain_logic(self):
        _assert_independent_of_ml_stack("app.services.scoring_service")

    def test_value_objects_are_free_of_heavy_imports(self):
        _assert_independent_of_ml_stack("app.services.prompts")

    def test_the_composition_root_is_where_implementations_live(self):
        """The complement: app.container is *expected* to pull them in.

        Only meaningful where the ML stack is installed, so it skips in the lean
        CI environment rather than asserting something it cannot observe.
        """
        ok, loaded, error = _import_in_clean_interpreter("app.container")
        if not ok:
            pytest.skip("ML stack not installed in this environment")

        assert loaded, (
            "app.container pulled in no heavy dependencies: the wiring has "
            "moved somewhere else."
        )
