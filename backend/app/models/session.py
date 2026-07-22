import logging
from typing import Dict, Optional

from app.database import DebateSession, SessionLocal

logger = logging.getLogger(__name__)


class SessionModel:
    """Handle database operations for debate sessions"""
    
    @staticmethod
    def create_session(session_data: Dict) -> Optional[DebateSession]:
        """Create a new debate session in the database"""
        db = SessionLocal()
        try:
            session = DebateSession(
                session_id=session_data.get("session_id"),
                topic_id=session_data.get("topic_id"),
                topic_text=session_data.get("topic_text"),
                duration=session_data.get("duration", 0),
                transcript=session_data.get("transcript", ""),
                word_count=session_data.get("word_count", 0),
                words_per_minute=session_data.get("words_per_minute", 0),
                voice_analysis=session_data.get("voice_analysis", {}),
                confidence_score=session_data.get("confidence_score", 0),
                emotion_summary=session_data.get("emotion_summary", {}),
                dominant_emotion=session_data.get("dominant_emotion", "neutral"),
                ai_feedback=session_data.get("ai_feedback", ""),
                overall_score=session_data.get("overall_score", 0)
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            return session
        except Exception:
            logger.exception("Error creating session record")
            db.rollback()
            return None
        finally:
            db.close()
    
    @staticmethod
    def get_session(session_id: str) -> Optional[DebateSession]:
        """Retrieve a session by ID"""
        db = SessionLocal()
        try:
            return db.query(DebateSession).filter(DebateSession.session_id == session_id).first()
        finally:
            db.close()
    
    @staticmethod
    def get_all_sessions(limit: int = 20) -> list:
        """Get recent sessions"""
        db = SessionLocal()
        try:
            return db.query(DebateSession).order_by(DebateSession.created_at.desc()).limit(limit).all()
        finally:
            db.close()
    
    @staticmethod
    def get_user_stats() -> Dict:
        """Calculate user statistics across all sessions"""
        db = SessionLocal()
        try:
            sessions = db.query(DebateSession).all()
            if not sessions:
                return {}

            total_sessions = len(sessions)

            def _mean(values):
                # Average over the sessions that actually recorded a value. Dividing
                # by total_sessions instead would understate the average whenever any
                # session is missing that metric.
                present = [v for v in values if v is not None]
                return round(sum(present) / len(present), 1) if present else None

            return {
                "total_sessions": total_sessions,
                "average_confidence": _mean(s.confidence_score for s in sessions),
                "average_score": _mean(s.overall_score for s in sessions),
                "total_words_spoken": sum(s.word_count or 0 for s in sessions),
            }
        finally:
            db.close()