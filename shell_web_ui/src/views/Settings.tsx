import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { motion } from 'framer-motion'
import { GiArtificialIntelligence } from 'react-icons/gi'
import {
  RiKey2Line,
  RiSave3Line,
  RiUserVoiceLine,
  RiUserLine,
  RiRecordCircleLine,
  RiLock2Line,
  RiSettings4Line,
  RiShieldKeyholeLine,
  RiPlugLine,
  RiBrainLine,
  RiCloudLine,
  RiCpuLine,
  RiTerminalWindowLine,
  RiRefreshLine,
  RiDownloadCloud2Line,
  RiRocketLine,
  RiTelegramLine,
  RiTranslate2,
  RiInstagramLine,
  RiWhatsappLine,
  RiMailLine
} from 'react-icons/ri'
import { normalizeGeminiApiKey } from '../services/api-key-utils'
import { sendWhatsAppMessage } from '../functions/whatsapp-manager-api'
import {
  SHELL_LANGUAGE_OPTIONS,
  SHELL_LANGUAGE_STORAGE_KEY,
  ShellLanguage,
  normalizeShellLanguage,
  readShellLanguage
} from '../services/language-settings'

interface SettingsProps {
  isSystemActive: boolean
}

type TabType = 'updates' | 'general' | 'keys' | 'connectors'
type VoiceRuntime = 'auto' | 'gemini' | 'backend'
type OfflineTtsStatus = {
  success?: boolean
  category?: string
  available?: boolean
  engine?: string
  label?: string
  language?: string
  locale?: string
  modelDir?: string
  reason?: string
  activeVoice?: string
  preferredFemaleVoice?: string
  preferredVoiceProfile?: string
  hinglishStrategy?: string
  candidates?: Array<{
    engine?: string
    available?: boolean
    reason?: string
  }>
}

type OfflineLlmStatus = {
  success?: boolean
  available?: boolean
  status?: string
  engine?: string
  label?: string
  modelFamily?: string
  modelRepo?: string
  modelFile?: string
  language?: string
  languageSupport?: string[]
  languageMismatch?: boolean
  languageWarning?: string
  reason?: string
  runtimeDownloads?: boolean
  installDir?: string
  selectedModelId?: string
  modelPath?: string
  modelSizeBytes?: number
  installedModels?: OfflineModelOption[]
  catalog?: OfflineModelCatalog
  candidates?: Array<{
    engine?: string
    available?: boolean
    reason?: string
  }>
}

type OfflineModelOption = {
  id?: string
  name?: string
  family?: string
  repo?: string
  filename?: string
  quantization?: string
  sizeMb?: number
  size_bytes?: number
  min_ram_gb?: number
  recommended_ram_gb?: number
  pc_tier?: string
  description?: string
  strengths?: string[]
  languages?: string[]
  installed?: boolean
  recommended?: boolean
  modelPath?: string
}

type OfflineModelCatalog = {
  success?: boolean
  category?: string
  runtimeDownloads?: boolean
  installDir?: string
  systemRamGb?: number
  selectedModelId?: string
  selectedModelPath?: string
  installedModels?: OfflineModelOption[]
  options?: OfflineModelOption[]
  status?: OfflineLlmStatus
}

type OfflineModelDownloadState = {
  status?: string
  percent?: number
  message?: string
  modelPath?: string
  downloadedBytes?: number
  totalBytes?: number
}

const normalizeVoiceRuntime = (value: unknown): VoiceRuntime => {
  const runtime = String(value || '').trim().toLowerCase()
  return runtime === 'auto' || runtime === 'gemini' ? runtime : 'auto'
}

const settingsTabs = [
  {
    id: 'updates' as const,
    label: 'SYSTEM',
    ariaLabel: 'Open settings system tab',
    Icon: RiTerminalWindowLine
  },
  {
    id: 'general' as const,
    label: 'GENERAL',
    ariaLabel: 'Open settings general tab',
    Icon: RiSettings4Line
  },
  {
    id: 'keys' as const,
    label: 'API KEYS',
    ariaLabel: 'Open settings api keys tab',
    Icon: RiKey2Line
  },
  {
    id: 'connectors' as const,
    label: 'PLUGINS & CONNECTORS',
    ariaLabel: 'Open settings connectors tab',
    Icon: RiPlugLine
  }
]

const allPlugins = [
  {
    id: 'gmail',
    name: 'Gmail API',
    developer: 'Google / Shell AI',
    category: 'communication' as const,
    description: 'Check inbox, draft replies, and send emails using browser-based web session.',
    icon: RiMailLine,
    brandColor: 'from-red-500/10 to-transparent',
    borderColor: 'border-red-500/20',
    iconColor: 'text-red-400',
  },
  {
    id: 'whatsapp',
    name: 'WhatsApp Web',
    developer: 'WhatsApp / Shell AI',
    category: 'communication' as const,
    description: 'Auto-reply to messages, view chat status, and send text updates via web scanner.',
    icon: RiWhatsappLine,
    brandColor: 'from-emerald-500/10 to-transparent',
    borderColor: 'border-emerald-500/20',
    iconColor: 'text-emerald-400',
  },
  {
    id: 'telegram',
    name: 'Telegram Bot',
    developer: 'Telegram / Shell AI',
    category: 'social' as const,
    description: 'Configure bot commands, read stats, and control Shell remotely using direct bot tokens.',
    icon: RiTelegramLine,
    brandColor: 'from-sky-500/10 to-transparent',
    borderColor: 'border-sky-500/20',
    iconColor: 'text-sky-400',
  },
  {
    id: 'instagram',
    name: 'Instagram Automation',
    developer: 'Meta / Shell AI',
    category: 'social' as const,
    description: 'Read DMs, search profiles, and automate posts using browser login session.',
    icon: RiInstagramLine,
    brandColor: 'from-purple-500/10 to-transparent',
    borderColor: 'border-purple-500/20',
    iconColor: 'text-purple-400',
  },
  {
    id: 'notion',
    name: 'Notion Database',
    developer: 'Notion Labs',
    category: 'productivity' as const,
    description: 'Sync notes, sync task lists, and fetch pages directly from your workspace.',
    icon: RiBrainLine,
    brandColor: 'from-zinc-500/5 to-transparent',
    borderColor: 'border-zinc-500/10 opacity-60',
    iconColor: 'text-zinc-400',
    comingSoon: true
  },
  {
    id: 'slack',
    name: 'Slack Integration',
    developer: 'Slack Technologies',
    category: 'communication' as const,
    description: 'Post messages to channels, monitor alerts, and notify workspace users.',
    icon: RiPlugLine,
    brandColor: 'from-yellow-500/5 to-transparent',
    borderColor: 'border-yellow-500/10 opacity-60',
    iconColor: 'text-yellow-400',
    comingSoon: true
  }
]

const SettingsView = ({ isSystemActive }: SettingsProps) => {
  const [activeTab, setActiveTab] = useState<TabType>('updates')
  const [pluginSearch, setPluginSearch] = useState('')
  const [pluginCategory, setPluginCategory] = useState<'all' | 'communication' | 'social' | 'productivity'>('all')

  const [voice, setVoice] = useState<'MALE' | 'FEMALE'>(
    (localStorage.getItem('shell_voice_profile') as 'MALE' | 'FEMALE') || 'MALE'
  )
  const [voiceRuntime, setVoiceRuntime] = useState<VoiceRuntime>(() =>
    normalizeVoiceRuntime(localStorage.getItem('shell_voice_runtime'))
  )
  const [micDevices, setMicDevices] = useState<MediaDeviceInfo[]>([])
  const [selectedMicId, setSelectedMicId] = useState(
    localStorage.getItem('shell_preferred_mic_device_id') || ''
  )
  const [micStatus, setMicStatus] = useState('Microphone list not loaded.')
  const [personality, setPersonality] = useState('')
  const [userName, setUserName] = useState(localStorage.getItem('shell_user_name') || '')
  const [language, setLanguage] = useState<ShellLanguage>(() => readShellLanguage())
  const [languageStatus, setLanguageStatus] = useState('Shell replies use this language.')
  const [, setOfflineTtsStatus] = useState<OfflineTtsStatus | null>(null)
  const [, setOfflineTtsMessage] = useState('Offline TTS status not checked yet.')
  const [, setOfflineTtsBusy] = useState(false)
  const [offlineLlmStatus, setOfflineLlmStatus] = useState<OfflineLlmStatus | null>(null)
  const [offlineLlmMessage, setOfflineLlmMessage] = useState('Offline brain status not checked yet.')
  const [offlineLlmBusy, setOfflineLlmBusy] = useState(false)
  const [offlineModelCatalog, setOfflineModelCatalog] = useState<OfflineModelCatalog | null>(null)
  const [offlineModelDownloads, setOfflineModelDownloads] = useState<Record<string, OfflineModelDownloadState>>({})
  const [offlineCodingLlmStatus, setOfflineCodingLlmStatus] = useState<OfflineLlmStatus | null>(null)
  const [offlineCodingLlmMessage, setOfflineCodingLlmMessage] = useState('Offline coding brain status not checked yet.')
  const [offlineCodingLlmBusy, setOfflineCodingLlmBusy] = useState(false)
  const [offlineCodingModelCatalog, setOfflineCodingModelCatalog] = useState<OfflineModelCatalog | null>(null)
  const [offlineCodingModelDownloads, setOfflineCodingModelDownloads] = useState<Record<string, OfflineModelDownloadState>>({})

  const [geminiKey, setGeminiKey] = useState(localStorage.getItem('shell_custom_api_key') || '')
  const [groqKey, setGroqKey] = useState(localStorage.getItem('shell_groq_api_key') || '')
  const [hfKey, setHfKey] = useState(localStorage.getItem('shell_hf_api_key') || '')
  const [tavilyKey, setTavilyKey] = useState(localStorage.getItem('shell_tavily_api_key') || '')
  const [livekitKey, setLivekitKey] = useState(localStorage.getItem('shell_livekit_api_key') || '')
  const [livekitSecret, setLivekitSecret] = useState(
    localStorage.getItem('shell_livekit_api_secret') || ''
  )
  const [livekitUrl, setLivekitUrl] = useState(localStorage.getItem('shell_livekit_url') || '')
  const [openaiKey, setOpenaiKey] = useState(localStorage.getItem('shell_openai_api_key') || '')
  const [openrouterKey, setOpenrouterKey] = useState(
    localStorage.getItem('shell_openrouter_api_key') || ''
  )
  const [mistralKey, setMistralKey] = useState(localStorage.getItem('shell_mistral_api_key') || '')
  const [googleSearchKey, setGoogleSearchKey] = useState(
    localStorage.getItem('shell_google_search_api_key') || ''
  )
  const [searchEngineId, setSearchEngineId] = useState(
    localStorage.getItem('shell_search_engine_id') || ''
  )
  const [weatherKey, setWeatherKey] = useState(localStorage.getItem('shell_openweather_api_key') || '')
  const [telegramToken, setTelegramToken] = useState(localStorage.getItem('shell_telegram_bot_token') || '')
  const [telegramAllowedChatIds, setTelegramAllowedChatIds] = useState(
    localStorage.getItem('shell_telegram_allowed_chat_ids') || ''
  )
  const [telegramRemoteEnabled, setTelegramRemoteEnabled] = useState(
    localStorage.getItem('shell_telegram_remote_control_enabled') === '1'
  )
  const [telegramAllowTerminal, setTelegramAllowTerminal] = useState(
    localStorage.getItem('shell_telegram_allow_terminal') === '1'
  )
  const [telegramTestMessage, setTelegramTestMessage] = useState('Shell AI test message from desktop UI.')
  const [telegramStatus, setTelegramStatus] = useState('Telegram status not checked yet.')
  const [telegramBusy, setTelegramBusy] = useState('')
  const [apiSaveResult, setApiSaveResult] = useState('')
  const [instagramUsername, setInstagramUsername] = useState(localStorage.getItem('shell_instagram_username') || '')
  const [instagramPassword, setInstagramPassword] = useState(localStorage.getItem('shell_instagram_password') || '')
  const [instagramTargetUser, setInstagramTargetUser] = useState('')
  const [instagramCommentReply, setInstagramCommentReply] = useState('Thanks for the support! 😊')
  const [instagramDmReply, setInstagramDmReply] = useState('Hey! Boss will get back to you soon. 👍')
  const [instagramStatus, setInstagramStatus] = useState('Instagram status not checked yet.')
  const [instagramBusy, setInstagramBusy] = useState('')

  const [whatsappContact, setWhatsappContact] = useState(localStorage.getItem('shell_whatsapp_test_contact') || '')
  const [whatsappMessage, setWhatsappMessage] = useState('Hello from Shell AI!')
  const [whatsappLogFilter, setWhatsappLogFilter] = useState('')
  const [whatsappStatus, setWhatsappStatus] = useState('WhatsApp status not checked yet.')
  const [whatsappBusy, setWhatsappBusy] = useState('')

  // Connectors State
  const [connectorsStatus, setConnectorsStatus] = useState<Record<string, { connected: boolean; account?: string | null; last_connected?: string | null; message_count?: number }>>({
    whatsapp: { connected: false },
    telegram: { connected: false },
    instagram: { connected: false },
    gmail: { connected: false }
  })
  const [connectorsLoading, setConnectorsLoading] = useState<Record<string, boolean>>({
    whatsapp: false,
    telegram: false,
    instagram: false,
    gmail: false
  })
  const [connectorsError, setConnectorsError] = useState<Record<string, string>>({
    whatsapp: '',
    telegram: '',
    instagram: '',
    gmail: ''
  })
  const [connectorsSuccess, setConnectorsSuccess] = useState<Record<string, string>>({
    whatsapp: '',
    telegram: '',
    instagram: '',
    gmail: ''
  })

  // Inputs for Connectors credentials
  const [telegramTokenInput, setTelegramTokenInput] = useState('')
  const [instagramUserDetail, setInstagramUserDetail] = useState({ username: '', password: '' })
  const [whatsappPhoneInput, setWhatsappPhoneInput] = useState('')

  const generalHydratedRef = useRef(false)
  const keysHydratedRef = useRef(false)

  const settingsTabRailRef = useRef<HTMLDivElement | null>(null)
  const settingsTabButtonRefs = useRef<Record<TabType, HTMLButtonElement | null>>({
    updates: null,
    general: null,
    keys: null,
    connectors: null
  })
  const [settingsTabIndicatorStyle, setSettingsTabIndicatorStyle] = useState({
    opacity: 1,
    transform: 'translate3d(4px, 0, 0)',
    width: '104px'
  })

  const [appVersion, setAppVersion] = useState('1.1.5')
  const [updateStatus, setUpdateStatus] = useState<
    'idle' | 'checking' | 'available' | 'downloading' | 'ready' | 'error'
  >('idle')
  const [updateVersion, setUpdateVersion] = useState('')
  const [updateNotes, setUpdateNotes] = useState('No new updates detected.')
  const [downloadProgress, setDownloadProgress] = useState(0)

  useEffect(() => {
    if (window.electron?.ipcRenderer) {
      window.electron.ipcRenderer.invoke('get-app-version').then((v) => setAppVersion(v))

      const handleUpdaterEvent = (_e: unknown, { status, data, error }: any) => {
        if (status === 'checking') setUpdateStatus('checking')
        if (status === 'available') {
          setUpdateStatus('available')
          setUpdateVersion(data?.version || '')
          setUpdateNotes(data?.releaseNotes || 'Bug fixes and performance improvements.')
        }
        if (status === 'not-available') {
          setUpdateStatus('idle')
          setUpdateNotes('System is up to date.')
        }
        if (status === 'downloading') {
          setUpdateStatus('downloading')
          setDownloadProgress(Math.round(Number(data?.percent || 0)))
        }
        if (status === 'downloaded') setUpdateStatus('ready')
        if (status === 'error') {
          setUpdateStatus('error')
          setUpdateNotes(`Error: ${error}`)
        }
      }
      window.electron.ipcRenderer.on('updater-event', handleUpdaterEvent)
      return () => {
        window.electron?.ipcRenderer?.off?.('updater-event', handleUpdaterEvent)
      }
    }
  }, [])

  useEffect(() => {
    if (activeTab !== 'general' || generalHydratedRef.current || !window.electron?.ipcRenderer) return
    generalHydratedRef.current = true
    window.electron.ipcRenderer.invoke('get-personality').then((res) => {
      if (res) setPersonality(res)
    }).catch(() => {})
    window.electron.ipcRenderer.invoke('get-settings').then((settings) => {
      const nextLanguage = normalizeShellLanguage(settings?.shell_language || settings?.language)
      setLanguage(nextLanguage)
      localStorage.setItem(SHELL_LANGUAGE_STORAGE_KEY, nextLanguage)
    }).catch(() => {})
    window.electron.ipcRenderer.invoke('offline-tts-status').then((status) => {
      applyOfflineTtsStatus(status)
    }).catch(() => {})
    window.electron.ipcRenderer.invoke('offline-llm-status').then((status) => {
      applyOfflineLlmStatus(status)
    }).catch(() => {})
    window.electron.ipcRenderer.invoke('offline-coding-llm-status').then((status) => {
      applyOfflineCodingLlmStatus(status)
    }).catch(() => {})
  }, [activeTab])

  useEffect(() => {
    if (!window.electron?.ipcRenderer) return
    const handleOfflineModelEvent = (_event: unknown, payload: any) => {
      const modelId = String(payload?.modelId || '')
      const isCodingEvent =
        payload?.category === 'coding' ||
        payload?.catalog?.category === 'coding' ||
        payload?.catalog?.status?.category === 'coding' ||
        modelId.includes('coder')
      const setDownloads = isCodingEvent ? setOfflineCodingModelDownloads : setOfflineModelDownloads
      if (modelId) {
        setDownloads((current) => ({
          ...current,
          [modelId]: {
            status: payload?.status,
            percent: Number(payload?.percent || 0),
            message: String(payload?.message || ''),
            modelPath: payload?.modelPath,
            downloadedBytes: Number(payload?.downloadedBytes || 0),
            totalBytes: Number(payload?.totalBytes || 0)
          }
        }))
      }
      if (payload?.catalog?.status) {
        if (isCodingEvent) {
          setOfflineCodingModelCatalog(payload.catalog as OfflineModelCatalog)
          applyOfflineCodingLlmStatus(payload.catalog.status)
        } else {
          setOfflineModelCatalog(payload.catalog as OfflineModelCatalog)
          applyOfflineLlmStatus(payload.catalog.status)
        }
      } else if (payload?.status === 'installed') {
        if (isCodingEvent) refreshOfflineCodingLlmStatus()
        else refreshOfflineLlmStatus()
      }
    }
    window.electron.ipcRenderer.on('offline-llm-download-event', handleOfflineModelEvent)
    return () => {
      window.electron?.ipcRenderer?.off?.('offline-llm-download-event', handleOfflineModelEvent)
    }
  }, [])

  useEffect(() => {
    if (activeTab !== 'keys' || keysHydratedRef.current || !window.electron?.ipcRenderer) return
    keysHydratedRef.current = true
    window.electron.ipcRenderer.invoke('secure-get-keys').then((keys) => {
      if (!keys || typeof keys !== 'object') return
      if (keys.geminiKey) {
        const normalizedGeminiKey = normalizeGeminiApiKey(keys.geminiKey)
        if (normalizedGeminiKey) {
          setGeminiKey(normalizedGeminiKey)
          localStorage.setItem('shell_custom_api_key', normalizedGeminiKey)
        }
      }
      if (keys.groqKey) setGroqKey(keys.groqKey)
      if (keys.hfKey) setHfKey(keys.hfKey)
      if (keys.tavilyKey) setTavilyKey(keys.tavilyKey)
      if (keys.livekitKey) setLivekitKey(keys.livekitKey)
      if (keys.livekitSecret) setLivekitSecret(keys.livekitSecret)
      if (keys.livekitUrl) setLivekitUrl(keys.livekitUrl)
      if (keys.openaiKey) setOpenaiKey(keys.openaiKey)
      if (keys.openrouterKey) setOpenrouterKey(keys.openrouterKey)
      if (keys.mistralKey) setMistralKey(keys.mistralKey)
      if (keys.googleSearchKey) setGoogleSearchKey(keys.googleSearchKey)
      if (keys.searchEngineId) setSearchEngineId(keys.searchEngineId)
      if (keys.weatherKey) setWeatherKey(keys.weatherKey)
      if (keys.telegramToken) setTelegramToken(keys.telegramToken)
      if (keys.telegramAllowedChatIds) setTelegramAllowedChatIds(keys.telegramAllowedChatIds)
      if (keys.telegramRemoteControlEnabled !== undefined) {
        setTelegramRemoteEnabled(String(keys.telegramRemoteControlEnabled) === '1')
      }
      if (keys.telegramAllowTerminal !== undefined) {
        setTelegramAllowTerminal(String(keys.telegramAllowTerminal) === '1')
      }
      if (keys.instagramUsername) {
        setInstagramUsername(keys.instagramUsername)
        localStorage.setItem('shell_instagram_username', keys.instagramUsername)
      }
      if (keys.instagramPassword) {
        setInstagramPassword(keys.instagramPassword)
        localStorage.setItem('shell_instagram_password', keys.instagramPassword)
      }
    }).catch(() => {})
  }, [activeTab])

  const updateSettingsTabIndicator = useCallback(() => {
    const activeButton = settingsTabButtonRefs.current[activeTab]
    if (!activeButton) {
      setSettingsTabIndicatorStyle((current) => ({ ...current, opacity: 0 }))
      return
    }

    setSettingsTabIndicatorStyle({
      opacity: 1,
      transform: `translate3d(${activeButton.offsetLeft}px, 0, 0)`,
      width: `${activeButton.offsetWidth}px`
    })
  }, [activeTab])

  useLayoutEffect(() => {
    updateSettingsTabIndicator()

    const rail = settingsTabRailRef.current
    const activeButton = settingsTabButtonRefs.current[activeTab]
    const resizeObserver =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => updateSettingsTabIndicator())
        : null

    if (rail) resizeObserver?.observe(rail)
    if (activeButton) resizeObserver?.observe(activeButton)
    window.addEventListener('resize', updateSettingsTabIndicator)

    return () => {
      resizeObserver?.disconnect()
      window.removeEventListener('resize', updateSettingsTabIndicator)
    }
  }, [activeTab, updateSettingsTabIndicator])

  const fetchConnectorsStatus = useCallback(() => {
    if (!window.electron?.ipcRenderer) return
    window.electron.ipcRenderer
      .invoke('social-media-status')
      .then((res) => {
        if (res && res.success && res.statuses) {
          setConnectorsStatus(res.statuses)
        }
      })
      .catch((err) => {
        console.error('Failed to fetch connectors status', err)
      })
  }, [])

  useEffect(() => {
    if (activeTab === 'connectors') {
      fetchConnectorsStatus()
    }
  }, [activeTab, fetchConnectorsStatus])

  const handleConnect = async (platform: string, payload: any) => {
    if (!window.electron?.ipcRenderer) return
    setConnectorsLoading((prev) => ({ ...prev, [platform]: true }))
    setConnectorsError((prev) => ({ ...prev, [platform]: '' }))
    setConnectorsSuccess((prev) => ({ ...prev, [platform]: '' }))
    try {
      const res = await window.electron.ipcRenderer.invoke('social-media-connect', {
        platform,
        ...payload
      })
      if (res && res.success) {
        setConnectorsSuccess((prev) => ({ ...prev, [platform]: res.message || 'Connected successfully!' }))
        fetchConnectorsStatus()
        if (platform === 'telegram') setTelegramTokenInput('')
        if (platform === 'instagram') setInstagramUserDetail({ username: '', password: '' })
        if (platform === 'whatsapp') setWhatsappPhoneInput('')
      } else {
        setConnectorsError((prev) => ({ ...prev, [platform]: res.error || res.message || 'Connection failed' }))
      }
    } catch (err: any) {
      setConnectorsError((prev) => ({ ...prev, [platform]: err.message || 'Connection error occurred' }))
    } finally {
      setConnectorsLoading((prev) => ({ ...prev, [platform]: false }))
    }
  }

  const handleDisconnect = async (platform: string) => {
    if (!window.electron?.ipcRenderer) return
    setConnectorsLoading((prev) => ({ ...prev, [platform]: true }))
    setConnectorsError((prev) => ({ ...prev, [platform]: '' }))
    setConnectorsSuccess((prev) => ({ ...prev, [platform]: '' }))
    try {
      const res = await window.electron.ipcRenderer.invoke('social-media-disconnect', { platform })
      if (res && res.success) {
        setConnectorsSuccess((prev) => ({ ...prev, [platform]: res.message || 'Disconnected successfully!' }))
        fetchConnectorsStatus()
      } else {
        setConnectorsError((prev) => ({ ...prev, [platform]: res.error || res.message || 'Disconnection failed' }))
      }
    } catch (err: any) {
      setConnectorsError((prev) => ({ ...prev, [platform]: err.message || 'Disconnection error occurred' }))
    } finally {
      setConnectorsLoading((prev) => ({ ...prev, [platform]: false }))
    }
  }

  const applyUpdateResult = (result: any) => {
    if (!result) return
    if (result.success === false) {
      setUpdateStatus('error')
      setUpdateNotes(result.message || result.error || 'Update check failed.')
      return
    }
    if (result.status === 'available') {
      setUpdateStatus('available')
      setUpdateVersion(result.version || '')
      setUpdateNotes(
        result.releaseNotes ||
          (result.canDownload === false
            ? 'Update found, but no Windows .exe installer asset is attached yet.'
            : 'New Shell AI installer is available.')
      )
      return
    }
    if (result.status === 'downloaded') {
      setUpdateStatus('ready')
      setDownloadProgress(100)
      setUpdateNotes(`Update downloaded: ${result.downloadedPath || 'ready to install'}`)
      return
    }
    if (result.status === 'installing') {
      setUpdateStatus('ready')
      setUpdateNotes(result.message || 'Update installer launched. Follow the setup window.')
      return
    }
    setUpdateStatus('idle')
    setUpdateNotes(result.message || 'System is up to date.')
  }

  const checkForUpdates = async () => {
    setUpdateStatus('checking')
    setUpdateNotes('Checking GitHub release feed for a newer Windows installer...')
    try {
      applyUpdateResult(await window.electron.ipcRenderer.invoke('check-for-updates'))
    } catch (e: any) {
      setUpdateStatus('error')
      setUpdateNotes(`Update check failed: ${e?.message || e}`)
    }
  }

  const downloadUpdate = async () => {
    setUpdateStatus('downloading')
    setDownloadProgress(0)
    setUpdateNotes('Downloading Windows installer...')
    try {
      applyUpdateResult(await window.electron.ipcRenderer.invoke('download-update'))
    } catch (e: any) {
      setUpdateStatus('error')
      setUpdateNotes(`Update download failed: ${e?.message || e}`)
    }
  }

  const installUpdate = async () => {
    try {
      applyUpdateResult(await window.electron.ipcRenderer.invoke('install-update'))
    } catch (e: any) {
      setUpdateStatus('error')
      setUpdateNotes(`Update launch failed: ${e?.message || e}`)
    }
  }

  const handleVoiceChange = (v: 'MALE' | 'FEMALE') => {
    if (isSystemActive) return
    setVoice(v)
    localStorage.setItem('shell_voice_profile', v)
  }

  const handleVoiceRuntimeChange = (runtime: VoiceRuntime) => {
    if (isSystemActive) return
    setVoiceRuntime(runtime)
    localStorage.setItem('shell_voice_runtime', runtime)
    window.dispatchEvent(new CustomEvent('shell-voice-runtime-changed'))
  }

  const handleLanguageChange = async (nextLanguage: ShellLanguage) => {
    setLanguage(nextLanguage)
    localStorage.setItem(SHELL_LANGUAGE_STORAGE_KEY, nextLanguage)
    window.dispatchEvent(new CustomEvent('shell-language-changed', { detail: { language: nextLanguage } }))

    if (!window.electron?.ipcRenderer) {
      setLanguageStatus('Saved locally. Shell text replies use this language now.')
      return
    }

    try {
      const result = await window.electron.ipcRenderer.invoke('set-settings', {
        language: nextLanguage,
        shell_language: nextLanguage
      })
      if (result?.success === false || result?.ok === false) {
        setLanguageStatus(result?.message || result?.error || 'Language save failed.')
        return
      }
      setLanguageStatus(
        isSystemActive
          ? 'Saved. Text replies update now; reconnect voice to refresh Gemini Live.'
          : 'Saved. Shell replies use this language now.'
      )
    } catch (error: any) {
      setLanguageStatus(`Language save failed: ${error?.message || error}`)
    }
  }

  const applyOfflineTtsStatus = (status: OfflineTtsStatus | null | undefined) => {
    if (!status || typeof status !== 'object') {
      setOfflineTtsStatus(null)
      setOfflineTtsMessage('Offline TTS status unavailable.')
      return
    }

    setOfflineTtsStatus(status)
    if (status.available) {
      const voiceLabel = status.activeVoice ? ` Voice: ${status.activeVoice}.` : ''
      setOfflineTtsMessage(`${status.label || status.engine || 'Offline TTS'} ready.${voiceLabel}`)
      return
    }
    setOfflineTtsMessage(status.reason || 'Kokoro offline voice is not ready. Shell will not use local OS TTS fallback.')
  }

  const refreshOfflineTtsStatus = async () => {
    setOfflineTtsBusy(true)
    try {
      const status = await window.electron?.ipcRenderer.invoke('offline-tts-status')
      applyOfflineTtsStatus(status)
    } catch (error: any) {
      setOfflineTtsStatus(null)
      setOfflineTtsMessage(`Offline TTS check failed: ${error?.message || error}`)
    } finally {
      setOfflineTtsBusy(false)
    }
  }

  const applyOfflineLlmStatus = (status: OfflineLlmStatus | null | undefined) => {
    if (!status || typeof status !== 'object') {
      setOfflineLlmStatus(null)
      setOfflineLlmMessage('Offline brain status unavailable.')
      return
    }

    setOfflineLlmStatus(status)
    const catalog = status.catalog || ((status as any).options ? (status as any) : null)
    if (catalog) setOfflineModelCatalog(catalog as OfflineModelCatalog)
    if (status.available) {
      const warning = String(status.languageWarning || '').trim()
      setOfflineLlmMessage(
        warning
          ? `${status.modelFamily || status.label || 'Offline brain'} ready. ${warning}`
          : `${status.modelFamily || status.label || 'Offline brain'} ready for chat and voice replies.`
      )
      return
    }
    setOfflineLlmMessage(
      status.reason ||
        (status.runtimeDownloads
          ? 'Download one offline brain model below to enable local chat and voice replies.'
          : 'Offline brain is not ready; Shell will use local fallback answers.')
    )
  }

  const refreshOfflineLlmStatus = async () => {
    setOfflineLlmBusy(true)
    try {
      const catalog = await window.electron?.ipcRenderer.invoke('offline-llm-catalog')
      if (catalog && typeof catalog === 'object') {
        setOfflineModelCatalog(catalog)
        applyOfflineLlmStatus((catalog as OfflineModelCatalog).status || (catalog as OfflineLlmStatus))
      } else {
        const status = await window.electron?.ipcRenderer.invoke('offline-llm-status')
        applyOfflineLlmStatus(status)
      }
    } catch (error: any) {
      setOfflineLlmStatus(null)
      setOfflineLlmMessage(`Offline brain check failed: ${error?.message || error}`)
    } finally {
      setOfflineLlmBusy(false)
    }
  }

  const downloadOfflineModel = async (modelId: string) => {
    if (!modelId || !window.electron?.ipcRenderer) return
    setOfflineModelDownloads((current) => ({
      ...current,
      [modelId]: { status: 'queued', percent: 0, message: 'Queued' }
    }))
    try {
      const result = await window.electron.ipcRenderer.invoke('offline-llm-download', { modelId })
      if (result?.catalog) setOfflineModelCatalog(result.catalog as OfflineModelCatalog)
      if (result?.catalog?.status) applyOfflineLlmStatus(result.catalog.status)
      if (result?.status === 'installed' || result?.status === 'selected') {
        setOfflineModelDownloads((current) => ({
          ...current,
          [modelId]: {
            status: 'installed',
            percent: 100,
            message: result?.message || 'Offline brain is active',
            modelPath: result?.modelPath
          }
        }))
        await refreshOfflineLlmStatus()
      }
      if (result?.success === false) {
        setOfflineModelDownloads((current) => ({
          ...current,
          [modelId]: { status: 'error', percent: 0, message: result?.message || 'Download failed' }
        }))
      }
    } catch (error: any) {
      setOfflineModelDownloads((current) => ({
        ...current,
        [modelId]: { status: 'error', percent: 0, message: `Download failed: ${error?.message || error}` }
      }))
    }
  }

  const selectOfflineModel = async (modelId: string) => {
    if (!modelId || !window.electron?.ipcRenderer) return
    setOfflineModelDownloads((current) => ({
      ...current,
      [modelId]: { ...current[modelId], status: 'selecting', percent: 100, message: 'Switching brain' }
    }))
    try {
      const result = await window.electron.ipcRenderer.invoke('offline-llm-select', { modelId })
      if (result?.success === false) {
        setOfflineModelDownloads((current) => ({
          ...current,
          [modelId]: { status: 'error', percent: 0, message: result?.message || 'Selection failed' }
        }))
        return
      }
      if (result?.catalog) setOfflineModelCatalog(result.catalog as OfflineModelCatalog)
      if (result?.catalog?.status) applyOfflineLlmStatus(result.catalog.status)
      setOfflineModelDownloads((current) => ({
        ...current,
        [modelId]: {
          status: 'installed',
          percent: 100,
          message: result?.message || 'Offline brain is active',
          modelPath: result?.modelPath
        }
      }))
      await refreshOfflineLlmStatus()
    } catch (error: any) {
      setOfflineModelDownloads((current) => ({
        ...current,
        [modelId]: { status: 'error', percent: 0, message: `Selection failed: ${error?.message || error}` }
      }))
    }
  }

  const applyOfflineCodingLlmStatus = (status: OfflineLlmStatus | null | undefined) => {
    if (!status || typeof status !== 'object') {
      setOfflineCodingLlmStatus(null)
      setOfflineCodingLlmMessage('Offline coding brain status unavailable.')
      return
    }

    setOfflineCodingLlmStatus(status)
    const catalog = status.catalog || ((status as any).options ? (status as any) : null)
    if (catalog) setOfflineCodingModelCatalog(catalog as OfflineModelCatalog)
    if (status.available) {
      const warning = String(status.languageWarning || '').trim()
      setOfflineCodingLlmMessage(
        warning
          ? `${status.modelFamily || status.label || 'Offline coding brain'} ready. ${warning}`
          : `${status.modelFamily || status.label || 'Offline coding brain'} ready for coding agents.`
      )
      return
    }
    setOfflineCodingLlmMessage(
      status.reason ||
        (status.runtimeDownloads
          ? 'Download one offline coding brain model below to enable local coding agents.'
          : 'Offline coding brain is not ready; Shell coding agents will use provider or local snippets.')
    )
  }

  const refreshOfflineCodingLlmStatus = async () => {
    setOfflineCodingLlmBusy(true)
    try {
      const catalog = await window.electron?.ipcRenderer.invoke('offline-coding-llm-catalog')
      if (catalog && typeof catalog === 'object') {
        setOfflineCodingModelCatalog(catalog)
        applyOfflineCodingLlmStatus((catalog as OfflineModelCatalog).status || (catalog as OfflineLlmStatus))
      } else {
        const status = await window.electron?.ipcRenderer.invoke('offline-coding-llm-status')
        applyOfflineCodingLlmStatus(status)
      }
    } catch (error: any) {
      setOfflineCodingLlmStatus(null)
      setOfflineCodingLlmMessage(`Offline coding brain check failed: ${error?.message || error}`)
    } finally {
      setOfflineCodingLlmBusy(false)
    }
  }

  const downloadOfflineCodingModel = async (modelId: string) => {
    if (!modelId || !window.electron?.ipcRenderer) return
    setOfflineCodingModelDownloads((current) => ({
      ...current,
      [modelId]: { status: 'queued', percent: 0, message: 'Queued' }
    }))
    try {
      const result = await window.electron.ipcRenderer.invoke('offline-coding-llm-download', { modelId })
      if (result?.catalog) setOfflineCodingModelCatalog(result.catalog as OfflineModelCatalog)
      if (result?.catalog?.status) applyOfflineCodingLlmStatus(result.catalog.status)
      if (result?.status === 'installed' || result?.status === 'selected') {
        setOfflineCodingModelDownloads((current) => ({
          ...current,
          [modelId]: {
            status: 'installed',
            percent: 100,
            message: result?.message || 'Offline coding brain is active',
            modelPath: result?.modelPath
          }
        }))
        await refreshOfflineCodingLlmStatus()
      }
      if (result?.success === false) {
        setOfflineCodingModelDownloads((current) => ({
          ...current,
          [modelId]: { status: 'error', percent: 0, message: result?.message || 'Download failed' }
        }))
      }
    } catch (error: any) {
      setOfflineCodingModelDownloads((current) => ({
        ...current,
        [modelId]: { status: 'error', percent: 0, message: `Download failed: ${error?.message || error}` }
      }))
    }
  }

  const selectOfflineCodingModel = async (modelId: string) => {
    if (!modelId || !window.electron?.ipcRenderer) return
    setOfflineCodingModelDownloads((current) => ({
      ...current,
      [modelId]: { ...current[modelId], status: 'selecting', percent: 100, message: 'Switching coding brain' }
    }))
    try {
      const result = await window.electron.ipcRenderer.invoke('offline-coding-llm-select', { modelId })
      if (result?.success === false) {
        setOfflineCodingModelDownloads((current) => ({
          ...current,
          [modelId]: { status: 'error', percent: 0, message: result?.message || 'Selection failed' }
        }))
        return
      }
      if (result?.catalog) setOfflineCodingModelCatalog(result.catalog as OfflineModelCatalog)
      if (result?.catalog?.status) applyOfflineCodingLlmStatus(result.catalog.status)
      setOfflineCodingModelDownloads((current) => ({
        ...current,
        [modelId]: {
          status: 'installed',
          percent: 100,
          message: result?.message || 'Offline coding brain is active',
          modelPath: result?.modelPath
        }
      }))
      await refreshOfflineCodingLlmStatus()
    } catch (error: any) {
      setOfflineCodingModelDownloads((current) => ({
        ...current,
        [modelId]: { status: 'error', percent: 0, message: `Selection failed: ${error?.message || error}` }
      }))
    }
  }

  const refreshMicrophones = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) {
      setMicStatus('Microphone device list unavailable.')
      return
    }

    try {
      let devices = await navigator.mediaDevices.enumerateDevices()
      let inputs = devices.filter((device) => device.kind === 'audioinput')

      if (navigator.mediaDevices.getUserMedia && inputs.every((device) => !device.label)) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
          stream.getTracks().forEach((track) => track.stop())
          devices = await navigator.mediaDevices.enumerateDevices()
          inputs = devices.filter((device) => device.kind === 'audioinput')
        } catch {}
      }

      setMicDevices(inputs)
      setMicStatus(
        inputs.length
          ? `${inputs.length} microphones available. Shell auto-selects the best input at voice start.`
          : 'No microphone found. Shell can still start and speak; voice input is disabled.'
      )
    } catch (err: any) {
      setMicStatus(`Microphone list failed: ${err?.message || err}`)
    }
  }

  const handleMicrophoneChange = (deviceId: string) => {
    if (isSystemActive) return
    setSelectedMicId(deviceId)
    const device = micDevices.find((item) => item.deviceId === deviceId)
    if (!deviceId) {
      localStorage.removeItem('shell_preferred_mic_device_id')
      localStorage.removeItem('shell_preferred_mic_label')
      setMicStatus('Default microphone selected.')
      return
    }
    localStorage.setItem('shell_preferred_mic_device_id', deviceId)
    if (device?.label) localStorage.setItem('shell_preferred_mic_label', device.label)
    setMicStatus(`Selected ${device?.label || 'microphone'}.`)
  }

  const handlePersonalityChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const text = e.target.value
    const words = text
      .trim()
      .split(/\s+/)
      .filter((w) => w.length > 0)
    if (words.length <= 150) setPersonality(text)
  }

  const savePersonality = async () => {
    if (window.electron?.ipcRenderer) {
      await window.electron.ipcRenderer.invoke('set-personality', personality)
      alert('Personality Matrix Saved Securely to OS.')
    }
  }

  const saveUserName = () => {
    localStorage.setItem('shell_user_name', userName)
    alert('User Designation Saved.')
  }

  const saveApiKeys = async () => {
    const normalizedGeminiKey = normalizeGeminiApiKey(geminiKey)
    setGeminiKey(normalizedGeminiKey)
    localStorage.setItem('shell_custom_api_key', normalizedGeminiKey)
    localStorage.setItem('shell_groq_api_key', groqKey)
    localStorage.setItem('shell_hf_api_key', hfKey)
    localStorage.setItem('shell_tavily_api_key', tavilyKey)
    localStorage.setItem('shell_livekit_api_key', livekitKey)
    localStorage.setItem('shell_livekit_api_secret', livekitSecret)
    localStorage.setItem('shell_livekit_url', livekitUrl)
    localStorage.setItem('shell_openai_api_key', openaiKey)
    localStorage.setItem('shell_openrouter_api_key', openrouterKey)
    localStorage.setItem('shell_mistral_api_key', mistralKey)
    localStorage.setItem('shell_google_search_api_key', googleSearchKey)
    localStorage.setItem('shell_search_engine_id', searchEngineId)
    localStorage.setItem('shell_openweather_api_key', weatherKey)
    localStorage.setItem('shell_telegram_bot_token', telegramToken)
    localStorage.setItem('shell_telegram_allowed_chat_ids', telegramAllowedChatIds)
    localStorage.setItem('shell_telegram_remote_control_enabled', telegramRemoteEnabled ? '1' : '0')
    localStorage.setItem('shell_telegram_allow_terminal', telegramAllowTerminal ? '1' : '0')
    localStorage.setItem('shell_instagram_username', instagramUsername)
    localStorage.setItem('shell_instagram_password', instagramPassword)

    let saveMessage = 'Saved locally. Restart Shell AI to apply runtime modules.'
    if (window.electron?.ipcRenderer) {
      try {
        const result = await window.electron.ipcRenderer.invoke('secure-save-keys', {
          geminiKey: normalizedGeminiKey,
          groqKey,
          hfKey,
          tavilyKey,
          livekitKey,
          livekitSecret,
          livekitUrl,
          openaiKey,
          openrouterKey,
          mistralKey,
          googleSearchKey,
          searchEngineId,
          weatherKey,
          telegramToken,
          telegramAllowedChatIds,
          telegramRemoteControlEnabled: telegramRemoteEnabled ? '1' : '0',
          telegramAllowTerminal: telegramAllowTerminal ? '1' : '0',
          instagramUsername,
          instagramPassword
        })
        if (result?.rejected && Object.keys(result.rejected).length) {
          saveMessage = `Saved with rejected fields: ${Object.keys(result.rejected).join(', ')}`
        } else {
          saveMessage = `Saved: ${(result?.saved || []).length} backend keys updated. Restart Shell AI to apply.`
        }
      } catch (e: any) {
        saveMessage = `Save failed: ${e?.message || e}`
      }
    }
    setApiSaveResult(saveMessage)
  }

  const formatToolResponse = (response: any) => {
    if (!response) return 'No backend response.'
    if (typeof response === 'string') return response
    if (typeof response.result === 'string') return response.result
    if (typeof response.message === 'string') return response.message
    if (typeof response.error === 'string') return response.error
    return JSON.stringify(response, null, 2)
  }

  const runTelegramTool = async (toolId: string, args: Record<string, any> = {}, busyLabel = 'telegram') => {
    setTelegramBusy(busyLabel)
    try {
      const response = await window.electron?.ipcRenderer.invoke('execute-tool', toolId, args)
      const text = formatToolResponse(response)
      setTelegramStatus(text)
      return response
    } catch (error) {
      const text = `Telegram action failed: ${String(error)}`
      setTelegramStatus(text)
      return { status: 'error', message: text }
    } finally {
      setTelegramBusy('')
    }
  }

  const saveTelegramConfig = async () => {
    localStorage.setItem('shell_telegram_bot_token', telegramToken)
    localStorage.setItem('shell_telegram_allowed_chat_ids', telegramAllowedChatIds)
    localStorage.setItem('shell_telegram_remote_control_enabled', telegramRemoteEnabled ? '1' : '0')
    localStorage.setItem('shell_telegram_allow_terminal', telegramAllowTerminal ? '1' : '0')

    if (window.electron?.ipcRenderer) {
      await window.electron.ipcRenderer.invoke('secure-save-keys', {
        telegramToken,
        telegramAllowedChatIds,
        telegramRemoteControlEnabled: telegramRemoteEnabled ? '1' : '0',
        telegramAllowTerminal: telegramAllowTerminal ? '1' : '0'
      })
    }

    await runTelegramTool(
      'shell_telegram:set_telegram_remote_config_tool',
      {
        allowed_chat_ids: telegramAllowedChatIds,
        remote_control_enabled: telegramRemoteEnabled,
        allow_terminal: telegramAllowTerminal
      },
      'save'
    )
  }

  const runInstagramTool = async (toolId: string, args: Record<string, any> = {}, busyLabel = 'insta') => {
    setInstagramBusy(busyLabel)
    try {
      const response = await window.electron?.ipcRenderer.invoke('execute-tool', toolId, args)
      const text = formatToolResponse(response)
      setInstagramStatus(text)
      return response
    } catch (error) {
      const text = `Instagram action failed: ${String(error)}`
      setInstagramStatus(text)
      return { status: 'error', message: text }
    } finally {
      setInstagramBusy('')
    }
  }

  const saveInstagramConfig = async () => {
    localStorage.setItem('shell_instagram_username', instagramUsername)
    localStorage.setItem('shell_instagram_password', instagramPassword)

    if (window.electron?.ipcRenderer) {
      setInstagramBusy('save')
      try {
        await window.electron.ipcRenderer.invoke('secure-save-keys', {
          instagramUsername,
          instagramPassword
        })
        setInstagramStatus('Instagram configuration saved securely to backend.')
      } catch (e: any) {
        setInstagramStatus(`Save failed: ${e?.message || e}`)
      } finally {
        setInstagramBusy('')
      }
    }
  }

  const runWhatsAppTool = async (toolId: string, args: Record<string, any> = {}, busyLabel = 'whatsapp') => {
    setWhatsappBusy(busyLabel)
    try {
      const response = await window.electron?.ipcRenderer.invoke('execute-tool', toolId, args)
      const text = formatToolResponse(response)
      setWhatsappStatus(text)
      return response
    } catch (error) {
      const text = `WhatsApp action failed: ${String(error)}`
      setWhatsappStatus(text)
      return { status: 'error', message: text }
    } finally {
      setWhatsappBusy('')
    }
  }

  const sendDirectWhatsApp = async () => {
    localStorage.setItem('shell_whatsapp_test_contact', whatsappContact)
    setWhatsappBusy('send')
    setWhatsappStatus(`Opening WhatsApp & automating GUI to send message to "${whatsappContact}"...`)
    try {
      const result = await sendWhatsAppMessage(whatsappContact, whatsappMessage)
      setWhatsappStatus(result)
    } catch (error) {
      setWhatsappStatus(`WhatsApp GUI automation failed: ${String(error)}`)
    } finally {
      setWhatsappBusy('')
    }
  }



  const currentWordCount = personality
    .trim()
    .split(/\s+/)
    .filter((w) => w.length > 0).length
  const offlineLlmReady = Boolean(offlineLlmStatus?.available)
  const offlineLlmBadge = offlineLlmBusy ? 'CHECKING' : offlineLlmReady ? 'READY' : 'FALLBACK'
  const offlineLlmEngine = String(offlineLlmStatus?.engine || 'fallback').toUpperCase()
  const offlineLlmCandidateSummary = (offlineLlmStatus?.candidates || [])
    .map((candidate) => `${String(candidate.engine || '').toUpperCase()}:${candidate.available ? 'READY' : 'NO'}`)
    .filter(Boolean)
    .join('  ')
  const offlineModelOptions = offlineModelCatalog?.options || offlineLlmStatus?.catalog?.options || []
  const offlineSelectedModelId =
    offlineLlmStatus?.selectedModelId || offlineModelCatalog?.selectedModelId || ''
  const offlineCodingLlmReady = Boolean(offlineCodingLlmStatus?.available)
  const offlineCodingLlmBadge = offlineCodingLlmBusy ? 'CHECKING' : offlineCodingLlmReady ? 'READY' : 'FALLBACK'
  const offlineCodingLlmEngine = String(offlineCodingLlmStatus?.engine || 'fallback').toUpperCase()
  const offlineCodingLlmCandidateSummary = (offlineCodingLlmStatus?.candidates || [])
    .map((candidate) => `${String(candidate.engine || '').toUpperCase()}:${candidate.available ? 'READY' : 'NO'}`)
    .filter(Boolean)
    .join('  ')
  const offlineCodingModelOptions = offlineCodingModelCatalog?.options || offlineCodingLlmStatus?.catalog?.options || []
  const offlineCodingSelectedModelId =
    offlineCodingLlmStatus?.selectedModelId || offlineCodingModelCatalog?.selectedModelId || ''
  const formatOfflineModelSize = (option: OfflineModelOption) => {
    const sizeMb = Number(option.sizeMb || 0)
    if (sizeMb > 0) return `${sizeMb.toFixed(sizeMb >= 1000 ? 0 : 1)} MB`
    const sizeBytes = Number(option.size_bytes || 0)
    if (sizeBytes > 0) return `${(sizeBytes / 1024 / 1024).toFixed(1)} MB`
    return 'Size unknown'
  }
  const formatOfflineModelRam = (option: OfflineModelOption) => {
    const minRam = Number(option.min_ram_gb || 0)
    const recommendedRam = Number(option.recommended_ram_gb || 0)
    if (minRam > 0 && recommendedRam > 0) return `RAM ${minRam}-${recommendedRam} GB`
    if (recommendedRam > 0) return `RAM ${recommendedRam} GB recommended`
    if (minRam > 0) return `RAM ${minRam}+ GB`
    return 'RAM unknown'
  }

  const cardClass =
    'shell-settings-card border p-6 md:p-8 rounded-2xl flex flex-col gap-5 transition-all shadow-lg'
  const inputContainerClass =
    'shell-settings-input flex items-center border rounded-lg px-4 py-3 transition-all duration-300 w-full'
  const titleClass = 'text-sm font-semibold text-white flex items-center gap-2'

  return (
    <div className="shell-settings-surface h-full min-h-0 p-4 md:p-8 lg:p-10 flex flex-col items-center text-zinc-100 overflow-hidden">
      <motion.div
        className="w-full max-w-4xl h-full min-h-0 flex flex-col gap-6 md:gap-8"
        initial={false}
        animate={{ opacity: 1 }}
      >
        <div className="shell-settings-header shrink-0 z-30 flex flex-col md:flex-row md:items-center justify-between gap-6 border-b pb-6 pt-1 backdrop-blur-xl">
          <div className="flex items-center gap-5">
            <div className="p-4 bg-[#111] rounded-2xl border border-white/10 flex items-center justify-center shadow-[0_0_15px_rgba(255,255,255,0.03)]">
              <GiArtificialIntelligence size={36} className="text-white" />
            </div>
            <div>
              <h2 className="text-3xl font-bold tracking-tight text-white">Command Center</h2>
              <p className="text-xs text-zinc-400 font-mono mt-1 tracking-widest flex items-center gap-2 uppercase">
                <RiRecordCircleLine
                  className={`${isSystemActive ? 'text-emerald-400 animate-pulse shadow-[0_0_8px_#34d399]' : 'text-zinc-600'}`}
                  size={14}
                />
                {isSystemActive ? 'System Online' : 'System Offline'}
              </p>
            </div>
          </div>

          <div
            ref={settingsTabRailRef}
            className="shell-tabs shell-settings-tabs flex p-1 rounded-xl w-full md:w-fit shadow-lg scrollbar-none"
          >
            <div className="shell-tab-indicator" style={settingsTabIndicatorStyle} />
            {settingsTabs.map((tab) => {
              const Icon = tab.Icon
              return (
                <button
                  key={tab.id}
                  ref={(element) => {
                    settingsTabButtonRefs.current[tab.id] = element
                  }}
                  aria-label={tab.ariaLabel}
                  onClick={() => setActiveTab(tab.id)}
                  className={`shell-tab flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-3 text-xs font-bold tracking-widest rounded-lg whitespace-nowrap ${
                    activeTab === tab.id ? 'shell-tab-active' : ''
                  }`}
                >
                  <Icon size={16} /> {tab.label}
                </button>
              )
            })}
          </div>
        </div>

        <div className="relative w-full flex-1 min-h-0 overflow-y-auto scrollbar-small pb-12 mt-2 pr-1">
          <>
            {activeTab === 'updates' && (
              <motion.div
                key="updates"
                initial={false}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full"
              >
                <div className={`${cardClass} md:col-span-1 border-emerald-500/20`}>
                  <div className="flex justify-between items-center border-b border-white/10 pb-4">
                    <span className={titleClass}>
                      <RiRocketLine className="text-emerald-400" size={18} /> OS Firmware
                    </span>
                    <span className="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-3 py-1 rounded font-mono font-bold tracking-widest">
                      v{appVersion}
                    </span>
                  </div>

                  <div className="flex flex-col gap-4 items-center justify-center flex-1 py-4 text-center">
                    {updateStatus === 'idle' || updateStatus === 'error' ? (
                      <>
                        <RiTerminalWindowLine size={48} className="text-zinc-700" />
                        <p className="text-xs text-zinc-400 font-mono">Current build is stable.</p>
                        <button
                          onClick={checkForUpdates}
                          className="mt-2 w-full py-3 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white font-bold tracking-widest text-[11px] flex items-center justify-center gap-2 transition-all cursor-pointer"
                        >
                          <RiRefreshLine size={16} /> CHECK FOR UPDATES
                        </button>
                      </>
                    ) : updateStatus === 'checking' ? (
                      <>
                        <RiRefreshLine size={48} className="text-emerald-500 animate-spin" />
                        <p className="text-xs text-emerald-400 font-mono animate-pulse">
                          PINGING NEURAL NETWORK...
                        </p>
                      </>
                    ) : updateStatus === 'available' ? (
                      <>
                        <RiDownloadCloud2Line size={48} className="text-cyan-400" />
                        <p className="text-xs text-cyan-400 font-mono">
                          NEW BUILD FOUND: v{updateVersion}
                        </p>
                        <button
                          onClick={downloadUpdate}
                          className="mt-2 w-full py-3 rounded-lg bg-cyan-500/20 hover:bg-cyan-500 text-cyan-400 hover:text-black font-bold tracking-widest text-[11px] flex items-center justify-center gap-2 transition-all border border-cyan-500/50 cursor-pointer"
                        >
                          <RiDownloadCloud2Line size={16} /> DOWNLOAD UPDATE
                        </button>
                      </>
                    ) : updateStatus === 'downloading' ? (
                      <div className="w-full flex flex-col gap-3">
                        <div className="flex justify-between text-[10px] font-mono text-zinc-400">
                          <span>DOWNLOADING PATCH...</span>
                          <span>{downloadProgress}%</span>
                        </div>
                        <div className="w-full h-2 bg-black rounded-full overflow-hidden border border-white/10">
                          <div
                            className="h-full bg-cyan-500 shadow-[0_0_10px_#06b6d4] transition-all duration-300"
                            style={{ width: `${downloadProgress}%` }}
                          />
                        </div>
                      </div>
                    ) : (
                      <>
                        <RiRecordCircleLine size={48} className="text-emerald-400 animate-pulse" />
                        <p className="text-xs text-emerald-400 font-mono">PATCH DOWNLOADED</p>
                        <button
                          onClick={installUpdate}
                          className="mt-2 w-full py-3 rounded-lg bg-emerald-500 text-black font-bold tracking-widest text-[11px] flex items-center justify-center gap-2 transition-all shadow-[0_0_20px_rgba(16,185,129,0.4)] cursor-pointer"
                        >
                          <RiRocketLine size={16} /> UPDATE NOW
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className={`${cardClass} md:col-span-1`}>
                  <div className="flex justify-between items-center border-b border-white/10 pb-4">
                    <span className={titleClass}>
                      <RiTerminalWindowLine className="text-zinc-400" size={18} /> Patch Notes
                    </span>
                  </div>
                  <div className="flex-1 bg-[#050505] border border-white/5 rounded-xl p-4 overflow-y-auto max-h-60 scrollbar-small">
                    <pre className="text-[11px] font-mono text-zinc-400 whitespace-pre-wrap leading-relaxed">
                      {updateNotes}
                    </pre>
                  </div>
                </div>
              </motion.div>
            )}

            {/* --- TAB 2: GENERAL --- */}
            {activeTab === 'general' && (
              <motion.div
                key="general"
                initial={false}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full"
              >
                <div className={`${cardClass} md:col-span-2`}>
                  <div className="flex justify-between items-center">
                    <span className={titleClass}>
                      <RiUserLine className="text-zinc-400" size={18} /> AI Personality Matrix
                    </span>
                    <div className="flex items-center gap-4">
                      <span
                        className={`text-[10px] font-mono tracking-widest ${currentWordCount >= 150 ? 'text-red-400' : 'text-zinc-400'}`}
                      >
                        {currentWordCount} / 150 WORDS
                      </span>
                      <button
                        onClick={savePersonality}
                        className="text-zinc-400 hover:text-white transition-colors bg-white/5 p-2 rounded-md hover:bg-white/10 border border-white/5"
                      >
                        <RiSave3Line size={18} />
                      </button>
                    </div>
                  </div>
                  <textarea
                    value={personality}
                    onChange={handlePersonalityChange}
                    placeholder="Define who Shell AI is. Example: 'You are a sassy, highly technical assistant...'"
                    className="bg-[#050505] border border-white/10 rounded-lg p-4 text-sm text-zinc-200 h-32 resize-none focus:border-white/30 outline-none transition-all scrollbar-small"
                  />
                </div>

                <div className={cardClass}>
                  <div className="flex justify-between items-end">
                    <span className={titleClass}>
                      <RiUserLine className="text-zinc-400" size={18} /> User Designation
                    </span>
                  </div>
                  <div className={inputContainerClass}>
                    <input
                      type="text"
                      value={userName}
                      onChange={(e) => setUserName(e.target.value)}
                      placeholder="Enter operator name..."
                      className="bg-transparent border-none outline-none text-sm text-zinc-100 w-full placeholder:text-zinc-600 font-medium"
                    />
                    <button
                      onClick={saveUserName}
                      className="text-zinc-500 hover:text-white transition-colors ml-2"
                    >
                      <RiSave3Line size={20} />
                    </button>
                  </div>
                </div>

                <div className={`${cardClass} md:col-span-2`}>
                  <div className="flex flex-col gap-1">
                    <span className={titleClass}>
                      <RiTranslate2 className="text-zinc-400" size={18} /> Shell Language
                    </span>
                    <span className="text-[10px] font-mono text-zinc-500">
                      Controls Shell text replies and Gemini Live prompt language.
                    </span>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    {SHELL_LANGUAGE_OPTIONS.map((item) => (
                      <button
                        key={item.id}
                        onClick={() => handleLanguageChange(item.id)}
                        className={`cursor-pointer rounded-lg border px-4 py-3 text-left transition-all ${
                          language === item.id
                            ? 'bg-white text-black border-white shadow-[0_0_15px_rgba(255,255,255,0.18)]'
                            : 'bg-[#050505] border-white/10 text-zinc-400 hover:text-white hover:border-white/30'
                        }`}
                      >
                        <span className="block text-[11px] font-black tracking-widest">
                          {item.label}
                        </span>
                        <span className="block text-[9px] font-mono opacity-65 mt-1">
                          {item.hint}
                        </span>
                      </button>
                    ))}
                  </div>
                  <div className="text-[9px] font-mono text-zinc-500">{languageStatus}</div>
                </div>

                <div className={`${cardClass} relative`}>
                  <div className="flex justify-between items-center">
                    <span className={titleClass}>
                      <RiUserVoiceLine className="text-zinc-400" size={18} /> OS Voice Profile
                    </span>
                    {isSystemActive && (
                      <span className="text-[10px] text-red-400 font-mono tracking-widest flex items-center gap-1 bg-red-500/10 px-2 py-1 rounded border border-red-500/20">
                        <RiLock2Line /> LOCKED AS Shell AI IS CONNECTED
                      </span>
                    )}
                  </div>
                  <div
                    className={`flex gap-3 h-12 mt-1 ${isSystemActive ? 'opacity-40 cursor-not-allowed' : ''}`}
                  >
                    {(['FEMALE', 'MALE'] as const).map((s) => (
                      <button
                        key={s}
                        onClick={() => handleVoiceChange(s)}
                        disabled={isSystemActive}
                        className={`cursor-pointer flex-1 flex items-center justify-center text-[12px] font-bold rounded-lg transition-all tracking-widest border ${
                          voice === s
                            ? 'bg-white text-black border-white shadow-[0_0_15px_rgba(255,255,255,0.2)]'
                            : 'bg-[#050505] border-white/10 text-zinc-400 hover:text-white hover:border-white/30'
                        }`}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                  <div
                    className={`grid grid-cols-1 sm:grid-cols-2 gap-3 ${isSystemActive ? 'opacity-40 cursor-not-allowed' : ''}`}
                  >
                    {[
                      { id: 'auto', label: 'AUTO LOCAL', hint: 'Desktop first' },
                      { id: 'gemini', label: 'GEMINI LIVE', hint: 'Cloud voice' }
                    ].map((item) => (
                      <button
                        key={item.id}
                        onClick={() => handleVoiceRuntimeChange(item.id as VoiceRuntime)}
                        disabled={isSystemActive}
                        className={`cursor-pointer rounded-lg border px-3 py-2 text-left transition-all ${
                          voiceRuntime === item.id
                            ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-200'
                            : 'bg-[#050505] border-white/10 text-zinc-400 hover:text-white hover:border-white/30'
                        }`}
                      >
                        <span className="block text-[10px] font-black tracking-widest">
                          {item.label}
                        </span>
                        <span className="block text-[9px] font-mono opacity-60 mt-0.5">
                          {item.hint}
                        </span>
                      </button>
                    ))}
                  </div>
                  <div
                    className={`mt-3 rounded-lg border border-white/10 bg-[#050505] p-3 ${isSystemActive ? 'opacity-40 cursor-not-allowed' : ''}`}
                  >
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <span className="text-[10px] font-black tracking-widest text-zinc-500">
                        INPUT MICROPHONE
                      </span>
                      <button
                        onClick={refreshMicrophones}
                        disabled={isSystemActive}
                        className="cursor-pointer rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[9px] font-black tracking-widest text-zinc-400 hover:border-emerald-500/40 hover:text-emerald-300 disabled:cursor-not-allowed"
                      >
                        REFRESH
                      </button>
                    </div>
                    <select
                      value={selectedMicId}
                      onChange={(event) => handleMicrophoneChange(event.target.value)}
                      disabled={isSystemActive}
                      className="w-full rounded-md border border-white/10 bg-black px-3 py-2 text-[11px] font-mono text-zinc-200 outline-none focus:border-emerald-500/50 disabled:cursor-not-allowed"
                    >
                      <option value="">Auto select best microphone</option>
                      {micDevices.map((device, index) => (
                        <option key={device.deviceId || index} value={device.deviceId}>
                          {device.label || `Microphone ${index + 1}`}
                        </option>
                      ))}
                    </select>
                    <div className="mt-2 text-[9px] font-mono text-zinc-500">{micStatus}</div>
                  </div>
                  {isSystemActive && (
                    <div
                      className="pointer-events-none absolute inset-0 z-10"
                      title="Disconnect AI to change voice"
                    ></div>
                  )}
                </div>

                <div className={`${cardClass} md:col-span-2`}>
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <span className="flex items-center gap-1 text-[10px] font-black tracking-widest text-zinc-500">
                          <RiBrainLine size={12} /> OFFLINE BRAIN
                        </span>
                        <span className="mt-1 block truncate text-[9px] font-mono text-zinc-500">
                          {offlineLlmEngine}
                          {offlineLlmStatus?.modelFamily ? ` / ${String(offlineLlmStatus.modelFamily).toUpperCase()}` : ''}
                          {offlineLlmStatus?.language ? ` / ${String(offlineLlmStatus.language).toUpperCase()}` : ''}
                        </span>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span
                          className={`rounded-full border px-2 py-1 text-[8px] font-black tracking-widest ${
                            offlineLlmReady
                              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                              : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                          }`}
                        >
                          {offlineLlmBadge}
                        </span>
                        <button
                          onClick={refreshOfflineLlmStatus}
                          disabled={offlineLlmBusy}
                          className="cursor-pointer rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[9px] font-black tracking-widest text-zinc-400 hover:border-emerald-500/40 hover:text-emerald-300 disabled:cursor-wait disabled:opacity-50"
                        >
                          {offlineLlmBusy ? '...' : 'REFRESH'}
                        </button>
                      </div>
                    </div>
                    <div className="text-[9px] font-mono leading-relaxed text-zinc-500">
                      {offlineLlmMessage}
                    </div>
                    {offlineModelOptions.length > 0 && (
                      <div className="mt-3 grid grid-cols-1 gap-2">
                        {offlineModelOptions.map((option) => {
                          const modelId = String(option.id || '')
                          const downloadState = offlineModelDownloads[modelId]
                          const status = String(downloadState?.status || '')
                          const isDownloading = status === 'queued' || status === 'downloading' || status === 'verifying'
                          const isSelecting = status === 'selecting'
                          const isSelected = offlineSelectedModelId === modelId
                          const isInstalled = Boolean(option.installed) || status === 'installed'
                          const percent = Math.max(0, Math.min(100, Number(downloadState?.percent || 0)))
                          return (
                            <div
                              key={modelId}
                              className={`rounded-lg border p-3 transition-all ${
                                isSelected
                                  ? 'border-emerald-500/30 bg-emerald-500/10'
                                  : isInstalled
                                    ? 'border-emerald-500/20 bg-emerald-500/[0.04]'
                                  : option.recommended
                                    ? 'border-cyan-500/25 bg-cyan-500/5'
                                    : 'border-white/10 bg-black/30'
                              }`}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-[10px] font-black tracking-widest text-zinc-200">
                                      {option.name || option.family || modelId}
                                    </span>
                                    {option.recommended && (
                                      <span className="rounded border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-[7px] font-black tracking-widest text-cyan-200">
                                        RECOMMENDED
                                      </span>
                                    )}
                                    {isSelected && (
                                      <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[7px] font-black tracking-widest text-emerald-200">
                                        ACTIVE
                                      </span>
                                    )}
                                    {isInstalled && (
                                      <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[7px] font-black tracking-widest text-emerald-200">
                                        INSTALLED
                                      </span>
                                    )}
                                  </div>
                                  <div className="mt-1 text-[8px] font-mono uppercase tracking-widest text-zinc-500">
                                    {option.pc_tier || 'LOCAL'} / {formatOfflineModelRam(option)} / {formatOfflineModelSize(option)} / {option.quantization || 'GGUF'}
                                    {Array.isArray(option.languages) && option.languages.length > 0
                                      ? ` / ${option.languages.join(', ').toUpperCase()}`
                                      : ''}
                                  </div>
                                  <div className="mt-1 text-[9px] font-mono leading-relaxed text-zinc-500">
                                    {option.description || 'Offline chat model.'}
                                  </div>
                                  {Array.isArray(option.strengths) && option.strengths.length > 0 && (
                                    <div className="mt-1 truncate text-[8px] font-mono text-zinc-600">
                                      {option.strengths.slice(0, 4).join('  /  ')}
                                    </div>
                                  )}
                                  {downloadState?.message && (
                                    <div className="mt-2 text-[8px] font-mono text-cyan-300">
                                      {downloadState.message}
                                    </div>
                                  )}
                                  {isDownloading && (
                                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
                                      <div
                                        className="h-full rounded-full bg-cyan-300 transition-all"
                                        style={{ width: `${percent}%` }}
                                      />
                                    </div>
                                  )}
                                </div>
                                <button
                                  onClick={() => (isInstalled ? selectOfflineModel(modelId) : downloadOfflineModel(modelId))}
                                  disabled={!modelId || isDownloading || isSelecting || isSelected}
                                  className={`shrink-0 cursor-pointer rounded-md border px-2.5 py-1.5 text-[8px] font-black tracking-widest transition-all disabled:cursor-wait disabled:opacity-60 ${
                                    isSelected
                                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                                      : isInstalled
                                        ? 'border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-200 hover:border-emerald-500/40'
                                      : 'border-white/10 bg-white/5 text-zinc-300 hover:border-cyan-500/40 hover:text-cyan-200'
                                  }`}
                                >
                                  {isSelected ? 'ACTIVE' : isSelecting ? '...' : isInstalled ? 'USE' : isDownloading ? `${percent}%` : 'DOWNLOAD'}
                                </button>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                    {offlineLlmStatus?.modelFile && (
                      <div className="mt-2 truncate text-[8px] font-mono tracking-widest text-zinc-600">
                        {offlineLlmStatus.modelFile}
                      </div>
                    )}
                    {offlineLlmCandidateSummary && (
                      <div className="mt-1 truncate text-[8px] font-mono tracking-widest text-zinc-600">
                        {offlineLlmCandidateSummary}
                      </div>
                    )}
                  </div>

                <div className={`${cardClass} md:col-span-2`}>
                    <div className="mb-2 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <span className="flex items-center gap-1 text-[10px] font-black tracking-widest text-zinc-500">
                          <RiTerminalWindowLine size={12} /> OFFLINE CODING BRAIN
                        </span>
                        <span className="mt-1 block truncate text-[9px] font-mono text-zinc-500">
                          {offlineCodingLlmEngine}
                          {offlineCodingLlmStatus?.modelFamily ? ` / ${String(offlineCodingLlmStatus.modelFamily).toUpperCase()}` : ''}
                          {offlineCodingLlmStatus?.language ? ` / ${String(offlineCodingLlmStatus.language).toUpperCase()}` : ''}
                        </span>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span
                          className={`rounded-full border px-2 py-1 text-[8px] font-black tracking-widest ${
                            offlineCodingLlmReady
                              ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
                              : 'border-amber-500/30 bg-amber-500/10 text-amber-300'
                          }`}
                        >
                          {offlineCodingLlmBadge}
                        </span>
                        <button
                          onClick={refreshOfflineCodingLlmStatus}
                          disabled={offlineCodingLlmBusy}
                          className="cursor-pointer rounded-md border border-white/10 bg-white/5 px-2 py-1 text-[9px] font-black tracking-widest text-zinc-400 hover:border-emerald-500/40 hover:text-emerald-300 disabled:cursor-wait disabled:opacity-50"
                        >
                          {offlineCodingLlmBusy ? '...' : 'REFRESH'}
                        </button>
                      </div>
                    </div>
                    <div className="text-[9px] font-mono leading-relaxed text-zinc-500">
                      {offlineCodingLlmMessage}
                    </div>
                    {offlineCodingModelOptions.length > 0 && (
                      <div className="mt-3 grid grid-cols-1 gap-2">
                        {offlineCodingModelOptions.map((option) => {
                          const modelId = String(option.id || '')
                          const downloadState = offlineCodingModelDownloads[modelId]
                          const status = String(downloadState?.status || '')
                          const isDownloading = status === 'queued' || status === 'downloading' || status === 'verifying'
                          const isSelecting = status === 'selecting'
                          const isSelected = offlineCodingSelectedModelId === modelId
                          const isInstalled = Boolean(option.installed) || status === 'installed'
                          const percent = Math.max(0, Math.min(100, Number(downloadState?.percent || 0)))
                          return (
                            <div
                              key={modelId}
                              className={`rounded-lg border p-3 transition-all ${
                                isSelected
                                  ? 'border-emerald-500/30 bg-emerald-500/10'
                                  : isInstalled
                                    ? 'border-emerald-500/20 bg-emerald-500/[0.04]'
                                  : option.recommended
                                    ? 'border-cyan-500/25 bg-cyan-500/5'
                                    : 'border-white/10 bg-black/30'
                              }`}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <span className="text-[10px] font-black tracking-widest text-zinc-200">
                                      {option.name || option.family || modelId}
                                    </span>
                                    {option.recommended && (
                                      <span className="rounded border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-[7px] font-black tracking-widest text-cyan-200">
                                        RECOMMENDED
                                      </span>
                                    )}
                                    {isSelected && (
                                      <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[7px] font-black tracking-widest text-emerald-200">
                                        ACTIVE
                                      </span>
                                    )}
                                    {isInstalled && (
                                      <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-1.5 py-0.5 text-[7px] font-black tracking-widest text-emerald-200">
                                        INSTALLED
                                      </span>
                                    )}
                                  </div>
                                  <div className="mt-1 text-[8px] font-mono uppercase tracking-widest text-zinc-500">
                                    {option.pc_tier || 'CODING'} / {formatOfflineModelRam(option)} / {formatOfflineModelSize(option)} / {option.quantization || 'GGUF'}
                                    {Array.isArray(option.languages) && option.languages.length > 0
                                      ? ` / ${option.languages.join(', ').toUpperCase()}`
                                      : ''}
                                  </div>
                                  <div className="mt-1 text-[9px] font-mono leading-relaxed text-zinc-500">
                                    {option.description || 'Offline coding model.'}
                                  </div>
                                  {Array.isArray(option.strengths) && option.strengths.length > 0 && (
                                    <div className="mt-1 truncate text-[8px] font-mono text-zinc-600">
                                      {option.strengths.slice(0, 4).join('  /  ')}
                                    </div>
                                  )}
                                  {downloadState?.message && (
                                    <div className="mt-2 text-[8px] font-mono text-cyan-300">
                                      {downloadState.message}
                                    </div>
                                  )}
                                  {isDownloading && (
                                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/10">
                                      <div
                                        className="h-full rounded-full bg-cyan-300 transition-all"
                                        style={{ width: `${percent}%` }}
                                      />
                                    </div>
                                  )}
                                </div>
                                <button
                                  onClick={() => (isInstalled ? selectOfflineCodingModel(modelId) : downloadOfflineCodingModel(modelId))}
                                  disabled={!modelId || isDownloading || isSelecting || isSelected}
                                  className={`shrink-0 cursor-pointer rounded-md border px-2.5 py-1.5 text-[8px] font-black tracking-widest transition-all disabled:cursor-wait disabled:opacity-60 ${
                                    isSelected
                                      ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200'
                                      : isInstalled
                                        ? 'border-emerald-500/25 bg-emerald-500/[0.06] text-emerald-200 hover:border-emerald-500/40'
                                      : 'border-white/10 bg-white/5 text-zinc-300 hover:border-cyan-500/40 hover:text-cyan-200'
                                  }`}
                                >
                                  {isSelected ? 'ACTIVE' : isSelecting ? '...' : isInstalled ? 'USE' : isDownloading ? `${percent}%` : 'DOWNLOAD'}
                                </button>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                    {offlineCodingLlmStatus?.modelFile && (
                      <div className="mt-2 truncate text-[8px] font-mono tracking-widest text-zinc-600">
                        {offlineCodingLlmStatus.modelFile}
                      </div>
                    )}
                    {offlineCodingLlmCandidateSummary && (
                      <div className="mt-1 truncate text-[8px] font-mono tracking-widest text-zinc-600">
                        {offlineCodingLlmCandidateSummary}
                      </div>
                    )}
                  </div>
              </motion.div>
            )}

            {/* --- TAB 3: API KEYS --- */}
            {activeTab === 'keys' && (
              <motion.div
                key="keys"
                initial={false}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="grid grid-cols-1 gap-6 w-full"
              >
                <div className={`${cardClass} gap-6`}>
                  <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-4">
                    <span className={titleClass}>
                      <RiKey2Line className="text-zinc-400" size={18} /> External API Endpoints
                    </span>
                    <button
                      onClick={saveApiKeys}
                      className="bg-white text-black px-6 py-2.5 rounded-lg text-xs font-bold tracking-widest hover:bg-zinc-200 transition-colors shadow-[0_0_15px_rgba(255,255,255,0.1)] flex items-center justify-center gap-2 cursor-pointer"
                    >
                      <RiSave3Line size={16} /> SAVE ALL KEYS
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiBrainLine size={14} /> Gemini Pro Core
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={geminiKey}
                          onChange={(e) => setGeminiKey(e.target.value)}
                          placeholder="AIzaSy_..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiCpuLine size={14} /> Groq Fast Inferencing
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={groqKey}
                          onChange={(e) => setGroqKey(e.target.value)}
                          placeholder="gsk_..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiCloudLine size={14} /> Hugging Face Vision
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={hfKey}
                          onChange={(e) => setHfKey(e.target.value)}
                          placeholder="hf_..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiPlugLine size={14} /> Tavily Deep Search
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={tavilyKey}
                          onChange={(e) => setTavilyKey(e.target.value)}
                          placeholder="tvly_..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiCloudLine size={14} /> LiveKit API Key
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={livekitKey}
                          onChange={(e) => setLivekitKey(e.target.value)}
                          placeholder="API..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiShieldKeyholeLine size={14} /> LiveKit Secret
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={livekitSecret}
                          onChange={(e) => setLivekitSecret(e.target.value)}
                          placeholder="secret..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 md:col-span-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiPlugLine size={14} /> LiveKit URL
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          value={livekitUrl}
                          onChange={(e) => setLivekitUrl(e.target.value)}
                          placeholder="wss://your-project.livekit.cloud"
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiBrainLine size={14} /> OpenAI
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={openaiKey}
                          onChange={(e) => setOpenaiKey(e.target.value)}
                          placeholder="sk-..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiBrainLine size={14} /> OpenRouter
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={openrouterKey}
                          onChange={(e) => setOpenrouterKey(e.target.value)}
                          placeholder="sk-or-..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiCpuLine size={14} /> Mistral
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={mistralKey}
                          onChange={(e) => setMistralKey(e.target.value)}
                          placeholder="mistral..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiPlugLine size={14} /> Google Search
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={googleSearchKey}
                          onChange={(e) => setGoogleSearchKey(e.target.value)}
                          placeholder="search key..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiPlugLine size={14} /> Search Engine ID
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          value={searchEngineId}
                          onChange={(e) => setSearchEngineId(e.target.value)}
                          placeholder="cx..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>

                    <div className="flex flex-col gap-2">
                      <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                        <RiCloudLine size={14} /> OpenWeather
                      </label>
                      <div className={inputContainerClass}>
                        <input
                          type="password"
                          value={weatherKey}
                          onChange={(e) => setWeatherKey(e.target.value)}
                          placeholder="weather key..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                    </div>
                  </div>

                  <div className="bg-[#050505] border border-cyan-500/15 p-5 rounded-2xl flex flex-col gap-5">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-4">
                      <span className={titleClass}>
                        <RiTelegramLine className="text-cyan-400" size={18} /> Telegram Remote Control
                      </span>
                      <div className="flex flex-wrap gap-2">
                        <button
                          aria-label="Check Telegram bot status"
                          onClick={() => runTelegramTool('shell_telegram:telegram_bot_status', {}, 'status')}
                          disabled={telegramBusy !== ''}
                          className="px-3 py-2 rounded-lg border border-white/10 text-[10px] font-bold tracking-widest text-zinc-300 hover:text-cyan-300 hover:border-cyan-500/30 disabled:opacity-50 transition-all"
                        >
                          {telegramBusy === 'status' ? 'CHECKING' : 'STATUS'}
                        </button>
                        <button
                          aria-label="Start Telegram bot"
                          onClick={() => runTelegramTool('shell_telegram:start_telegram_bot', {}, 'start')}
                          disabled={telegramBusy !== ''}
                          className="px-3 py-2 rounded-lg bg-cyan-500/15 border border-cyan-500/30 text-[10px] font-bold tracking-widest text-cyan-300 hover:bg-cyan-500 hover:text-black disabled:opacity-50 transition-all"
                        >
                          {telegramBusy === 'start' ? 'STARTING' : 'START'}
                        </button>
                        <button
                          aria-label="Stop Telegram bot"
                          onClick={() => runTelegramTool('shell_telegram:stop_telegram_bot', {}, 'stop')}
                          disabled={telegramBusy !== ''}
                          className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/25 text-[10px] font-bold tracking-widest text-red-300 hover:bg-red-500 hover:text-white disabled:opacity-50 transition-all"
                        >
                          {telegramBusy === 'stop' ? 'STOPPING' : 'STOP'}
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <div className="flex flex-col gap-2">
                        <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                          <RiKey2Line size={14} /> BotFather Token
                        </label>
                        <div className={inputContainerClass}>
                          <input
                            type="password"
                            value={telegramToken}
                            onChange={(e) => setTelegramToken(e.target.value)}
                            placeholder="123456789:AA..."
                            className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                          />
                        </div>
                      </div>

                      <div className="flex flex-col gap-2">
                        <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                          <RiUserLine size={14} /> Allowed Chat IDs
                        </label>
                        <div className={inputContainerClass}>
                          <input
                            value={telegramAllowedChatIds}
                            onChange={(e) => setTelegramAllowedChatIds(e.target.value)}
                            placeholder="123456789,987654321"
                            className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                      <label className="cursor-pointer rounded-xl border border-white/10 bg-black/40 p-4 flex items-start gap-3 hover:border-cyan-500/30 transition-all">
                        <input
                          type="checkbox"
                          checked={telegramRemoteEnabled}
                          onChange={(e) => setTelegramRemoteEnabled(e.target.checked)}
                          className="mt-1 accent-cyan-400"
                        />
                        <span>
                          <span className="block text-[11px] font-bold tracking-widest text-zinc-100">
                            Enable PC Control
                          </span>
                          <span className="block mt-1 text-[10px] font-mono text-zinc-500 leading-relaxed">
                            Telegram se open app, screenshot, status jaise safe commands allow karta hai.
                          </span>
                        </span>
                      </label>

                      <label className="cursor-pointer rounded-xl border border-red-500/20 bg-red-500/5 p-4 flex items-start gap-3 hover:border-red-500/40 transition-all">
                        <input
                          type="checkbox"
                          checked={telegramAllowTerminal}
                          onChange={(e) => setTelegramAllowTerminal(e.target.checked)}
                          className="mt-1 accent-red-400"
                        />
                        <span>
                          <span className="block text-[11px] font-bold tracking-widest text-red-200">
                            Allow Terminal Commands
                          </span>
                          <span className="block mt-1 text-[10px] font-mono text-red-300/70 leading-relaxed">
                            Dangerous mode. Sirf trusted chat IDs ke liye enable karo.
                          </span>
                        </span>
                      </label>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_auto] gap-3">
                      <div className={inputContainerClass}>
                        <input
                          value={telegramTestMessage}
                          onChange={(e) => setTelegramTestMessage(e.target.value)}
                          placeholder="Test message..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                      <button
                        aria-label="Save Telegram remote control settings"
                        onClick={saveTelegramConfig}
                        disabled={telegramBusy !== ''}
                        className="px-5 py-3 rounded-lg bg-white text-black text-[10px] font-black tracking-widest hover:bg-zinc-200 disabled:opacity-50 transition-all"
                      >
                        {telegramBusy === 'save' ? 'SAVING' : 'SAVE TELEGRAM'}
                      </button>
                      <button
                        aria-label="Send Telegram test message"
                        onClick={() =>
                          runTelegramTool(
                            'shell_telegram:send_telegram_message_tool',
                            { message: telegramTestMessage },
                            'send'
                          )
                        }
                        disabled={telegramBusy !== ''}
                        className="px-5 py-3 rounded-lg border border-cyan-500/30 text-cyan-300 text-[10px] font-black tracking-widest hover:bg-cyan-500 hover:text-black disabled:opacity-50 transition-all"
                      >
                        {telegramBusy === 'send' ? 'SENDING' : 'SEND TEST'}
                      </button>
                    </div>

                    <pre className="min-h-28 max-h-52 overflow-auto scrollbar-small whitespace-pre-wrap rounded-xl bg-black/70 border border-white/10 p-4 text-[11px] text-zinc-300 font-mono leading-relaxed">
                      {telegramStatus}
                    </pre>
                  </div>

                  {/* --- Instagram Remote Control --- */}
                  <div className="bg-[#050505] border border-cyan-500/15 p-5 rounded-2xl flex flex-col gap-5 mt-4">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-4">
                      <span className={titleClass}>
                        <RiInstagramLine className="text-pink-500" size={18} /> Instagram Controller
                      </span>
                      <div className="flex flex-wrap gap-2">
                        <button
                          aria-label="Check Instagram Login Status"
                          onClick={() => runInstagramTool('shell_instagram:instagram_login_check', {}, 'login')}
                          disabled={instagramBusy !== ''}
                          className="px-3 py-2 rounded-lg border border-white/10 text-[10px] font-bold tracking-widest text-zinc-300 hover:text-pink-400 hover:border-pink-500/30 disabled:opacity-50 transition-all cursor-pointer"
                        >
                          {instagramBusy === 'login' ? 'CHECKING...' : 'LOGIN CHECK'}
                        </button>
                        <button
                          aria-label="Check Instagram DMs"
                          onClick={() => runInstagramTool('shell_instagram:instagram_check_dms', {}, 'dms')}
                          disabled={instagramBusy !== ''}
                          className="px-3 py-2 rounded-lg bg-pink-500/15 border border-pink-500/30 text-[10px] font-bold tracking-widest text-pink-300 hover:bg-pink-500 hover:text-black disabled:opacity-50 transition-all cursor-pointer"
                        >
                          {instagramBusy === 'dms' ? 'FETCHING...' : 'CHECK DMS'}
                        </button>
                        <button
                          aria-label="Get Instagram Followers"
                          onClick={() => runInstagramTool('shell_instagram:instagram_get_followers_tool', {}, 'followers')}
                          disabled={instagramBusy !== ''}
                          className="px-3 py-2 rounded-lg border border-white/10 text-[10px] font-bold tracking-widest text-zinc-300 hover:text-pink-400 hover:border-pink-500/30 disabled:opacity-50 transition-all cursor-pointer"
                        >
                          {instagramBusy === 'followers' ? 'FETCHING...' : 'FOLLOWERS'}
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <div className="flex flex-col gap-2">
                        <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                          <RiUserLine size={14} /> Username
                        </label>
                        <div className={inputContainerClass}>
                          <input
                            value={instagramUsername}
                            onChange={(e) => setInstagramUsername(e.target.value)}
                            placeholder="Enter Instagram username..."
                            className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                          />
                        </div>
                      </div>

                      <div className="flex flex-col gap-2">
                        <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                          <RiKey2Line size={14} /> Password
                        </label>
                        <div className={inputContainerClass}>
                          <input
                            type="password"
                            value={instagramPassword}
                            onChange={(e) => setInstagramPassword(e.target.value)}
                            placeholder="Enter Instagram password..."
                            className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                      <div className="flex flex-col gap-2">
                        <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase">
                          Comment Auto-Reply text
                        </label>
                        <div className={inputContainerClass}>
                          <input
                            value={instagramCommentReply}
                            onChange={(e) => setInstagramCommentReply(e.target.value)}
                            className="bg-transparent border-none outline-none text-xs text-zinc-100 w-full placeholder:text-zinc-700"
                          />
                        </div>
                        <button
                          onClick={() =>
                            runInstagramTool(
                              'shell_instagram:instagram_auto_reply_comments',
                              { reply_message: instagramCommentReply },
                              'comment_reply'
                            )
                          }
                          disabled={instagramBusy !== ''}
                          className="w-full py-2.5 rounded-lg border border-pink-500/30 text-pink-300 text-[10px] font-black tracking-widest hover:bg-pink-500 hover:text-black disabled:opacity-50 transition-all cursor-pointer"
                        >
                          {instagramBusy === 'comment_reply' ? 'REPLYING...' : 'AUTO-REPLY COMMENTS'}
                        </button>
                      </div>

                      <div className="flex flex-col gap-2">
                        <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase">
                          DM Auto-Reply text
                        </label>
                        <div className={inputContainerClass}>
                          <input
                            value={instagramDmReply}
                            onChange={(e) => setInstagramDmReply(e.target.value)}
                            className="bg-transparent border-none outline-none text-xs text-zinc-100 w-full placeholder:text-zinc-700"
                          />
                        </div>
                        <button
                          onClick={() =>
                            runInstagramTool(
                              'shell_instagram:instagram_auto_reply_dms',
                              { reply_message: instagramDmReply },
                              'dm_reply'
                            )
                          }
                          disabled={instagramBusy !== ''}
                          className="w-full py-2.5 rounded-lg border border-pink-500/30 text-pink-300 text-[10px] font-black tracking-widest hover:bg-pink-500 hover:text-black disabled:opacity-50 transition-all cursor-pointer"
                        >
                          {instagramBusy === 'dm_reply' ? 'REPLYING...' : 'AUTO-REPLY DMS'}
                        </button>
                      </div>

                      <div className="flex flex-col gap-2">
                        <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase">
                          Profile Info Lookup
                        </label>
                        <div className={inputContainerClass}>
                          <input
                            value={instagramTargetUser}
                            onChange={(e) => setInstagramTargetUser(e.target.value)}
                            placeholder="username (e.g. virat.kohli)"
                            className="bg-transparent border-none outline-none text-xs text-zinc-100 w-full placeholder:text-zinc-700"
                          />
                        </div>
                        <button
                          onClick={() =>
                            runInstagramTool(
                              'shell_instagram:instagram_get_profile_info_tool',
                              { username: instagramTargetUser },
                              'profile_info'
                            )
                          }
                          disabled={instagramBusy !== ''}
                          className="w-full py-2.5 rounded-lg bg-pink-500/10 border border-pink-500/25 text-pink-300 text-[10px] font-black tracking-widest hover:bg-pink-500 hover:text-black disabled:opacity-50 transition-all cursor-pointer"
                        >
                          {instagramBusy === 'profile_info' ? 'SEARCHING...' : 'LOOKUP PROFILE'}
                        </button>
                      </div>
                    </div>

                    <div className="flex justify-end gap-3 mt-1">
                      <button
                        onClick={saveInstagramConfig}
                        disabled={instagramBusy !== ''}
                        className="px-6 py-3 rounded-lg bg-white text-black text-[10px] font-black tracking-widest hover:bg-zinc-200 disabled:opacity-50 transition-all cursor-pointer"
                      >
                        {instagramBusy === 'save' ? 'SAVING...' : 'SAVE INSTAGRAM CONFIG'}
                      </button>
                    </div>

                    <pre className="min-h-28 max-h-52 overflow-auto scrollbar-small whitespace-pre-wrap rounded-xl bg-black/70 border border-white/10 p-4 text-[11px] text-zinc-300 font-mono leading-relaxed">
                      {instagramStatus}
                    </pre>
                  </div>

                  {/* --- WhatsApp Controller --- */}
                  <div className="bg-[#050505] border border-cyan-500/15 p-5 rounded-2xl flex flex-col gap-5 mt-4">
                    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-white/10 pb-4">
                      <span className={titleClass}>
                        <RiWhatsappLine className="text-emerald-400" size={18} /> WhatsApp Controller & Auto-Reply
                      </span>
                      <div className="flex flex-wrap gap-2">
                        <button
                          aria-label="Check WhatsApp Auto Reply Status"
                          onClick={() => runWhatsAppTool('shell_whatsapp_auto_reply:auto_reply_status', {}, 'status')}
                          disabled={whatsappBusy !== ''}
                          className="px-3 py-2 rounded-lg border border-white/10 text-[10px] font-bold tracking-widest text-zinc-300 hover:text-emerald-400 hover:border-emerald-500/30 disabled:opacity-50 transition-all cursor-pointer"
                        >
                          {whatsappBusy === 'status' ? 'CHECKING...' : 'STATUS'}
                        </button>
                        <button
                          aria-label="Start WhatsApp Bot"
                          onClick={() => runWhatsAppTool('shell_whatsapp_auto_reply:start_auto_reply', {}, 'start')}
                          disabled={whatsappBusy !== ''}
                          className="px-3 py-2 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-[10px] font-bold tracking-widest text-emerald-300 hover:bg-emerald-500 hover:text-black disabled:opacity-50 transition-all cursor-pointer"
                        >
                          {whatsappBusy === 'start' ? 'STARTING...' : 'START AUTO-REPLY'}
                        </button>
                        <button
                          aria-label="Stop WhatsApp Bot"
                          onClick={() => runWhatsAppTool('shell_whatsapp_auto_reply:stop_auto_reply', {}, 'stop')}
                          disabled={whatsappBusy !== ''}
                          className="px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/25 text-[10px] font-bold tracking-widest text-red-300 hover:bg-red-500 hover:text-white disabled:opacity-50 transition-all cursor-pointer"
                        >
                          {whatsappBusy === 'stop' ? 'STOPPING...' : 'STOP AUTO-REPLY'}
                        </button>
                        <button
                          aria-label="Get WhatsApp Contact Memory"
                          onClick={() => runWhatsAppTool('shell_whatsapp_auto_reply:whatsapp_contact_memory', {}, 'memory')}
                          disabled={whatsappBusy !== ''}
                          className="px-3 py-2 rounded-lg border border-white/10 text-[10px] font-bold tracking-widest text-zinc-300 hover:text-emerald-400 hover:border-emerald-500/30 disabled:opacity-50 transition-all cursor-pointer"
                        >
                          {whatsappBusy === 'memory' ? 'LOADING...' : 'CONTACT MEMORY'}
                        </button>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                      <div className="flex flex-col gap-2">
                        <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                          <RiUserLine size={14} /> Direct Message Recipient Name
                        </label>
                        <div className={inputContainerClass}>
                          <input
                            value={whatsappContact}
                            onChange={(e) => setWhatsappContact(e.target.value)}
                            placeholder="Enter contact name (e.g. Papa, Raj)..."
                            className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                          />
                        </div>
                      </div>

                      <div className="flex flex-col gap-2">
                        <label className="text-[10px] text-zinc-400 font-mono tracking-widest uppercase flex items-center gap-2">
                          <RiTranslate2 size={14} /> Message Text
                        </label>
                        <div className={inputContainerClass}>
                          <input
                            value={whatsappMessage}
                            onChange={(e) => setWhatsappMessage(e.target.value)}
                            placeholder="Type direct WhatsApp message..."
                            className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                          />
                        </div>
                      </div>
                    </div>

                    <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto_auto] gap-3">
                      <div className={inputContainerClass}>
                        <input
                          value={whatsappLogFilter}
                          onChange={(e) => setWhatsappLogFilter(e.target.value)}
                          placeholder="Filter log by contact name..."
                          className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full placeholder:text-zinc-700"
                        />
                      </div>
                      <button
                        onClick={() =>
                          runWhatsAppTool(
                            'shell_whatsapp_auto_reply:whatsapp_reply_log',
                            { filter: whatsappLogFilter },
                            'view_log'
                          )
                        }
                        disabled={whatsappBusy !== ''}
                        className="px-5 py-3 rounded-lg border border-emerald-500/30 text-emerald-300 text-[10px] font-black tracking-widest hover:bg-emerald-500 hover:text-black disabled:opacity-50 transition-all cursor-pointer"
                      >
                        {whatsappBusy === 'view_log' ? 'FETCHING...' : 'VIEW REPLY LOG'}
                      </button>
                      <button
                        onClick={() =>
                          runWhatsAppTool(
                            'shell_whatsapp_auto_reply:clear_whatsapp_reply_log_tool',
                            { confirm: 'yes' },
                            'clear_log'
                          )
                        }
                        disabled={whatsappBusy !== ''}
                        className="px-5 py-3 rounded-lg bg-red-500/10 border border-red-500/25 text-[10px] font-bold tracking-widest text-red-300 hover:bg-red-500 hover:text-white disabled:opacity-50 transition-all cursor-pointer"
                      >
                        {whatsappBusy === 'clear_log' ? 'CLEARING...' : 'CLEAR REPLY LOG'}
                      </button>
                    </div>

                    <div className="flex justify-end gap-3 mt-1">
                      <button
                        onClick={sendDirectWhatsApp}
                        disabled={whatsappBusy !== ''}
                        className="px-6 py-3 rounded-lg bg-white text-black text-[10px] font-black tracking-widest hover:bg-zinc-200 disabled:opacity-50 transition-all cursor-pointer"
                      >
                        {whatsappBusy === 'send' ? 'SENDING MESSAGE...' : 'SEND MSG (DIRECT)'}
                      </button>
                    </div>

                    <pre className="min-h-28 max-h-52 overflow-auto scrollbar-small whitespace-pre-wrap rounded-xl bg-black/70 border border-white/10 p-4 text-[11px] text-zinc-300 font-mono leading-relaxed">
                      {whatsappStatus}
                    </pre>
                  </div>



                  {apiSaveResult && (
                    <div className="bg-emerald-500/5 border border-emerald-500/20 p-3 rounded-xl text-[10px] text-emerald-300 font-mono">
                      {apiSaveResult}
                    </div>
                  )}

                  <div className="bg-[#050505] border border-white/5 p-4 rounded-xl mt-2 flex items-start gap-3">
                    <RiShieldKeyholeLine className="text-zinc-500 shrink-0 mt-0.5" size={16} />
                    <p className="text-[10px] text-zinc-400 font-mono leading-relaxed">
                      [SECURITY NOTICE]: All API keys are encrypted and stored strictly in your
                      local OS. Shell AI does not transmit these keys to any centralized server. You
                      maintain full ownership and billing control over your provider endpoints.
                    </p>
                  </div>
                </div>
              </motion.div>
            )}

            {activeTab === 'connectors' && (
              <div className="flex flex-col gap-6 w-full animate-fadeIn">
                {/* Search & Category Filter Bar */}
                <div className="flex flex-col sm:flex-row gap-4 items-center justify-between border-b border-white/10 pb-6 mb-2">
                  <div className="flex gap-2 bg-black/40 border border-white/10 rounded-lg px-3 py-2 w-full sm:max-w-xs focus-within:border-zinc-500 transition-all">
                    <input
                      type="text"
                      value={pluginSearch}
                      onChange={(e) => setPluginSearch(e.target.value)}
                      placeholder="Search plugins & connectors..."
                      className="bg-transparent border-none outline-none text-xs font-mono text-zinc-100 w-full placeholder:text-zinc-600"
                    />
                  </div>
                  <div className="flex gap-1.5 p-1 bg-black/40 border border-white/5 rounded-lg overflow-x-auto max-w-full">
                    {(['all', 'communication', 'social', 'productivity'] as const).map((cat) => (
                      <button
                        key={cat}
                        onClick={() => setPluginCategory(cat)}
                        className={`px-3 py-1 rounded-md text-[10px] font-bold tracking-wider uppercase transition-all cursor-pointer whitespace-nowrap ${
                          pluginCategory === cat
                            ? 'bg-white text-black font-semibold shadow'
                            : 'text-zinc-400 hover:text-white hover:bg-white/5'
                        }`}
                      >
                        {cat}
                      </button>
                    ))}
                  </div>
                </div>

                <motion.div
                  key="connectors"
                  initial={false}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.2 }}
                  className="grid grid-cols-1 md:grid-cols-2 gap-6 w-full"
                >
                  {allPlugins
                    .filter((p) => {
                      const matchesSearch =
                        p.name.toLowerCase().includes(pluginSearch.toLowerCase()) ||
                        p.description.toLowerCase().includes(pluginSearch.toLowerCase()) ||
                        p.developer.toLowerCase().includes(pluginSearch.toLowerCase());
                      const matchesCategory = pluginCategory === 'all' || p.category === pluginCategory;
                      return matchesSearch && matchesCategory;
                    })
                    .map((plugin) => {
                      const isConnected = connectorsStatus[plugin.id]?.connected || false;
                      const details = connectorsStatus[plugin.id] || {};
                      const isLoading = connectorsLoading[plugin.id] || false;
                      const errorMsg = connectorsError[plugin.id] || '';
                      const successMsg = connectorsSuccess[plugin.id] || '';
                      const IconComponent = plugin.icon;

                      return (
                        <div
                          key={plugin.id}
                          className={`${cardClass} border-white/10 bg-gradient-to-br ${plugin.brandColor} ${plugin.borderColor} flex flex-col justify-between h-full relative overflow-hidden group`}
                        >
                          <div className="absolute inset-0 bg-white/[0.01] opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
                          
                          <div>
                            <div className="flex justify-between items-start border-b border-white/10 pb-4 mb-4">
                              <div className="flex flex-col">
                                <span className={`${titleClass} flex items-center gap-2`}>
                                  <IconComponent className={plugin.iconColor} size={20} />
                                  {plugin.name}
                                </span>
                                <span className="text-[10px] text-zinc-500 font-sans mt-0.5">by {plugin.developer}</span>
                              </div>
                              
                              {plugin.comingSoon ? (
                                <span className="px-2 py-0.5 rounded bg-zinc-800/50 text-zinc-500 text-[9px] font-bold tracking-wider">
                                  COMING SOON
                                </span>
                              ) : (
                                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-widest flex items-center gap-1.5 ${
                                  isConnected
                                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-[0_0_10px_rgba(16,185,129,0.1)]'
                                    : 'bg-red-500/10 text-red-400 border border-red-500/20'
                                }`}>
                                  <span className={`w-1.5 h-1.5 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
                                  {isConnected ? 'CONNECTED' : 'DISCONNECTED'}
                                </span>
                              )}
                            </div>

                            <p className="text-[11px] text-zinc-400 leading-relaxed font-sans mb-6">
                              {plugin.description}
                            </p>

                            {!plugin.comingSoon && (
                              <div className="flex flex-col gap-4 text-xs font-mono text-zinc-300 mb-4">
                                {isConnected ? (
                                  <div className="flex flex-col gap-2 bg-black/30 border border-white/5 p-3 rounded-xl">
                                    <p className="text-emerald-300 text-[11px]">✓ Integration configured successfully.</p>
                                    {details.account && (
                                      <p className="text-zinc-400 text-[11px]">Account: <span className="text-white">{details.account}</span></p>
                                    )}
                                    {details.last_connected && (
                                      <p className="text-zinc-400 text-[11px]">Last Active: <span className="text-white">{new Date(details.last_connected).toLocaleString()}</span></p>
                                    )}
                                    {details.message_count !== undefined && details.message_count > 0 && (
                                      <p className="text-zinc-400 text-[11px]">Messages Sent: <span className="text-white">{details.message_count}</span></p>
                                    )}
                                  </div>
                                ) : (
                                  <>
                                    {plugin.id === 'whatsapp' && (
                                      <div className="flex flex-col gap-1.5">
                                        <label className="text-[10px] text-zinc-500 font-mono tracking-widest uppercase">Phone Number (Optional)</label>
                                        <div className={`${inputContainerClass} bg-black/40 border-zinc-800`}>
                                          <input
                                            type="text"
                                            value={whatsappPhoneInput}
                                            onChange={(e) => setWhatsappPhoneInput(e.target.value)}
                                            placeholder="+919876543210"
                                            className="bg-transparent border-none outline-none text-xs font-mono text-zinc-100 w-full placeholder:text-zinc-800"
                                          />
                                        </div>
                                      </div>
                                    )}
                                    {plugin.id === 'telegram' && (
                                      <div className="flex flex-col gap-1.5">
                                        <label className="text-[10px] text-zinc-500 font-mono tracking-widest uppercase">Telegram Bot Token</label>
                                        <div className={`${inputContainerClass} bg-black/40 border-zinc-800`}>
                                          <input
                                            type="password"
                                            value={telegramTokenInput}
                                            onChange={(e) => setTelegramTokenInput(e.target.value)}
                                            placeholder="123456789:bot_token"
                                            className="bg-transparent border-none outline-none text-xs font-mono text-zinc-100 w-full placeholder:text-zinc-800"
                                          />
                                        </div>
                                      </div>
                                    )}
                                  </>
                                )}
                              </div>
                            )}
                          </div>

                          {!plugin.comingSoon && (
                            <div className="flex flex-col gap-2 mt-auto">
                              {isConnected ? (
                                <button
                                  onClick={() => handleDisconnect(plugin.id)}
                                  disabled={isLoading}
                                  className="w-full py-2.5 rounded-lg bg-red-500/10 border border-red-500/25 text-red-400 hover:bg-red-500 hover:text-white transition-all text-xs font-bold tracking-wider cursor-pointer disabled:opacity-50"
                                >
                                  {isLoading ? 'DISCONNECTING...' : 'DISCONNECT'}
                                </button>
                              ) : (
                                <button
                                  onClick={() => {
                                    if (plugin.id === 'telegram') {
                                      handleConnect('telegram', { bot_token: telegramTokenInput });
                                    } else if (plugin.id === 'whatsapp') {
                                      handleConnect('whatsapp', { phone_number: whatsappPhoneInput });
                                    } else {
                                      handleConnect(plugin.id, {});
                                    }
                                  }}
                                  disabled={isLoading}
                                  className="w-full py-2.5 rounded-lg bg-white text-black hover:bg-zinc-200 transition-all text-xs font-bold tracking-wider cursor-pointer disabled:opacity-50"
                                >
                                  {isLoading
                                    ? 'INITIALIZING...'
                                    : plugin.id === 'whatsapp'
                                    ? 'CONNECT (QR CODE)'
                                    : plugin.id === 'telegram'
                                    ? 'CONNECT BOT'
                                    : 'CONNECT ACCOUNT'}
                                </button>
                              )}

                              {errorMsg && (
                                <div className="bg-red-500/5 border border-red-500/20 p-2.5 rounded-lg text-[10px] text-red-400 font-sans mt-2">
                                  {errorMsg}
                                </div>
                              )}
                              {successMsg && (
                                <div className="bg-emerald-500/5 border border-emerald-500/20 p-2.5 rounded-lg text-[10px] text-emerald-400 font-sans mt-2">
                                  {successMsg}
                                </div>
                              )}
                            </div>
                          )}

                          {plugin.comingSoon && (
                            <button
                              disabled
                              className="w-full py-2.5 rounded-lg bg-white/5 border border-white/5 text-zinc-500 text-xs font-bold tracking-wider mt-auto cursor-not-allowed"
                            >
                              COMING SOON
                            </button>
                          )}
                        </div>
                      );
                    })}
                </motion.div>
              </div>
            )}
          </>
        </div>
      </motion.div>
    </div>
  )
}

export default SettingsView
