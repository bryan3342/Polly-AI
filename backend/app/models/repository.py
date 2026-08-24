"""Persistence adapter for finished sessions.

Wraps SessionModel behind the SessionRepository protocol so callers depend on
the operation ("save this record") rather than on SQLAlchemy, and so the
numpy-to-JSON sanitisation happens in exactly one place instead of at every
call site.
"""

import logging
from typing import Dict

from app.models.session import SessionModel
from app.utils.serialization import sanitize

logger = logging.getLogger(__name__)


class SqlSessionRepository:
    def save(self, record: Dict) -> bool:
        """Persist one session record, returning whether it was written."""
        saved = SessionModel.create_session(sanitize(record)) is not None
        if saved:
            logger.info("Session %s saved to database", record.get("session_id"))
        else:
            logger.warning("Session %s could not be saved", record.get("session_id"))
        return saved
