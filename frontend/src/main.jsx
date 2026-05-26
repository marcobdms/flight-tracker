import React from 'react'
import ReactDOM from 'react-dom/client'
import { Toaster } from 'react-hot-toast'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
    <Toaster
      position="bottom-right"
      toastOptions={{
        style: {
          background: 'rgba(20, 20, 35, 0.95)',
          color: '#e2e8f0',
          border: '1px solid rgba(102, 126, 234, 0.3)',
          borderRadius: '12px',
          backdropFilter: 'blur(20px)',
          fontFamily: 'Inter, sans-serif',
        },
        success: { iconTheme: { primary: '#22c55e', secondary: '#fff' } },
        error: { iconTheme: { primary: '#ef4444', secondary: '#fff' } },
      }}
    />
  </React.StrictMode>
)
