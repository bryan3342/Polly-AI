import { useState, useRef, useEffect } from 'react';
import { useWS } from '../context/WebSocketContext';
import { FiSend, FiRefreshCw } from 'react-icons/fi';

export default function Chatbox() {
    const { chat, sendChat, connected, topic, processing, newTopic } = useWS();
    const [input, setInput] = useState('');
    const endRef = useRef(null);

    useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [chat]);

    const send = () => {
        const t = input.trim();
        if (!t || !connected) return;
        sendChat(t);
        setInput('');
    };

    return (
        <div className="chat-panel">

            {/* ── topic header ───────────────── */}
            <div className="topic-bar">
                {topic ? (
                    <div style={{ minWidth: 0 }}>
                        <div className="label">Debate Topic</div>
                        <div className="text">{topic.topic}</div>
                        <div className="topic-tags">
                            <span className="topic-tag cat">{topic.category}</span>
                            <span className="topic-tag diff">{topic.difficulty}</span>
                        </div>
                    </div>
                ) : (
                    <div>
                        <div className="label">Debate Topic</div>
                        <div className="text" style={{ color: '#4b5563' }}>Waiting for connection...</div>
                    </div>
                )}
                <button className="topic-refresh" onClick={newTopic} disabled={!connected} title="New topic">
                    <FiRefreshCw size={14} />
                </button>
            </div>

            {/* ── messages ───────────────────── */}
            <div className="messages">
                {chat.length === 0 && (
                    <div className="messages-empty">
                        {connected ? 'Start a recording or ask Polly a question.' : 'Connecting to server...'}
                    </div>
                )}

                {chat.map((m, i) => {
                    if (m.role === 'system')    return <div key={i} className="msg-system">{m.content}</div>;
                    if (m.role === 'user')      return <div key={i} className="msg-bubble user">{m.content}</div>;
                    return (
                        <div key={i} className="msg-bubble assistant">
                            <div className="sender">Polly AI</div>
                            {m.content}
                        </div>
                    );
                })}

                {processing && (
                    <div className="typing-dots">
                        <span /><span /><span />
                    </div>
                )}

                <div ref={endRef} />
            </div>

            {/* ── input ──────────────────────── */}
            <div className="chat-input-bar">
                <div className="chat-input-wrap">
                    <input
                        value={input}
                        onChange={e => setInput(e.target.value)}
                        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
                        placeholder={connected ? 'Ask Polly for coaching...' : 'Connecting...'}
                        disabled={!connected}
                    />
                    <button className="send-btn" onClick={send} disabled={!connected || !input.trim()}>
                        <FiSend size={14} />
                    </button>
                </div>
            </div>
        </div>
    );
}
