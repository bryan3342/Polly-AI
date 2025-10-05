import React, { useRef, useEffect } from 'react';
import { useWebSocket } from '../context/WebSocketContext';

const Camera = () => {
    // Access the WebSocket context, which includes the sendMessage function and frame interval
    const { sendMessage, FRAME_INTERVAL_MS } = useWebSocket();
    
    // Refs for the video element and a canvas element (used for capturing frames)
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const frameTimerRef = useRef(null);

    // Function to start the camera stream
    const startCamera = async () => {
        try {
            // Request access to the user's media devices (webcam)
            const stream = await navigator.mediaDevices.getUserMedia({ video: true });
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
        } catch (err) {
            console.error("Error accessing the camera: ", err);
        }
    };

    // Function to capture the current frame, convert it to base64, and send it
    const sendFrame = () => {
        const video = videoRef.current;
        const canvas = canvasRef.current;
        
        if (video && canvas && video.readyState === video.HAVE_ENOUGH_DATA) {
            const context = canvas.getContext('2d');
            
            // Set canvas size to video size
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;

            // Draw the current video frame onto the canvas
            context.drawImage(video, 0, 0, canvas.width, canvas.height);

            // Convert the canvas image to a base64 string
            const base64Data = canvas.toDataURL('image/jpeg', 0.8); // 80% quality JPEG

            // Prepare and send the message to the WebSocket backend
            const message = {
                type: 'frame',
                data: base64Data,
                timestamp: Date.now() / 1000 // UNIX timestamp
            };
            
            sendMessage(message);
        }
    };

    // useEffect hook to initialize the camera and set up the frame sending interval
    useEffect(() => {
        startCamera();

        // Start the frame sending interval
        frameTimerRef.current = setInterval(() => {
            sendFrame();
        }, FRAME_INTERVAL_MS); // FRAME_INTERVAL_MS is 1000ms (1.0 sec)

        // Cleanup function: stop the stream and clear the interval when the component unmounts
        return () => {
            clearInterval(frameTimerRef.current);
            if (videoRef.current && videoRef.current.srcObject) {
                const tracks = videoRef.current.srcObject.getTracks();
                tracks.forEach(track => track.stop());
            }
        };
    }, [FRAME_INTERVAL_MS, sendMessage]);


    return (
        <div className="w-[899px] h-[816px] bg-transparent border-[3px] border-gray-700 relative overflow-hidden">
            {/* The video element displays the live feed */}
            <video 
                ref={videoRef} 
                autoPlay 
                playsInline 
                muted 
                className="w-full h-full object-cover" 
            />
            {/* The canvas is used internally to capture frames but is hidden from view */}
            <canvas ref={canvasRef} style={{ display: 'none' }} />
        </div>
    );
}

export default Camera;