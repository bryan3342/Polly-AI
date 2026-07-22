import json

import pytest

from app.services.topic_service import TOPICS_FILE, TopicService

TOPICS = [
    {"id": 1, "topic": "Topic A", "category": "Tech", "difficulty": "easy"},
    {"id": 2, "topic": "Topic B", "category": "Tech", "difficulty": "hard"},
    {"id": 3, "topic": "Topic C", "category": "Health", "difficulty": "easy"},
]


@pytest.fixture
def service(tmp_path):
    """A service backed by a fixture topics file rather than the real data file.

    _load_topics now takes the path as an argument and no longer writes the data
    file as a side effect, so this points it at a temp file instead of patching.
    """
    path = tmp_path / "topics.json"
    path.write_text(json.dumps(TOPICS), encoding="utf-8")
    return TopicService(str(path))


class TestGetRandomTopic:
    def test_returns_a_known_topic(self, service):
        assert service.get_random_topic() in TOPICS

    def test_filters_by_difficulty(self, service):
        for _ in range(10):
            assert service.get_random_topic(difficulty="easy")["difficulty"] == "easy"

    def test_filters_by_category(self, service):
        for _ in range(10):
            assert service.get_random_topic(category="Tech")["category"] == "Tech"

    def test_combined_filters_pin_single_topic(self, service):
        assert service.get_random_topic(difficulty="easy", category="Tech") == TOPICS[0]

    def test_unmatched_filter_falls_back_to_all_topics(self, service):
        assert service.get_random_topic(difficulty="impossible") in TOPICS


class TestGetTopicById:
    def test_finds_exact_topic(self, service):
        assert service.get_topic_by_id(2) == TOPICS[1]

    def test_unknown_id_returns_none(self, service):
        """Behaviour change: previously an unknown id returned a *random* topic.

        Answering a lookup for id 999 with an unrelated topic silently gives the
        caller the wrong record; None lets the caller decide how to handle a miss.
        """
        assert service.get_topic_by_id(999) is None


class TestGetAllCategories:
    def test_returns_sorted_unique_categories(self, service):
        assert service.get_all_categories() == ["Health", "Tech"]


class TestLoadTopics:
    def test_real_data_file_is_the_only_source_of_topics(self):
        """Topics were previously duplicated verbatim in the source as `default_topics`."""
        with open(TOPICS_FILE, encoding="utf-8") as f:
            on_disk = json.load(f)
        assert TopicService().topics == on_disk

    def test_missing_file_falls_back_without_raising(self, tmp_path):
        service = TopicService(str(tmp_path / "nope.json"))
        assert len(service.topics) == 1
        assert service.get_random_topic()["topic"]

    def test_malformed_file_falls_back_without_raising(self, tmp_path):
        bad = tmp_path / "topics.json"
        bad.write_text("{not json", encoding="utf-8")
        assert len(TopicService(str(bad)).topics) == 1

    def test_empty_file_falls_back_without_raising(self, tmp_path):
        empty = tmp_path / "topics.json"
        empty.write_text("[]", encoding="utf-8")
        assert len(TopicService(str(empty)).topics) == 1
