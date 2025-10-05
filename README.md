# Polly AI  
**AI-Powered Debate Coach with Real-Time Feedback**

## Contributors:
### Giancarlo Forero, Sharlyn Barreto, Bryan Mejia

## Overview  
Polly AI is an intelligent debate coaching application designed to help users improve their **public speaking, debating, and argumentation skills**.  

Using **real-time emotion detection, voice analysis, speech-to-text transcription, and Google Gemini AI**, Polly AI provides personalized coaching and detailed feedback on **delivery, confidence, emotional presentation, and argument quality**.  

Whether you're practicing for a debate competition, working on presentation skills, or building communication confidence, Polly AI serves as your AI-powered debate coach.

---

## Features  
-  **Real-Time Speech-to-Text** → Record your voice and get instant transcription (currently mock, supports integration with Google Speech-to-Text)
-  **Voice & Tone Analysis** → Evaluates pitch, confidence score, energy, and articulation using librosa
-  **Live Facial Emotion Detection** → Tracks emotions (happy, sad, angry, neutral, surprised, fear, disgust) in real-time via webcam using DeepFace
-  **AI Debate Coaching** → Google Gemini AI provides personalized feedback on arguments, delivery, and improvement areas
-  **Random Debate Topics** → Get assigned a random debate topic on connection to practice immediately
-  **Interactive Chat Interface** → Ask questions and get coaching advice through a chat interface with markdown support
-  **Session Analysis** → Comprehensive feedback reports including speech metrics, voice analysis, and emotion summaries

---

## Tech Stack  

**Frontend**  
- **React.js** – Core UI framework with hooks
- **Tailwind CSS** – Styling
- **WebRTC (MediaRecorder API)** – Live audio recording
- **WebSocket** – Real-time bidirectional communication
- **React Webcam** – Live video feed for emotion detection
- **React Markdown** – Formatted AI responses

**Backend**  
- **FastAPI** – High-performance async Python backend
- **WebSocket** – Real-time frame processing and communication
- **Google Gemini AI (gemini-1.5-flash)** – Intelligent debate coaching and feedback
- **DeepFace** – Facial emotion recognition from video frames
- **librosa** – Audio feature extraction and voice analysis
- **SQLite** – Session data persistence
- **Python asyncio** – Concurrent processing

**Computer Vision & Audio Processing**  
- **OpenCV** – Image processing for facial analysis
- **DeepFace** – Emotion classification
- **librosa** – Voice tone, pitch, and confidence analysis
- **NumPy** – Audio signal processing

---

## How It Works  

1. **Connect** → User opens the app and WebSocket connects to the backend
2. **Topic Assignment** → Polly AI greets the user and assigns a random debate topic
3. **Practice** → User can either:
   - Type their argument in the chat
   - Record audio by holding the microphone button
4. **Real-Time Analysis**:
   - Webcam captures video frames every second
   - Backend analyzes facial emotions using DeepFace
   - Audio is transcribed to text (mock or Google Speech-to-Text)
   - Voice characteristics analyzed with librosa
5. **AI Feedback** → Google Gemini AI evaluates the argument and provides:
   - Overall assessment
   - Specific strengths
   - Areas for improvement
   - Actionable coaching tips
6. **Continuous Learning** → User can chat with Polly AI for clarification, tips, or request new topics

---

## Key Features in Detail

## Debate Topic System
- Random topic generation on connection
- Topics stored in database
- Can request new topics anytime

## Emotion Tracking
- Real-time webcam analysis
- Frame-by-frame emotion detection
- Session emotion summaries (dominant emotion, detection rate)

## Voice Analysis
- Pitch analysis (average and variance)
- Energy/volume tracking
- Articulation rate measurement
- Confidence scoring (0-100)
- Tone descriptions (confident, energetic, expressive, etc.)

## AI Coaching
- Contextual feedback based on emotional state
- Analysis of argument structure and persuasiveness
- Speech pattern evaluation (pace, filler words, pauses)
- Personalized improvement suggestions
