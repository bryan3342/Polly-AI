import cv2
import sys
import time
from app.services.emotion_service import EmotionService

# For Documentation and Reference:
# https://pypi.org/project/opencv-python/

def test_camera():
    print("Testing Camera Emotion Detection...")
    print("Press 'q' to quit the camera feed.")

    # Initialize Emotion Detection Service
    try:
        emotion_service = EmotionService()
        print("Emotion Detection Service initialized successfully.")

    except Exception as e:
        print(f"Error initializing Emotion Detection Service: {str(e)}")
        sys.exit(1)

    # Loading Face Detection Classifier
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )

    # Start video capture from the default camera (0)
    cap = cv2.VideoCapture(0)

    # Check if the camera opened successfully
    if not cap.isOpened():
        print("Error: Could not open camera.")
        sys.exit(1)
    
    print("Camera opened successfully.")

    emotion_timeline = []
    last_emotion_time = time.time()
    current_emotion_result = None

    while True:

        ret, frame = cap.read()

        # Different flip options:
        #
        # frame = cv2.flip(frame, 0)   Vertical flip (upside down)
        # frame = cv2.flip(frame, 1)   Horizontal flip (mirror fix)
        # frame = cv2.flip(frame, -1)  Both vertical and horizontal

        frame = cv2.flip(frame, 1)

        if not ret:
            print("Error: Could not read frame.")
            break
    
        current_time = time.time()
        
        # Detect faces using Haar Cascade
        faces = face_cascade.detectMultiScale(
            frame, 
            scaleFactor=1.1, 
            minNeighbors=5,
            minSize=(30, 30)    
        )

        # Process emotion every 1 second (not every frame - too slow)
        if current_time - last_emotion_time >= 1.0:
            # Analyzing emotions / To edit visit services/emotion_service.py
            emotion_result = emotion_service.analyze_frame(frame)
            emotion_timeline.append(emotion_result)
            current_emotion_result = emotion_result
            last_emotion_time = current_time

            if emotion_result['face_detected']:
                print(f"Emotion Detected: {emotion_result['dominant_emotion']} (Confidence: {emotion_result['confidence']:.2f})")
            

        # Draw rectangles around detected faces
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)

            if current_emotion_result and current_emotion_result['face_detected']:
                emotion_text = f"{current_emotion_result['dominant_emotion'].upper()}"
                confidence_text = f"({current_emotion_result['confidence']*100:.1f}%)"

                cv2.putText(
                    frame, 
                    emotion_text, 
                    (x, y - 35), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    1.0, 
                    (0, 255, 0), 
                    2
                )

                cv2.putText(
                    frame, 
                    confidence_text, 
                    (x, y-10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.6, 
                    (0, 255, 0), 
                    2
                )

        # Show emotion bars on the left side
        if current_emotion_result and current_emotion_result['face_detected']:
            y_offset = 30

            sorted_emotions = sorted(
                current_emotion_result['emotions'].items(), 
                key=lambda item: item[1], 
                reverse=True
            )

            # Display all emotions with bars
            for emotion, score in sorted_emotions:
                # Emotion Bar
                bar_length = int(score * 200)  # Scale to fit on screen 
                color = (0, 255, 0) if emotion == current_emotion_result['dominant_emotion'] else (100, 100, 100)

                cv2.rectangle(frame, (10, y_offset), (10 + bar_length, y_offset + 15), color, -1)
                cv2.putText(
                    frame,
                    f"{emotion} ({score*100:.1f}%)", 
                    (15 + bar_length, y_offset + 12),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    (255, 255, 255),
                    1
                )
                y_offset += 25
        

        cv2.imshow('Face Detection Feed', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    
    print("Camera released and all windows closed.")

if __name__ == "__main__":
    test_camera()


def run_camera_headless(stop_event=None):
    """Run the same detection loop as test_camera but without any GUI calls.

    This is safe to run in a background thread (no cv2.imshow / waitKey).
    stop_event should be a threading.Event or any object with is_set() method.
    """
    import threading

    if stop_event is None:
        stop_event = threading.Event()

    # Initialize Emotion Detection Service
    try:
        emotion_service = EmotionService()
    except Exception as e:
        print(f"Error initializing Emotion Detection Service in headless runner: {e}")
        return

    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )

    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Headless runner: Could not open camera.")
        return

    print("Headless runner: Camera opened successfully.")

    emotion_timeline = []
    last_emotion_time = time.time()
    current_emotion_result = None

    try:
        while not stop_event.is_set():
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue

            frame = cv2.flip(frame, 1)

            current_time = time.time()

            faces = face_cascade.detectMultiScale(
                frame,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=(30, 30)
            )

            if current_time - last_emotion_time >= 1.0:
                try:
                    emotion_result = emotion_service.analyze_frame(frame)
                except Exception as e:
                    print(f"Error analyzing frame in headless runner: {e}")
                    emotion_result = None

                if emotion_result:
                    emotion_timeline.append(emotion_result)
                    current_emotion_result = emotion_result
                    if emotion_result.get('face_detected'):
                        print(f"Emotion Detected: {emotion_result['dominant_emotion']} (Confidence: {emotion_result['confidence']:.2f})")

                last_emotion_time = current_time

            # small sleep to yield
            time.sleep(0.01)

    finally:
        cap.release()
        print("Headless runner: Camera released and headless loop stopped.")