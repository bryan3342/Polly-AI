"""Polly AI backend package.

Logging is configured here, at package import, so that it is in place before any
submodule is imported. Configuring it inside main.py instead would leave the
service modules -- which log during construction at import time -- writing
through the default handler with no level or timestamp.
"""

from app.logging_config import setup_logging

setup_logging()
