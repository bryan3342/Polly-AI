import { useState, useEffect } from 'react';

const Timer = () => {
    const [seconds, setSeconds] = useState(0);
    const [minutes, setMinutes] = useState(0);
    const [isRunning, setIsRunning] = useState(false);

    useEffect(() => {
        let interval = null;
        if (isRunning) {
            interval = setInterval(() => {
                setSeconds(prevSeconds => {
                    if (prevSeconds === 59) {
                        setMinutes(prevMinutes => prevMinutes + 1);
                        return 0;
                    }
                    return prevSeconds + 1;
                });
            }, 1000);
        } else {
            clearInterval(interval);
        }
        return () => clearInterval(interval);
    }, [isRunning]);

    const startTimer = () => setIsRunning(true);
    const stopTimer = () => setIsRunning(false);
    const resetTimer = () => {
        setIsRunning(false);
        setSeconds(0);
        setMinutes(0);
    };
    
    const formatTime = (time) => time.toString().padStart(2, '0');

    return (
        <div className="timer-container">
            <div className="timer-display flex justify-center">
                <div className="bg-white/25 flex items-center justify-center" style={{width: '120px', height: '73px', borderRadius: '25px'}}>
                    <div className="text-3xl font-bold text-white">
                        {formatTime(minutes)}:{formatTime(seconds)}
                    </div>
                </div>
            </div>
            <div className="text-white">
                <button onClick={startTimer} disabled={isRunning}>
                    Start
                </button>
                <button onClick={stopTimer} disabled={!isRunning}>
                    Stop
                </button>
                <button onClick={resetTimer}>
                    Reset
                </button>
            </div>
        </div>
    );
};

export default Timer;