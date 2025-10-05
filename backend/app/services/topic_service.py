import random
import json
import os
from typing import Dict, List

class TopicService:
    def __init__(self):
        self.topics = self._load_topics()
        print(f"TopicService initialized with {len(self.topics)} topics.")
    
    def _load_topics(self) -> List[Dict]:
        """Load debate topics from JSON file or use default topics"""
        topics_file = os.path.join(os.path.dirname(__file__), "..", "data", "topics.json")
        
        # Default topics if file doesn't exist
        default_topics = [
            {
                "id": 1,
                "topic": "Social media does more harm than good to society",
                "category": "Technology",
                "difficulty": "medium"
            },
            {
                "id": 2,
                "topic": "Remote work should be the default for all office jobs",
                "category": "Work & Career",
                "difficulty": "easy"
            },
            {
                "id": 3,
                "topic": "Artificial intelligence will create more jobs than it destroys",
                "category": "Technology",
                "difficulty": "hard"
            },
            {
                "id": 4,
                "topic": "College education is not worth the cost anymore",
                "category": "Education",
                "difficulty": "medium"
            },
            {
                "id": 5,
                "topic": "Video games are an effective educational tool",
                "category": "Education",
                "difficulty": "easy"
            },
            {
                "id": 6,
                "topic": "Climate change is the most pressing issue of our generation",
                "category": "Environment",
                "difficulty": "medium"
            },
            {
                "id": 7,
                "topic": "Universal basic income would benefit society",
                "category": "Economics",
                "difficulty": "hard"
            },
            {
                "id": 8,
                "topic": "Celebrities have too much influence on society",
                "category": "Society",
                "difficulty": "easy"
            },
            {
                "id": 9,
                "topic": "Traditional news media is becoming obsolete",
                "category": "Media",
                "difficulty": "medium"
            },
            {
                "id": 10,
                "topic": "Space exploration is a waste of resources",
                "category": "Science",
                "difficulty": "medium"
            },
            {
                "id": 11,
                "topic": "Standardized testing does not accurately measure intelligence",
                "category": "Education",
                "difficulty": "easy"
            },
            {
                "id": 12,
                "topic": "Cryptocurrency will replace traditional banking",
                "category": "Technology",
                "difficulty": "hard"
            },
            {
                "id": 13,
                "topic": "Fast fashion is destroying the environment",
                "category": "Environment",
                "difficulty": "easy"
            },
            {
                "id": 14,
                "topic": "Professional athletes are overpaid",
                "category": "Sports",
                "difficulty": "medium"
            },
            {
                "id": 15,
                "topic": "Self-driving cars will make roads safer",
                "category": "Technology",
                "difficulty": "medium"
            }
        ]
        
        try:
            if os.path.exists(topics_file):
                with open(topics_file, 'r') as f:
                    return json.load(f)
            else:
                # Create the file with default topics
                os.makedirs(os.path.dirname(topics_file), exist_ok=True)
                with open(topics_file, 'w') as f:
                    json.dump(default_topics, f, indent=2)
                return default_topics
        except Exception as e:
            print(f"Error loading topics: {e}")
            return default_topics
    
    def get_random_topic(self, difficulty: str = None, category: str = None) -> Dict:
        """Get a random debate topic, optionally filtered by difficulty or category"""
        filtered_topics = self.topics
        
        if difficulty:
            filtered_topics = [t for t in filtered_topics if t.get("difficulty") == difficulty]
        
        if category:
            filtered_topics = [t for t in filtered_topics if t.get("category") == category]
        
        if not filtered_topics:
            filtered_topics = self.topics  # Fallback to all topics
        
        return random.choice(filtered_topics)
    
    def get_topic_by_id(self, topic_id: int) -> Dict:
        """Get a specific topic by ID"""
        for topic in self.topics:
            if topic.get("id") == topic_id:
                return topic
        return self.get_random_topic()  # Fallback to random
    
    def get_all_categories(self) -> List[str]:
        """Get list of all available categories"""
        categories = set()
        for topic in self.topics:
            if "category" in topic:
                categories.add(topic["category"])
        return sorted(list(categories))