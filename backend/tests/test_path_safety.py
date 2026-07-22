"""Regression tests for the static-file path traversal vulnerability.

Before the fix, GET /../../backend/.env returned the file's contents -- including
GEMINI_API_KEY and SECRET_KEY -- over plain HTTP.
"""

import os

import pytest

from app.utils.paths import resolve_within


@pytest.fixture
def static_root(tmp_path):
    root = tmp_path / "dist"
    root.mkdir()
    (root / "index.html").write_text("<html></html>", encoding="utf-8")
    assets = root / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log(1)", encoding="utf-8")

    # A secret sitting outside the served root, as backend/.env does in the repo.
    (tmp_path / ".env").write_text("SECRET_KEY=hunter2", encoding="utf-8")
    return str(root)


@pytest.mark.parametrize("attack", [
    "../.env",
    "../../.env",
    "..\\.env",
    "....//.env",
    "a/../../.env",
    "/etc/passwd",
    "../dist/../.env",
])
def test_traversal_attempts_are_rejected(static_root, attack):
    assert resolve_within(static_root, attack) is None


def test_legitimate_files_still_resolve(static_root):
    assert resolve_within(static_root, "index.html") == os.path.join(static_root, "index.html")
    assert resolve_within(static_root, "assets/app.js") == os.path.join(static_root, "assets", "app.js")


def test_root_itself_is_allowed(static_root):
    assert resolve_within(static_root, "") == os.path.realpath(static_root)


def test_nonexistent_path_inside_root_is_allowed(static_root):
    """SPA routes don't exist on disk; containment is the only question here."""
    assert resolve_within(static_root, "some/spa/route") is not None
