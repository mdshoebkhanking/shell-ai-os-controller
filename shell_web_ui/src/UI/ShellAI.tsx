import { useState, useEffect, useLayoutEffect, Suspense, lazy, useCallback, useRef } from 'react'
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
  RiToolsLine,
  RiMore2Line
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

const glassPanel = 'shell-liquid-panel'

const primaryTabs = [
  { id: 'DASHBOARD', icon: <RiLayoutGridLine /> },
  { id: 'Apps', icon: <RiFolderOpenLine /> },
  { id: 'NOTES', icon: <RiFolderOpenLine /> },
  { id: 'GALLERY', icon: <RiImageLine /> },
  { id: 'CONTROL', icon: <RiToolsLine /> },
  { id: 'SETTINGS', icon: <RiSettings4Line /> }
]

const optionalTabs = [
  { id: 'Macros', icon: <RiBrainLine /> },
  { id: 'PHONE', icon: <RiPhoneLine /> }
]

const tabs = [...primaryTabs, ...optionalTabs]

const ShellAI = (props: ShellProps) => {
  const [activeTab, setActiveTab] = useState('DASHBOARD')
  const [stats, setStats] = useState<any>(null)
  const [chatHistory, setChatHistory] = useState<any[]>([])
  const [showSourceModal, setShowSourceModal] = useState(false)
  const [showMoreTabs, setShowMoreTabs] = useState(false)
  const historyClearVersionRef = useRef(0)
  const tabRailRef = useRef<HTMLDivElement | null>(null)
  const tabButtonRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const [tabIndicatorStyle, setTabIndicatorStyle] = useState({
    opacity: 1,
    transform: 'translate3d(4px, 0, 0)',
    width: '96px'
  })
  const isOptionalTabActive = optionalTabs.some((tab) => tab.id === activeTab)

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

  const updateTabIndicator = useCallback(() => {
    const activeButton = tabButtonRefs.current[activeTab]
    if (!activeButton) {
      setTabIndicatorStyle((current) => ({ ...current, opacity: 0 }))
      return
    }

    setTabIndicatorStyle({
      opacity: 1,
      transform: `translate3d(${activeButton.offsetLeft}px, 0, 0)`,
      width: `${activeButton.offsetWidth}px`
    })
  }, [activeTab])

  useLayoutEffect(() => {
    updateTabIndicator()

    const rail = tabRailRef.current
    const activeButton = tabButtonRefs.current[activeTab]
    const resizeObserver =
      typeof ResizeObserver !== 'undefined'
        ? new ResizeObserver(() => updateTabIndicator())
        : null

    if (rail) resizeObserver?.observe(rail)
    if (activeButton) resizeObserver?.observe(activeButton)
    window.addEventListener('resize', updateTabIndicator)

    return () => {
      resizeObserver?.disconnect()
      window.removeEventListener('resize', updateTabIndicator)
    }
  }, [activeTab, updateTabIndicator])

  const handleTranscriptCleared = useCallback(() => {
    historyClearVersionRef.current += 1
    setChatHistory([])
  }, [])

  const handleVisionClick = () => {
    setShowSourceModal(true)
  }

  const activeView = () => {
    if (activeTab === 'DASHBOARD') {
      return (
        <DashboardView
          props={props}
          stats={stats}
          chatHistory={chatHistory}
          onVisionClick={handleVisionClick}
          onTranscriptCleared={handleTranscriptCleared}
        />
      )
    }
    if (activeTab === 'PHONE') return <PhoneView glassPanel={glassPanel} />
    return (
      <Suspense fallback={<ViewSkeleton />}>
        {activeTab === 'Macros' && <WorkFlowEditorView />}
        {activeTab === 'Apps' && <AppsView />}
        {activeTab === 'NOTES' && <NotesView glassPanel={glassPanel} />}
        {activeTab === 'CONTROL' && <ControlCenter />}
        {activeTab === 'SETTINGS' && <SettingsView isSystemActive={props.isSystemActive} />}
        {activeTab === 'GALLERY' && <GalleryView />}
      </Suspense>
    )
  }

  return (
    <div className="shell-ui-root h-full w-full text-zinc-100 font-sans overflow-hidden select-none flex flex-col relative pb-4">
      <div className="shell-topbar h-14 w-full flex items-center justify-between px-6 z-50">
        <div className="flex items-center gap-3 min-w-0">
          <div className="shell-logo-glass relative h-9 w-9 shrink-0 rounded-xl border p-1 overflow-hidden">
            <img
              src="./shell-logo.png"
              alt="Shell AI"
              className="h-full w-full object-contain"
              draggable={false}
            />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-black tracking-[0.2em] text-sm text-zinc-100">Shell AI</span>
            <span className="text-[11px] font-mono text-slate-300/75 tracking-widest">
              CONTROL INTERFACE
            </span>
          </div>
        </div>

        <div className="relative hidden md:flex items-center gap-2">
          <div ref={tabRailRef} className="shell-tabs flex p-1">
            <div
              className="shell-tab-indicator"
              style={tabIndicatorStyle}
            />
            {primaryTabs.map((tab) => (
              <button
                key={tab.id}
                ref={(element) => {
                  tabButtonRefs.current[tab.id] = element
                }}
                aria-label={`Open ${tab.id} view`}
                onClick={() => {
                  setActiveTab(tab.id)
                  setShowMoreTabs(false)
                }}
                className={`shell-tab cursor-pointer px-3 xl:px-4 py-1.5 text-[10px] font-bold tracking-widest rounded-full flex items-center justify-center gap-2 min-w-24 ${
                  activeTab === tab.id ? 'shell-tab-active' : ''
                }`}
              >
                {tab.icon} {tab.id}
              </button>
            ))}
          </div>
          <button
            aria-label="Open more Shell views"
            onClick={() => setShowMoreTabs((value) => !value)}
            className={`shell-control-button cursor-pointer h-9 rounded-full border px-3 text-[10px] font-black tracking-widest flex items-center gap-2 ${
              isOptionalTabActive
                ? 'shell-primary-action'
                : 'border-white/10 bg-white/5 text-zinc-400 hover:text-slate-100'
            }`}
          >
            <RiMore2Line /> MORE
          </button>
          {showMoreTabs && (
            <div className="shell-liquid-panel absolute right-0 top-12 z-50 w-44 p-2 flex flex-col gap-2">
              {optionalTabs.map((tab) => (
                <button
                  key={tab.id}
                  aria-label={`Open ${tab.id} view`}
                  onClick={() => {
                    setActiveTab(tab.id)
                    setShowMoreTabs(false)
                  }}
                  className={`shell-control-button cursor-pointer rounded-xl border px-3 py-2 text-left text-[10px] font-black tracking-widest flex items-center gap-2 ${
                    activeTab === tab.id
                      ? 'shell-primary-action'
                      : 'border-white/10 bg-black/40 text-zinc-400 hover:text-slate-100'
                  }`}
                >
                  {tab.icon}
                  {tab.id}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center gap-4 text-[11px] font-mono font-bold opacity-70">
          <div className="shell-status-ready flex items-center gap-2 rounded-full border px-3 py-1">
            <RiWifiLine /> <span>{props.backendVoiceState === 'LISTENING' ? 'LISTENING' : 'READY'}</span>
          </div>
        </div>
      </div>

      <div className="shell-page-surface flex-1 min-h-0 overflow-hidden relative">
        <div className="absolute inset-0 shell-view-pane">
          {activeView()}
        </div>
      </div>

      <div className="md:hidden shrink-0 border-t border-white/10 bg-slate-950/90 px-2 py-2 overflow-x-auto scrollbar-small">
        <div className="flex gap-2 min-w-max">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              aria-label={`Open ${tab.id} view`}
              onClick={() => setActiveTab(tab.id)}
              className={`shell-control-button cursor-pointer min-w-20 px-3 py-2 rounded-xl text-[9px] font-black tracking-widest flex flex-col items-center gap-1 border ${
                activeTab === tab.id
                  ? 'shell-primary-action'
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
        <div className="absolute inset-0 z-100 flex items-center justify-center bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
          <div className={`${glassPanel} w-96 p-1 border-slate-300/20 flex flex-col shadow-2xl`}>
            <div className="flex items-center justify-between p-4 border-b border-white/5 bg-white/5">
              <span className="text-xs font-bold tracking-widest text-slate-200">
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
                className="shell-control-button cursor-pointer group flex flex-col items-center justify-center gap-3 p-6 rounded-2xl bg-black/40 border border-white/10 hover:border-slate-300/35 hover:bg-white/10"
              >
                <div className="p-3 rounded-full bg-zinc-900 group-hover:bg-white/12 text-zinc-400 group-hover:text-slate-100 transition-colors">
                  <RiCameraLine size={28} />
                </div>
                <span className="text-[10px] font-bold tracking-widest text-zinc-300 group-hover:text-slate-100">
                  CAMERA FEED
                </span>
              </button>

              <button
                onClick={() => {
                  props.startVision('screen')
                  setShowSourceModal(false)
                }}
                className="shell-control-button cursor-pointer group flex flex-col items-center justify-center gap-3 p-6 rounded-2xl bg-black/40 border border-white/10 hover:border-slate-300/35 hover:bg-white/10"
              >
                <div className="p-3 rounded-full bg-zinc-900 group-hover:bg-white/12 text-zinc-400 group-hover:text-slate-100 transition-colors">
                  <RiComputerLine size={28} />
                </div>
                <span className="text-[10px] font-bold tracking-widest text-zinc-300 group-hover:text-slate-100">
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
