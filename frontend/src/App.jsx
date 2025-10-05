import './App.css'
import Navbar from './components/Navbar';
import Chatbox from './components/Chatbox';
import FaceDetection from './components/FaceDetection';

function App() {
  return (
    <>
      <Navbar />
      <div
        style={{
          backgroundColor: '#0A0F26',
          minHeight: '100vh',
          width: '100%',
        }}
      >
        <div className="flex flex-row justify-center gap-8 pt-10 px-4">
          <FaceDetection />
          <Chatbox />
        </div>
      </div>
    </>
  );
}

export default App;
