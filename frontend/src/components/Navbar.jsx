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
import '../index.css';
// Import your CSS file where you define the styles below
// import '../styles/Navbar.css'; 

function Navbar() {
    return (
    <nav className="navbar">
        <div className="navbar-brand">
        <h1>Polly Bird</h1>
        </div>
      
      {/* Navigation Links (Future Pages) */}
      <div className="navbar-links">
        {/* If you use React Router, change <a> to <Link to="..."> */}
        <a href="#debate" className="nav-link">Debate</a>
        <a href="#history" className="nav-link">History</a>
        <a href="#settings" className="nav-link">Settings</a>
      </div>

    </nav>
  );
}

export default Navbar;