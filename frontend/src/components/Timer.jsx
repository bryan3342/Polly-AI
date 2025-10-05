import { useState, useEffect } from 'react';
<<<<<<< HEAD
import '@fontsource/tektur';

const INITIAL_TIME_SECONDS = 120;

// Component now accepts control props from its parent
const CountdownTimer = ({ isRunning, onTimerEnd, onResetSignal }) => {
    
    // State stores the total number of seconds remaining
    const [secondsRemaining, setSecondsRemaining] = useState(INITIAL_TIME_SECONDS);

    // --- EFFECT: Handles the Countdown Logic ---
    useEffect(() => {
        //  Stop if timer is paused or has reached zero
        if (!isRunning || secondsRemaining === 0) {
            if (secondsRemaining === 0 && onTimerEnd) {
                // Notifies the parent component when time is up
                // onTimerEnd(); // Uncomment when you implement this handler
            }
            return;
        }

        // Set up the interval to decrement time
        const interval = setInterval(() => {
            setSecondsRemaining(prevTime => prevTime - 1);
        }, 1000);

        // Cleanup: Clear the interval
        return () => clearInterval(interval);

    }, [isRunning, secondsRemaining, onTimerEnd]);


    // --- EFFECT: Handles External Reset Signal ---
    // If the parent component needs to force a reset
    useEffect(() => {
        if (onResetSignal) {
            setSecondsRemaining(INITIAL_TIME_SECONDS);
        }
    }, [onResetSignal]);


    // --- FORMATTING LOGIC ---
    const formatTime = (totalSeconds) => {
        // Ensure time doesn't display negative values
        const timeToDisplay = Math.max(0, totalSeconds); 
        
        const minutes = Math.floor(timeToDisplay / 60);
        const seconds = timeToDisplay % 60;
        
        // Pad seconds with '0' (e.g., 5:09)
        const formattedSeconds = seconds.toString().padStart(2, '0');
        
        return `${minutes}:${formattedSeconds}`;
    };

    // Style logic: text color changes when time is low
    const timerColor = secondsRemaining <= 10 && secondsRemaining > 0 ? 'text-red-500' : 'text-white';
    
    // ----------------------------------------------------------------------
    // --- JSX Display (Styled to Match Mockup) ---
    // ----------------------------------------------------------------------
    
    return (
        <div className="timer-display flex justify-center">
            {/* The display div now uses the visual style */}
            <div className="bg-white/25 flex items-center justify-center"
                 style={{ width: '140px', height: '64px', borderRadius: '18px' }}>

                {/* Time text using Tektur font with requested shadow; preserve low-time color */}
                <div
                    className={`${timerColor} text-xl font-bold`}
                    style={{ fontFamily: 'Tektur, monospace', textShadow: '0 4px 8px rgba(0,0,0,0.3), 0 2px 4px rgba(0,0,0,0.2)' }}
                >
                    {formatTime(secondsRemaining)}
                </div>
            </div>
=======

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
>>>>>>> bb23d5235afa54507dbb3480bfb6baa723475251
        </div>
    );
};

<<<<<<< HEAD
export default CountdownTimer;
=======
export default Timer;
>>>>>>> bb23d5235afa54507dbb3480bfb6baa723475251
