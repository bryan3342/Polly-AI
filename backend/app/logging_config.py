"""Central logging setup.

Logs go to stdout with levels and timestamps so the platform (Fly, Docker) can
capture and filter them, rather than being emitted as bare `print` output.
"""

import logging
import sys

from app.config import config

_CONFIGURED = False


def setup_logging() -> None:
    """Configure root logging once, at application startup."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger()
    root.setLevel(config.LOG_LEVEL.upper())
    root.handlers = [handler]
    _CONFIGURED = True
