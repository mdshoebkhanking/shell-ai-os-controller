import { Suspense, lazy, useState, useEffect, useRef, useCallback } from 'react'
import MiniOverlay from './components/MiniOverlay'
import { getScreenSourceId } from './hooks/CaptureDesktop'
import ShellAI from './UI/ShellAI'
import { shellSpeechInstruction } from './services/language-settings'
import { normalizeGeminiApiKey } from './services/api-key-utils'

const TerminalOverlay = lazy(() => import('./components/TerminalOverlay'))
const LeafletMapWidget = lazy(() => import('./Widgets/MapView'))
const ImageWidget = lazy(() => import('./Widgets/ImageWidget'))
const EmailWidget = lazy(() => import('./Widgets/EmailWidget'))
const WeatherWidget = lazy(() => import('./Widgets/WeatherWidget'))
const StockWidget = lazy(() => import('./Widgets/StockWidget'))
const LiveCodingWidget = lazy(() => import('./Widgets/LiveCodingWidget'))
const WormholeWidget = lazy(() => import('./Widgets/WormholeWidget'))
const OracleWidget = lazy(() => import('./Widgets/RagOrcaleWidget'))
const ResearchWidget = lazy(() => import('./Widgets/DeepResearch'))
const SemanticWidget = lazy(() => import('./Widgets/SematicSearch'))
const SmartDropZonesWidget = lazy(() => import('./Widgets/SmartZoneWidget'))

export type VisionMode = 'camera' | 'screen' | 'none'

type SystemNotice = {
  title: string
  message: string
}

type VoiceRuntime = 'auto' | 'gemini' | 'backend'
type ShellVoiceService = typeof import('./services/shell-voice-ai')['shellService']
type ShellVoiceWindow = Window & {
  __shellVoiceService?: ShellVoiceService
}
type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout?: number }) => number
  cancelIdleCallback?: (handle: number) => void
}

// Browser Web Speech Recognition type shim
type BrowserSpeechRecognition = any

let shellVoiceServicePromise: Promise<ShellVoiceService> | null = null

const getShellService = async () => {
  if ((window as ShellVoiceWindow).__shellVoiceService) {
    return (window as ShellVoiceWindow).__shellVoiceService as ShellVoiceService
  }
  if (!shellVoiceServicePromise) {
    shellVoiceServicePromise = import('./services/shell-voice-ai').then((module) => {
      ;(window as ShellVoiceWindow).__shellVoiceService = module.shellService
      return module.shellService
    })
  }
  return shellVoiceServicePromise
}

const peekShellService = () => (window as ShellVoiceWindow).__shellVoiceService || null

const normalizeVoiceRuntime = (value: unknown): VoiceRuntime => {
  const runtime = String(value || '').trim().toLowerCase()
  return runtime === 'gemini' || runtime === 'backend' || runtime === 'auto' ? runtime : 'auto'
}

const desktopBridgeExpected = () => Boolean((window as any).__shellElectronBridge?.call || window.electron?.ipcRenderer)

const hasGeminiVoiceKey = async () => {
  const localKey = normalizeGeminiApiKey(localStorage.getItem('shell_custom_api_key'))
  if (localKey) return true
  if (!desktopBridgeExpected()) return false
  try {
    const secureKeys = window.electron?.ipcRenderer
      ? await window.electron.ipcRenderer.invoke('secure-get-keys')
      : null
    const configuredKey =
      normalizeGeminiApiKey(secureKeys?.geminiKey) ||
      localKey
    return Boolean(configuredKey)
  } catch {
    return false
  }
}

// Get browser SpeechRecognition API (cross-browser)
const getBrowserSpeechRecognition = (): (new () => BrowserSpeechRecognition) | null => {
  const w = window as any
  return w.SpeechRecognition || w.webkitSpeechRecognition || null
}

const IndexRoot = () => {
  const [isOverlay, setIsOverlay] = useState(false)

  const [isSystemActive, setIsSystemActive] = useState(false)
  const [isMicMuted, setIsMicMuted] = useState(true)
  const [backendVoiceState, setBackendVoiceState] = useState('OFFLINE')
  const [systemNotice, setSystemNotice] = useState<SystemNotice | null>(null)
  const [mountDeferredWidgets, setMountDeferredWidgets] = useState(false)
  const [voiceRuntime, setVoiceRuntime] = useState<VoiceRuntime>(() =>
    normalizeVoiceRuntime(localStorage.getItem('shell_voice_runtime'))
  )

  // Browser Web Speech Recognition fallback — used when Python sounddevice has no mic
  const browserSpeechRef = useRef<BrowserSpeechRecognition | null>(null)
  const browserSpeechActiveRef = useRef(false)

  const [isVideoOn, setIsVideoOn] = useState(false)
  const [visionMode, setVisionMode] = useState<VisionMode>('none')

  const processingVideoRef = useRef<HTMLVideoElement>(document.createElement('video'))
  const activeStreamRef = useRef<MediaStream | null>(null)
  const aiIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const lastSystemNoticeRef = useRef('')
  const resolvedVoiceRuntime: 'gemini' | 'backend' =
    voiceRuntime === 'auto' ? (desktopBridgeExpected() ? 'backend' : 'gemini') : voiceRuntime
  const usesGeminiVoice = resolvedVoiceRuntime === 'gemini'
  const usesShellBackend = Boolean(window.shellAPI && resolvedVoiceRuntime === 'backend')

  const showSystemNotice = (title: string, rawMessage: unknown) => {
    const message = String(rawMessage || '').trim()
    if (!message) return
    const noticeKey = `${title}:${message}`
    if (noticeKey === lastSystemNoticeRef.current) return
    lastSystemNoticeRef.current = noticeKey
    setSystemNotice({ title, message })
  }

  const clearSystemNotice = () => {
    lastSystemNoticeRef.current = ''
    setSystemNotice(null)
  }

  useEffect(() => {
    window.electron.ipcRenderer.on('overlay-mode', (_e, mode) => setIsOverlay(mode))
    return () => {
      window.electron.ipcRenderer.removeAllListeners('overlay-mode')
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    const mount = () => {
      if (!cancelled) setMountDeferredWidgets(true)
    }
    const idleWindow = window as IdleWindow
    if (idleWindow.requestIdleCallback && idleWindow.cancelIdleCallback) {
      const handle = idleWindow.requestIdleCallback(mount, { timeout: 1800 })
      return () => {
        cancelled = true
        idleWindow.cancelIdleCallback?.(handle)
      }
    }
    const timer = window.setTimeout(mount, 1200)
    return () => {
      cancelled = true
      window.clearTimeout(timer)
    }
  }, [])

  useEffect(() => {
    if (!usesShellBackend || !window.shellAPI) return
    const onVoiceStatus = (_event: unknown, payload?: any) => {
      const state = String(payload?.state || 'unknown').toUpperCase()
      const message = String(payload?.message || payload?.error || '').trim()
      setBackendVoiceState(message ? `${state}: ${message}` : state)
      if (state === 'MIC_MISSING' || state === 'MIC MISSING') {
        setIsSystemActive(true)
        setIsMicMuted(true)
        // Trigger browser Speech Recognition fallback automatically
        // (will be started via the backendVoiceState watcher useEffect below)
        return
      }
      if (state === 'ERROR') {
        showSystemNotice('Voice failed', message || 'Backend voice runtime unavailable.')
      }
      if (state === 'ERROR' || state === 'STOPPED') {
        setIsSystemActive(false)
        setIsMicMuted(true)
      }
      if (state === 'LISTENING' || state === 'STARTING') {
        clearSystemNotice()
        setIsSystemActive(true)
        setIsMicMuted(false)
      }
    }
    window.shellAPI.on('voice-status', onVoiceStatus)
    return () => window.shellAPI?.off('voice-status', onVoiceStatus)
  }, [usesShellBackend])

  useEffect(() => {
    const onStorage = () => {
      setVoiceRuntime(normalizeVoiceRuntime(localStorage.getItem('shell_voice_runtime')))
    }
    window.addEventListener('storage', onStorage)
    window.addEventListener('shell-voice-runtime-changed', onStorage)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('shell-voice-runtime-changed', onStorage)
    }
  }, [])

  useEffect(() => {
    if (window.electron?.ipcRenderer) {
      const nextVoiceMode = voiceRuntime === 'gemini' ? 'cloud' : 'local'
      window.electron.ipcRenderer.invoke('set-settings', {
        voice_mode: nextVoiceMode
      }).catch((err) => console.error('Failed to sync voice mode on start:', err))
    }
  }, [voiceRuntime])


  useEffect(() => {
    const onGeminiVoiceStatus = (event: Event) => {
      const payload = (event as CustomEvent<{ state?: string; message?: string }>).detail || {}
      const state = String(payload.state || '').toUpperCase()
      if (!state) return
      setBackendVoiceState(payload.message ? `${state}: ${payload.message}` : state)
      if (state === 'MIC MISSING') {
        showSystemNotice(
          'Microphone not found',
          payload.message || 'Shell can still start and speak; voice input is disabled.'
        )
        setIsSystemActive(true)
        setIsMicMuted(true)
        peekShellService()?.setMute(true)
        return
      }
      if (state === 'ERROR' || state === 'CLOSED') {
        if (state === 'ERROR') showSystemNotice('Gemini Live failed', payload.message || 'Voice connection failed.')
        setIsSystemActive(false)
        setIsMicMuted(true)
        stopVision()
      }
      if (state === 'LISTENING' || state === 'CONNECTING' || state === 'MIC READY') {
        clearSystemNotice()
        setIsSystemActive(true)
        setIsMicMuted(false)
      }
    }
    window.addEventListener('shell-gemini-voice-status', onGeminiVoiceStatus)
    return () => window.removeEventListener('shell-gemini-voice-status', onGeminiVoiceStatus)
  }, [])

  useEffect(() => {
    const watchdog = setInterval(() => {
      if (usesShellBackend) return
      const shellService = peekShellService()
      if (isSystemActive && shellService && !shellService.isConnected) {
        if (shellService.lastError) {
          setBackendVoiceState(`ERROR: ${shellService.lastError}`)
          showSystemNotice('Gemini Live failed', shellService.lastError)
        }
        setIsSystemActive(false)
        setIsMicMuted(true)
        stopVision()
      }
    }, 1000)
    return () => clearInterval(watchdog)
  }, [isSystemActive, usesShellBackend])

  const toggleSystem = async () => {
    if (!isSystemActive) {
      let shellService: ShellVoiceService | null = null
      try {
        if (usesShellBackend) {
          const result = (await window.shellAPI.startVoice()) as any
          if (result?.success === false) {
            const message = result.message || result.error || 'backend unavailable'
            showSystemNotice('Voice failed', message)
            setBackendVoiceState(`ERROR: ${message}`)
            setIsSystemActive(false)
            setIsMicMuted(true)
            return
          }
          setBackendVoiceState('STARTING')
          setIsSystemActive(true)
          setIsMicMuted(false)
          clearSystemNotice()
          return
        }
        shellService = await getShellService()
        await shellService.connect()
        await shellService.waitUntilReady()
        const hasMicrophoneInput = shellService.hasMicrophoneInput
        setIsSystemActive(true)
        setIsMicMuted(!hasMicrophoneInput)
        setBackendVoiceState(
          hasMicrophoneInput
            ? 'GEMINI LIVE'
            : `MIC MISSING: ${shellService.lastError || 'Shell can still speak; voice input is disabled.'}`
        )
        shellService.setMute(!hasMicrophoneInput)
        if (hasMicrophoneInput) {
          clearSystemNotice()
        } else {
          showSystemNotice(
            'Microphone not found',
            shellService.lastError || 'Shell can still start and speak; voice input is disabled.'
          )
        }
      } catch (err: any) {
        const message =
          err?.message === 'NO_API_KEY'
            ? 'Gemini API key missing. Open Settings > API Keys and save a valid Google AI Studio key.'
            : `Connection failed: ${err?.message || err}`
        setBackendVoiceState(`ERROR: ${message}`)
        showSystemNotice('Gemini Live failed', message)
        if (err?.message === 'NO_API_KEY') {
          if (shellService) shellService.lastError = message
        }
        setIsSystemActive(false)
        setIsMicMuted(true)
      }
    } else {
      if (usesShellBackend) {
        await window.shellAPI.stopVoice()
      } else {
        peekShellService()?.disconnect()
      }
      setIsSystemActive(false)
      setIsMicMuted(true)
      setBackendVoiceState('OFFLINE')
      peekShellService()?.setMute(true)
      stopVision()
      // Stop browser speech fallback if running
      stopBrowserSpeech()
    }
  }

  // ── Browser Web Speech Recognition fallback ─────────────────────────────────
  // When Python's sounddevice has no input device (MIC_MISSING), use the
  // browser's SpeechRecognition API to capture voice and send to Shell
  // with source='voice' so Kokoro TTS speaks the reply.

  const stopBrowserSpeech = useCallback(() => {
    browserSpeechActiveRef.current = false
    const recognition = browserSpeechRef.current
    if (recognition) {
      try { recognition.stop() } catch {}
      try { recognition.abort() } catch {}
      browserSpeechRef.current = null
    }
  }, [])

  const startBrowserSpeech = useCallback(() => {
    const SpeechRecognition = getBrowserSpeechRecognition()
    if (!SpeechRecognition) {
      setBackendVoiceState('MIC_MISSING: Browser speech API not available')
      return
    }
    if (browserSpeechActiveRef.current) return
    browserSpeechActiveRef.current = true
    setBackendVoiceState('LISTENING')
    setIsMicMuted(false)
    clearSystemNotice()

    const recognition: BrowserSpeechRecognition = new SpeechRecognition()
    recognition.continuous = true
    recognition.interimResults = false
    recognition.lang = 'hi-IN'  // Hinglish — Hindi locale picks up mixed speech well
    recognition.maxAlternatives = 1
    browserSpeechRef.current = recognition

    recognition.onstart = () => {
      setBackendVoiceState('LISTENING')
      setIsMicMuted(false)
    }

    recognition.onresult = async (event: any) => {
      const last = event.results[event.results.length - 1]
      if (!last?.isFinal) return
      const transcript = String(last[0]?.transcript || '').trim()
      if (!transcript) return
      // Emit voice transcript so UI shows it
      window.shellAPI?.emit?.('voice-transcript', { text: transcript })
      setBackendVoiceState('PROCESSING')
      // Send to Shell backend as voice source → reply will trigger Kokoro TTS
      try {
        if (window.electron?.ipcRenderer) {
          await window.electron.ipcRenderer.invoke('chat-message', transcript, { source: 'voice' })
        } else if (window.shellAPI?.call) {
          await window.shellAPI.call('chat-message', transcript, { source: 'voice' })
        }
      } catch {}
      setBackendVoiceState('LISTENING')
    }

    recognition.onerror = (event: any) => {
      const err = String(event?.error || 'unknown')
      if (err === 'no-speech') {
        // Silently restart on no-speech — normal during pauses
        if (browserSpeechActiveRef.current) {
          try { recognition.start() } catch {}
        }
        return
      }
      if (err === 'aborted' || err === 'not-allowed') {
        browserSpeechActiveRef.current = false
        setBackendVoiceState('MIC_MISSING: Browser mic permission denied')
        setIsMicMuted(true)
        showSystemNotice('Mic permission denied', 'Browser mic access allow karo Settings mein.')
        return
      }
      // On other errors, attempt restart
      if (browserSpeechActiveRef.current) {
        setTimeout(() => {
          if (browserSpeechActiveRef.current) {
            try { recognition.start() } catch {}
          }
        }, 1000)
      }
    }

    recognition.onend = () => {
      // Auto-restart for continuous listening
      if (browserSpeechActiveRef.current) {
        setTimeout(() => {
          if (browserSpeechActiveRef.current) {
            try { recognition.start() } catch {}
          }
        }, 200)
      } else {
        setBackendVoiceState('STOPPED')
        setIsMicMuted(true)
      }
    }

    try {
      recognition.start()
    } catch {
      browserSpeechActiveRef.current = false
      setBackendVoiceState('ERROR: Browser speech start failed')
    }
  }, [clearSystemNotice, showSystemNotice])

  const toggleMic = async () => {
    // Browser speech fallback: when backend has no mic (sounddevice fails),
    // use browser SpeechRecognition to toggle mic on/off
    if (usesShellBackend && isSystemActive && backendVoiceState.toUpperCase().includes('MIC_MISSING')) {
      if (isMicMuted) {
        // User wants to unmute — start browser speech recognition
        startBrowserSpeech()
      } else {
        // User wants to mute — stop browser speech
        stopBrowserSpeech()
        setIsMicMuted(true)
        setBackendVoiceState('MIC_MISSING: Browser mic paused')
      }
      return
    }
    // If browser speech is active, toggle it
    if (browserSpeechActiveRef.current) {
      stopBrowserSpeech()
      setIsMicMuted(true)
      return
    }
    const loadedShellService = peekShellService()
    if (!usesShellBackend && isSystemActive && loadedShellService && !loadedShellService.hasMicrophoneInput && isMicMuted) {
      loadedShellService.setMute(true)
      showSystemNotice(
        'Microphone not found',
        loadedShellService.lastError || 'Shell can still start and speak; voice input is disabled.'
      )
      return
    }
    const s = !isMicMuted
    setIsMicMuted(s)
    if (usesShellBackend && window.shellAPI) {
      await window.shellAPI.call('set-voice-muted', s)
      return
    }
    const shellService = await getShellService()
    shellService.setMute(s)
  }

  // Auto-start browser Speech Recognition when Python backend reports MIC_MISSING
  // This is the key bridge: browser mic -> Shell voice pipeline -> Kokoro TTS reply
  useEffect(() => {
    const state = backendVoiceState.toUpperCase()
    if (
      usesShellBackend &&
      isSystemActive &&
      (state.startsWith('MIC_MISSING') || state === 'MIC MISSING') &&
      !browserSpeechActiveRef.current
    ) {
      // Small delay to let the backend settle
      const timer = setTimeout(() => {
        startBrowserSpeech()
      }, 500)
      return () => clearTimeout(timer)
    }
    return undefined
  }, [backendVoiceState, isSystemActive, usesShellBackend, startBrowserSpeech])

  const speakRealVoice = async (text: string) => {
    if (!usesGeminiVoice) return false
    if (!(await hasGeminiVoiceKey())) return false
    const shellService = await getShellService()
    try {
      if (!shellService.isConnected) {
        await shellService.connect()
        await shellService.waitUntilReady()
        const hasMicrophoneInput = shellService.hasMicrophoneInput
        setIsSystemActive(true)
        setIsMicMuted(!hasMicrophoneInput)
        shellService.setMute(!hasMicrophoneInput)
        setBackendVoiceState(
          hasMicrophoneInput
            ? 'GEMINI LIVE'
            : `MIC MISSING: ${shellService.lastError || 'Shell can still speak; voice input is disabled.'}`
        )
        if (hasMicrophoneInput) {
          clearSystemNotice()
        } else {
          showSystemNotice(
            'Microphone not found',
            shellService.lastError || 'Shell can still start and speak; voice input is disabled.'
          )
        }
      }
      await shellService.forceSpeak(
        `Speak this naturally in Shell AI voice. ${shellSpeechInstruction()} Keep it short: ${text}`
      )
      return true
    } catch (err: any) {
      const message =
        err?.message === 'NO_API_KEY'
          ? 'Real Gemini voice needs a valid key in Settings > API Keys.'
          : `Real Gemini voice failed: ${err?.message || err}`
      setBackendVoiceState(`ERROR: ${message}`)
      showSystemNotice('Real voice failed', message)
      shellService.lastError = message
      return false
    }
  }

  const startVision = async (mode: 'camera' | 'screen') => {
    try {
      if (!navigator.mediaDevices) throw new Error('Media devices unavailable in this host')

      let stream: MediaStream | null = null

      if (mode === 'camera') {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: 640, height: 480 }
        })
      } else if (typeof (navigator.mediaDevices as any).getDisplayMedia === 'function') {
        stream = await (navigator.mediaDevices as any).getDisplayMedia({
          audio: false,
          video: {
            width: { ideal: 1280 },
            height: { ideal: 720 },
            frameRate: { ideal: 12, max: 30 }
          }
        })
      } else {
        const sourceId = await getScreenSourceId()
        if (!sourceId) throw new Error('Screen share source select cancel hua.')
        stream = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: {
            // @ts-ignore
            mandatory: {
              chromeMediaSource: 'desktop',
              chromeMediaSourceId: sourceId,
              maxWidth: 1280,
              maxHeight: 720
            }
          }
        })
      }

      if (!stream) throw new Error('No media stream returned')

      if (activeStreamRef.current) {
        activeStreamRef.current.getTracks().forEach((t) => t.stop())
      }

      activeStreamRef.current = stream

      processingVideoRef.current.muted = true
      processingVideoRef.current.playsInline = true
      processingVideoRef.current.srcObject = stream

      setVisionMode(mode)
      setIsVideoOn(true)

      try {
        await processingVideoRef.current.play()
      } catch {}

      startAIProcessing()

      const [videoTrack] = stream.getVideoTracks()
      if (videoTrack) videoTrack.onended = () => stopVision()
    } catch (e: any) {
      if (!activeStreamRef.current) stopVision()
      showSystemNotice(
        mode === 'camera' ? 'Camera failed' : 'Screen share failed',
        `${mode === 'camera' ? 'Camera feed' : 'Screen share'} start nahi ho paya: ${e?.message || e}`
      )
    }
  }

  const stopVision = () => {
    setIsVideoOn(false)
    setVisionMode('none')

    if (activeStreamRef.current) {
      activeStreamRef.current.getTracks().forEach((t) => t.stop())
      activeStreamRef.current = null
    }

    if (processingVideoRef.current) {
      processingVideoRef.current.srcObject = null
    }

    if (aiIntervalRef.current) {
      clearInterval(aiIntervalRef.current)
      aiIntervalRef.current = null
    }
  }

  const startAIProcessing = () => {
    if (aiIntervalRef.current) clearInterval(aiIntervalRef.current)

    aiIntervalRef.current = setInterval(() => {
      const vid = processingVideoRef.current
      const shellService = peekShellService()
      if (vid && vid.readyState === 4 && shellService?.socket?.readyState === WebSocket.OPEN) {
        const canvas = document.createElement('canvas')
        canvas.width = 800
        canvas.height = 450
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.drawImage(vid, 0, 0, canvas.width, canvas.height)
          const base64 = canvas.toDataURL('image/jpeg', 0.6).split(',')[1]
          shellService?.sendVideoFrame(base64)
        }
      }
    }, 2000)
  }

  if (isOverlay) {
    return (
      <div className="w-screen h-screen overflow-hidden flex items-center justify-center bg-transparent">
        <MiniOverlay
          isSystemActive={isSystemActive}
          toggleSystem={toggleSystem}
          isMicMuted={isMicMuted}
          toggleMic={toggleMic}
          isVideoOn={isVideoOn}
          visionMode={visionMode}
          startVision={startVision}
          stopVision={stopVision}
        />
        {systemNotice && (
          <div className="shell-notice absolute right-4 top-4 z-50 w-[min(360px,calc(100vw-24px))] rounded-2xl border p-3 text-red-100 shadow-2xl">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-[10px] font-black uppercase tracking-[0.2em] text-red-300">
                  {systemNotice.title}
                </div>
                <div className="mt-2 text-[12px] leading-relaxed text-red-100/90">{systemNotice.message}</div>
              </div>
              <button
                type="button"
                onClick={clearSystemNotice}
                className="shrink-0 rounded border border-red-400/30 px-2 py-1 text-[10px] font-bold text-red-100 hover:bg-red-500/20"
                aria-label="Dismiss notification"
              >
                x
              </button>
            </div>
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="shell-app-frame flex flex-col h-screen w-screen overflow-hidden relative border rounded-xl">
      <div className="flex-1 relative">
        <ShellAI
          isSystemActive={isSystemActive}
          toggleSystem={toggleSystem}
          isMicMuted={isMicMuted}
          toggleMic={toggleMic}
          isVideoOn={isVideoOn}
          visionMode={visionMode}
          startVision={startVision}
          stopVision={stopVision}
          activeStream={activeStreamRef.current}
          backendVoiceState={backendVoiceState}
          voiceRuntime={resolvedVoiceRuntime}
          speakRealVoice={speakRealVoice}
        />
      </div>
      {systemNotice && (
        <div className="shell-notice absolute right-6 top-16 z-50 w-[min(420px,calc(100vw-32px))] rounded-2xl border p-4 text-red-100 shadow-2xl">
          <div className="flex items-start justify-between gap-3">
            <div>
              <div className="text-[11px] font-black uppercase tracking-[0.2em] text-red-300">{systemNotice.title}</div>
              <div className="mt-2 text-[12px] leading-relaxed text-red-100/90">{systemNotice.message}</div>
            </div>
            <button
              type="button"
              onClick={clearSystemNotice}
              className="shrink-0 rounded border border-red-400/30 px-2 py-1 text-[10px] font-bold text-red-100 hover:bg-red-500/20"
              aria-label="Dismiss notification"
            >
              x
            </button>
          </div>
        </div>
      )}
      {mountDeferredWidgets && (
        <Suspense fallback={null}>
          <SmartDropZonesWidget />
          <SemanticWidget />
          <OracleWidget />
          <WormholeWidget />
          <LeafletMapWidget />
          <StockWidget />
          <WeatherWidget />
          <ImageWidget />
          <EmailWidget />
          <TerminalOverlay />
          <LiveCodingWidget />
          <ResearchWidget />
        </Suspense>
      )}
    </div>
  )
}

export default IndexRoot
