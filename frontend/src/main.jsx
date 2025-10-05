import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import '@fontsource/inria-sans/400.css';
import App from './App.jsx'
// Import the WebSocketProvider. Assuming the path is correct after the rename.
import { WebSocketProvider } from './context/WebSocketContext.jsx' 

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {/* Wrap the entire application (App) with the WebSocketProvider */}
    <WebSocketProvider>
      <App />
    </WebSocketProvider>
  </StrictMode>,
)