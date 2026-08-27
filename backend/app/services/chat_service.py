import asyncio
import logging
from typing import Dict, List

from google import genai
from google.genai import types

from app.config import config

logger = logging.getLogger(__name__)

# Configurable, and versioned: model names expire. See Config.CHAT_MODEL.
MODEL_NAME = config.CHAT_MODEL
MAX_RETRIES = 3
MAX_HISTORY_MESSAGES = 20

SYSTEM_INSTRUCTION = (
    "You are Polly AI, an expert debate coach. You help people improve their "
    "debate and public speaking skills through constructive feedback and encouragement. "
    "Keep responses concise (2-4 paragraphs max) and actionable."
)


class ChatService:
    """Gemini-backed debate coaching.

    Uses the `google-genai` SDK. The previous `google-generativeai` package is
    deprecated and receives no further model support (issue #28).
    """

    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set; chat responses will be unavailable.")

        # The client is cheap to construct and thread-safe; a single instance is
        # reused across sessions.
        self.client = genai.Client(api_key=self.api_key) if self.api_key else None
        self._chats: Dict[str, list] = {}  # session_id -> conversation history
        logger.info("ChatService initialized (model=%s, key_set=%s)", MODEL_NAME, bool(self.api_key))

    def _get_history(self, session_id: str) -> list:
        if session_id not in self._chats:
            self._chats[session_id] = []
        return self._chats[session_id]

    def get_history(self, session_id: str) -> List[Dict]:
        """Read-only view of the conversation history for a session."""
        return list(self._chats.get(session_id, []))

    def _build_contents(self, session_id: str, prompt: str) -> List[types.Content]:
        """Turn the stored history into typed SDK turns.

        The old SDK path flattened everything into one string prefixed with
        "User:"/"Polly AI:" labels, which the model could confuse with content.
        Roles are now carried structurally.
        """
        contents: List[types.Content] = []
        for msg in self._get_history(session_id)[-MAX_HISTORY_MESSAGES:]:
            role = "user" if msg["role"] == "user" else "model"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
        return contents

    def _build_system_instruction(self, emotion_summary: Dict = None) -> str:
        instruction = SYSTEM_INSTRUCTION
        if emotion_summary and emotion_summary.get("emotion_summary"):
            emotions = emotion_summary.get("emotion_summary", {})
            instruction += (
                "\n\nThe user's current emotional state detected via camera: "
                f"{emotions.get('dominant', 'neutral')}"
            )
        return instruction

    async def get_coach_response(self, session_id: str, prompt: str,
                               emotion_summary: Dict = None,
                               record_history: bool = True) -> str:
        """Get a Gemini response with full conversation context.

        `record_history` is False for machine-generated prompts (e.g. the
        post-session analysis prompt) so they do not pollute the user-facing
        conversation context of subsequent chat turns.
        """
        if not self.client:
            return "Error: Gemini API key is not configured. Please set GEMINI_API_KEY."

        contents = self._build_contents(session_id, prompt)
        gen_config = types.GenerateContentConfig(
            system_instruction=self._build_system_instruction(emotion_summary),
        )

        for attempt in range(MAX_RETRIES):
            try:
                # generate_content is a blocking network call. Running it directly
                # in this coroutine would stall the whole event loop -- freezing
                # frame processing for every other connected session -- so it is
                # offloaded to a worker thread.
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=MODEL_NAME,
                    contents=contents,
                    config=gen_config,
                )
                reply = (response.text or "").strip()
                if not reply:
                    raise ValueError("Gemini returned an empty response")

                if record_history:
                    history = self._get_history(session_id)
                    history.append({"role": "user", "content": prompt})
                    history.append({"role": "assistant", "content": reply})

                return reply

            except Exception as e:
                error_str = str(e)
                logger.warning(
                    "Gemini API error (attempt %d/%d) for session %s: %s",
                    attempt + 1, MAX_RETRIES, session_id, error_str,
                )

                if "429" in error_str or "rate" in error_str.lower():
                    if attempt < MAX_RETRIES - 1:
                        wait_time = (attempt + 1) * 5  # 5s, 10s, 15s
                        logger.info("Rate limited; retrying in %ds", wait_time)
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
