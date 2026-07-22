import logging
from datetime import datetime, timezone

from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, JSON, Text
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import config

logger = logging.getLogger(__name__)

# Read through the central config so the default is defined in exactly one place.
DATABASE_URL = config.DATABASE_URL

# Create engine
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})

# Create session
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

class DebateSession(Base):
    __tablename__ = "debate_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, index=True)
    topic_id = Column(Integer)
    topic_text = Column(String)
    duration = Column(Float)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Transcript data
    transcript = Column(Text)
    word_count = Column(Integer)
    words_per_minute = Column(Float)
    
    # Voice analysis
    voice_analysis = Column(JSON)
    confidence_score = Column(Float)
    
    # Emotion data
    emotion_summary = Column(JSON)
    dominant_emotion = Column(String)
    
    # AI Feedback
    ai_feedback = Column(Text)
    overall_score = Column(Float)

# Create tables
def init_db():
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created.")

# Get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()