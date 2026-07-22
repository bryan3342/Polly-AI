from unittest.mock import patch

import pytest

from app.services.topic_service import TopicService

TOPICS = [
    {"id": 1, "topic": "Topic A", "category": "Tech", "difficulty": "easy"},
    {"id": 2, "topic": "Topic B", "category": "Tech", "difficulty": "hard"},
    {"id": 3, "topic": "Topic C", "category": "Health", "difficulty": "easy"},
]


@pytest.fixture
def service():
    # Patch topic loading so tests never touch app/data/topics.json
    # (the real loader creates the file as a side effect).
    with patch.object(TopicService, "_load_topics", return_value=list(TOPICS)):
        return TopicService()


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

    def test_unknown_id_falls_back_to_a_valid_topic(self, service):
        assert service.get_topic_by_id(999) in TOPICS


class TestGetAllCategories:
    def test_returns_sorted_unique_categories(self, service):
        assert service.get_all_categories() == ["Health", "Tech"]
