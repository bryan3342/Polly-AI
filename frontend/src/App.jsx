import './App.css'
import Navbar from './components/Navbar';

function App() {


  return (
    <>
      <Navbar />
      <div className="debate-container">
        {/* Box 1: Camera Display & Controls */}
        <div className="video-area">
          {/* ... WebcamDisplay component here ... */}
          {/* ... ControlPanel component here ... */}
        </div>

        {/* Box 2: AI Feedback / Chat */}
        <div className="chat-box">
          {/* ... AIFeedback component here ... */}
        </div>
      </div>
    </>
  );
}

export default App



