import { useState, useEffect, Suspense, lazy, useCallback, useRef } from 'react'
import {
  RiWifiLine,
  RiLayoutGridLine,
  RiBrainLine,
  RiFolderOpenLine,
  RiPhoneLine,
  RiSettings4Line,
  RiCameraLine,
  RiComputerLine,
  RiCloseLine,
  RiImageLine,
  RiToolsLine
} from 'react-icons/ri'
import { getSystemStatus } from '@renderer/services/system-info'
import { getHistory } from '@renderer/services/shell-ai-brain'
import ViewSkeleton from '@renderer/components/ViewSkelrton'

import DashboardView from '../views/Dashboard'
import PhoneView from '../views/Phone'
import { VisionMode } from '@renderer/IndexRoot'

const AppsView = lazy(() => import('../views/APP'))
const WorkFlowEditorView = lazy(() => import('../views/WorkFlowEditor'))
const NotesView = lazy(() => import('../views/Notes'))
const SettingsView = lazy(() => import('../views/Settings'))
const GalleryView = lazy(() => import('../views/Gallery'))
const ControlCenter = lazy(() => import('../views/ControlCenter'))

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

const glassPanel = 'bg-zinc-950/40 backdrop-blur-xl border border-white/5 rounded-2xl shadow-xl'

const tabs = [
  { id: 'DASHBOARD', icon: <RiLayoutGridLine /> },
  { id: 'Macros', icon: <RiBrainLine /> },
  { id: 'Apps', icon: <RiFolderOpenLine /> },
  { id: 'NOTES', icon: <RiFolderOpenLine /> },
  { id: 'GALLERY', icon: <RiImageLine /> },
  { id: 'PHONE', icon: <RiPhoneLine /> },
  { id: 'CONTROL', icon: <RiToolsLine /> },
  { id: 'SETTINGS', icon: <RiSettings4Line /> }
]

const ShellAI = (props: ShellProps) => {
  const [activeTab, setActiveTab] = useState('DASHBOARD')
  const [stats, setStats] = useState<any>(null)
  const [chatHistory, setChatHistory] = useState<any[]>([])
  const [showSourceModal, setShowSourceModal] = useState(false)
  const historyClearVersionRef = useRef(0)

  const fetchHistory = useCallback(async () => {
    const clearVersion = historyClearVersionRef.current
    const history = await getHistory()
    if (clearVersion !== historyClearVersionRef.current) return
    if (Array.isArray(history)) setChatHistory(history.slice(-15))
  }, [])

  useEffect(() => {
    const timer = setInterval(() => {
      getSystemStatus().then(setStats)
    }, 500)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    fetchHistory()
    const interval = setInterval(fetchHistory, 500)
    return () => clearInterval(interval)
  }, [fetchHistory])

  const handleTranscriptCleared = useCallback(() => {
    historyClearVersionRef.current += 1
    setChatHistory([])
  }, [])

  const handleVisionClick = () => {
    setShowSourceModal(true)
  }

  return (
    <div className="h-full w-full bg-black text-zinc-100 font-sans overflow-hidden select-none flex flex-col relative pb-4">
      <div className="h-14 w-full flex items-center justify-between px-6 bg-zinc-950/80 border-b border-white/5 z-50 backdrop-blur-md">
        <div className="flex items-center gap-3 min-w-0">
          <div className="relative h-9 w-9 shrink-0 rounded-xl border border-emerald-500/25 bg-black/50 p-1 shadow-[0_0_20px_rgba(16,185,129,0.18)] overflow-hidden">
            <img
              src="./shell-logo.png"
              alt="Shell AI"
              className="h-full w-full object-contain drop-shadow-[0_0_10px_rgba(16,185,129,0.55)]"
              draggable={false}
            />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-black tracking-[0.2em] text-sm text-zinc-100">Shell AI</span>
            <span className="text-[11px] font-mono text-emerald-500/60 tracking-widest">
              NEURAL INTERFACE
            </span>
          </div>
        </div>

        <div className="hidden md:flex gap-2 bg-black/40 p-1 rounded-lg border border-white/5">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              aria-label={`Open ${tab.id} view`}
              onClick={() => setActiveTab(tab.id)}
              className={`cursor-pointer px-3 xl:px-5 py-1.5 text-[10px] font-bold tracking-widest rounded-md transition-all duration-300 flex items-center gap-2 ${
                activeTab === tab.id
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)]'
                  : 'text-zinc-500 hover:text-zinc-300 hover:bg-white/5'
              }`}
            >
              {tab.icon} {tab.id}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-4 text-[11px] font-mono font-bold opacity-70">
          <div className="flex items-center gap-2 text-emerald-500 rounded-lg border border-emerald-500/15 bg-emerald-500/5 px-3 py-1">
            <RiWifiLine /> <span>{props.backendVoiceState === 'LISTENING' ? 'LISTENING' : 'READY'}</span>
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-hidden relative bg-[radial-gradient(circle_at_center,var(--tw-gradient-stops))] from-zinc-900/50 via-black to-black">
        <div className={`absolute inset-0 ${activeTab === 'DASHBOARD' ? 'block' : 'hidden'}`}>
          <DashboardView
            props={props}
            stats={stats}
            chatHistory={chatHistory}
            onVisionClick={handleVisionClick}
            onTranscriptCleared={handleTranscriptCleared}
          />
        </div>

        <div className={`absolute inset-0 ${activeTab === 'PHONE' ? 'block' : 'hidden'}`}>
          <PhoneView glassPanel={glassPanel} />
        </div>

        <div className={`absolute inset-0 ${activeTab !== 'DASHBOARD' && activeTab !== 'PHONE' ? 'block' : 'hidden'}`}>
          <Suspense fallback={<ViewSkeleton />}>
            {activeTab === 'Macros' && <WorkFlowEditorView />}
            {activeTab === 'Apps' && <AppsView />}
            {activeTab === 'NOTES' && <NotesView glassPanel={glassPanel} />}
            {activeTab === 'CONTROL' && <ControlCenter />}
            {activeTab === 'SETTINGS' && <SettingsView isSystemActive={props.isSystemActive} />}
            {activeTab === 'GALLERY' && <GalleryView />}
          </Suspense>
        </div>
      </div>

      <div className="md:hidden shrink-0 border-t border-white/10 bg-zinc-950/95 px-2 py-2 overflow-x-auto scrollbar-small">
        <div className="flex gap-2 min-w-max">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              aria-label={`Open ${tab.id} view`}
              onClick={() => setActiveTab(tab.id)}
              className={`cursor-pointer min-w-20 px-3 py-2 rounded-lg text-[9px] font-black tracking-widest flex flex-col items-center gap-1 border transition-all ${
                activeTab === tab.id
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30'
                  : 'bg-black/40 text-zinc-500 border-white/10'
              }`}
            >
              {tab.icon}
              <span>{tab.id}</span>
            </button>
          ))}
        </div>
      </div>

      {showSourceModal && (
        <div className="absolute inset-0 z-100 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
          <div className={`${glassPanel} w-96 p-1 border-emerald-500/30 flex flex-col shadow-2xl`}>
            <div className="flex items-center justify-between p-4 border-b border-white/5 bg-white/5">
              <span className="text-xs font-bold tracking-widest text-emerald-400">
                ESTABLISH UPLINK
              </span>
              <button
                aria-label="Close vision source selector"
                onClick={() => setShowSourceModal(false)}
                className="cursor-pointer text-zinc-500 hover:text-white"
              >
                <RiCloseLine size={18} />
              </button>
            </div>

            <div className="p-4 grid grid-cols-2 gap-4">
              <button
                onClick={() => {
                  props.startVision('camera')
                  setShowSourceModal(false)
                }}
                className="cursor-pointer group flex flex-col items-center justify-center gap-3 p-6 rounded-xl bg-black/40 border border-white/10 hover:border-emerald-500/50 hover:bg-emerald-500/10 transition-all"
              >
                <div className="p-3 rounded-full bg-zinc-900 group-hover:bg-emerald-500 text-zinc-400 group-hover:text-black transition-colors">
                  <RiCameraLine size={28} />
                </div>
                <span className="text-[10px] font-bold tracking-widest text-zinc-300 group-hover:text-emerald-400">
                  CAMERA FEED
                </span>
              </button>

              <button
                onClick={() => {
                  props.startVision('screen')
                  setShowSourceModal(false)
                }}
                className="cursor-pointer group flex flex-col items-center justify-center gap-3 p-6 rounded-xl bg-black/40 border border-white/10 hover:border-emerald-500/50 hover:bg-emerald-500/10 transition-all"
              >
                <div className="p-3 rounded-full bg-zinc-900 group-hover:bg-emerald-500 text-zinc-400 group-hover:text-black transition-colors">
                  <RiComputerLine size={28} />
                </div>
                <span className="text-[10px] font-bold tracking-widest text-zinc-300 group-hover:text-emerald-400">
                  SCREEN SHARE
                </span>
              </button>

              {props.isVideoOn && (
                <button
                  aria-label="Stop active vision capture"
                  onClick={() => {
                    props.stopVision()
                    setShowSourceModal(false)
                  }}
                  className="cursor-pointer col-span-2 flex items-center justify-center gap-2 p-3 rounded-xl bg-red-500/10 border border-red-500/30 text-red-300 hover:bg-red-500 hover:text-black transition-all text-[10px] font-black tracking-widest"
                >
                  STOP CAPTURE
                </button>
              )}
            </div>

            <div className="p-3 bg-black/20 text-center">
              <p className="text-[9px] text-zinc-600 font-mono">
                SELECT INPUT SOURCE FOR NEURAL PROCESSING
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ShellAI
