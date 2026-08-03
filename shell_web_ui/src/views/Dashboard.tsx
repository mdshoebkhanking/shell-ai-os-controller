import { memo, useEffect, useCallback, useRef, useState, lazy, Suspense } from 'react'
const Sphere = lazy(() => import('@renderer/components/Sphere'))
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
  RiCloseCircleLine,
  RiAttachment2,
  RiCloseLine,
  RiFileTextLine,
  RiFileCopyLine,
  RiFolderOpenLine
} from 'react-icons/ri'
import { VisionMode } from '@renderer/IndexRoot'
import { normalizeGeminiApiKey } from '@renderer/services/api-key-utils'

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
  chatHistory: any[]
  onVisionClick: () => void
  onTranscriptCleared?: () => void
}

type ActivityKind = 'research' | 'image' | 'build' | 'search' | 'file' | 'tool'
type ActivityStatus = 'running' | 'done' | 'error'

type ActivityState = {
  id: string
  kind: ActivityKind
  status: ActivityStatus
  title: string
  prompt: string
  message: string
  progress: number
  startedAt: number
}

type AttachedFile = {
  id: string
  name: string
  type: string
  size: number
  text?: string
  dataUrl?: string
  error?: string
}

type ToolUiAction = {
  type?: string
  label?: string
  path?: string
  message?: string
  url?: string
}

const GEMINI_STARTUP_VOICE_MESSAGE =
  'Shell AI is online. Premium Gemini voice is active. Your private command center is standing by.'
const LOCAL_STARTUP_VOICE_MESSAGE =
  'Command center ready.'

type FaceApiModule = typeof import('face-api.js')

const glassPanel = 'shell-liquid-panel'
const MAX_CHAT_ATTACHMENTS = 4
const WINDOWS_OR_LOW_CORE_DEVICE =
  /Windows/i.test(navigator.userAgent || '') || (navigator.hardwareConcurrency || 0) <= 4
const FACE_SCAN_INTERVAL_MS = WINDOWS_OR_LOW_CORE_DEVICE ? 900 : 250
const VOICE_AMPLITUDE_MIN_PAINT_MS = WINDOWS_OR_LOW_CORE_DEVICE ? 48 : 32
const VOICE_AMPLITUDE_MIN_DELTA = 0.035
const MAX_CHAT_ATTACHMENT_BYTES = 5 * 1024 * 1024
const MAX_TEXT_ATTACHMENT_CHARS = 26000

const ACTIVITY_STEPS: Record<ActivityKind, string[]> = {
  research: ['Parse request', 'Search sources', 'Cross-check facts', 'Prepare answer'],
  image: ['Lock prompt', 'Generate image', 'Save gallery', 'Sync preview'],
  build: ['Plan build', 'Generate files', 'Validate output', 'Package result'],
  search: ['Route query', 'Open source', 'Read result', 'Return summary'],
  file: ['Load file', 'Inspect content', 'Attach context', 'Ready for Shell'],
  tool: ['Route task', 'Run tool', 'Read result', 'Report status']
}

const ACTIVITY_TITLES: Record<ActivityKind, string> = {
  research: 'DEEP RESEARCH',
  image: 'IMAGE GENERATION',
  build: 'BUILD TASK',
  search: 'LIVE SEARCH',
  file: 'FILE CONTEXT',
  tool: 'SHELL ACTION'
}

const ACTIVITY_AGENT_COUNT: Record<ActivityKind, number> = {
  research: 4,
  image: 2,
  build: 3,
  search: 2,
  file: 1,
  tool: 1
}

const clampProgress = (value: unknown, fallback = 18) => {
  const number = Number(value)
  if (!Number.isFinite(number)) return fallback
  return Math.min(100, Math.max(0, Math.round(number)))
}

const coerceActivityKind = (value: unknown): ActivityKind => {
  const kind = String(value || '').toLowerCase()
  if (kind === 'research' || kind === 'image' || kind === 'build' || kind === 'search' || kind === 'file') return kind
  return 'tool'
}

const formatBytes = (size: number) => {
  if (!Number.isFinite(size) || size <= 0) return '0 KB'
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

const isTextLikeFile = (file: File) => {
  const type = (file.type || '').toLowerCase()
  const name = file.name.toLowerCase()
  return (
    type.startsWith('text/') ||
    /\.(txt|md|markdown|json|csv|log|py|js|jsx|ts|tsx|html|css|xml|yaml|yml|ini|env|bat|ps1|sh)$/i.test(name)
  )
}

const readFileAsText = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || '').slice(0, MAX_TEXT_ATTACHMENT_CHARS))
    reader.onerror = () => reject(reader.error || new Error('file text read failed'))
    reader.readAsText(file)
  })

const readFileAsDataUrl = (file: File) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(reader.error || new Error('file data read failed'))
    reader.readAsDataURL(file)
  })

const transcriptMessageText = (message: any) => {
  const partsText = Array.isArray(message?.parts)
    ? message.parts.map((part: any) => String(part?.text || '').trim()).filter(Boolean).join('\n')
    : ''
  return String(partsText || message?.content || message?.text || '').trim()
}

const transcriptRoleLabel = (message: any) =>
  String(message?.role || '').toLowerCase() === 'user' ? 'YOU' : 'SHELL'

const transcriptModeLabel = (message: any) => {
  if (String(message?.role || '').toLowerCase() === 'user') return ''
  return String(message?.modeLabel || '').trim()
}

const transcriptUiActions = (message: any): ToolUiAction[] =>
  Array.isArray(message?.uiActions) ? message.uiActions : Array.isArray(message?.ui_actions) ? message.ui_actions : []

const coerceActivityStatus = (value: unknown): ActivityStatus => {
  const status = String(value || '').toLowerCase()
  if (status === 'done' || status === 'complete' || status === 'completed' || status === 'saved') return 'done'
  if (status === 'error' || status === 'failed' || status === 'fail') return 'error'
  return 'running'
}

const createActivityState = (payload: any, fallbackKind: ActivityKind = 'tool'): ActivityState => {
  const kind = payload?.kind ? coerceActivityKind(payload.kind) : fallbackKind
  const status = coerceActivityStatus(payload?.status)
  const prompt = String(payload?.prompt || payload?.query || payload?.target || payload?.file_name || '').trim()
  return {
    id: String(payload?.id || `${kind}-${Date.now()}`),
    kind,
    status,
    title: String(payload?.title || ACTIVITY_TITLES[kind]),
    prompt,
    message: String(
      payload?.message ||
      (status === 'error'
        ? 'TASK FAILED'
        : status === 'done'
          ? 'TASK COMPLETE'
          : kind === 'research'
            ? 'SEARCHING AND VERIFYING'
            : kind === 'image'
              ? 'GENERATING VISUAL'
              : 'WORKING')
    ),
    progress: clampProgress(payload?.progress, status === 'done' || status === 'error' ? 100 : 18),
    startedAt: Number(payload?.startedAt || Date.now())
  }
}

const compactForSpeech = (value: string, limit = 240) => {
  const cleaned = String(value || '')
    .replace(/\s+/g, ' ')
    .replace(/[{}[\]"`]/g, '')
    .trim()
  if (cleaned.length <= limit) return cleaned
  return `${cleaned.slice(0, limit).replace(/\s+\S*$/, '')}...`
}

const hasBrowserGeminiVoiceKey = () => {
  try {
    return Boolean(normalizeGeminiApiKey(localStorage.getItem('shell_custom_api_key')))
  } catch {
    return false
  }
}

const clampSpeechLevel = (value: unknown) => Math.max(0, Math.min(1, Number(value || 0)))

const speechDurationFromPayload = (payload: any, fallbackText = '') => {
  const durationMs = Number(payload?.durationMs || payload?.audioDurationMs || 0)
  if (Number.isFinite(durationMs) && durationMs > 0) return Math.max(700, Math.min(22000, durationMs))
  const chars = Number(payload?.chars || fallbackText.length || 0)
  return Math.max(900, Math.min(18000, chars * 58 + 520))
}

function DashboardView({
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
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const speechReactionTimersRef = useRef<number[]>([])
  const faceScanInterval = useRef<NodeJS.Timeout | null>(null)
  const faceApiRef = useRef<FaceApiModule | null>(null)
  const voiceAmplitudePaintAtRef = useRef(0)
  const voiceAmplitudeValueRef = useRef(0)
  const lastSpokenRef = useRef('')
  const transcriptPinnedRef = useRef(true)

  const [modelsLoaded, setModelsLoaded] = useState(false)

  const [networkStats, setNetworkStats] = useState({ ping: 24, rate: 1.2, tx: 40, rx: 60 })
  const [transcriptPrompt, setTranscriptPrompt] = useState('')
  const [isSendingPrompt, setIsSendingPrompt] = useState(false)
  const [voiceEventState, setVoiceEventState] = useState(backendVoiceState || 'OFFLINE')
  const [voiceAmplitude, setVoiceAmplitude] = useState(0)
  const [speechState, setSpeechState] = useState('VOICE OUT')
  const [speechReactionActive, setSpeechReactionActive] = useState(false)
  const [activityState, setActivityState] = useState<ActivityState | null>(null)
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([])
  const useGeminiTestVoice = voiceRuntime === 'gemini' && hasBrowserGeminiVoiceKey()
  const testVoiceText = useGeminiTestVoice ? GEMINI_STARTUP_VOICE_MESSAGE : LOCAL_STARTUP_VOICE_MESSAGE

  const readTranscriptPrompt = () => (transcriptPrompt || transcriptInputRef.current?.value || '').trim()

  const updateVoiceAmplitude = useCallback((value: unknown, force = false) => {
    const next = clampSpeechLevel(value)
    const now = performance.now()
    if (
      !force &&
      now - voiceAmplitudePaintAtRef.current < VOICE_AMPLITUDE_MIN_PAINT_MS &&
      Math.abs(next - voiceAmplitudeValueRef.current) < VOICE_AMPLITUDE_MIN_DELTA
    ) {
      return
    }
    voiceAmplitudePaintAtRef.current = now
    voiceAmplitudeValueRef.current = next
    setVoiceAmplitude(next)
  }, [])

  const clearSpeechReaction = useCallback(() => {
    speechReactionTimersRef.current.forEach((timer) => window.clearTimeout(timer))
    speechReactionTimersRef.current = []
    setSpeechReactionActive(false)
  }, [])

  const runSpeechReaction = useCallback((payload: any = {}, fallbackText = '') => {
    clearSpeechReaction()
    setSpeechReactionActive(true)
    const durationMs = speechDurationFromPayload(payload, fallbackText)
    const frameMs = Math.max(45, Math.min(140, Number(payload?.amplitudeFrameMs || 70)))
    const frames = Array.isArray(payload?.amplitudeFrames)
      ? payload.amplitudeFrames.map(clampSpeechLevel).filter((value: number) => Number.isFinite(value))
      : []

    if (frames.length) {
      frames.forEach((level: number, index: number) => {
        const timer = window.setTimeout(() => {
          updateVoiceAmplitude(Math.max(0.08, Math.min(1, level)))
        }, index * frameMs)
        speechReactionTimersRef.current.push(timer)
      })
    } else {
      const frameCount = Math.max(8, Math.ceil(durationMs / frameMs))
      for (let index = 0; index < frameCount; index += 1) {
        const timer = window.setTimeout(() => {
          const wave = Math.abs(Math.sin(index * 0.9)) * 0.42
          const consonants = Math.abs(Math.sin(index * 0.37 + fallbackText.length * 0.11)) * 0.22
          updateVoiceAmplitude(Math.min(1, 0.14 + wave + consonants))
        }, index * frameMs)
        speechReactionTimersRef.current.push(timer)
      }
    }

    const finishTimer = window.setTimeout(() => {
      updateVoiceAmplitude(0, true)
      setSpeechReactionActive(false)
      setSpeechState('VOICE OUT')
      speechReactionTimersRef.current = []
    }, durationMs + 180)
    speechReactionTimersRef.current.push(finishTimer)
  }, [clearSpeechReaction, updateVoiceAmplitude])

  const onTranscriptScroll = () => {
    const node = scrollRef.current
    if (!node) return
    transcriptPinnedRef.current = node.scrollHeight - node.scrollTop - node.clientHeight < 40
  }

  const speakShell = useCallback(async (text: string) => {
    const speechText = compactForSpeech(text)
    if (!speechText) return
    clearSpeechReaction()
    updateVoiceAmplitude(0, true)
    setSpeechState('VOICE QUEUED')
    try {
      if (voiceRuntime === 'gemini' && speakRealVoice) {
        let didSendToRealVoice = false
        try {
          didSendToRealVoice = await speakRealVoice(speechText)
        } catch {
          didSendToRealVoice = false
        }
        if (didSendToRealVoice) {
          setSpeechState('GEMINI LIVE')
          return
        }
      }

      const result = await window.shellAPI?.speakText?.(speechText)
      if (result && (result as any)?.success !== false) {
        if ((result as any)?.queued) {
          updateVoiceAmplitude(0, true)
          setSpeechState('VOICE QUEUED')
          return
        }
        setSpeechState('SPEAKING')
        runSpeechReaction(result, speechText)
        return
      }

      clearSpeechReaction()
      updateVoiceAmplitude(0, true)
      setSpeechState('VOICE ERR')
    } catch {
      clearSpeechReaction()
      updateVoiceAmplitude(0, true)
      setSpeechState('VOICE ERR')
    }
  }, [clearSpeechReaction, runSpeechReaction, speakRealVoice, updateVoiceAmplitude, voiceRuntime])

  useEffect(() => {
    if (scrollRef.current && transcriptPinnedRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [chatHistory])

  useEffect(() => {
    setVoiceEventState(backendVoiceState || 'OFFLINE')
  }, [backendVoiceState])

  useEffect(() => {
    if (!window.shellAPI) return
    const onVoiceStatus = (_event: unknown, payload?: any) => {
      setVoiceEventState(String(payload?.state || 'unknown').toUpperCase())
    }
    let amplitudeDecayTimer: number | undefined
    const onVoiceAmplitude = (_event: unknown, payload?: any) => {
      const value = Math.max(0, Math.min(1, Number(payload?.value || 0)))
      updateVoiceAmplitude(value)
      if (amplitudeDecayTimer) window.clearTimeout(amplitudeDecayTimer)
      amplitudeDecayTimer = window.setTimeout(() => updateVoiceAmplitude(0, true), 240)
    }
    const onSpeechStatus = (_event: unknown, payload?: any) => {
      const state = String(payload?.state || 'ready').toUpperCase()
      if (state === 'QUEUED') {
        clearSpeechReaction()
        updateVoiceAmplitude(0, true)
        setSpeechState('VOICE QUEUED')
        return
      }
      if (state === 'SPEAKING') {
        setSpeechState('SPEAKING')
        runSpeechReaction(payload, String(payload?.text || payload?.message || '').trim())
        return
      }
      clearSpeechReaction()
      updateVoiceAmplitude(0, true)
      setSpeechState(state === 'ERROR' ? 'VOICE ERR' : 'VOICE OUT')
    }
    const onChatUpdated = (_event: unknown, payload?: any) => {
      const reply = String(payload?.reply || '').trim()
      if (!reply || reply === lastSpokenRef.current) return
      if (payload?.source !== 'voice' && payload?.voice !== true) return
      lastSpokenRef.current = reply
      speakShell(reply)
    }
    window.shellAPI.on('voice-status', onVoiceStatus)
    window.shellAPI.on('voice-amplitude', onVoiceAmplitude)
    window.shellAPI.on('speech-status', onSpeechStatus)
    window.shellAPI.on('chat-updated', onChatUpdated)
    return () => {
      if (amplitudeDecayTimer) window.clearTimeout(amplitudeDecayTimer)
      clearSpeechReaction()
      window.shellAPI?.off('voice-status', onVoiceStatus)
      window.shellAPI?.off('voice-amplitude', onVoiceAmplitude)
      window.shellAPI?.off('speech-status', onSpeechStatus)
      window.shellAPI?.off('chat-updated', onChatUpdated)
    }
  }, [clearSpeechReaction, runSpeechReaction, speakShell, updateVoiceAmplitude])

  useEffect(() => {
    const normalizePrompt = (value: unknown, fallback = 'Shell AI task') =>
      String(value || '').trim() || fallback
    const setImageActivity = (payload: any) => {
      const prompt = normalizePrompt(payload?.prompt || payload?.image?.displayName, 'Shell AI image')
      if (payload?.loading) {
        setActivityState(createActivityState({
          id: payload?.id,
          kind: 'image',
          status: 'running',
          title: 'IMAGE GENERATION',
          prompt,
          message: 'GENERATING VISUAL',
          progress: payload?.progress || 38
        }, 'image'))
        return
      }
      if (payload?.error) {
        setActivityState(createActivityState({
          id: payload?.id,
          kind: 'image',
          status: 'error',
          title: 'IMAGE GENERATION',
          prompt,
          message: String(payload?.errorMessage || 'IMAGE GENERATION FAILED').slice(0, 180),
          progress: 100
        }, 'image'))
        return
      }
      if (payload?.saved || payload?.image?.filename) {
        setActivityState(createActivityState({
          id: payload?.id,
          kind: 'image',
          status: 'done',
          title: 'IMAGE GENERATION',
          prompt,
          message: 'SAVED TO GALLERY',
          progress: 100
        }, 'image'))
        return
      }
      if (payload?.url) {
        setActivityState(createActivityState({
          id: payload?.id,
          kind: 'image',
          status: 'running',
          title: 'IMAGE GENERATION',
          prompt,
          message: 'SAVING TO GALLERY',
          progress: 82
        }, 'image'))
      }
    }
    const setWorkActivity = (payload: any, fallbackKind: ActivityKind = 'tool') => {
      setActivityState(createActivityState(payload || {}, fallbackKind))
    }
    const onDomImageGeneration = (event: Event) =>
      setImageActivity((event as CustomEvent).detail || {})
    const onBridgeImageGeneration = (_event: unknown, payload?: unknown) =>
      setImageActivity(payload)
    const onActivityUpdated = (_event: unknown, payload?: unknown) =>
      setWorkActivity(payload, 'tool')
    const onGalleryUpdated = (_event: unknown, payload?: any) => {
      if (!payload?.image) return
      setActivityState((current) => {
        if (!current || current.kind !== 'image' || current.status !== 'running') return current
        return createActivityState({
          ...current,
          status: 'done',
          prompt: normalizePrompt(payload.image.displayName || current.prompt, 'Shell AI image'),
          message: 'SAVED TO GALLERY',
          progress: 100
        }, 'image')
      })
    }
    const onDeepResearchStart = (event: Event) => {
      const detail = (event as CustomEvent).detail || {}
      setWorkActivity({
        id: detail.id,
        kind: 'research',
        status: 'running',
        title: 'DEEP RESEARCH',
        prompt: normalizePrompt(detail.query, 'Research task'),
        message: 'SEARCHING AND VERIFYING',
        progress: 18
      }, 'research')
    }
    const onDeepResearchDone = (event: Event) => {
      const detail = (event as CustomEvent).detail || {}
      setWorkActivity({
        id: detail.id,
        kind: 'research',
        status: detail.success === false ? 'error' : 'done',
        title: 'DEEP RESEARCH',
        prompt: normalizePrompt(detail.query, 'Research task'),
        message: detail.success === false ? 'RESEARCH FAILED' : 'RESEARCH COMPLETE',
        progress: 100
      }, 'research')
    }
    const onSemanticStart = (event: Event) => {
      const detail = (event as CustomEvent).detail || {}
      setWorkActivity({
        kind: 'search',
        status: 'running',
        title: 'SEMANTIC SEARCH',
        prompt: normalizePrompt(detail.target, 'Workspace search'),
        message: `${normalizePrompt(detail.mode, 'SEARCH').toUpperCase()} IN PROGRESS`,
        progress: 22
      }, 'search')
    }
    const onSemanticDone = (event: Event) => {
      const detail = (event as CustomEvent).detail || {}
      setWorkActivity({
        kind: 'search',
        status: detail.success === false ? 'error' : 'done',
        title: 'SEMANTIC SEARCH',
        message: detail.success === false ? 'SEARCH FAILED' : 'SEARCH COMPLETE',
        progress: 100
      }, 'search')
    }
    const onOracleProgress = (event: Event) => {
      const detail = (event as CustomEvent).detail || {}
      setWorkActivity({
        kind: 'research',
        status: 'running',
        title: 'RAG ORACLE',
        prompt: normalizePrompt(detail.path || detail.query || detail.message, 'Knowledge task'),
        message: normalizePrompt(detail.message || detail.stage, 'INDEXING SOURCES').toUpperCase(),
        progress: clampProgress(detail.progress, 44)
      }, 'research')
    }
    const onOracleDone = (event: Event) => {
      const detail = (event as CustomEvent).detail || {}
      setWorkActivity({
        kind: 'research',
        status: detail.success === false ? 'error' : 'done',
        title: 'RAG ORACLE',
        message: detail.success === false ? 'ORACLE FAILED' : 'ORACLE COMPLETE',
        progress: 100
      }, 'research')
    }
    const onAiStartCoding = (event: Event) => {
      const detail = (event as CustomEvent).detail || {}
      setWorkActivity({
        kind: 'build',
        status: 'running',
        title: 'CODE BUILD',
        prompt: normalizePrompt(detail.prompt || detail.file_name, 'Build task'),
        message: 'GENERATING FILE',
        progress: 28
      }, 'build')
    }

    window.addEventListener('image-gen', onDomImageGeneration)
    window.addEventListener('deep-research-start', onDeepResearchStart)
    window.addEventListener('deep-research-done', onDeepResearchDone)
    window.addEventListener('semantic-start', onSemanticStart)
    window.addEventListener('semantic-done', onSemanticDone)
    window.addEventListener('oracle-progress', onOracleProgress)
    window.addEventListener('oracle-ingest-start', onOracleProgress)
    window.addEventListener('oracle-ingest-done', onOracleDone)
    window.addEventListener('oracle-answered', onOracleDone)
    window.addEventListener('ai-start-coding', onAiStartCoding)
    window.shellAPI?.on?.('image-gen', onBridgeImageGeneration)
    window.shellAPI?.on?.('gallery-updated', onGalleryUpdated)
    window.shellAPI?.on?.('activity-updated', onActivityUpdated)
    return () => {
      window.removeEventListener('image-gen', onDomImageGeneration)
      window.removeEventListener('deep-research-start', onDeepResearchStart)
      window.removeEventListener('deep-research-done', onDeepResearchDone)
      window.removeEventListener('semantic-start', onSemanticStart)
      window.removeEventListener('semantic-done', onSemanticDone)
      window.removeEventListener('oracle-progress', onOracleProgress)
      window.removeEventListener('oracle-ingest-start', onOracleProgress)
      window.removeEventListener('oracle-ingest-done', onOracleDone)
      window.removeEventListener('oracle-answered', onOracleDone)
      window.removeEventListener('ai-start-coding', onAiStartCoding)
      window.shellAPI?.off?.('image-gen', onBridgeImageGeneration)
      window.shellAPI?.off?.('gallery-updated', onGalleryUpdated)
      window.shellAPI?.off?.('activity-updated', onActivityUpdated)
    }
  }, [])

  useEffect(() => {
    if (!activityState || activityState.status === 'running') return
    const timeout = window.setTimeout(() => {
      setActivityState((current) => (current?.id === activityState.id ? null : current))
    }, activityState.status === 'error' ? 9000 : 5200)
    return () => window.clearTimeout(timeout)
  }, [activityState?.id, activityState?.status])

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
    if (!isVideoOn || visionMode !== 'camera' || modelsLoaded) return
    let cancelled = false
    const loadModels = async () => {
      try {
        const faceapi = await import('face-api.js')
        const MODEL_URL = './models'
        await Promise.all([
          faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL),
          faceapi.nets.faceExpressionNet.loadFromUri(MODEL_URL),
          faceapi.nets.ageGenderNet.loadFromUri(MODEL_URL)
        ])
        if (!cancelled) {
          faceApiRef.current = faceapi
          setModelsLoaded(true)
        }
      } catch (e) { }
    }
    loadModels()
    return () => {
      cancelled = true
    }
  }, [isVideoOn, visionMode, modelsLoaded])

  useEffect(() => {
    if (
      isVideoOn &&
      visionMode === 'camera' &&
      modelsLoaded &&
      faceApiRef.current &&
      videoElementRef.current &&
      canvasRef.current
    ) {
      const faceapi = faceApiRef.current
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

            ctx.strokeStyle = '#60a5fa'
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

            ctx.fillStyle = '#60a5fa'
            ctx.font = 'bold 16px monospace'
            ctx.fillText(labelText, mirroredX + 5, y - 14)
          } else {
            ctx.fillStyle = 'rgba(96, 165, 250, 0.82)'
            ctx.font = 'bold 14px monospace'
            ctx.fillText('SCANNING OPTICS...', 20, 30)
          }
        } catch (e) { }
      }, FACE_SCAN_INTERVAL_MS)
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
        node.onloadedmetadata = () => node.play().catch(() => { })
      }
    },
    [activeStream, isVideoOn, visionMode]
  )

  const setMobileVideoRef = useCallback(
    (node: HTMLVideoElement | null) => {
      if (node && activeStream && isVideoOn) {
        node.srcObject = activeStream
        node.onloadedmetadata = () => node.play().catch(() => { })
      }
    },
    [activeStream, isVideoOn, visionMode]
  )

  const toggleSource = () => {
    const nextMode = visionMode === 'camera' ? 'screen' : 'camera'
    startVision(nextMode)
  }

  const attachFiles = async (files: FileList | null) => {
    const selected = Array.from(files || []).slice(0, Math.max(0, MAX_CHAT_ATTACHMENTS - attachedFiles.length))
    if (!selected.length) return
    const prepared: AttachedFile[] = []
    for (const file of selected) {
      const base = {
        id: `${file.name}-${file.size}-${file.lastModified}-${Date.now()}`,
        name: file.name,
        type: file.type || 'application/octet-stream',
        size: file.size
      }
      if (file.size > MAX_CHAT_ATTACHMENT_BYTES) {
        prepared.push({ ...base, error: `Too large: ${formatBytes(file.size)}` })
        continue
      }
      try {
        if (isTextLikeFile(file)) {
          prepared.push({ ...base, text: await readFileAsText(file) })
        } else {
          prepared.push({ ...base, dataUrl: await readFileAsDataUrl(file) })
        }
      } catch (error) {
        prepared.push({ ...base, error: error instanceof Error ? error.message : 'Could not read file' })
      }
    }
    setAttachedFiles((current) => [...current, ...prepared].slice(0, MAX_CHAT_ATTACHMENTS))
    setActivityState(createActivityState({
      kind: 'file',
      status: 'done',
      title: 'FILE CONTEXT',
      prompt: prepared.map((item) => item.name).join(', '),
      message: 'FILES ATTACHED',
      progress: 100
    }, 'file'))
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const removeAttachedFile = (id: string) => {
    setAttachedFiles((current) => current.filter((item) => item.id !== id))
  }

  const sendTranscriptPrompt = async (overrideText = '') => {
    const cleanOverride = typeof overrideText === 'string' ? overrideText : ''
    const text = cleanOverride.trim() || readTranscriptPrompt()
    if ((!text && attachedFiles.length === 0) || isSendingPrompt) return
    setIsSendingPrompt(true)
    setTranscriptPrompt('')
    transcriptPinnedRef.current = true
    const attachments = attachedFiles
    setAttachedFiles([])
    try {
      await window.electron?.ipcRenderer.invoke('chat-message', text, {
        source: 'text',
        entry: 'chart',
        attachments
      })
    } finally {
      setIsSendingPrompt(false)
    }
  }

  const runTranscriptAction = useCallback(async (action: ToolUiAction) => {
    const actionType = String(action?.type || '').toUpperCase()
    const path = String(action?.path || '').trim()
    if (actionType === 'OPEN_FILE_LOCATION' && path) {
      await window.electron?.ipcRenderer.invoke('open-image-location', path)
      return
    }
    if (actionType === 'OPEN_URL') {
      const url = String(action?.url || '').trim()
      if (url) await window.shellAPI?.call('open-url', url)
      return
    }
    if (actionType === 'APPROVE_ACTION') {
      await sendTranscriptPrompt(String(action?.message || 'yes').trim())
    }
  }, [sendTranscriptPrompt])

  const clearTranscript = async () => {
    try {
      await window.electron?.ipcRenderer.invoke('clear-history')
    } finally {
      lastSpokenRef.current = ''
      onTranscriptCleared?.()
    }
  }

  const copyTranscript = async () => {
    const text = chatHistory
      .map((message) => {
        const body = transcriptMessageText(message)
        return body ? `${transcriptRoleLabel(message)}: ${body}` : ''
      })
      .filter(Boolean)
      .join('\n\n')
    if (!text.trim()) return

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text)
      } else {
        const scratch = document.createElement('textarea')
        scratch.value = text
        scratch.setAttribute('readonly', 'true')
        scratch.style.position = 'fixed'
        scratch.style.left = '-9999px'
        document.body.appendChild(scratch)
        scratch.select()
        document.execCommand('copy')
        document.body.removeChild(scratch)
      }
      setActivityState(createActivityState({
        kind: 'file',
        status: 'done',
        title: 'TRANSCRIPT',
        message: 'COPIED',
        progress: 100
      }, 'file'))
    } catch {
      setActivityState(createActivityState({
        kind: 'file',
        status: 'error',
        title: 'TRANSCRIPT',
        message: 'COPY FAILED',
        progress: 100
      }, 'file'))
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
  const activitySteps = activityState ? ACTIVITY_STEPS[activityState.kind] : []
  const activityStepIndex = activityState
    ? activityState.status === 'done'
      ? activitySteps.length - 1
      : Math.min(activitySteps.length - 1, Math.max(0, Math.floor((activityState.progress / 100) * activitySteps.length)))
    : 0
  const activeAgentCount =
    activityState?.status === 'running' ? ACTIVITY_AGENT_COUNT[activityState.kind] || 1 : 0
  const agentStripCountText = `${activeAgentCount} ${activeAgentCount === 1 ? 'AGENT' : 'AGENTS'}`
  const orbSpeaking = speechState === 'SPEAKING' || speechState === 'GEMINI LIVE' || speechReactionActive
  const activityPanel = activityState ? (
    <div className="shell-workstream-anchor" aria-live="polite">
      <div className={`shell-workstream-panel shell-workstream-${activityState.status} shell-workstream-${activityState.kind}`}>
        <div className="shell-workstream-head">
          <span>LIVE WORK</span>
          <span className="shell-workstream-badge">
            {activityState.status === 'running'
              ? 'ACTIVE'
              : activityState.status === 'done'
                ? 'COMPLETE'
                : 'ATTENTION'}
          </span>
        </div>
        <div className="shell-workstream-core">
          <div className="shell-workstream-orb" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div className="min-w-0">
            <div className="shell-workstream-title">{activityState.title}</div>
            <div className="shell-workstream-message">{activityState.message}</div>
            {activityState.prompt && <div className="shell-workstream-prompt">{activityState.prompt}</div>}
          </div>
        </div>
        <div className="shell-workstream-progress-row" aria-hidden="true">
          <div className="shell-workstream-progress">
            <span style={{ width: `${activityState.progress}%` }} />
          </div>
          <span>{activityState.progress}%</span>
        </div>
        <div className="shell-workstream-steps">
          {activitySteps.map((step, index) => (
            <span
              key={step}
              className={
                index < activityStepIndex || activityState.status === 'done'
                  ? 'is-complete'
                  : index === activityStepIndex && activityState.status === 'running'
                    ? 'is-active'
                    : ''
              }
            >
              {step}
            </span>
          ))}
        </div>
      </div>
    </div>
  ) : null

  return (
    <div className="flex-1 p-4 grid grid-cols-12 gap-4 h-full overflow-y-auto md:overflow-hidden relative w-full scrollbar-small">
      <div className="hidden xl:flex xl:col-span-3 flex-col gap-4 h-full z-40 overflow-y-auto pr-1 scrollbar-small">
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
              className="shell-control-button absolute top-2 right-2 z-30 p-1.5 rounded-lg bg-black/50 text-blue-300 border border-blue-500/20 hover:bg-blue-500 hover:text-black"
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
            className={`absolute inset-0 bg-linear-to-r from-blue-500/10 to-transparent transition-opacity duration-700 ${isSystemActive ? 'opacity-100' : 'opacity-0'}`}
          />

          <div className="flex items-center justify-between border-b border-white/10 pb-2 relative z-10">
            <span className="text-[10px] font-bold tracking-widest text-zinc-400 flex items-center gap-1">
              <RiPulseLine className={isSystemActive ? 'text-blue-400 animate-pulse' : ''} />{' '}
              NETWORK TELEMETRY
            </span>
            <span
              className={`text-[8px] px-2 py-0.5 rounded-full font-mono font-bold border ${isSystemActive ? 'text-blue-300 border-blue-500/30 bg-blue-500/10' : 'text-zinc-600 border-zinc-800 bg-zinc-900'}`}
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
                <RiWifiLine className={isSystemActive ? 'text-blue-300' : 'text-zinc-600'} />
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
                  className="h-full bg-blue-500 shadow-[0_0_8px_rgba(96,165,250,0.8)] transition-all duration-300 ease-out"
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

        {activityPanel}

      </div>

      <div className="col-span-12 md:col-span-7 xl:col-span-5 relative flex flex-col items-center justify-center min-h-[320px] md:min-h-0">
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
          className={`w-[60vh] h-[60vh] max-w-full transition-opacity duration-300 ${isSystemActive ? 'opacity-100 scale-100' : 'opacity-92 scale-95'}`}
        >
          <Suspense fallback={<div className="w-full h-full rounded-full border border-blue-500/20 bg-blue-500/5 animate-pulse flex items-center justify-center text-[10px] text-blue-400 font-mono tracking-widest">LOADING CORE...</div>}>
            <Sphere
              active={isSystemActive}
              speaking={orbSpeaking}
              voiceLevel={voiceAmplitude}
            />
          </Suspense>
        </div>

        <div className="shell-orb-dock-anchor absolute">
          <div
            className="shell-liquid-dock shell-session-dock flex items-center"
          >
            <button
              type="button"
              aria-label="Toggle vision source"
              aria-pressed={isVideoOn}
              onClick={onVisionClick}
              className={`shell-control-button shell-dock-button cursor-pointer ${isVideoOn ? 'shell-dock-button-active' : ''
                }`}
              title={isVideoOn ? 'Switch vision source' : 'Start camera or screen vision'}
            >
              {isVideoOn ? <RiSwapBoxLine size={20} /> : <RiCameraLine size={20} />}
            </button>
            <button
              type="button"
              aria-label={isSystemActive ? 'Stop Shell voice' : 'Start Shell voice'}
              aria-pressed={isSystemActive}
              onClick={toggleSystem}
              className={`shell-control-button shell-dock-button shell-dock-button-main cursor-pointer ${isSystemActive ? 'shell-dock-button-live' : ''
                }`}
              title={isSystemActive ? 'Stop Shell voice' : 'Start Shell voice'}
            >
              <RiPhoneFill size={24} />
            </button>
            <button
              type="button"
              aria-label={isMicMuted ? 'Unmute microphone' : 'Mute microphone'}
              aria-pressed={!isMicMuted}
              onClick={toggleMic}
              className={`shell-control-button shell-dock-button cursor-pointer ${isMicMuted ? 'shell-dock-button-danger' : 'shell-dock-button-active'
                }`}
              title={isMicMuted ? 'Unmute microphone' : 'Mute microphone'}
            >
              {isMicMuted ? <RiMicOffLine size={20} /> : <RiMicLine size={20} />}
            </button>
            <button
              type="button"
              aria-label="Test Shell voice"
              aria-pressed={speechState === 'SPEAKING'}
              onClick={() => speakShell(testVoiceText)}
              className={`shell-control-button shell-dock-button cursor-pointer ${speechState === 'SPEAKING'
                  ? 'shell-dock-button-speaking'
                  : speechState === 'VOICE ERR'
                    ? 'shell-dock-button-danger'
                    : ''
                }`}
              title={voiceRuntime === 'gemini' ? 'Gemini Live voice' : 'Local Shell voice'}
            >
              <RiVolumeUpLine size={20} />
            </button>
          </div>
        </div>
      </div>

      <div className="col-span-12 md:col-span-5 xl:col-span-4 flex flex-col overflow-hidden min-h-[420px] md:min-h-0 md:h-full z-40">
        <div className={`${glassPanel} h-full p-4 lg:p-5 flex flex-col gap-4 border-blue-500/10 bg-slate-950/55`}>
          <div className="flex items-start justify-between gap-3 border-b border-blue-500/10 pb-3">
            <div className="min-w-0">
              <span className="flex items-center gap-2 text-[10px] font-bold tracking-widest text-zinc-300">
                <RiTerminalBoxLine className="text-blue-300" /> TRANSCRIPT
              </span>
              <div className="mt-1 h-px w-24 bg-linear-to-r from-blue-400/70 to-transparent" />
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <button
                aria-label="Copy transcript"
                onClick={copyTranscript}
                disabled={chatHistory.length === 0}
                className="cursor-pointer rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-[8px] font-black tracking-widest text-zinc-500 hover:border-blue-500/40 hover:bg-blue-500/10 hover:text-blue-200 transition-all flex items-center gap-1 disabled:cursor-not-allowed disabled:opacity-40"
              >
                <RiFileCopyLine size={12} />
                COPY
              </button>
              <button
                aria-label="Clear transcript"
                onClick={clearTranscript}
                className="cursor-pointer rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-[8px] font-black tracking-widest text-zinc-500 hover:border-red-500/40 hover:bg-red-500/10 hover:text-red-300 transition-all flex items-center gap-1"
              >
                <RiCloseCircleLine size={12} />
                CLEAR
              </button>
              <span
                className={`rounded-full border px-2 py-1 text-[8px] font-mono font-bold ${voiceEventState === 'ERROR' ? 'border-red-500/30 bg-red-500/10 text-red-300' : isSystemActive ? 'border-blue-500/30 bg-blue-500/10 text-blue-300' : 'border-white/10 bg-white/5 text-zinc-500'}`}
              >
                {voiceDisplayState}
              </span>
            </div>
          </div>
          <div
            ref={scrollRef}
            onScroll={onTranscriptScroll}
            className="flex-1 min-h-0 overflow-y-auto overscroll-contain space-y-4 pr-2 scrollbar-small select-text"
          >
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
              chatHistory.map((msg, idx) => {
                const actions = transcriptUiActions(msg)
                return (
                  <div
                    key={idx}
                    className={`flex flex-col select-text ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
                  >
                    <span
                      className={`mb-1 px-1 text-[8px] font-black tracking-widest ${msg.role === 'user' ? 'text-blue-300/70' : 'text-zinc-500'}`}
                    >
                      {transcriptRoleLabel(msg)}
                    </span>
                    {transcriptModeLabel(msg) && (
                      <span className="mb-1 inline-flex items-center rounded-full border border-emerald-400/20 bg-emerald-400/10 px-2 py-0.5 text-[8px] font-black uppercase tracking-widest text-emerald-100">
                        {transcriptModeLabel(msg)}
                      </span>
                    )}
                    <div
                      className={`max-w-[96%] py-3 px-3.5 rounded-2xl text-[12px] leading-relaxed border font-mono font-semibold shadow-[0_10px_24px_rgba(0,0,0,0.22)] select-text ${msg.role === 'user' ? 'bg-blue-500/10 border-blue-400/25 text-blue-50 rounded-br-md' : 'bg-black/45 border-white/10 text-zinc-300 rounded-bl-md'}`}
                    >
                      {transcriptMessageText(msg)}
                    </div>
                    {msg.role !== 'user' && actions.length > 0 && (
                      <div className="mt-2 flex max-w-[96%] flex-wrap gap-2">
                        {actions.map((action, actionIdx) => (
                          <button
                            key={`${idx}-${actionIdx}-${action.type || 'action'}`}
                            type="button"
                            onClick={() => runTranscriptAction(action)}
                            className="inline-flex h-7 items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.06] px-3 text-[9px] font-black uppercase tracking-widest text-zinc-200 hover:border-sky-300/40 hover:bg-sky-300/10 focus:outline-none focus:ring-2 focus:ring-sky-300/35"
                          >
                            <RiFolderOpenLine size={13} />
                            {String(action.label || 'Open folder')}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                )
              })
            )}
          </div>
          <div className="shrink-0 border-t border-blue-500/10 pt-3">
            <div className="mb-1 flex justify-end" aria-live="polite">
              <span
                className={`inline-flex h-5 items-center gap-1 rounded-full border px-2 text-[8px] font-black tracking-widest ${activeAgentCount
                    ? 'border-emerald-400/25 bg-emerald-400/10 text-emerald-100'
                    : 'border-white/10 bg-white/[0.03] text-zinc-500'
                  }`}
                title="Active agents for this task"
              >
                <span className={`h-1.5 w-1.5 rounded-full ${activeAgentCount ? 'bg-emerald-300 animate-pulse' : 'bg-zinc-600'}`} />
                {agentStripCountText}
              </span>
            </div>
            {attachedFiles.length > 0 && (
              <div className="shell-attachment-tray" aria-label="Attached files">
                {attachedFiles.map((file) => (
                  <div
                    key={file.id}
                    className={`shell-attachment-chip ${file.error ? 'shell-attachment-error' : ''}`}
                    title={`${file.name} (${formatBytes(file.size)})${file.error ? ` - ${file.error}` : ''}`}
                  >
                    <RiFileTextLine size={13} />
                    <span>{file.name}</span>
                    <small>{file.error || formatBytes(file.size)}</small>
                    <button
                      type="button"
                      aria-label={`Remove ${file.name}`}
                      onClick={() => removeAttachedFile(file.id)}
                      className="shell-control-button"
                    >
                      <RiCloseLine size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
            <div className="flex items-center gap-2 rounded-2xl border border-blue-500/20 bg-black/55 p-2 shadow-[0_0_28px_rgba(96,165,250,0.08),inset_0_1px_0_rgba(255,255,255,0.06)]">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={(event) => attachFiles(event.target.files)}
              />
              <button
                aria-label="Attach files to Shell"
                onClick={() => fileInputRef.current?.click()}
                disabled={attachedFiles.length >= MAX_CHAT_ATTACHMENTS}
                className="shell-control-button shell-attach-button cursor-pointer h-11 w-11 shrink-0 rounded-xl border disabled:cursor-not-allowed disabled:opacity-40"
                title="Attach file"
              >
                <RiAttachment2 size={16} />
              </button>
              <input
                ref={transcriptInputRef}
                value={transcriptPrompt}
                onChange={(event) => setTranscriptPrompt(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') sendTranscriptPrompt()
                }}
                aria-label="Shell command input"
                placeholder={attachedFiles.length ? 'Ask Shell about attached files' : 'Type to Shell command or image request'}
                className="min-w-0 flex-1 bg-transparent px-3 py-3 text-[12px] font-mono text-zinc-100 outline-none placeholder:text-zinc-600"
              />
              <button
                aria-label="Send transcript message"
                onClick={sendTranscriptPrompt}
                disabled={isSendingPrompt}
                className="shell-control-button shell-primary-action cursor-pointer h-11 shrink-0 rounded-xl border px-4 text-black disabled:cursor-not-allowed disabled:opacity-40 flex items-center gap-2 text-[9px] font-black tracking-widest"
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

const areDashboardShellPropsEqual = (previous: ShellProps, next: ShellProps) =>
  previous.isSystemActive === next.isSystemActive &&
  previous.isMicMuted === next.isMicMuted &&
  previous.isVideoOn === next.isVideoOn &&
  previous.visionMode === next.visionMode &&
  previous.activeStream === next.activeStream &&
  previous.backendVoiceState === next.backendVoiceState &&
  previous.voiceRuntime === next.voiceRuntime &&
  previous.toggleSystem === next.toggleSystem &&
  previous.toggleMic === next.toggleMic &&
  previous.startVision === next.startVision &&
  previous.stopVision === next.stopVision &&
  previous.speakRealVoice === next.speakRealVoice

export default memo(
  DashboardView,
  (previous, next) =>
    previous.chatHistory === next.chatHistory &&
    previous.onVisionClick === next.onVisionClick &&
    previous.onTranscriptCleared === next.onTranscriptCleared &&
    areDashboardShellPropsEqual(previous.props, next.props)
)
