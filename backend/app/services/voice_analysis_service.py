import io
import logging
from typing import Dict

import librosa
import numpy as np

from app.utils.audio import DecodedRecording

logger = logging.getLogger(__name__)


class VoiceAnalysisService:
    def __init__(self):
        logger.info("VoiceAnalysisService initialized.")

    def analyze_audio(self, recording: DecodedRecording) -> Dict:
        """Analyze a decoded recording for tone, pitch, energy and confidence.

        Takes an already-decoded recording rather than the raw upload: librosa
        cannot demux the browser's WebM/Opus, and decoding is the caller's job
        so it happens once per recording rather than once per analyser.
        """
        if not recording:
            return self._degraded("no audio to analyse")

        try:
            y, sr = librosa.load(recording.as_stream(), sr=None)

            if y.size == 0:
                return self._degraded("decoded audio was empty")
            
            # Calculate various audio features
            analysis = {}
            
            # 1. Pitch/Fundamental Frequency
            pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
            pitch_values = []
            for t in range(pitches.shape[1]):
                index = magnitudes[:, t].argmax()
                pitch = pitches[index, t]
                if pitch > 0:
                    pitch_values.append(pitch)
            
            if pitch_values:
                analysis["average_pitch"] = round(float(np.mean(pitch_values)), 2)
                analysis["pitch_variance"] = round(float(np.std(pitch_values)), 2)
            else:
                analysis["average_pitch"] = 0
                analysis["pitch_variance"] = 0
            
            # 2. Energy/Volume
            rms = librosa.feature.rms(y=y)[0]
            analysis["average_energy"] = round(float(np.mean(rms)), 4)
            analysis["energy_variance"] = round(float(np.std(rms)), 4)
            
            # 3. Speaking Rate (zero crossing rate as proxy)
            zcr = librosa.feature.zero_crossing_rate(y)[0]
            analysis["articulation_rate"] = round(float(np.mean(zcr)), 4)
            
            # 4. Spectral Features (voice quality)
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            analysis["voice_brightness"] = round(float(np.mean(spectral_centroid)), 2)
            
            # 5. Confidence Indicators
            # Higher energy + stable pitch = more confidence
            confidence_score = self._calculate_confidence(
                analysis["average_energy"],
                analysis["pitch_variance"],
                analysis["energy_variance"]
            )
            analysis["confidence_score"] = confidence_score
            
            # 6. Duration
            analysis["duration"] = round(float(len(y) / sr), 2)
            
            return analysis
            
        except Exception as e:
            logger.exception("Voice analysis failed")
            return self._degraded(str(e))

    @staticmethod
    def _degraded(reason: str) -> Dict:
        """A result explicitly marked unmeasured.

        Never invents a mid-range confidence_score: a fabricated number would
        flow into the overall rating and be persisted as if it had been measured.
        """
        return {
            "average_pitch": None,
            "pitch_variance": None,
            "average_energy": None,
            "energy_variance": None,
            "articulation_rate": None,
            "voice_brightness": None,
            "confidence_score": None,
            "duration": None,
            "degraded": True,
            "error": reason,
        }

    
    def _calculate_confidence(self, energy: float, pitch_var: float, energy_var: float) -> int:
        """
        Calculate a confidence score (0-100) based on voice characteristics
        Higher energy + lower variance = more confidence
        """
        # Normalize and weight factors
        confidence = 50  # baseline
        
        # Higher energy increases confidence (up to +25)
        if energy > 0.01:
            confidence += min(25, energy * 1000)
        
        # Lower pitch variance increases confidence (up to +15)
        if pitch_var < 50:
            confidence += (50 - pitch_var) / 50 * 15
        
        # Lower energy variance increases confidence (up to +10)
        if energy_var < 0.01:
            confidence += (0.01 - energy_var) * 1000
        
        return int(max(0, min(100, confidence)))
    
    def get_tone_description(self, analysis: Dict) -> str:
        """Convert analysis metrics into human-readable tone description"""
        if not analysis or analysis.get("degraded"):
            return "unavailable"

        confidence = analysis.get("confidence_score")
        energy = analysis.get("average_energy")
        pitch_var = analysis.get("pitch_variance")
        if confidence is None or energy is None or pitch_var is None:
            return "unavailable"

        descriptions = []
        
        # Confidence
        if confidence >= 75:
            descriptions.append("confident")
        elif confidence >= 50:
            descriptions.append("moderately confident")
        else:
            descriptions.append("uncertain")
        
        # Energy
        if energy > 0.02:
            descriptions.append("energetic")
        elif energy > 0.01:
            descriptions.append("steady")
        else:
            descriptions.append("calm")
        
        # Pitch variance
        if pitch_var > 80:
            descriptions.append("expressive")
        elif pitch_var > 40:
            descriptions.append("varied")
        else:
            descriptions.append("monotone")
        
        return ", ".join(descriptions)