// const Navbar = () => {
//     return(
//         <>
//         <nav className="navbar">
//             <div className="navbar-brand">
//             <h1>POLLY-AI</h1>
//             </div>
//         </nav>
//         <p className="text-blue-100">Play</p>
//         </>
//     )
// }

// export default Navbar;

// import React from 'react';
// import './Navbar.css';
// Import your CSS file where you define the styles below
// import '../styles/Navbar.css'; 

function Navbar() {
    return (
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

export default Navbar;