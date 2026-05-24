import { useEffect, useRef, useState } from 'react'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'

export default function TerminalOverlay() {
  const containerRef = useRef<HTMLDivElement>(null)
  const xtermRef = useRef<Terminal | null>(null)
  const fitAddonRef = useRef<FitAddon | null>(null)
  const pendingChunksRef = useRef<string[]>([])
  const hideTimerRef = useRef<NodeJS.Timeout | null>(null)

  const [isVisible, setIsVisible] = useState(false)

  useEffect(() => {
    const cleanupListener = window.electron.ipcRenderer.on('terminal-data', (_event, data) => {
      const chunk = String(data || '')
      setIsVisible(true)

      if (xtermRef.current) {
        xtermRef.current.write(chunk)
        requestAnimationFrame(() => {
          try {
            fitAddonRef.current?.fit()
          } catch (e) {}
        })
      } else {
        pendingChunksRef.current.push(chunk)
      }

      if (hideTimerRef.current) clearTimeout(hideTimerRef.current)
      hideTimerRef.current = setTimeout(() => setIsVisible(false), 10000)
    })

    return () => {
      if (typeof cleanupListener === 'function') cleanupListener()
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current)
      xtermRef.current?.dispose()
    }
  }, [])

  useEffect(() => {
    if (!isVisible) {
      xtermRef.current?.dispose()
      xtermRef.current = null
      fitAddonRef.current = null
      return
    }
    if (xtermRef.current) return

    const initTimer = setTimeout(() => {
      if (!containerRef.current || xtermRef.current) return

      const term = new Terminal({
        cursorBlink: true,
        cursorStyle: 'block',
        theme: {
          background: '#050505',
          foreground: '#00ff41',
          cursor: '#00ff41',
          selectionBackground: 'rgba(0, 255, 65, 0.3)',
          black: '#050505',
          green: '#00ff41',
          red: '#ff003c',
          cyan: '#00e5ff'
        },
        fontFamily: '"Fira Code", "Cascadia Code", Consolas, monospace',
        fontSize: 12,
        lineHeight: 1.1,
        letterSpacing: 0.5,
        rows: 16,
        cols: 80,
        convertEol: true,
        allowProposedApi: true
      })

      const fitAddon = new FitAddon()
      fitAddonRef.current = fitAddon
      term.loadAddon(fitAddon)
      term.open(containerRef.current)
      xtermRef.current = term

      try {
        fitAddon.fit()
      } catch (e) {}

      const pending = pendingChunksRef.current.splice(0)
      for (const chunk of pending) term.write(chunk)
    }, 50)

    return () => clearTimeout(initTimer)
  }, [isVisible])

  if (!isVisible) return null

  return (
    <div className="fixed bottom-6 right-6 z-9999 w-162.5 transition-all duration-500 ease-out transform translate-y-0 opacity-100 scale-100">
      <div className="relative bg-black/85 backdrop-blur-md border border-green-500/30 rounded-lg shadow-[0_0_30px_rgba(0,255,65,0.15)] overflow-hidden flex flex-col">
        <div className="absolute inset-0 pointer-events-none bg-[linear-gradient(rgba(18,16,16,0)_50%,rgba(0,0,0,0.1)_50%),linear-gradient(90deg,rgba(255,0,0,0.03),rgba(0,255,0,0.01),rgba(0,0,255,0.03))] z-10 bg-size-[100%_2px,3px_100%] opacity-20" />

        <div className="flex items-center justify-between px-3 py-2 bg-green-900/10 border-b border-green-500/20">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse shadow-[0_0_8px_#00ff41]" />
            <span className="text-[10px] font-mono font-bold tracking-widest text-green-400/80 uppercase">
              SHELL TERMINAL
            </span>
          </div>

          <button
            onClick={() => setIsVisible(false)}
            className="text-green-500/50 hover:text-green-400 transition-colors text-xs font-mono"
          >
            [MINIMIZE]
          </button>
        </div>

        <div className="relative p-2 h-85 bg-transparent scrollbar-small">
          <div ref={containerRef} style={{ height: '100%', width: '100%' }} className="terminal-container" />
        </div>

        <div className="h-1 w-full bg-linear-to-r from-green-500/0 via-green-500/30 to-green-500/0" />
      </div>
    </div>
  )
}
