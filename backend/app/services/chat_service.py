from app.config import config
import google.generativeai as genai
from typing import Dict, List
import asyncio

class ChatService:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        if not self.api_key:
            print("Warning: GEMINI_API_KEY is not set.")

        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-lite')
        self._chats: Dict[str, list] = {}  # session_id -> conversation history
        print(f"ChatService initialized with Gemini API (model: gemini-2.0-flash-lite, key set: {bool(self.api_key)})")

    def _get_history(self, session_id: str) -> list:
        if session_id not in self._chats:
            self._chats[session_id] = []
        return self._chats[session_id]

    async def get_gpt_response(self, session_id: str, prompt: str,
                                emotion_summary: Dict = None,
                                chat_history: List[Dict] = None) -> str:
        """Get Gemini response with full conversation context"""
        if not self.api_key:
            return "Error: Gemini API key is not configured. Please set GEMINI_API_KEY."

        system_context = (
            "You are Polly AI, an expert debate coach. You help people improve their "
            "debate and public speaking skills through constructive feedback and encouragement. "
            "Keep responses concise (2-4 paragraphs max) and actionable."
        )

        if emotion_summary and emotion_summary.get("emotion_summary"):
            emotions = emotion_summary.get("emotion_summary", {})
            system_context += f"\n\nThe user's current emotional state detected via camera: {emotions.get('dominant', 'neutral')}"

        # Build conversation context from chat history
        history = self._get_history(session_id)

        # Include recent history (last 10 exchanges) for context
        recent = history[-20:] if len(history) > 20 else history
        conversation = f"{system_context}\n\n"

        if recent:
            conversation += "Previous conversation:\n"
            for msg in recent:
                role = "User" if msg["role"] == "user" else "Polly AI"
                conversation += f"{role}: {msg['content']}\n"
            conversation += "\n"

        conversation += f"User: {prompt}"

        # Retry up to 3 times for rate limit errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.model.generate_content(conversation)
                reply = response.text.strip()

                # Store in history
                history.append({"role": "user", "content": prompt})
                history.append({"role": "assistant", "content": reply})

                return reply

            except Exception as e:
                error_str = str(e)
                print(f"Gemini API error (attempt {attempt + 1}/{max_retries}): {error_str}")

                # Retry on rate limit (429) errors
                if "429" in error_str or "rate" in error_str.lower():
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                        print(f"Rate limited. Waiting {wait_time}s before retry...")
                        await asyncio.sleep(wait_time)
                        continue
                    return "I'm currently at my request limit. Please wait a minute and try again."

                if "403" in error_str or "key" in error_str.lower():
                    return "There's an issue with the AI configuration. Please contact the admin."

                return "I'm having trouble responding right now. Please try again."

        return "I'm having trouble responding right now. Please try again."

    def clear_history(self, session_id: str):
        """Clear conversation history for a session"""
        self._chats.pop(session_id, None)
