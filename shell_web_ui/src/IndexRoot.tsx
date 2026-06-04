import { useState, useEffect, useRef } from 'react'
import MiniOverlay from './components/MiniOverlay'
import { shellService } from './services/shell-voice-ai'
import { getScreenSourceId } from './hooks/CaptureDesktop'
import ShellAI from './UI/ShellAI'
import TerminalOverlay from './components/TerminalOverlay'
import LeafletMapWidget from './Widgets/MapView'
import ImageWidget from './Widgets/ImageWidget'
import EmailWidget from './Widgets/EmailWidget'
import WeatherWidget from './Widgets/WeatherWidget'
import StockWidget from './Widgets/StockWidget'
import LiveCodingWidget from './Widgets/LiveCodingWidget'
import WormholeWidget from './Widgets/WormholeWidget'
import OracleWidget from './Widgets/RagOrcaleWidget'
import ResearchWidget from './Widgets/DeepResearch'
import SemanticWidget from './Widgets/SematicSearch'
import SmartDropZonesWidget from './Widgets/SmartZoneWidget'

export type VisionMode = 'camera' | 'screen' | 'none'

type SystemNotice = {
  title: string
  message: string
}

const IndexRoot = () => {
  const [isOverlay, setIsOverlay] = useState(false)

  const [isSystemActive, setIsSystemActive] = useState(false)
  const [isMicMuted, setIsMicMuted] = useState(true)
  const [backendVoiceState, setBackendVoiceState] = useState('OFFLINE')
  const [systemNotice, setSystemNotice] = useState<SystemNotice | null>(null)
  const [voiceRuntime, setVoiceRuntime] = useState<'gemini' | 'backend'>(
    (localStorage.getItem('shell_voice_runtime') as 'gemini' | 'backend') || 'gemini'
  )

  const [isVideoOn, setIsVideoOn] = useState(false)
  const [visionMode, setVisionMode] = useState<VisionMode>('none')

  const processingVideoRef = useRef<HTMLVideoElement>(document.createElement('video'))
  const activeStreamRef = useRef<MediaStream | null>(null)
  const aiIntervalRef = useRef<NodeJS.Timeout | null>(null)
  const lastSystemNoticeRef = useRef('')
  const usesGeminiVoice = voiceRuntime === 'gemini'
  const usesShellBackend = Boolean(window.shellAPI && !usesGeminiVoice)

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
    if (!usesShellBackend || !window.shellAPI) return
    const onVoiceStatus = (_event: unknown, payload?: any) => {
      const state = String(payload?.state || 'unknown').toUpperCase()
      const message = String(payload?.message || payload?.error || '').trim()
      setBackendVoiceState(message ? `${state}: ${message}` : state)
      if (state === 'MIC_MISSING' || state === 'MIC MISSING') {
        showSystemNotice(
          'Microphone not found',
          message || 'Shell can still start and speak; voice input is disabled.'
        )
        setIsSystemActive(true)
        setIsMicMuted(true)
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
      const stored = localStorage.getItem('shell_voice_runtime')
      if (stored === 'backend' || stored === 'gemini') setVoiceRuntime(stored)
    }
    window.addEventListener('storage', onStorage)
    window.addEventListener('shell-voice-runtime-changed', onStorage)
    return () => {
      window.removeEventListener('storage', onStorage)
      window.removeEventListener('shell-voice-runtime-changed', onStorage)
    }
  }, [])

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
        shellService.setMute(true)
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
      if (isSystemActive && !shellService.isConnected) {
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
          shellService.lastError = message
        }
        setIsSystemActive(false)
        setIsMicMuted(true)
      }
    } else {
      if (usesShellBackend) {
        await window.shellAPI.stopVoice()
      } else {
        shellService.disconnect()
      }
      setIsSystemActive(false)
      setIsMicMuted(true)
      setBackendVoiceState('OFFLINE')
      shellService.setMute(true)
      stopVision()
    }
  }

  const toggleMic = async () => {
    if (usesShellBackend && isSystemActive && isMicMuted && backendVoiceState.toUpperCase().includes('MIC_MISSING')) {
      showSystemNotice(
        'Microphone not found',
        'Shell can still start and speak; voice input is disabled.'
      )
      return
    }
    if (!usesShellBackend && isSystemActive && !shellService.hasMicrophoneInput && isMicMuted) {
      shellService.setMute(true)
      showSystemNotice(
        'Microphone not found',
        shellService.lastError || 'Shell can still start and speak; voice input is disabled.'
      )
      return
    }
    const s = !isMicMuted
    setIsMicMuted(s)
    if (usesShellBackend && window.shellAPI) {
      await window.shellAPI.call('set-voice-muted', s)
      return
    }
    shellService.setMute(s)
  }

  const speakRealVoice = async (text: string) => {
    if (!usesGeminiVoice) return false
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
        `Speak this naturally in Shell AI voice. Keep it short and Hinglish-friendly: ${text}`
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
      if (vid && vid.readyState === 4 && shellService.socket?.readyState === WebSocket.OPEN) {
        const canvas = document.createElement('canvas')
        canvas.width = 800
        canvas.height = 450
        const ctx = canvas.getContext('2d')
        if (ctx) {
          ctx.drawImage(vid, 0, 0, canvas.width, canvas.height)
          const base64 = canvas.toDataURL('image/jpeg', 0.6).split(',')[1]
          shellService.sendVideoFrame(base64)
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
          voiceRuntime={voiceRuntime}
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
    </div>
  )
}

export default IndexRoot
