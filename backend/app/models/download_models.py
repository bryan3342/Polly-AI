from deepface import DeepFace
import os


print("Test to see if its working")

try:
    DeepFace.build_model("Emotion")
    print("DeepFace is working correctly.")
except Exception as e:
    print(f"Error initializing DeepFace: {e}")
    