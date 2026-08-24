"""Filesystem path safety helpers."""

import os
from typing import Optional


def resolve_within(root: str, relative_path: str) -> Optional[str]:
    """Resolve `relative_path` under `root`, or return None if it escapes.

    Guards the static-file route: the path segment comes from the URL and may
    contain traversal sequences ("../../backend/.env"), URL-decoded separators,
    or symlinks. Both sides are fully resolved before comparison so the check
    cannot be bypassed by any of those.
    """
    root_real = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(root_real, relative_path))

    if candidate == root_real or candidate.startswith(root_real + os.sep):
        return candidate
    return None
