import { FaCircle, FaStop, FaVideo, FaVideoSlash, FaMicrophone, FaMicrophoneSlash } from 'react-icons/fa';
import { useWS } from '../context/WebSocketContext';

export default function Toolbar({ isRecording, cameraOn, muted, time, onRecord, onStop, onCam, onMic }) {
    const { connected } = useWS();

    const fmt = (s) => `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`;

    return (
        <div className="toolbar">
            <div className="toolbar-inner">

                {/* record */}
                <button className="toolbar-btn" onClick={onRecord} disabled={isRecording || !connected} title="Record">
                    <FaCircle size={10} style={{ color: isRecording ? '#f8717180' : '#ef4444' }} />
                    <span>Record</span>
                </button>

                {/* stop */}
                <button className="toolbar-btn" onClick={onStop} disabled={!isRecording} title="Stop">
                    <FaStop size={10} />
                    <span>Stop</span>
                </button>

                <div className="toolbar-divider" />

                {/* timer */}
                <div className="toolbar-timer">
                    {isRecording && <div className="rec-dot" />}
                    <span className={`time ${isRecording ? 'live' : ''}`}>{fmt(time)}</span>
                </div>

                <div className="toolbar-divider" />

                {/* camera */}
                <button className={`toolbar-btn ${!cameraOn ? 'active' : ''}`} onClick={onCam} title={cameraOn ? 'Turn off camera' : 'Turn on camera'}>
                    {cameraOn ? <FaVideo size={13} /> : <FaVideoSlash size={13} />}
                </button>

                {/* mic */}
                <button className={`toolbar-btn ${muted ? 'active' : ''}`} onClick={onMic} title={muted ? 'Unmute' : 'Mute'}>
                    {muted ? <FaMicrophoneSlash size={13} /> : <FaMicrophone size={13} />}
                </button>
            </div>
        </div>
    );
}
