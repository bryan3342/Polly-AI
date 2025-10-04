from app.config import config
import openai
from typing import List, Dict

class ChatService:
    def __init__(self):
        self.api_key = config.OPENAI_API_KEY
        if not self.api_key:
            print("Warning: OPENAI_API_KEY is not set. Please set it in your environment variables.")
        
        # Initialize OpenAI chat
        openai.api_key = self.api_key
        print("ChatService initialized with OpenAI API key.")

    async def get_gpt_response(self, session_id: str, prompt: str, emotion_summary: Dict):

        if not self.api_key:
            return "Error: OpenAI API key is not configured."

        system_prompt = (
            "You are an AI assistant that helps users improve their debate skills. "
            "Based on the user's emotional state during their practice session, provide constructive feedback. "
            "Use the following emotional summary to tailor your advice:\n"
            f"{emotion_summary}\n"
            "Offer specific suggestions on how to manage emotions like nervousness, confidence, and enthusiasm during debates."
        )

        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ]
        
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=messages,
                max_tokens=500,
                n=1,
                stop=None,
                temperature=0.7,
            )

            return response.choices[0].message['content'].strip()
        except Exception as e:
            print(f"Error getting GPT response: {str(e)}")
            return "Error: Unable to get response from OpenAI."