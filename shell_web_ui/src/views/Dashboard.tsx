import { useEffect, useCallback, useRef, useState } from 'react'
import Sphere from '@renderer/components/Sphere'
import {
  RiCameraLine,
  RiTerminalBoxLine,
  RiSwapBoxLine,
  RiMicLine,
  RiMicOffLine,
  RiPhoneFill,
  RiHistoryLine,
  RiPulseLine,
  RiWifiLine,
  RiServerLine,
  RiEarthLine,
  RiSendPlane2Line,
  RiVolumeUpLine,
  RiCloseCircleLine
} from 'react-icons/ri'
import * as faceapi from 'face-api.js'
import { VisionMode } from '@renderer/IndexRoot'

interface ShellProps {
  isSystemActive: boolean
  toggleSystem: () => void
  isMicMuted: boolean
  toggleMic: () => void
  isVideoOn: boolean
  visionMode: VisionMode
  startVision: (mode: 'camera' | 'screen') => void
  stopVision: () => void
  activeStream: MediaStream | null
  backendVoiceState?: string
  voiceRuntime?: 'gemini' | 'backend'
  speakRealVoice?: (text: string) => Promise<boolean>
}

interface DashboardViewProps {
  props: ShellProps
  stats: any
  chatHistory: any[]
  onVisionClick: () => void
  onTranscriptCleared?: () => void
}

type ImageGenerationState = {
  status: 'generating' | 'saving' | 'saved' | 'error'
  prompt: string
  message: string
}

const glassPanel = 'bg-zinc-950/40 backdrop-blur-xl border border-white/5 rounded-2xl shadow-xl'

const compactForSpeech = (value: string, limit = 240) => {
  const cleaned = String(value || '')
    .replace(/\s+/g, ' ')
    .replace(/[{}[\]"`]/g, '')
    .trim()
  if (cleaned.length <= limit) return cleaned
  return `${cleaned.slice(0, limit).replace(/\s+\S*$/, '')}...`
}

const speakWithBrowser = (text: string) =>
  new Promise<boolean>((resolve) => {
    if (!('speechSynthesis' in window) || typeof SpeechSynthesisUtterance === 'undefined') {
      resolve(false)
      return
    }

    try {
      window.speechSynthesis.cancel()
      const utterance = new SpeechSynthesisUtterance(text)
      utterance.rate = 0.92
      utterance.pitch = 1
      utterance.volume = 1
      const voices = window.speechSynthesis.getVoices()
      const preferredVoice =
        voices.find((voice) => /rishi|samantha|daniel|reed|flo/i.test(voice.name)) || voices[0]
      if (preferredVoice) utterance.voice = preferredVoice

      let started = false
      utterance.onstart = () => {
        started = true
        resolve(true)
      }
      utterance.onerror = () => resolve(started)
      window.speechSynthesis.speak(utterance)
      window.setTimeout(() => resolve(window.speechSynthesis.speaking || started), 250)
    } catch {
      resolve(false)
    }
  })

export default function DashboardView({
  props,
  chatHistory,
  onVisionClick,
  onTranscriptCleared
}: DashboardViewProps) {
  const {
    isSystemActive,
    isVideoOn,
    visionMode,
    startVision,
    activeStream,
    toggleMic,
    toggleSystem,
    isMicMuted,
    backendVoiceState,
    voiceRuntime,
    speakRealVoice
  } = props

  const scrollRef = useRef<HTMLDivElement>(null)
  const videoElementRef = useRef<HTMLVideoElement | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const transcriptInputRef = useRef<HTMLInputElement | null>(null)
  const faceScanInterval = useRef<NodeJS.Timeout | null>(null)
  const lastSpokenRef = useRef('')

  const [modelsLoaded, setModelsLoaded] = useState(false)

  const [networkStats, setNetworkStats] = useState({ ping: 24, rate: 1.2, tx: 40, rx: 60 })
  const [transcriptPrompt, setTranscriptPrompt] = useState('')
  const [isSendingPrompt, setIsSendingPrompt] = useState(false)
  const [voiceEventState, setVoiceEventState] = useState(backendVoiceState || 'OFFLINE')
  const [speechState, setSpeechState] = useState('VOICE OUT')
  const [imageGenerationState, setImageGenerationState] = useState<ImageGenerationState | null>(null)

  const readTranscriptPrompt = () => (transcriptPrompt || transcriptInputRef.current?.value || '').trim()

  const speakShell = useCallback(async (text: string) => {
    const speechText = compactForSpeech(text)
    if (!speechText) return
    setSpeechState('SPEAKING')
    try {
      if (voiceRuntime === 'gemini' && speakRealVoice) {
        const didSendToRealVoice = await speakRealVoice(speechText)
        setSpeechState(didSendToRealVoice ? 'GEMINI LIVE' : 'VOICE ERR')
        return
      }

      const spokeInBrowser = await speakWithBrowser(speechText)
      if (spokeInBrowser) {
        setSpeechState('VOICE OUT')
        return
      }

      const result = await window.electron?.ipcRenderer.invoke('speak-text', speechText)
      if (result?.success === false) setSpeechState('VOICE ERR')
      else setSpeechState('VOICE OUT')
    } catch {
      setSpeechState('VOICE ERR')
    }
  }, [speakRealVoice, voiceRuntime])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [chatHistory])

  useEffect(() => {
    setVoiceEventState(backendVoiceState || 'OFFLINE')
  }, [backendVoiceState])

  useEffect(() => {
    if (!window.shellAPI) return
    const onVoiceStatus = (_event: unknown, payload?: any) => {
      setVoiceEventState(String(payload?.state || 'unknown').toUpperCase())
    }
    const onSpeechStatus = (_event: unknown, payload?: any) => {
      const state = String(payload?.state || 'ready').toUpperCase()
      setSpeechState(state === 'SPEAKING' ? 'SPEAKING' : state === 'ERROR' ? 'VOICE ERR' : 'VOICE OUT')
    }
    const onChatUpdated = (_event: unknown, payload?: any) => {
      const reply = String(payload?.reply || '').trim()
      if (!reply || reply === lastSpokenRef.current) return
      if (payload?.source !== 'voice' && payload?.voice !== true) return
      lastSpokenRef.current = reply
      speakShell(reply)
    }
    window.shellAPI.on('voice-status', onVoiceStatus)
    window.shellAPI.on('speech-status', onSpeechStatus)
    window.shellAPI.on('chat-updated', onChatUpdated)
    return () => {
      window.shellAPI?.off('voice-status', onVoiceStatus)
      window.shellAPI?.off('speech-status', onSpeechStatus)
      window.shellAPI?.off('chat-updated', onChatUpdated)
    }
  }, [speakShell])

  useEffect(() => {
    const normalizePrompt = (value: unknown) => String(value || '').trim() || 'Shell AI image'
    const onImageGenerationPayload = (payload: any) => {
      const prompt = normalizePrompt(payload?.prompt || payload?.image?.displayName)
      if (payload?.loading) {
        setImageGenerationState({
          status: 'generating',
          prompt,
          message: 'GENERATING IMAGE'
        })
        return
      }
      if (payload?.error) {
        setImageGenerationState({
          status: 'error',
          prompt,
          message: String(payload?.errorMessage || 'IMAGE GENERATION FAILED').slice(0, 180)
        })
        return
      }
      if (payload?.saved || payload?.image?.filename) {
        setImageGenerationState({
          status: 'saved',
          prompt,
          message: 'SAVED TO GALLERY'
        })
        return
      }
      if (payload?.url) {
        setImageGenerationState({
          status: 'saving',
          prompt,
          message: 'SAVING TO GALLERY'
        })
      }
    }
    const onDomImageGeneration = (event: Event) =>
      onImageGenerationPayload((event as CustomEvent).detail || {})
    const onBridgeImageGeneration = (_event: unknown, payload?: unknown) =>
      onImageGenerationPayload(payload)
    const onGalleryUpdated = (_event: unknown, payload?: any) => {
      if (!payload?.image) return
      setImageGenerationState((current) => {
        if (!current || (current.status !== 'generating' && current.status !== 'saving')) return current
        return {
          status: 'saved',
          prompt: normalizePrompt(payload.image.displayName || current.prompt),
          message: 'SAVED TO GALLERY'
        }
      })
    }

    window.addEventListener('image-gen', onDomImageGeneration)
    window.shellAPI?.on?.('image-gen', onBridgeImageGeneration)
    window.shellAPI?.on?.('gallery-updated', onGalleryUpdated)
    return () => {
      window.removeEventListener('image-gen', onDomImageGeneration)
      window.shellAPI?.off?.('image-gen', onBridgeImageGeneration)
      window.shellAPI?.off?.('gallery-updated', onGalleryUpdated)
    }
  }, [])

  useEffect(() => {
    if (!isSystemActive) {
      setNetworkStats({ ping: 0, rate: 0.0, tx: 0, rx: 0 })
      return
    }

    const interval = setInterval(() => {
      setNetworkStats({
        ping: Math.floor(Math.random() * (45 - 12 + 1)) + 12,
        rate: +(Math.random() * 8.5 + 0.5).toFixed(2),
        tx: Math.floor(Math.random() * 100),
        rx: Math.floor(Math.random() * 100)
      })
    }, 1700)

    return () => clearInterval(interval)
  }, [isSystemActive])

  useEffect(() => {
    const loadModels = async () => {
      try {
        const MODEL_URL = './models'
        await Promise.all([
          faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL),
          faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL),
          faceapi.nets.ageGenderNet.loadFromUri(MODEL_URL)
        ])
        setModelsLoaded(true)
      } catch (e) {}
    }
    loadModels()
  }, [])

  useEffect(() => {
    if (
      isVideoOn &&
      visionMode === 'camera' &&
      modelsLoaded &&
      videoElementRef.current &&
      canvasRef.current
    ) {
      if (faceScanInterval.current) clearInterval(faceScanInterval.current)

      faceScanInterval.current = setInterval(async () => {
        const video = videoElementRef.current
        const canvas = canvasRef.current
        if (!video || !canvas || video.readyState !== 4 || video.videoWidth === 0) return

        try {
          const vw = video.videoWidth
          const vh = video.videoHeight

          if (canvas.width !== vw || canvas.height !== vh) {
            canvas.width = vw
            canvas.height = vh
          }

          const ctx = canvas.getContext('2d')
          if (!ctx) return

          const options = new faceapi.SsdMobilenetv1Options({ minConfidence: 0.3 })
          const detection = await faceapi
            .detectSingleFace(video, options)
            .withFaceExpressions()
            .withAgeAndGender()

          ctx.clearRect(0, 0, vw, vh)

          if (detection) {
            const { x, y, width, height } = detection.detection.box

            const mirroredX = vw - x - width

            ctx.strokeStyle = '#34d399'
            ctx.lineWidth = 4
            const l = 25

            ctx.beginPath()
            ctx.moveTo(mirroredX, y + l)
            ctx.lineTo(mirroredX, y)
            ctx.lineTo(mirroredX + l, y)
            ctx.moveTo(mirroredX + width - l, y)
            ctx.lineTo(mirroredX + width, y)
            ctx.lineTo(mirroredX + width, y + l)
            ctx.moveTo(mirroredX, y + height - l)
            ctx.lineTo(mirroredX, y + height)
            ctx.lineTo(mirroredX + l, y + height)
            ctx.moveTo(mirroredX + width - l, y + height)
            ctx.lineTo(mirroredX + width, y + height)
            ctx.lineTo(mirroredX + width, y + height - l)
            ctx.stroke()

            const expressions = detection.expressions
            const domExp = Object.keys(expressions).reduce((a, b) =>
              expressions[a] > expressions[b] ? a : b
            )
            const gender = detection.gender === 'male' ? 'M' : 'F'
            const age = Math.round(detection.age)
            const labelText = ` ID:${gender} | AGE:${age} | ${domExp.toUpperCase()} `

            ctx.fillStyle = 'rgba(10, 10, 10, 0.85)'
            ctx.fillRect(mirroredX, y - 32, width, 26)

            ctx.fillStyle = '#34d399'
            ctx.font = 'bold 16px monospace'
            ctx.fillText(labelText, mirroredX + 5, y - 14)
          } else {
            ctx.fillStyle = 'rgba(52, 211, 153, 0.8)'
            ctx.font = 'bold 14px monospace'
            ctx.fillText('SCANNING OPTICS...', 20, 30)
          }
        } catch (e) {}
      }, 250)
    } else {
      if (faceScanInterval.current) clearInterval(faceScanInterval.current)
      const ctx = canvasRef.current?.getContext('2d')
      if (ctx) ctx.clearRect(0, 0, canvasRef.current!.width, canvasRef.current!.height)
    }

    return () => {
      if (faceScanInterval.current) clearInterval(faceScanInterval.current)
    }
  }, [isVideoOn, visionMode, modelsLoaded])

  const setVideoRef = useCallback(
    (node: HTMLVideoElement | null) => {
      videoElementRef.current = node
      if (node && activeStream && isVideoOn) {
        node.srcObject = activeStream
        node.onloadedmetadata = () => node.play().catch(() => {})
      }
    },
    [activeStream, isVideoOn, visionMode]
  )

  const setMobileVideoRef = useCallback(
    (node: HTMLVideoElement | null) => {
      if (node && activeStream && isVideoOn) {
        node.srcObject = activeStream
        node.onloadedmetadata = () => node.play().catch(() => {})
      }
    },
    [activeStream, isVideoOn, visionMode]
  )

  const toggleSource = () => {
    const nextMode = visionMode === 'camera' ? 'screen' : 'camera'
    startVision(nextMode)
  }

  const sendTranscriptPrompt = async () => {
    const text = readTranscriptPrompt()
    if (!text || isSendingPrompt) return
    setIsSendingPrompt(true)
    setTranscriptPrompt('')
    try {
      await window.electron?.ipcRenderer.invoke('chat-message', text, { source: 'text' })
    } finally {
      setIsSendingPrompt(false)
    }
  }

  const clearTranscript = async () => {
    try {
      await window.electron?.ipcRenderer.invoke('clear-history')
    } finally {
      lastSpokenRef.current = ''
      onTranscriptCleared?.()
    }
  }

  const visionDisplayLabel = isVideoOn
    ? visionMode === 'screen'
      ? 'SCREEN FEED'
      : 'OPTICAL FEED'
    : 'OPTICS OFFLINE'
  const voiceDisplayState =
    !isSystemActive && ['OFFLINE', 'STOPPED', 'UNKNOWN'].includes(String(voiceEventState || '').toUpperCase())
      ? 'STANDBY'
      : voiceEventState

  return (
    <div className="flex-1 p-4 bg-white/2 grid grid-cols-12 gap-4 h-full overflow-y-auto md:overflow-hidden relative animate-in fade-in zoom-in duration-300 w-full scrollbar-small">
      <div className="hidden lg:flex col-span-3 flex-col gap-4 h-full z-40 overflow-y-auto pr-1 scrollbar-small">
        <div
          className={`${glassPanel} h-32 shrink-0 flex flex-col p-1 overflow-hidden relative group`}
        >
          <div className="absolute top-3 left-3 z-30 flex items-center gap-2">
            <span
              className={`w-1.5 h-1.5 rounded-full ${isVideoOn ? 'bg-red-500 animate-pulse shadow-[0_0_8px_red]' : 'bg-zinc-600'}`}
            />
            <span
              className={`text-[9px] font-bold tracking-widest ${isVideoOn ? 'text-red-400/80' : 'text-zinc-600'}`}
            >
              {visionDisplayLabel}
            </span>
          </div>

          {isVideoOn && (
            <button
              aria-label="Switch vision source"
              onClick={toggleSource}
              className="absolute top-2 right-2 z-30 p-1.5 rounded-md bg-black/50 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500 hover:text-black transition-all"
            >
              <RiSwapBoxLine size={14} />
            </button>
          )}

          <div
            className={`w-full h-full rounded-xl overflow-hidden bg-black/20 relative border border-white/5 transition-all ${isVideoOn ? 'opacity-100' : 'opacity-30'}`}
          >
            <video
              key={visionMode}
              ref={setVideoRef}
              className={`absolute inset-0 w-full h-full object-cover ${visionMode === 'camera' ? '-scale-x-100' : ''}`}
              autoPlay
              playsInline
              muted
            />

            <canvas
              ref={canvasRef}
              className="absolute inset-0 w-full h-full object-cover pointer-events-none z-20"
            />

            {!isVideoOn && (
              <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-zinc-500">
                <div className="rounded-full border border-white/10 bg-white/5 p-3">
                  <RiCameraLine size={24} />
                </div>
                <span className="text-[9px] font-mono tracking-widest">NO SIGNAL</span>
              </div>
            )}
          </div>
        </div>

        <div
          className={`${glassPanel} h-32 shrink-0 p-4 flex flex-col justify-between relative overflow-hidden`}
        >
          <div
            className={`absolute inset-0 bg-linear-to-r from-emerald-500/5 to-transparent transition-opacity duration-1000 ${isSystemActive ? 'opacity-100' : 'opacity-0'}`}
          />

          <div className="flex items-center justify-between border-b border-white/10 pb-2 relative z-10">
            <span className="text-[10px] font-bold tracking-widest text-zinc-400 flex items-center gap-1">
              <RiPulseLine className={isSystemActive ? 'text-emerald-500 animate-pulse' : ''} />{' '}
              NETWORK TELEMETRY
            </span>
            <span
              className={`text-[8px] px-2 py-0.5 rounded-full font-mono font-bold border ${isSystemActive ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : 'text-zinc-600 border-zinc-800 bg-zinc-900'}`}
            >
              {isSystemActive ? 'SECURE UPLINK' : 'STANDBY'}
            </span>
          </div>

          <div className="flex items-center justify-between mt-2 relative z-10">
            <div className="flex flex-col">
              <span className="text-[8px] text-zinc-600 font-mono tracking-widest flex items-center gap-1">
                WSS LATENCY
              </span>
              <span className="text-xs font-bold text-emerald-50 font-mono flex items-center gap-1.5 transition-all">
                <RiWifiLine className={isSystemActive ? 'text-emerald-400' : 'text-zinc-600'} />
                {isSystemActive ? `${networkStats.ping}ms` : '--'}
              </span>
            </div>

            <div className="flex flex-col items-center">
              <span className="text-[8px] text-zinc-600 font-mono tracking-widest">
                PACKET RATE
              </span>
              <span className="text-xs font-bold text-emerald-50 font-mono transition-all">
                {isSystemActive ? `${networkStats.rate} MB/s` : '--'}
              </span>
            </div>

            <div className="flex flex-col items-end">
              <span className="text-[8px] text-zinc-600 font-mono tracking-widest">ROUTING</span>
              <span className="text-xs font-bold text-emerald-50 font-mono flex items-center gap-1.5">
                {isSystemActive ? 'GLOBAL' : 'LOCAL'}
                {isSystemActive ? (
                  <RiEarthLine className="text-cyan-400" />
                ) : (
                  <RiServerLine className="text-zinc-500" />
                )}
              </span>
            </div>
          </div>

          <div className="w-full flex flex-col gap-1 mt-3 relative z-10">
            <div className="flex items-center gap-2">
              <span className="text-[7px] font-mono text-zinc-500 w-3">TX</span>
              <div className="flex-1 h-1 bg-black/60 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 shadow-[0_0_8px_#10b981] transition-all duration-300 ease-out"
                  style={{ width: `${isSystemActive ? networkStats.tx : 0}%` }}
                />
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[7px] font-mono text-zinc-500 w-3">RX</span>
              <div className="flex-1 h-1 bg-black/60 rounded-full overflow-hidden">
                <div
                  className="h-full bg-cyan-500 shadow-[0_0_8px_#06b6d4] transition-all duration-300 ease-out delay-75"
                  style={{ width: `${isSystemActive ? networkStats.rx : 0}%` }}
                />
              </div>
            </div>
          </div>
        </div>

      </div>

      <div className="col-span-12 md:col-span-7 lg:col-span-5 relative flex flex-col items-center justify-center min-h-[320px] md:min-h-0">
        <div
          className={`lg:hidden absolute top-4 right-4 w-32 h-28 ${glassPanel} z-50 overflow-hidden ${isVideoOn ? 'block' : 'hidden'}`}
        >
          <div className="absolute top-2 left-2 z-10 rounded bg-black/60 px-2 py-1 text-[8px] font-bold tracking-widest text-emerald-300">
            {visionDisplayLabel}
          </div>
          <video
            ref={setMobileVideoRef}
            className={`w-full h-full object-cover ${visionMode === 'camera' ? '-scale-x-100' : ''}`}
            autoPlay
            playsInline
            muted
          />
        </div>

        <div
          className={`w-[52vh] h-[52vh] md:w-[42vh] md:h-[42vh] lg:w-[60vh] lg:h-[60vh] max-w-full transition-all duration-1000 ${isSystemActive ? 'opacity-100 scale-100' : 'opacity-85 scale-90 grayscale'}`}
        >
          <Sphere />
        </div>

        <div className="absolute bottom-5 md:bottom-8 lg:bottom-10 z-50">
          <div
            className={`${glassPanel} px-4 py-2.5 lg:px-6 lg:py-3 rounded-full flex items-center gap-4 lg:gap-6 border border-emerald-500/20 shadow-[0_0_30px_rgba(0,0,0,0.5)]`}
          >
            <button
              aria-label="Toggle vision source"
              onClick={onVisionClick}
              className={`cursor-pointer p-3 rounded-full transition-all ${isVideoOn ? 'bg-red-500/20 text-red-400' : 'hover:bg-white/10 text-zinc-400'}`}
            >
              {isVideoOn ? <RiSwapBoxLine size={20} /> : <RiCameraLine size={20} />}
            </button>
            <button
              aria-label={isSystemActive ? 'Stop Shell voice' : 'Start Shell voice'}
              onClick={toggleSystem}
              className="relative group mx-2"
            >
              <div
                className={`cursor-pointer p-4 rounded-full border-2 transition-all duration-500 ${isSystemActive ? 'bg-emerald-500 border-emerald-400 text-black shadow-[0_0_20px_#10b981]' : 'bg-red-500/10 border-red-500/50 text-red-500'}`}
              >
                <RiPhoneFill size={24} className={isSystemActive ? 'animate-pulse' : ''} />
              </div>
            </button>
            <button
              aria-label={isMicMuted ? 'Unmute microphone' : 'Mute microphone'}
              onClick={toggleMic}
              className={`cursor-pointer p-3 rounded-full transition-all ${isMicMuted ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/10 text-emerald-400'}`}
            >
              {isMicMuted ? <RiMicOffLine size={20} /> : <RiMicLine size={20} />}
            </button>
            <button
              aria-label="Test Shell voice"
              onClick={() => speakShell('Shell AI real Gemini voice ready hai. Main natural voice mein bol raha hoon.')}
              className={`cursor-pointer p-3 rounded-full transition-all ${speechState === 'SPEAKING' ? 'bg-cyan-500/20 text-cyan-300 shadow-[0_0_14px_rgba(34,211,238,0.35)]' : speechState === 'VOICE ERR' ? 'bg-red-500/20 text-red-300' : 'bg-white/5 text-zinc-400 hover:bg-cyan-500/10 hover:text-cyan-300'}`}
              title={voiceRuntime === 'gemini' ? 'Gemini Live voice' : speechState}
            >
              <RiVolumeUpLine size={20} />
            </button>
          </div>
        </div>
      </div>

      <div className="col-span-12 md:col-span-5 lg:col-span-4 flex flex-col overflow-hidden min-h-[420px] md:min-h-0 md:h-full z-40">
        <div className={`${glassPanel} h-full p-4 lg:p-5 flex flex-col gap-4 border-emerald-500/10 bg-zinc-950/55`}>
          <div className="flex items-start justify-between gap-3 border-b border-emerald-500/10 pb-3">
            <div className="min-w-0">
              <span className="flex items-center gap-2 text-[10px] font-bold tracking-widest text-zinc-300">
                <RiTerminalBoxLine className="text-emerald-400" /> TRANSCRIPT
              </span>
              <div className="mt-1 h-px w-24 bg-linear-to-r from-emerald-400/60 to-transparent" />
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button
                aria-label="Clear transcript"
                onClick={clearTranscript}
                className="cursor-pointer rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-[8px] font-black tracking-widest text-zinc-500 hover:border-red-500/40 hover:bg-red-500/10 hover:text-red-300 transition-all flex items-center gap-1"
              >
                <RiCloseCircleLine size={12} />
                CLEAR
              </button>
              <span
                className={`rounded-full border px-2 py-1 text-[8px] font-mono font-bold ${voiceEventState === 'ERROR' ? 'border-red-500/30 bg-red-500/10 text-red-300' : isSystemActive ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300' : 'border-white/10 bg-white/5 text-zinc-500'}`}
              >
                {voiceDisplayState}
              </span>
            </div>
          </div>
          {imageGenerationState && (
            <div
              className={`shrink-0 overflow-hidden rounded-2xl border p-3 ${
                imageGenerationState.status === 'error'
                  ? 'border-red-500/30 bg-red-500/10'
                  : imageGenerationState.status === 'saved'
                    ? 'border-emerald-500/30 bg-emerald-500/10'
                    : 'border-cyan-500/30 bg-cyan-500/10'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <div
                    className={`text-[9px] font-black tracking-widest ${
                      imageGenerationState.status === 'error'
                        ? 'text-red-300'
                        : imageGenerationState.status === 'saved'
                          ? 'text-emerald-300'
                          : 'text-cyan-300'
                    }`}
                  >
                    {imageGenerationState.message}
                  </div>
                  <div className="mt-1 truncate text-[10px] font-mono text-zinc-400">
                    {imageGenerationState.prompt}
                  </div>
                </div>
                {(imageGenerationState.status === 'generating' ||
                  imageGenerationState.status === 'saving') && (
                  <div className="flex shrink-0 items-end gap-1" aria-label="Image generation animation">
                    {[0, 1, 2, 3].map((item) => (
                      <span
                        key={item}
                        className="block h-5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_12px_rgba(34,211,238,0.75)] animate-pulse"
                        style={{ animationDelay: `${item * 120}ms` }}
                      />
                    ))}
                  </div>
                )}
              </div>
              {(imageGenerationState.status === 'generating' ||
                imageGenerationState.status === 'saving') && (
                <div className="mt-3 h-1 overflow-hidden rounded-full bg-black/50">
                  <div className="h-full w-1/2 animate-[pulse_1.2s_ease-in-out_infinite] rounded-full bg-linear-to-r from-cyan-400 via-emerald-300 to-cyan-400 shadow-[0_0_16px_rgba(16,185,129,0.5)]" />
                </div>
              )}
            </div>
          )}
          <div ref={scrollRef} className="flex-1 min-h-0 overflow-y-auto space-y-4 pr-2 scrollbar-small">
            {chatHistory.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-zinc-700 gap-3 opacity-60">
                <div className="rounded-2xl border border-white/10 bg-black/30 p-4">
                  <RiHistoryLine size={28} />
                </div>
                <span className="text-[9px] tracking-widest uppercase font-mono">
                  No Transcript
                </span>
              </div>
            ) : (
              chatHistory.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                >
                  <span
                    className={`mb-1 px-1 text-[8px] font-black tracking-widest ${msg.role === 'user' ? 'text-emerald-500/60' : 'text-zinc-500'}`}
                  >
                    {msg.role === 'user' ? 'YOU' : 'SHELL'}
                  </span>
                  <div
                    className={`max-w-[96%] py-3 px-3.5 rounded-2xl text-[12px] leading-relaxed border font-mono font-semibold shadow-[0_10px_24px_rgba(0,0,0,0.22)] ${msg.role === 'user' ? 'bg-emerald-500/10 border-emerald-400/20 text-emerald-50 rounded-br-md' : 'bg-black/50 border-white/10 text-zinc-300 rounded-bl-md'}`}
                  >
                    {msg.parts && msg.parts[0] ? msg.parts[0].text : msg.content}
                  </div>
                </div>
              ))
            )}
          </div>
          <div className="shrink-0 border-t border-emerald-500/10 pt-3">
            <div className="flex items-center gap-2 rounded-2xl border border-emerald-500/20 bg-black/70 p-2 shadow-[0_0_28px_rgba(16,185,129,0.08),inset_0_1px_0_rgba(255,255,255,0.04)]">
              <input
                ref={transcriptInputRef}
                value={transcriptPrompt}
                onChange={(event) => setTranscriptPrompt(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') sendTranscriptPrompt()
                }}
                aria-label="Shell command input"
                placeholder="Type to Shell command or image request"
                className="min-w-0 flex-1 bg-transparent px-3 py-3 text-[12px] font-mono text-zinc-100 outline-none placeholder:text-zinc-600"
              />
              <button
                aria-label="Send transcript message"
                onClick={sendTranscriptPrompt}
                disabled={isSendingPrompt}
                className="cursor-pointer h-11 shrink-0 rounded-xl border border-emerald-400/40 bg-emerald-400 px-4 text-black hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-40 transition-all flex items-center gap-2 text-[9px] font-black tracking-widest shadow-[0_0_18px_rgba(52,211,153,0.28)]"
              >
                <RiSendPlane2Line size={16} />
                <span>SEND</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
