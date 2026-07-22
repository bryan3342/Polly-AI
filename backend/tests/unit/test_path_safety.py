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
    "a/../../.env",
    "../dist/../.env",
    "/etc/passwd",          # absolute path: os.path.join discards the root
    "../" * 12 + ".env",
])
def test_traversal_attempts_are_rejected(static_root, attack):
    assert resolve_within(static_root, attack) is None


@pytest.mark.skipif(os.sep != "\\", reason="backslash is only a separator on Windows")
def test_backslash_traversal_rejected_on_windows(static_root):
    """On POSIX a backslash is a legal filename character, not a separator.

    `dist/..\\.env` names a file *inside* the root there, so it is correctly
    allowed; only on Windows does it escape.
    """
    assert resolve_within(static_root, "..\\.env") is None


@pytest.mark.parametrize("path", [
    "index.html", "assets/app.js", "some/spa/route",
    "../.env", "/etc/passwd", "..\\.env",
    "....//.env", "..../.env", "...", "a..b/.env",
    "", ".", "./assets/../index.html",
])
def test_result_is_always_none_or_inside_the_root(static_root, path):
    """The invariant that actually matters: never hand back a path outside the root.

    Whether an exotic segment resolves away is platform-dependent — Windows
    rewrites a run of dots, POSIX treats it as a literal directory name, and a
    backslash is a separator only on Windows — so asserting a specific verdict
    per payload bakes in the host OS. This asserts the security property, which
    holds everywhere.
    """
    result = resolve_within(static_root, path)
    if result is not None:
        root = os.path.realpath(static_root)
        assert result == root or result.startswith(root + os.sep)


def test_legitimate_files_still_resolve(static_root):
    assert resolve_within(static_root, "index.html") == os.path.join(static_root, "index.html")
    assert resolve_within(static_root, "assets/app.js") == os.path.join(static_root, "assets", "app.js")


def test_root_itself_is_allowed(static_root):
    assert resolve_within(static_root, "") == os.path.realpath(static_root)


def test_nonexistent_path_inside_root_is_allowed(static_root):
    """SPA routes don't exist on disk; containment is the only question here."""
    assert resolve_within(static_root, "some/spa/route") is not None
