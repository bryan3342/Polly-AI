import { useState, useRef, useEffect } from 'react';
import { useWebSocket } from '../context/WebSocketContext';

const Chatbox = () => {
    const { chatHistory, sendMessage, isConnected, currentTopic } = useWebSocket();
    const [input, setInput] = useState('');
    const messagesEndRef = useRef(null);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [chatHistory]);

    const handleSend = () => {
        const text = input.trim();
        if (!text || !isConnected) return;

        sendMessage({ type: 'chat', message: text });
        setInput('');
    };

    const handleKeyDown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    return (
        <div className="w-full lg:w-[420px] flex flex-col bg-gray-900/50 border-2 border-gray-700 rounded-lg overflow-hidden"
             style={{ height: 'calc(56.25vw - 2rem)', maxHeight: '600px', minHeight: '400px' }}>
            {currentTopic && (
                <div className="bg-[#5E7BCF]/20 border-b border-gray-700 px-4 py-3">
                    <p className="text-xs text-gray-400 uppercase tracking-wide">Topic</p>
                    <p className="text-white text-sm mt-1">{currentTopic.topic}</p>
                    <span className="text-xs text-gray-500">{currentTopic.category} &middot; {currentTopic.difficulty}</span>
                </div>
            )}

            <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {chatHistory.length === 0 && (
                    <p className="text-gray-500 text-sm text-center pt-8">
                        {isConnected ? 'Send a message to start coaching...' : 'Waiting for connection...'}
                    </p>
                )}
                {chatHistory.map((msg, i) => (
                    <div key={i} className={`text-sm ${
                        msg.role === 'system' ? 'text-gray-400 italic text-center text-xs' :
                        msg.role === 'polly' ? 'text-blue-300' : 'text-white'
                    }`}>
                        {msg.role === 'polly' && <span className="text-blue-400 font-semibold">Polly: </span>}
                        {msg.content}
                    </div>
                ))}
                <div ref={messagesEndRef} />
            </div>

            <div className="border-t border-gray-700 p-3 flex gap-2">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={isConnected ? "Ask Polly for feedback..." : "Connecting..."}
                    disabled={!isConnected}
                    className="flex-1 bg-gray-800 text-white text-sm px-3 py-2 rounded-lg border border-gray-600 focus:border-[#5E7BCF] focus:outline-none disabled:opacity-50"
                />
                <button
                    onClick={handleSend}
                    disabled={!isConnected || !input.trim()}
                    className="bg-[#5E7BCF] text-white text-sm px-4 py-2 rounded-lg hover:bg-[#4a68b8] transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    Send
                </button>
            </div>
        </div>
    );
};

export default Chatbox;
