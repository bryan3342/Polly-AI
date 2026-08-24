import json
import logging
import os
import random
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TOPICS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "topics.json")

# Minimal safety net so the app still starts if the data file is missing or
# corrupt. The full topic set lives in data/topics.json, which is the single
# source of truth -- it is not duplicated here.
_FALLBACK_TOPIC = {
    "id": 0,
    "topic": "Social media does more harm than good to society",
    "category": "General",
    "difficulty": "medium",
}


class TopicService:
    def __init__(self, topics_file: str = TOPICS_FILE):
        self.topics = self._load_topics(topics_file)
        logger.info("TopicService initialized with %d topics.", len(self.topics))

    def _load_topics(self, topics_file: str) -> List[Dict]:
        """Load debate topics from the JSON data file."""
        try:
            with open(topics_file, "r", encoding="utf-8") as f:
                topics = json.load(f)
        except FileNotFoundError:
            logger.error("Topics file not found at %s; using fallback topic.", topics_file)
            return [dict(_FALLBACK_TOPIC)]
        except (json.JSONDecodeError, OSError):
            logger.exception("Could not read topics from %s; using fallback topic.", topics_file)
            return [dict(_FALLBACK_TOPIC)]

        if not isinstance(topics, list) or not topics:
            logger.error("Topics file %s is empty or malformed; using fallback topic.", topics_file)
            return [dict(_FALLBACK_TOPIC)]

        return topics

    def get_random_topic(self, difficulty: str = None, category: str = None) -> Dict:
        """Get a random debate topic, optionally filtered by difficulty or category"""
        filtered = self.topics

        if difficulty:
            filtered = [t for t in filtered if t.get("difficulty") == difficulty]
        if category:
            filtered = [t for t in filtered if t.get("category") == category]

        if not filtered:
            filtered = self.topics  # Fallback to all topics

        return random.choice(filtered)

    def get_topic_by_id(self, topic_id: int) -> Optional[Dict]:
        """Get a specific topic by ID, or None if no topic has that ID."""
        for topic in self.topics:
            if topic.get("id") == topic_id:
                return topic
        return None

    def get_all_categories(self) -> List[str]:
        """Get list of all available categories"""
        return sorted({t["category"] for t in self.topics if "category" in t})
