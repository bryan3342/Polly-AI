import { useRef, useEffect, useState } from 'react';
import { useWebSocket } from '../context/WebSocketContext';

const Camera = () => {
    const { sendMessage, FRAME_INTERVAL_MS, emotionData, isConnected } = useWebSocket();
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const frameTimerRef = useRef(null);
    const [cameraError, setCameraError] = useState(null);

    useEffect(() => {
        let stream = null;

        const startCamera = async () => {
            try {
                stream = await navigator.mediaDevices.getUserMedia({ video: true });
                if (videoRef.current) {
                    videoRef.current.srcObject = stream;
                }
                setCameraError(null);
            } catch {
                setCameraError('Camera access denied. Please allow camera permissions.');
            }
        };

        startCamera();

        frameTimerRef.current = setInterval(() => {
            const video = videoRef.current;
            const canvas = canvasRef.current;

            if (video && canvas && video.readyState === video.HAVE_ENOUGH_DATA && isConnected) {
                const context = canvas.getContext('2d');
                canvas.width = video.videoWidth;
                canvas.height = video.videoHeight;
                context.drawImage(video, 0, 0, canvas.width, canvas.height);

                const base64Data = canvas.toDataURL('image/jpeg', 0.7);
                sendMessage({
                    type: 'frame',
                    data: base64Data,
                    timestamp: Date.now() / 1000
                });
            }
        }, FRAME_INTERVAL_MS);

        return () => {
            clearInterval(frameTimerRef.current);
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
        };
    }, [FRAME_INTERVAL_MS, sendMessage, isConnected]);

    const dominant = emotionData?.dominant_emotion;
    const confidence = emotionData?.confidence;

    return (
        <div className="flex-1 max-w-4xl w-full">
            <div className="relative aspect-video bg-gray-900 border-2 border-gray-700 rounded-lg overflow-hidden">
                {cameraError ? (
                    <div className="absolute inset-0 flex items-center justify-center text-gray-400 text-sm p-4 text-center">
                        {cameraError}
                    </div>
                ) : (
                    <video
                        ref={videoRef}
                        autoPlay
                        playsInline
                        muted
                        className="w-full h-full object-cover"
                    />
                )}
                <canvas ref={canvasRef} style={{ display: 'none' }} />

                {dominant && (
                    <div className="absolute bottom-3 left-3 bg-black/60 text-white px-3 py-1.5 rounded-lg text-sm">
                        {dominant} {confidence ? `(${(confidence * 100).toFixed(0)}%)` : ''}
                    </div>
                )}

                <div className={`absolute top-3 right-3 w-3 h-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}
                     title={isConnected ? 'Connected' : 'Disconnected'} />
            </div>
        </div>
    );
};

export default Camera;
