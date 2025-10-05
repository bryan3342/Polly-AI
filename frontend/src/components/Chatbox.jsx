import React, { useState, useRef, useEffect } from 'react';
import { useWebSocket } from '../context/WebSocketContext';
import ReactMarkdown from 'react-markdown';

const Chatbox = () => {
    const [message, setMessage] = useState('');
    const [isRecording, setIsRecording] = useState(false);
    const messagesEndRef = useRef(null);
    const mediaRecorderRef = useRef(null);
    const audioChunksRef = useRef([]);

    // Get WebSocket context
    const { isConnected, chatHistory, error, sendMessage, setChatHistory } = useWebSocket();

    // Auto-scroll to bottom when new messages arrive
    useEffect(() => {
        scrollToBottom();
    }, [chatHistory]);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    };

    // Send text message
    const handleSendMessage = () => {
    if (message.trim() && isConnected) {
        // Add user message to chat history
        const userMessage = { role: 'user', content: message, timestamp: new Date().toISOString() };
        setChatHistory(prev => [...prev, userMessage]);
        
        // Send message to backend via WebSocket
        sendMessage({
            type: 'chat',
            message: message
        });
        
        setMessage('');
    } else if (!isConnected) {
        console.error("Cannot send message: Not connected to WebSocket");
    }
};

    // Handle Enter key press
    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    // Audio recording functions
    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorderRef.current = new MediaRecorder(stream);
            audioChunksRef.current = [];

            mediaRecorderRef.current.ondataavailable = (event) => {
                audioChunksRef.current.push(event.data);
            };

            mediaRecorderRef.current.onstop = async () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                
                // Convert blob to base64
                const reader = new FileReader();
                reader.readAsDataURL(audioBlob);
                reader.onloadend = () => {
                    const base64Audio = reader.result;
                    
                    // Send audio to backend for transcription
                    if (isConnected) {
                        sendMessage({
                            type: 'transcribe_audio',
                            data: base64Audio
                        });
                        
                        setChatHistory(prev => [...prev, { 
                            role: 'user', 
                            content: '[Processing audio...]', 
                            timestamp: new Date().toISOString() 
                        }]);
                    }
                };
                
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorderRef.current.start();
            setIsRecording(true);

        } catch (error) {
            console.error('Error accessing microphone:', error);
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
        }
    };

    // Message component
    const Message = ({ msg }) => {
        const isUser = msg.role === 'user';
        const isSystem = msg.role === 'system';
        const isPolly = msg.role === 'polly';

        return (
            <div className={`mb-4 ${isUser ? 'text-right' : 'text-left'}`}>
                <div className={`inline-block max-w-[80%] p-3 rounded-lg ${
                    isUser 
                        ? 'bg-blue-600 text-white rounded-br-none' 
                        : isSystem 
                        ? 'bg-gray-600 text-gray-200 rounded-bl-none' 
                        : 'bg-purple-600 text-white rounded-bl-none'
                }`} style={{
                    backgroundColor: isUser ? '#2563EB' : isSystem ? '#4B5563' : '#7C3AED',
                    color: 'white',
                    padding: '12px',
                    borderRadius: '8px',
                    maxWidth: '80%',
                    wordBreak: 'break-word'
                }}>
                    {!isUser && (
                        <div style={{fontSize: '10px', opacity: 0.75, marginBottom: '4px'}}>
                            {isSystem ? 'System' : isPolly ? 'Polly AI' : 'Assistant'}
                        </div>
                    )}
                    <div style={{fontSize: '14px', lineHeight: '1.4'}}>
                        <ReactMarkdown
                            components={{
                                strong: ({node, ...props}) => <strong style={{fontWeight: 'bold'}} {...props} />,
                                em: ({node, ...props}) => <em style={{fontStyle: 'italic'}} {...props} />,
                                h1: ({node, ...props}) => <h1 style={{fontSize: '1.5em', fontWeight: 'bold', marginTop: '0.5em', marginBottom: '0.5em'}} {...props} />,
                                h2: ({node, ...props}) => <h2 style={{fontSize: '1.3em', fontWeight: 'bold', marginTop: '0.4em', marginBottom: '0.4em'}} {...props} />,
                                h3: ({node, ...props}) => <h3 style={{fontSize: '1.1em', fontWeight: 'bold', marginTop: '0.3em', marginBottom: '0.3em'}} {...props} />,
                                ul: ({node, ...props}) => <ul style={{marginLeft: '1.5em', marginTop: '0.5em', marginBottom: '0.5em'}} {...props} />,
                                ol: ({node, ...props}) => <ol style={{marginLeft: '1.5em', marginTop: '0.5em', marginBottom: '0.5em'}} {...props} />,
                                li: ({node, ...props}) => <li style={{marginBottom: '0.25em'}} {...props} />,
                                p: ({node, ...props}) => <p style={{marginBottom: '0.5em'}} {...props} />,
                            }}
                        >
                            {msg.content}
                        </ReactMarkdown>
                    </div>
                    {msg.timestamp && (
                        <div style={{fontSize: '10px', opacity: 0.5, marginTop: '4px'}}>
                            {new Date(msg.timestamp).toLocaleTimeString()}
                        </div>
                    )}
                </div>
            </div>
        );
    };

    return (
        <div style={{
            width: '419px',
            height: '716px',
            backgroundColor: '#1f2937',
            border: '3px solid #374151',
            borderRadius: '8px',
            display: 'flex',
            flexDirection: 'column'
        }}>
            {/* Header */}
            <div style={{
                backgroundColor: '#111827',
                padding: '16px',
                borderRadius: '8px 8px 0 0',
                borderBottom: '1px solid #374151'
            }}>
                <h3 style={{color: 'white', fontSize: '18px', fontWeight: 'bold', margin: 0}}>Polly AI</h3>
                <div style={{display: 'flex', alignItems: 'center', marginTop: '4px'}}>
                    <div style={{
                        width: '8px',
                        height: '8px',
                        backgroundColor: isConnected ? '#10B981' : '#EF4444',
                        borderRadius: '50%',
                        marginRight: '8px'
                    }}></div>
                    <span style={{color: '#9CA3AF', fontSize: '12px'}}>
                        {isConnected ? 'Connected' : 'Disconnected (Demo Mode)'}
                    </span>
                </div>
                {error && (
                    <div style={{color: '#F87171', fontSize: '12px', marginTop: '4px'}}>
                        Error: {error}
                    </div>
                )}
            </div>

            {/* Messages Area */}
            <div style={{
                flex: 1,
                padding: '16px',
                overflowY: 'auto',
                backgroundColor: '#1f2937'
            }}>
                {chatHistory && chatHistory.length > 0 ? (
                    chatHistory.map((msg, index) => (
                        <Message key={index} msg={msg} />
                    ))
                ) : (
                    <div style={{color: '#6B7280', textAlign: 'center', fontSize: '14px', marginTop: '32px'}}>
                        No messages yet. Start a conversation with Polly AI!
                    </div>
                )}
                <div ref={messagesEndRef} />
            </div>

            {/* Input Area */}
            <div style={{
                padding: '16px',
                borderTop: '1px solid #374151',
                backgroundColor: '#111827',
                borderRadius: '0 0 8px 8px'
            }}>
                <div style={{display: 'flex', gap: '8px'}}>
                    <input
                        type="text"
                        value={message}
                        onChange={(e) => setMessage(e.target.value)}
                        onKeyPress={handleKeyPress}
                        placeholder="Type your message..."
                        style={{
                            flex: 1,
                            backgroundColor: '#374151',
                            color: 'white',
                            padding: '8px 12px',
                            borderRadius: '6px',
                            border: '1px solid #4B5563',
                            outline: 'none',
                            fontSize: '14px'
                        }}
                    />
                    <button
                        onClick={handleSendMessage}
                        disabled={!message.trim()}
                        style={{
                            backgroundColor: message.trim() ? '#7C3AED' : '#4B5563',
                            color: 'white',
                            padding: '8px 16px',
                            borderRadius: '6px',
                            border: 'none',
                            cursor: message.trim() ? 'pointer' : 'not-allowed',
                            fontSize: '14px',
                            fontWeight: 'bold',
                            opacity: message.trim() ? 1 : 0.5
                        }}
                    >
                        Send
                    </button>
                </div>
                
                {/* Audio Recording Button */}
                <div style={{marginTop: '12px', display: 'flex', justifyContent: 'center'}}>
                    <button
                        onMouseDown={startRecording}
                        onMouseUp={stopRecording}
                        onMouseLeave={stopRecording}
                        style={{
                            backgroundColor: isRecording ? '#EF4444' : '#4B5563',
                            color: 'white',
                            padding: '8px 16px',
                            borderRadius: '20px',
                            border: 'none',
                            cursor: 'pointer',
                            fontSize: '12px',
                            fontWeight: 'bold',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px'
                        }}
                    >
                        <span>🎤</span>
                        <span>{isRecording ? 'Recording...' : 'Hold to Record'}</span>
                    </button>
                </div>
                
                <div style={{color: '#6B7280', textAlign: 'center', marginTop: '8px', fontSize: '11px'}}>
                    Press Enter to send • Hold microphone to record voice message
                </div>
            </div>
        </div>
    );
};

export default Chatbox;

