import './App.css'
import Navbar from './components/Navbar';
import Timer from './components/Timer';
import Camera from './components/Camera';
import Chatbox from './components/Chatbox';

function App() {


  return (
    <div style={{ 
      backgroundColor: '#0A0F26', 
      minHeight: '100vh',
      width: '100%'
    }}>
      <div className='flex flex-row justify-around pt-10'>
      <Camera />
      <Chatbox />
      </div>

    </div>
  );
}

export default App



