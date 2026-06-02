import './assets/main.css'
import './shellBridge'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import IndexRoot from './IndexRoot'

window.addEventListener('unhandledrejection', (event) => {
  const reason = event.reason
  if (
    reason &&
    typeof reason === 'object' &&
    (reason as { type?: string; msg?: string }).type === 'cancelation' &&
    (reason as { type?: string; msg?: string }).msg === 'operation is manually canceled'
  ) {
    event.preventDefault()
  }
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <IndexRoot />
  </StrictMode>
)
