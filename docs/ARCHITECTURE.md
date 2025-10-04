# System Architecture - Polly AI

## Overview

Polly AI is a full-stack application that analyzes speech, tone, and facial expressions from video input to provide comprehensive feedback for interview and debate preparation.

---

## Technology Stack

### Frontend
- **Framework:** React 18+
- **Build Tool:** Vite
- **Language:** JavaScript/TypeScript
- **Real-time Communication:** WebRTC, Socket.io-client
- **State Management:** React Context + Hooks
- **Styling:** Tailwind CSS
- **Charts/Visualization:** Recharts
- **Icons:** Lucide React
- **HTTP Client:** Axios

### Backend
- **Framework:** FastAPI (Python 3.9+)
- **ASGI Server:** Uvicorn
- **Language:** Python
- **API Documentation:** OpenAPI (Swagger), ReDoc
- **WebSocket:** Python Socket.IO
- **Async Support:** asyncio, aiofiles

### AI/ML Services
- **Speech-to-Text:** OpenAI Whisper API
- **Tone Analysis:** pyAudioAnalysis, librosa
- **Facial Emotion Detection:** OpenCV, DeepFace
- **AI Feedback Generation:** OpenAI GPT-4 API
- **Audio Processing:** FFmpeg

### Data Storage
- **Database:** PostgreSQL (metadata, sessions)
- **Cache:** Redis (API responses, session data)
- **File Storage:** AWS S3 / MinIO (video files)
- **ORM:** SQLAlchemy

### Infrastructure
- **Containerization:** Docker, Docker Compose
- **Reverse Proxy:** Nginx (production)
- **Process Manager:** Supervisor (production)
- **CI/CD:** GitHub Actions
- **Deployment:** AWS / DigitalOcean / Heroku

### Development Tools
- **Version Control:** Git, GitHub
- **API Testing:** Postman, pytest
- **Code Quality:** ESLint, Prettier, Black, pylint
- **Environment Management:** dotenv
