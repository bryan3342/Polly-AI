import cv2
import sys

def test_camera():
    print("Testing Camera Access...")
    print("Press 'q' to quit the camera feed.")


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
    print(f" Resolution: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
    print(f" FPS: {cap.get(cv2.CAP_PROP_FPS)}\n")

    frame_count = 0
    face_detected_count = 0

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
    
        frame_count += 1

        

        faces = face_cascade.detectMultiScale(
            frame, 
            scaleFactor=1.1, 
            minNeighbors=5,
            minSize=(30, 30)    
        )

        # Draw rectangles around detected faces
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (255, 0, 0), 2)
            cv2.putText(
                frame, 
                "Face Detected", 
                (x, y-10), 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, 
                (0, 255, 0), 
                2
            )

        if len(faces) > 0:
            face_detected_count += 1

        # Display detection stats on the frame
        status_text = f"Faces: {len(faces)} | Frame Detections: {frame_count}"
        cv2.putText(
            frame, 
            status_text, 
            (10, 30), 
            cv2.FONT_HERSHEY_SIMPLEX, 
            0.7, 
            (255, 0, 0), 
            2
        )

        cv2.imshow('Face Detection Feed', frame)


        # Print stats every 30 frames
        if frame_count % 30 == 0:
            print(f"Captured {frame_count} frames.")
            detection_rate = (face_detected_count / frame_count) * 100
            print(f"Face Detection Rate: {detection_rate:.2f}%")

        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


    cap.release()
    cv2.destroyAllWindows()
    print("Camera released and all windows closed.")

if __name__ == "__main__":
    test_camera()