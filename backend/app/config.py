import os
from dotenv import load_dotenv


load_dotenv()

class Config:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./debate_sessions.db")
    SECRET_KEY = os.getenv("SECRET_KEY")
    CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]

    FRAME_PROCESS_INTERVAL = 1.0        # Every second, process a video frame
    AUDIO_CHUNK_DURATION = 3.0          # Every 3 secs, audio processes


config = Config()