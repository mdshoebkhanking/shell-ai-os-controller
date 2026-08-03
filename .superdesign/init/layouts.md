# SuperDesign Init: Layouts

## `shell_web_ui/src/App.tsx`
Root wrapper delegates to `IndexRoot`.

```tsx
import IndexRoot from "./IndexRoot"

const App = () => {
  return (
    <>
      <IndexRoot />
    </>
  )
}

export default App
```

## `shell_web_ui/src/main.tsx`
Imports global Shell CSS and bridge, then renders `IndexRoot`.

```tsx
import './assets/main.css'
import './shellBridge'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import IndexRoot from './IndexRoot'

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
```

## `shell_web_ui/src/IndexRoot.tsx` Layout Summary
Full desktop renderer. It switches between `ShellAI` full interface and `MiniOverlay`, wires voice state, system notices, camera/screen streams, terminal overlay, and widgets. For SuperDesign, use the file directly as context when reproducing the current app UI; for the marketing website, use it as product behavior reference only.

Key rendered structure:

```tsx
return isOverlay ? (
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
) : (
  <div className="shell-app-frame h-screen w-screen overflow-hidden border border-zinc-800">
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
    <TerminalOverlay />
    <LeafletMapWidget />
    <ImageWidget />
    <EmailWidget />
    <WeatherWidget />
    <StockWidget />
    <LiveCodingWidget />
    <WormholeWidget />
    <OracleWidget />
    <ResearchWidget />
    <SemanticWidget />
    <SmartDropZonesWidget />
  </div>
)
```

## `shell_web_ui/src/UI/ShellAI.tsx`
Main full app shell layout. Important for marketing site: topbar logo, tabs, liquid panels, ready status, and module names.

```tsx
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

  const activeView = () => {
    if (activeTab === 'DASHBOARD') return <DashboardView props={props} stats={stats} chatHistory={chatHistory} onVisionClick={() => setShowSourceModal(true)} onTranscriptCleared={() => setChatHistory([])} />
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
            <img src="./shell-logo.png" alt="Shell AI" className="h-full w-full object-contain" draggable={false} />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-black tracking-[0.2em] text-sm text-zinc-100">Shell AI</span>
            <span className="text-[11px] font-mono text-slate-300/75 tracking-widest">CONTROL INTERFACE</span>
          </div>
        </div>

        <div className="relative hidden md:flex items-center gap-2">
          <div className="shell-tabs flex p-1">
            {primaryTabs.map((tab) => (
              <button
                key={tab.id}
                aria-label={`Open ${tab.id} view`}
                onClick={() => setActiveTab(tab.id)}
                className={`shell-tab cursor-pointer px-3 xl:px-4 py-1.5 text-[10px] font-bold tracking-widest rounded-full flex items-center justify-center gap-2 min-w-24 ${activeTab === tab.id ? 'shell-tab-active' : ''}`}
              >
                {tab.icon} {tab.id}
              </button>
            ))}
          </div>
          <button className="shell-control-button cursor-pointer h-9 rounded-full border px-3 text-[10px] font-black tracking-widest flex items-center gap-2">
            <RiMore2Line /> MORE
          </button>
        </div>

        <div className="flex items-center gap-4 text-[11px] font-mono font-bold opacity-70">
          <div className="shell-status-ready flex items-center gap-2 rounded-full border px-3 py-1">
            <RiWifiLine /> <span>{props.backendVoiceState === 'LISTENING' ? 'LISTENING' : 'READY'}</span>
          </div>
        </div>
      </div>

      <div className="shell-page-surface flex-1 min-h-0 overflow-hidden relative">
        <div className="absolute inset-0 shell-view-pane">{activeView()}</div>
      </div>
    </div>
  )
}

export default ShellAI
```

## `shell_web_ui/src/components/Titlebar.tsx`
Window-control titlebar for desktop app. Not needed for public website, but useful as OS visual reference.

```tsx
import { useState, useEffect } from 'react'
import {
  RiSubtractLine,
  RiCloseLine,
  RiCheckboxBlankLine,
  RiCheckboxMultipleBlankLine
} from 'react-icons/ri'

const TitleBar = () => {
  const [isMaximized, setIsMaximized] = useState(false)
  const [isMac, setIsMac] = useState(false)

  useEffect(() => {
    if (window.electron && window.electron.process) setIsMac(window.electron.process.platform === 'darwin')
    else setIsMac(navigator.userAgent.toLowerCase().includes('mac'))
  }, [])

  const minimize = () => window.electron.ipcRenderer.send('window-min')
  const toggleMaximize = () => {
    setIsMaximized(!isMaximized)
    window.electron.ipcRenderer.send('window-max')
  }
  const close = () => window.electron.ipcRenderer.send('window-close')

  return (
    <div className="w-full h-10 flex items-center justify-between px-4 bg-zinc-900 border-b border-zinc-800 drag-region select-none z-1000 relative">
      {!isMac && (
        <div className="flex h-full no-drag ml-auto -mr-4 z-50">
          <button onClick={minimize} className="w-12 h-full flex items-center justify-center text-zinc-400 hover:bg-white/10 hover:text-white transition-colors">
            <RiSubtractLine size={16} />
          </button>
          <button onClick={toggleMaximize} className="w-12 h-full flex items-center justify-center text-zinc-400 hover:bg-white/10 hover:text-white transition-colors">
            {isMaximized ? <RiCheckboxMultipleBlankLine size={14} /> : <RiCheckboxBlankLine size={14} />}
          </button>
          <button onClick={close} className="w-12 h-full flex items-center justify-center text-zinc-400 hover:bg-red-600 hover:text-white transition-colors">
            <RiCloseLine size={18} />
          </button>
        </div>
      )}
    </div>
  )
}

export default TitleBar
```

