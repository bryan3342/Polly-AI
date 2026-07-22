import json

import pytest

from app.services.topic_service import TopicService, TOPICS_FILE


def test_loads_topics_from_data_file():
    service = TopicService()
    assert len(service.topics) > 1
    assert all("topic" in t for t in service.topics)


def test_data_file_is_the_only_source_of_topics():
    """Topics used to be duplicated verbatim in the source as `default_topics`."""
    with open(TOPICS_FILE, encoding="utf-8") as f:
        on_disk = json.load(f)
    assert TopicService().topics == on_disk


def test_missing_file_falls_back_without_raising(tmp_path):
    service = TopicService(str(tmp_path / "nope.json"))
    assert len(service.topics) == 1
    assert service.get_random_topic()["topic"]


def test_malformed_file_falls_back_without_raising(tmp_path):
    bad = tmp_path / "topics.json"
    bad.write_text("{not json", encoding="utf-8")
    assert len(TopicService(str(bad)).topics) == 1


def test_empty_file_falls_back_without_raising(tmp_path):
    empty = tmp_path / "topics.json"
    empty.write_text("[]", encoding="utf-8")
    assert len(TopicService(str(empty)).topics) == 1


def test_filter_falls_back_to_all_when_no_match():
    service = TopicService()
    assert service.get_random_topic(difficulty="nonexistent") in service.topics


def test_unknown_id_returns_none_not_a_different_topic():
    """Returning a random topic for an unknown id silently answers the wrong question."""
    assert TopicService().get_topic_by_id(-1) is None


def test_get_topic_by_id_roundtrip():
    service = TopicService()
    expected = service.topics[0]
    assert service.get_topic_by_id(expected["id"]) == expected
