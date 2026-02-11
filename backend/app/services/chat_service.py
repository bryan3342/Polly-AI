from app.config import config
import google.generativeai as genai
from typing import Dict

class ChatService:
    def __init__(self):
        self.api_key = config.GEMINI_API_KEY
        if not self.api_key:
            print("Warning: GEMINI_API_KEY is not set.")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        print("ChatService initialized with Gemini API.")

    async def get_gpt_response(self, session_id: str, prompt: str, emotion_summary: Dict = None):
        """Get Gemini response for chat or feedback"""
        if not self.api_key:
            return "Error: Gemini API key is not configured."

        system_context = """You are Polly AI, an expert debate coach. You help people improve their 
        debate and public speaking skills through constructive feedback and encouragement."""
        
        if emotion_summary and emotion_summary.get("emotion_summary"):
            emotions = emotion_summary.get("emotion_summary", {})
            system_context += f"\n\nCurrent emotional state: {emotions.get('dominant', 'neutral')}"

        try:
            full_prompt = f"{system_context}\n\nUser: {prompt}"
            
            response = self.model.generate_content(full_prompt)
            return response.text.strip()
            
        except Exception as e:
            print(f"Error getting Gemini response: {str(e)}")
            return "Error: Unable to get response from Gemini."