import React from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { loadConfig } from './lib/config'
import './styles/app.css'

loadConfig().then(() => {
  createRoot(document.getElementById('root')).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>,
  )
})
