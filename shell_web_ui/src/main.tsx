import './assets/main.css'
import './shellBridge'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import IndexRoot from './IndexRoot'

const shellSearchParams = new URLSearchParams(window.location.search)
const shellPerfMode = (shellSearchParams.get('shell_perf') || '').trim().toLowerCase()
const isWindowsShellHost =
  /Windows/i.test(navigator.userAgent || '') || shellSearchParams.get('shell_host') === 'pyqt'
const explicitSafePerfMode = ['safe', 'low', 'eco'].includes(shellPerfMode)
const prefersWindowsPerf =
  explicitSafePerfMode ||
  (shellPerfMode !== 'windows' && shellPerfMode !== 'chrome' && isWindowsShellHost && (navigator.hardwareConcurrency || 0) <= 4)

if (prefersWindowsPerf) {
  document.documentElement.classList.add('shell-windows-perf')
}

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
