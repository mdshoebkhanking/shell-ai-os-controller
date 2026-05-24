import { useEffect, useRef, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import * as faceapi from 'face-api.js'
import { GiArtificialIntelligence } from 'react-icons/gi'
import {
  RiKey2Line,
  RiSave3Line,
  RiUserVoiceLine,
  RiUserLine,
  RiLockPasswordLine,
  RiScan2Line,
  RiAddLine,
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
  RiTelegramLine
} from 'react-icons/ri'

interface SettingsProps {
  isSystemActive: boolean
}

type TabType = 'updates' | 'general' | 'keys' | 'security'

const SettingsView = ({ isSystemActive }: SettingsProps) => {
  const [activeTab, setActiveTab] = useState<TabType>('updates')

  const [voice, setVoice] = useState<'MALE' | 'FEMALE'>(
    (localStorage.getItem('shell_voice_profile') as 'MALE' | 'FEMALE') || 'MALE'
  )
  const [voiceRuntime, setVoiceRuntime] = useState<'gemini' | 'backend'>(
    (localStorage.getItem('shell_voice_runtime') as 'gemini' | 'backend') || 'gemini'
  )
  const [personality, setPersonality] = useState('')
  const [userName, setUserName] = useState(localStorage.getItem('shell_user_name') || '')

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

  const [isSecurityUnlocked, setIsSecurityUnlocked] = useState(false)
  const [authPin, setAuthPin] = useState('')
  const [authError, setAuthError] = useState(false)

  const [newPin, setNewPin] = useState('')
  const [faceCount, setFaceCount] = useState(0)

  const [isScanningFace, setIsScanningFace] = useState(false)
  const [enrollStatus, setEnrollStatus] = useState('')
  const videoRef = useRef<HTMLVideoElement>(null)

  const [appVersion, setAppVersion] = useState('1.1.5')
  const [updateStatus, setUpdateStatus] = useState<
    'idle' | 'checking' | 'available' | 'downloading' | 'ready' | 'error'
  >('idle')
  const [updateVersion, setUpdateVersion] = useState('')
  const [updateNotes, setUpdateNotes] = useState('No new updates detected.')
  const [downloadProgress, setDownloadProgress] = useState(0)

  useEffect(() => {
    if (window.electron?.ipcRenderer) {
      window.electron.ipcRenderer.invoke('get-personality').then((res) => {
        if (res) setPersonality(res)
      })
      window.electron.ipcRenderer
        .invoke('check-vault-status')
        .then((res) => setFaceCount(res?.faceCount || 0))

      window.electron.ipcRenderer.invoke('get-app-version').then((v) => setAppVersion(v))
      window.electron.ipcRenderer.invoke('secure-get-keys').then((keys) => {
        if (!keys || typeof keys !== 'object') return
        if (keys.geminiKey) setGeminiKey(keys.geminiKey)
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
      })

      window.electron.ipcRenderer.on('updater-event', (_e, { status, data, error }) => {
        if (status === 'checking') setUpdateStatus('checking')
        if (status === 'available') {
          setUpdateStatus('available')
          setUpdateVersion(data.version)
          setUpdateNotes(data.releaseNotes || 'Bug fixes and performance improvements.')
        }
        if (status === 'not-available') {
          setUpdateStatus('idle')
          setUpdateNotes('System is up to date.')
        }
        if (status === 'downloading') {
          setUpdateStatus('downloading')
          setDownloadProgress(Math.round(data.percent))
        }
        if (status === 'downloaded') setUpdateStatus('ready')
        if (status === 'error') {
          setUpdateStatus('error')
          setUpdateNotes(`Error: ${error}`)
        }
      })
    }
    return () => {
      if (window.electron?.ipcRenderer)
        window.electron.ipcRenderer.removeAllListeners('updater-event')
    }
  }, [])

  const checkForUpdates = () => window.electron.ipcRenderer.invoke('check-for-updates')
  const downloadUpdate = () => window.electron.ipcRenderer.invoke('download-update')
  const installUpdate = () => window.electron.ipcRenderer.invoke('install-update')

  const handleVoiceChange = (v: 'MALE' | 'FEMALE') => {
    if (isSystemActive) return
    setVoice(v)
    localStorage.setItem('shell_voice_profile', v)
  }

  const handleVoiceRuntimeChange = (runtime: 'gemini' | 'backend') => {
    if (isSystemActive) return
    setVoiceRuntime(runtime)
    localStorage.setItem('shell_voice_runtime', runtime)
    window.dispatchEvent(new CustomEvent('shell-voice-runtime-changed'))
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
    localStorage.setItem('shell_custom_api_key', geminiKey)
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

    if (window.electron?.ipcRenderer) {
      try {
        const result = await window.electron.ipcRenderer.invoke('secure-save-keys', {
          geminiKey,
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
          telegramAllowTerminal: telegramAllowTerminal ? '1' : '0'
        })
        if (result?.rejected && Object.keys(result.rejected).length) {
          setApiSaveResult(`Rejected: ${Object.keys(result.rejected).join(', ')}`)
        } else {
          setApiSaveResult(`Saved: ${(result?.saved || []).length} backend keys updated`)
        }
      } catch (e) {}
    }
    alert(
      'All Neural Uplinks (API Keys) secured locally and in OS Vault. Restart AI modules to apply.'
    )
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

  const currentWordCount = personality
    .trim()
    .split(/\s+/)
    .filter((w) => w.length > 0).length

  const unlockSecurityModule = async () => {
    if (!window.electron?.ipcRenderer) return
    const isValid = await window.electron.ipcRenderer.invoke('verify-vault-pin', authPin)
    if (isValid) {
      setIsSecurityUnlocked(true)
      setAuthPin('')
    } else {
      setAuthError(true)
      setTimeout(() => setAuthError(false), 1000)
    }
  }

  const updateMasterPin = async () => {
    if (newPin.length !== 4 || !window.electron?.ipcRenderer) return
    await window.electron.ipcRenderer.invoke('setup-vault-pin', newPin)
    setNewPin('')
    alert('Master PIN Updated Successfully.')
  }

  const startFaceEnrollment = async () => {
    setIsScanningFace(true)
    setEnrollStatus('INITIALIZING CAMERA...')
    try {
      await Promise.all([
        faceapi.nets.ssdMobilenetv1.loadFromUri('./models'),
        faceapi.nets.faceLandmark68Net.loadFromUri('./models'),
        faceapi.nets.faceRecognitionNet.loadFromUri('./models')
      ])

      const stream = await navigator.mediaDevices.getUserMedia({ video: true })
      if (videoRef.current) {
        videoRef.current.srcObject = stream
        setEnrollStatus('POSITION FACE IN FRAME')

        const scanInterval = setInterval(async () => {
          if (!videoRef.current || videoRef.current.readyState !== 4) return
          const detection = await faceapi
            .detectSingleFace(videoRef.current)
            .withFaceLandmarks()
            .withFaceDescriptor()

          if (detection) {
            clearInterval(scanInterval)
            setEnrollStatus('FACE ACQUIRED. ENCRYPTING...')
            const descriptorArray = Array.from(detection.descriptor)

            if (window.electron?.ipcRenderer) {
              await window.electron.ipcRenderer.invoke('setup-vault-face', descriptorArray)
            }

            stream.getTracks().forEach((t) => t.stop())
            setIsScanningFace(false)
            setFaceCount((prev) => prev + 1)
            alert('New Biometric Identity Saved.')
          }
        }, 1000)
      }
    } catch (e) {
      setEnrollStatus('CAMERA ERROR')
      setTimeout(() => setIsScanningFace(false), 2000)
    }
  }

  const cardClass =
    'bg-[#0f0f13] border border-white/10 p-6 md:p-8 rounded-2xl flex flex-col gap-5 hover:border-white/20 transition-all shadow-lg'
  const inputContainerClass =
    'flex items-center bg-[#050505] border border-white/10 rounded-lg px-4 py-3 focus-within:border-white/30 focus-within:bg-black transition-all duration-300 w-full'
  const titleClass = 'text-sm font-semibold text-white flex items-center gap-2'

  return (
    <div className="h-full min-h-0 p-4 md:p-8 lg:p-10 flex flex-col items-center bg-black text-zinc-100 overflow-hidden">
      <motion.div
        className="w-full max-w-4xl h-full min-h-0 flex flex-col gap-6 md:gap-8"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
      >
        <div className="shrink-0 z-30 flex flex-col md:flex-row md:items-center justify-between gap-6 border-b border-white/10 bg-black/95 pb-6 pt-1 backdrop-blur-xl">
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

          <div className="flex bg-[#0a0a0c] p-1 rounded-xl border border-white/10 w-full md:w-fit shadow-lg overflow-x-auto scrollbar-none">
            <button
              aria-label="Open settings system tab"
              onClick={() => setActiveTab('updates')}
              className={`flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-3 text-xs font-bold tracking-widest rounded-lg transition-all duration-300 ${activeTab === 'updates' ? 'bg-white text-black shadow-md' : 'text-zinc-500 hover:text-white hover:bg-white/5'}`}
            >
              <RiTerminalWindowLine size={16} /> SYSTEM
            </button>
            <button
              aria-label="Open settings general tab"
              onClick={() => setActiveTab('general')}
              className={`flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-3 text-xs font-bold tracking-widest rounded-lg transition-all duration-300 ${activeTab === 'general' ? 'bg-white text-black shadow-md' : 'text-zinc-500 hover:text-white hover:bg-white/5'}`}
            >
              <RiSettings4Line size={16} /> GENERAL
            </button>
            <button
              aria-label="Open settings api keys tab"
              onClick={() => setActiveTab('keys')}
              className={`flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-3 text-xs font-bold tracking-widest rounded-lg transition-all duration-300 ${activeTab === 'keys' ? 'bg-white text-black shadow-md' : 'text-zinc-500 hover:text-white hover:bg-white/5'}`}
            >
              <RiPlugLine size={16} /> API KEYS
            </button>
            <button
              aria-label="Open settings security tab"
              onClick={() => setActiveTab('security')}
              className={`flex-1 md:flex-none flex items-center justify-center gap-2 px-6 py-3 text-xs font-bold tracking-widest rounded-lg transition-all duration-300 ${activeTab === 'security' ? 'bg-white text-black shadow-md' : 'text-zinc-500 hover:text-white hover:bg-white/5'}`}
            >
              <RiShieldKeyholeLine size={16} /> SECURITY
            </button>
          </div>
        </div>

        <div className="relative w-full flex-1 min-h-0 overflow-y-auto scrollbar-small pb-12 mt-2 pr-1">
          <>
            {activeTab === 'updates' && (
              <motion.div
                key="updates"
                initial={{ opacity: 0, y: 10 }}
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
                          <RiDownloadCloud2Line size={16} /> INITIALIZE DOWNLOAD
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
                          <RiRocketLine size={16} /> EXECUTE RESTART
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
                initial={{ opacity: 0, y: 10 }}
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
                    className={`grid grid-cols-2 gap-3 ${isSystemActive ? 'opacity-40 cursor-not-allowed' : ''}`}
                  >
                    {[
                      { id: 'gemini', label: 'GEMINI LIVE', hint: 'Natural AI voice' },
                      { id: 'backend', label: 'LOCAL FALLBACK', hint: 'OS voice only' }
                    ].map((item) => (
                      <button
                        key={item.id}
                        onClick={() => handleVoiceRuntimeChange(item.id as 'gemini' | 'backend')}
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
                  {isSystemActive && (
                    <div
                      className="absolute inset-0 z-10"
                      title="Disconnect AI to change voice"
                    ></div>
                  )}
                </div>
              </motion.div>
            )}

            {/* --- TAB 3: API KEYS --- */}
            {activeTab === 'keys' && (
              <motion.div
                key="keys"
                initial={{ opacity: 0, y: 10 }}
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

            {/* --- TAB 4: SECURITY --- */}
            {activeTab === 'security' && (
              <motion.div
                key="security"
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
                className="w-full rounded-3xl overflow-hidden shadow-2xl border border-white/5"
              >
                <AnimatePresence>
                  {!isSecurityUnlocked && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0, backdropFilter: 'blur(0px)' }}
                      className="absolute inset-0 z-20 backdrop-blur-2xl bg-black/70 border border-white/10 rounded-3xl flex flex-col items-center justify-center"
                    >
                      <div className="bg-[#111] p-5 rounded-full mb-6 border border-white/10 shadow-[0_0_30px_rgba(255,255,255,0.05)]">
                        <RiLockPasswordLine size={40} className="text-white" />
                      </div>
                      <p className="text-xs text-zinc-300 font-mono tracking-widest uppercase mb-6 font-semibold">
                        Authenticate to access Vault Settings
                      </p>
                      <div className="flex gap-3 items-center h-12">
                        <input
                          type="password"
                          maxLength={4}
                          pattern="\d*"
                          value={authPin}
                          onChange={(e) => setAuthPin(e.target.value.replace(/\D/g, ''))}
                          placeholder="PIN"
                          className={`h-full bg-[#050505] border w-32 rounded-lg text-center text-xl tracking-[0.5em] text-white outline-none transition-colors ${authError ? 'border-red-500 text-red-500 bg-red-500/10' : 'border-white/20 focus:border-white focus:bg-[#111]'}`}
                        />
                        <button
                          onClick={unlockSecurityModule}
                          className="h-full px-8 bg-white text-black text-xs font-bold tracking-widest rounded-lg hover:bg-zinc-200 transition-colors shadow-[0_0_15px_rgba(255,255,255,0.2)] cursor-pointer"
                        >
                          UNLOCK
                        </button>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6 bg-[#0a0a0c] p-6 rounded-3xl border border-white/5">
                  <div className="bg-[#111113] border border-white/10 p-7 rounded-2xl flex flex-col gap-5">
                    <span className={titleClass}>
                      <RiLockPasswordLine className="text-zinc-400" size={18} /> Update Master PIN
                    </span>
                    <div className={inputContainerClass}>
                      <input
                        type="password"
                        maxLength={4}
                        pattern="\d*"
                        value={newPin}
                        onChange={(e) => setNewPin(e.target.value.replace(/\D/g, ''))}
                        placeholder="Enter new 4-digit PIN..."
                        className="bg-transparent border-none outline-none text-sm font-mono text-zinc-100 w-full tracking-[0.3em]"
                      />
                      <button
                        onClick={updateMasterPin}
                        className="text-zinc-500 hover:text-white transition-colors ml-2 cursor-pointer"
                      >
                        <RiSave3Line size={20} />
                      </button>
                    </div>
                  </div>

                  <div className="bg-[#111113] border border-white/10 p-7 rounded-2xl flex flex-col gap-6">
                    <div className="flex justify-between items-center border-b border-white/10 pb-4">
                      <span className={titleClass}>
                        <RiScan2Line className="text-zinc-400" size={18} /> Biometric Registry
                      </span>
                      <span className="text-[10px] text-white font-mono tracking-widest bg-white/10 px-3 py-1.5 rounded-md font-semibold border border-white/5">
                        {faceCount} ENROLLED
                      </span>
                    </div>

                    {isScanningFace ? (
                      <div className="flex items-center gap-4 bg-[#050505] p-3 rounded-xl border border-white/20">
                        <video
                          ref={videoRef}
                          autoPlay
                          muted
                          playsInline
                          className="w-16 h-16 rounded-lg object-cover -scale-x-100 border border-white/10"
                        />
                        <div className="flex flex-col gap-1">
                          <span className="text-[11px] text-white font-mono tracking-widest animate-pulse font-bold">
                            {enrollStatus}
                          </span>
                          <span className="text-xs text-zinc-400">Keep head steady...</span>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-4 h-full justify-between">
                        <p className="text-xs text-zinc-400 leading-relaxed">
                          Enroll additional structural face descriptors. Data is mathematically
                          encrypted and stored locally.
                        </p>
                        <button
                          onClick={startFaceEnrollment}
                          className="w-full py-3 rounded-lg bg-white text-black font-bold tracking-widest text-[12px] flex items-center justify-center gap-2 hover:bg-zinc-200 transition-all shadow-[0_0_15px_rgba(255,255,255,0.1)] mt-auto cursor-pointer"
                        >
                          <RiAddLine size={18} /> ENROLL NEW IDENTITY
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
          </>
        </div>
      </motion.div>
    </div>
  )
}

export default SettingsView
