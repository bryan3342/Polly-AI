"""The post-session analysis prompt sent to the coaching model.

Domain text, not transport: it describes how a session is summarised for the
coach, and changing the wording should not mean touching the WebSocket layer.
"""

from typing import Dict


def build_feedback_prompt(topic: Dict, duration: float, transcript_data: Dict,
                           speech_analysis: Dict, tone_description: str,
                           voice_analysis: Dict, emotion_summary: Dict) -> str:
    """Compose the post-session analysis prompt sent to the coaching model."""
    emotions = (emotion_summary or {}).get("emotion_summary", {}) or {}
    confidence = (voice_analysis or {}).get("confidence_score")
    detections = emotions.get("detections")

    caveat = ""
    if transcript_data.get("is_mock"):
        caveat = (
            "\nNOTE: Speech-to-text is not enabled, so the transcript and the metrics "
            "derived from it are placeholders. Do not comment on the wording of the "
            "transcript; focus your feedback on vocal delivery and composure.\n"
        )

    return f"""
        Analyze this debate practice session and provide constructive feedback.
        {caveat}
        DEBATE TOPIC: {topic.get('topic')}
        DURATION: {duration:.1f} seconds

        TRANSCRIPT:
        {transcript_data.get('text', 'No transcript available')}

        SPEECH METRICS:
        - Word count: {speech_analysis.get('word_count', 0)}
        - Speaking pace: {speech_analysis.get('words_per_minute', 0)} words/minute
        - Filler words: {speech_analysis.get('filler_word_count', 0)} ({speech_analysis.get('filler_percentage', 0)}%)
        - Average pause duration: {speech_analysis.get('average_pause_duration', 0)} seconds

        VOICE ANALYSIS:
        - Tone: {tone_description}
        - Confidence score: {'unavailable' if confidence is None else f'{confidence}/100'}

        EMOTIONAL STATE:
        - Dominant emotion: {emotions.get('dominant', 'not detected')}
        - Detection rate: {'unavailable' if detections is None else f'{detections:.1%}'}

        Please provide:
        1. Overall assessment (2-3 sentences)
        2. Strengths (2-3 specific points)
        3. Areas for improvement (2-3 specific points)
        4. Actionable tips for next practice (3-4 concrete suggestions)

        Keep feedback constructive, specific, and encouraging.
        """
