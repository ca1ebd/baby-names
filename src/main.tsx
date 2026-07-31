import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { storage } from './lib/storage'
import App from './App.tsx'

window.storage = storage

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
