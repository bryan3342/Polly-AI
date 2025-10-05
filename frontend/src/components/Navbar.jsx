import Timer from "./Timer";
import { FaPlay } from "react-icons/fa6";
import { FaPause } from "react-icons/fa6";
import { MdPersonOff } from "react-icons/md";

import React, { useState } from "react";

<<<<<<< HEAD
const NavbarTwo = () => {
    const [isTimerRunning, setIsTimerRunning] = useState(false);

    const toggleRunning = () => {
        setIsTimerRunning((prev) => !prev);
    };

    const IconComponent = isTimerRunning ? FaPause : FaPlay;

    const transparentLightBlue = "rgba(136, 167, 255, 0.45)";
=======
// import React from 'react';
// import './Navbar.css';
// Import your CSS file where you define the styles below
// import '../styles/Navbar.css'; 
>>>>>>> bb23d5235afa54507dbb3480bfb6baa723475251

    return (
<<<<<<< HEAD
        <>
                    <div
                        className="fixed bottom-4 left-1/2 transform -translate-x-1/2 flex items-center justify-between text-white rounded-full shadow-xl px-4 z-50"
style={{ width: "550px", height: "79px", backgroundColor: transparentLightBlue }}
            >
                {/* Left: Play/Pause + Camera Off */}
                <div className="flex items-center space-x-3 text-2xl">
                    <button
                        aria-label={isTimerRunning ? "Pause timer" : "Start timer"}
                        onClick={toggleRunning}
                        className="text-white p-3 rounded-full hover:bg-white/20 transition duration-150"
                    >
                        <IconComponent />
                    </button>

                    <button
                        aria-label="Toggle camera"
                        className="text-red-300 opacity-80 p-3 rounded-full hover:bg-red-500/80 hover:text-white transition duration-150"
                    >
                        <MdPersonOff />
                    </button>
                </div>

                {/* Center: Timer */}
                <div className="text-base px-3 font-inria">
                    <Timer isRunning={isTimerRunning} />
                </div>

                {/* Right: Done */}
                <div>
                    <button
                        className="text-sm px-5 py-4 rounded-full shadow-lg bg-[#5E7BCF] hover:bg-[#FFFFFF80] transition duration-150"
                        aria-label="Done"
                    >
                        Done
                    </button>
                </div>
            </div>
        </>
    );
};

export default NavbarTwo;


=======
      <>
      <div className='flex flex-row items-center p-4 bg-[#4F8AE2] text-white'>
      <p>play</p>
      <p>pause</p>
      <p>no camera</p>
      <p>timer?</p>
      <p>Done</p>
      </div>
      </>
        

  );
}
>>>>>>> bb23d5235afa54507dbb3480bfb6baa723475251

