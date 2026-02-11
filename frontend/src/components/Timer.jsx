import { useState, useEffect } from 'react';

const INITIAL_TIME_SECONDS = 120;

const Timer = ({ isRunning, onTimerEnd, onResetSignal }) => {
    const [secondsRemaining, setSecondsRemaining] = useState(INITIAL_TIME_SECONDS);

    useEffect(() => {
        if (!isRunning || secondsRemaining === 0) {
            if (secondsRemaining === 0 && onTimerEnd) {
                onTimerEnd();
            }
            return;
        }

        const interval = setInterval(() => {
            setSecondsRemaining(prevTime => prevTime - 1);
        }, 1000);

        return () => clearInterval(interval);
    }, [isRunning, secondsRemaining, onTimerEnd]);

    useEffect(() => {
        if (onResetSignal) {
            setSecondsRemaining(INITIAL_TIME_SECONDS);
        }
    }, [onResetSignal]);

    const formatTime = (totalSeconds) => {
        const timeToDisplay = Math.max(0, totalSeconds);
        const minutes = Math.floor(timeToDisplay / 60);
        const seconds = timeToDisplay % 60;
        const formattedSeconds = seconds.toString().padStart(2, '0');
        return `${minutes}:${formattedSeconds}`;
    };

    const timerColor = secondsRemaining <= 10 && secondsRemaining > 0 ? 'text-red-500' : 'text-white';

    return (
        <div className="timer-display flex justify-center">
            <div className="bg-white/25 flex items-center justify-center"
                 style={{ width: '140px', height: '64px', borderRadius: '18px' }}>
                <div
                    className={`${timerColor} text-xl font-bold`}
                    style={{ fontFamily: 'Tektur, monospace', textShadow: '0 4px 8px rgba(0,0,0,0.3), 0 2px 4px rgba(0,0,0,0.2)' }}
                >
                    {formatTime(secondsRemaining)}
                </div>
            </div>
        </div>
    );
};

export default Timer;
