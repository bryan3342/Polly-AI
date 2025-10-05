import React, { createContext, useContext, useState, useEffect, useRef } from 'react';

const WebSocketContext = createContext(null);

// Configuration matching your FastAPI backend
const WS_URL = 'ws://localhost:8000/ws/user-' + Math.random().toString(36).substring(2, 9);
const FRAME_INTERVAL_MS = 1000; // Matches your backend's FRAME_PROCESS_INTERVAL (1.0 sec)

export const WebSocketProvider = ({ children }) => {
    const [isConnected, setIsConnected] = useState(false);
    const [emotionData, setEmotionData] = useState(null);
    const [chatHistory, setChatHistory] = useState([]);
    const [error, setError] = useState(null);
    const wsRef = useRef(null);

    // --- WebSocket Connection Management ---
    useEffect(() => {
        wsRef.current = new WebSocket(WS_URL);

        wsRef.current.onopen = () => {
            setIsConnected(true);
            setError(null);
            console.log('WebSocket Connected:', WS_URL);
            // Add initial welcome message
            setChatHistory([{ role: 'system', content: 'Connected to Polly AI. Send a chat message to begin coaching.' }]);
        };

        wsRef.current.onmessage = (event) => {
            const message = JSON.parse(event.data);
            
            // Handle incoming messages based on type
            switch (message.type) {
                case 'emotion_update':
                    setEmotionData(message.data);
                    break;
                
                case 'transcription_complete':
                    const transcriptMessage = { 
                        role: 'user', 
                        content: message.transcript, 
                        timestamp: message.timestamp 
                    };
                    setChatHistory(prev => {
                        // Remove the "[Processing audio...]" message and add the transcript
                        const filtered = prev.filter(msg => msg.content !== '[Processing audio...]');
                        return [...filtered, transcriptMessage];
                    });
                    break;

                case 'gpt_response':
                case 'chat_response':  // ADD THIS LINE
                    const gptMessage = { role: 'polly', content: message.message, timestamp: message.timestamp };
                    setChatHistory(prev => [...prev, gptMessage]);
                    break;
                case 'error':
                    console.error("WS Error:", message.message);
                    setError(message.message);
                    break;
                case 'session_ended':
                    console.log('Session Ended:', message.summary);
                    setChatHistory(prev => [...prev, { role: 'system', content: `Session ended. Summary received: ${JSON.stringify(message.summary.emotion_summary.dominant)}` }]);
                    break;
                default:
                    // console.log('Unhandled message type:', message.type);
            }
        };

        wsRef.current.onclose = (event) => {
            setIsConnected(false);
            console.log('WebSocket Disconnected:', event.code, event.reason);
            if (!event.wasClean) {
                setError('Connection lost unexpectedly. Check backend server.');
            }
        };

        wsRef.current.onerror = (err) => {
            console.error('WebSocket Error:', err);
            setError('WebSocket connection error.');
            wsRef.current.close();
        };

        // Clean up function runs when component unmounts
        return () => {
            if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.close(1000, "Component Unmounted");
            }
        };
    }, []);

    // --- Send Logic ---
    const sendMessage = (message) => {
        if (wsRef.current && isConnected) {
            wsRef.current.send(JSON.stringify(message));
            return true;
        }
        console.error("Cannot send message: WebSocket not open.");
        return false;
    };

    // --- Context Value ---
    const contextValue = {
        isConnected,
        emotionData,
        chatHistory,
        error,
        sendMessage, // <--- Used by Camera.jsx
        FRAME_INTERVAL_MS, // <--- Used by Camera.jsx
        setChatHistory
    };

    return (
        <WebSocketContext.Provider value={contextValue}>
            {children}
        </WebSocketContext.Provider>
    );
};

export const useWebSocket = () => useContext(WebSocketContext);
