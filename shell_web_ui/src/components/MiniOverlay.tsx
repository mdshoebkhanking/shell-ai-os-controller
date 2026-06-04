import { useState, useEffect, useRef } from 'react'
import {
  RiMicLine,
  RiMicOffLine,
  RiComputerLine,
  RiCameraLine,
  RiFullscreenLine,
  RiDragMove2Fill
} from 'react-icons/ri'
import { GiPowerButton } from 'react-icons/gi'
import { shellService } from '@renderer/services/shell-voice-ai'
import { VisionMode } from '@renderer/IndexRoot'

interface OverlayProps {
  isSystemActive: boolean
  toggleSystem: () => void
  isMicMuted: boolean
  toggleMic: () => void
  isVideoOn: boolean
  visionMode: VisionMode
  startVision: (mode: 'camera' | 'screen') => void
  stopVision: () => void
}

const MiniOverlay = ({
  isSystemActive,
  toggleSystem,
  isMicMuted,
  toggleMic,
  isVideoOn,
  visionMode,
  startVision,
  stopVision
}: OverlayProps) => {
  const [isTalking, setIsTalking] = useState(false)
  const analyzerRef = useRef<AnalyserNode | null>(null)
  const dataArrayRef = useRef<Uint8Array | any | null>(null)

  useEffect(() => {
    if (isSystemActive && shellService.analyser) {
      analyzerRef.current = shellService.analyser
      dataArrayRef.current = new Uint8Array(shellService.analyser.frequencyBinCount)
      const checkAudio = () => {
        if (analyzerRef.current && dataArrayRef.current) {
          analyzerRef.current.getByteFrequencyData(dataArrayRef.current)
          const avg = dataArrayRef.current.reduce((a, b) => a + b) / dataArrayRef.current.length
          setIsTalking(avg > 10)
        }
        if (isSystemActive) requestAnimationFrame(checkAudio)
      }
      checkAudio()
    } else {
      setIsTalking(false)
    }
  }, [isSystemActive])

  const handleVisionClick = (mode: 'camera' | 'screen') => {
    if (isVideoOn && visionMode === mode) {
      stopVision()
    } else {
      startVision(mode)
    }
  }

  const expand = () => {
    window.electron.ipcRenderer.send('toggle-overlay')
  }

  return (
    <div className="shell-liquid-dock w-full h-full flex items-center justify-between px-3 rounded-full border drag-region overflow-hidden">
      <div className="flex items-center gap-3 no-drag">
        <div
          className={`w-8 h-8 rounded-full flex items-center justify-center border transition-all duration-300 ${isSystemActive ? (isTalking ? 'border-blue-400 bg-blue-500/20 shadow-[0_0_15px_rgba(96,165,250,0.55)]' : 'border-blue-400/50 bg-blue-900/20') : 'border-zinc-700 bg-zinc-900'}`}
        >
          <div
            className={`w-2.5 h-2.5 rounded-full transition-colors duration-300 ${isSystemActive ? (isTalking ? 'bg-blue-300' : 'bg-blue-500') : 'bg-red-900'}`}
          />
        </div>
      </div>

      <div className="flex items-center gap-2 no-drag">
        <button
          onClick={toggleMic}
          disabled={!isSystemActive}
          className={`shell-control-button p-2.5 rounded-full ml-1 ${!isSystemActive ? 'opacity-30' : isMicMuted ? 'text-red-500 bg-red-500/10' : 'text-blue-300 bg-blue-500/10'}`}
        >
          {isMicMuted ? <RiMicOffLine size={18} /> : <RiMicLine size={18} />}
        </button>

        <button
          onClick={toggleSystem}
          className={`shell-control-button p-3 rounded-full border shadow-lg mx-1 ${isSystemActive ? 'shell-primary-action' : 'bg-zinc-800 border-zinc-600 text-zinc-500 hover:text-red-400'}`}
        >
          <GiPowerButton size={20} className={isSystemActive ? 'animate-pulse' : ''} />
        </button>

        <button
          onClick={() => handleVisionClick('camera')}
          disabled={!isSystemActive}
          className={`shell-control-button p-2.5 rounded-full ${!isSystemActive ? 'opacity-30' : isVideoOn && visionMode === 'camera' ? 'text-red-400 bg-red-500/10 animate-pulse border border-red-500/30' : 'text-zinc-400 hover:text-white hover:bg-white/10'}`}
          title="Toggle Camera"
        >
          <RiCameraLine size={18} />
        </button>

        <button
          onClick={() => handleVisionClick('screen')}
          disabled={!isSystemActive}
          className={`shell-control-button p-2.5 rounded-full ${!isSystemActive ? 'opacity-30' : isVideoOn && visionMode === 'screen' ? 'text-red-400 bg-red-500/10 animate-pulse border border-red-500/30' : 'text-zinc-400 hover:text-white hover:bg-white/10'}`}
          title="Toggle Screen"
        >
          <RiComputerLine size={18} />
        </button>
      </div>

      <div className="pl-4 border-l border-blue-500/20 no-drag flex items-center gap-2">
        <button
          onClick={expand}
          className="shell-control-button p-2 rounded-full text-zinc-500 hover:text-blue-300 hover:bg-blue-500/10"
        >
          <RiFullscreenLine size={16} />
        </button>
        <div className="drag-region cursor-move text-blue-400/30">
          <RiDragMove2Fill size={14} />
        </div>
      </div>
    </div>
  )
}

export default MiniOverlay
