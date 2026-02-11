import './App.css'
import Navbar from './components/Navbar';
import Camera from './components/Camera';
import Chatbox from './components/Chatbox';
import { useWebSocket } from './context/WebSocketContext';

function App() {
  const { isConnected, error } = useWebSocket();

  return (
    <>
      <div style={{
        backgroundColor: '#0A0F26',
        minHeight: '100vh',
        width: '100%'
      }}>
        {error && (
          <div className="bg-red-900/50 text-red-200 text-center py-2 text-sm">
            {error}
          </div>
        )}
        <div className="flex flex-col lg:flex-row justify-around items-start gap-4 p-4 pt-6 pb-28">
          <Camera />
          <Chatbox />
        </div>
      </div>
      <Navbar />
    </>
  );
}

export default App
