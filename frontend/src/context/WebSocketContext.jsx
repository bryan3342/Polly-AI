import { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';

const WebSocketContext = createContext(null);

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';
const SESSION_ID = 'user-' + Math.random().toString(36).substring(2, 9);
const WS_URL = `${WS_BASE_URL}/ws/${SESSION_ID}`;
const FRAME_INTERVAL_MS = 1000;
const RECONNECT_DELAY_MS = 3000;

export const WebSocketProvider = ({ children }) => {
    const [isConnected, setIsConnected] = useState(false);
    const [emotionData, setEmotionData] = useState(null);
    const [chatHistory, setChatHistory] = useState([]);
    const [currentTopic, setCurrentTopic] = useState(null);
    const [error, setError] = useState(null);
    const wsRef = useRef(null);
    const reconnectTimerRef = useRef(null);

    const connect = useCallback(() => {
        if (wsRef.current?.readyState === WebSocket.OPEN) return;

        try {
            wsRef.current = new WebSocket(WS_URL);
        } catch {
            setError('Backend server not available. Start the backend with: uvicorn app.main:app --reload');
            return;
        }

        wsRef.current.onopen = () => {
            setIsConnected(true);
            setError(null);
            setChatHistory([{ role: 'system', content: 'Connected to Polly AI. Ready to coach!' }]);
        };

        wsRef.current.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);

                switch (message.type) {
                    case 'emotion_update':
                        setEmotionData(message.data);
                        break;
                    case 'chat_response':
                        setChatHistory(prev => [...prev, {
                            role: 'polly',
                            content: message.message,
                            timestamp: message.timestamp
                        }]);
                        break;
                    case 'topic_assigned':
                        setCurrentTopic(message.topic);
                        setChatHistory(prev => [...prev, {
                            role: 'system',
                            content: `Debate topic: "${message.topic.topic}" (${message.topic.category} - ${message.topic.difficulty})`
                        }]);
                        break;
                    case 'analysis_complete':
                        setChatHistory(prev => [...prev, {
                            role: 'system',
                            content: `Analysis complete! Score: ${message.results?.feedback || 'See results'}`
                        }]);
                        break;
                    case 'error':
                        setError(message.message);
                        break;
                    case 'session_ended':
                        setChatHistory(prev => [...prev, {
                            role: 'system',
                            content: 'Session ended.'
                        }]);
                        break;
                }
            } catch {
                // Ignore malformed messages
            }
        };

        wsRef.current.onclose = (event) => {
            setIsConnected(false);
            if (!event.wasClean) {
                setError('Connection lost. Reconnecting...');
                reconnectTimerRef.current = setTimeout(connect, RECONNECT_DELAY_MS);
            }
        };

        wsRef.current.onerror = () => {
            setError('Cannot connect to backend. Make sure the server is running.');
            wsRef.current?.close();
        };
    }, []);

    useEffect(() => {
        connect();

        return () => {
            clearTimeout(reconnectTimerRef.current);
            if (wsRef.current?.readyState === WebSocket.OPEN) {
                wsRef.current.close(1000, 'Component unmounted');
            }
        };
    }, [connect]);

    const sendMessage = useCallback((message) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(message));
            return true;
        }
        return false;
    }, []);

    const contextValue = {
        isConnected,
        emotionData,
        chatHistory,
        currentTopic,
        error,
        sendMessage,
        setChatHistory,
        FRAME_INTERVAL_MS,
    };

    return (
        <WebSocketContext.Provider value={contextValue}>
            {children}
        </WebSocketContext.Provider>
    );
};

export const useWebSocket = () => useContext(WebSocketContext);
