"""Regression tests for the get_user_stats averaging bug.

The old implementation filtered falsy values out of the numerator but divided by
the unfiltered session count, understating every average.
"""

import pytest

from app.database import Base, DebateSession
from app.models.session import SessionModel


@pytest.fixture
def db(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    monkeypatch.setattr("app.models.session.SessionLocal", TestSession)
    return TestSession


def _add(db, **kwargs):
    s = db()
    s.add(DebateSession(**kwargs))
    s.commit()
    s.close()


def test_no_sessions_returns_empty(db):
    assert SessionModel.get_user_stats() == {}


def test_average_ignores_sessions_missing_the_metric(db):
    _add(db, session_id="a", confidence_score=80, overall_score=90, word_count=100)
    _add(db, session_id="b", confidence_score=None, overall_score=None, word_count=None)

    stats = SessionModel.get_user_stats()

    assert stats["total_sessions"] == 2
    # Averaged over the one session that recorded a value, not halved to 40.
    assert stats["average_confidence"] == 80.0
    assert stats["average_score"] == 90.0
    assert stats["total_words_spoken"] == 100


def test_average_across_multiple_present_values(db):
    _add(db, session_id="a", confidence_score=60, overall_score=70, word_count=10)
    _add(db, session_id="b", confidence_score=80, overall_score=90, word_count=20)

    stats = SessionModel.get_user_stats()
    assert stats["average_confidence"] == 70.0
    assert stats["average_score"] == 80.0
    assert stats["total_words_spoken"] == 30


def test_all_metrics_missing_yields_none_not_zero(db):
    _add(db, session_id="a", confidence_score=None, overall_score=None, word_count=None)

    stats = SessionModel.get_user_stats()
    assert stats["average_confidence"] is None
    assert stats["average_score"] is None
    assert stats["total_words_spoken"] == 0
