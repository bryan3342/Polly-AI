from app.config import config
import io
from typing import Dict

class SpeechService:
    def __init__(self):
        print("SpeechService initialized (using mock transcription).")
    
    async def transcribe_audio(self, audio_data: bytes) -> Dict:
        """Mock transcription - replace with Google Cloud Speech-to-Text if needed"""
        
        return {
            "text": "Mock transcription: You presented a strong argument about the debate topic. Your main points were clear and well-structured. You maintained good pacing throughout your speech.",
            "segments": [
                {"start": 0, "end": 5},
                {"start": 5, "end": 10},
                {"start": 10, "end": 15}
            ],
            "duration": 15.0,
            "language": "en"
        }
    
    def analyze_speech_patterns(self, transcript_data: Dict) -> Dict:
        """Analyze speech patterns from transcript"""
        text = transcript_data.get("text", "")
        segments = transcript_data.get("segments", [])
        duration = transcript_data.get("duration", 0)
        
        if not text or duration == 0:
            return {}
        
        words = text.split()
        word_count = len(words)
        wpm = (word_count / duration) * 60 if duration > 0 else 0
        
        filler_words = ["um", "uh", "like", "you know", "so", "basically", "actually"]
        filler_count = sum(text.lower().count(f" {filler} ") for filler in filler_words)
        
        pauses = []
        for i in range(len(segments) - 1):
            gap = segments[i + 1].get("start", 0) - segments[i].get("end", 0)
            if gap > 0.5:
                pauses.append(gap)
        
        avg_pause = sum(pauses) / len(pauses) if pauses else 0
        
        return {
            "word_count": word_count,
            "words_per_minute": round(wpm, 1),
            "filler_word_count": filler_count,
            "filler_percentage": round((filler_count / word_count * 100), 1) if word_count > 0 else 0,
            "pause_count": len(pauses),
            "average_pause_duration": round(avg_pause, 2),
            "total_speaking_time": round(duration, 1)
        }