# SuperDesign Init: Components

## Framework Snapshot
- Framework: React 19 + Vite.
- Styling: Tailwind CSS v4 imported through `shell_web_ui/src/assets/main.css`.
- UI library: custom components plus `react-icons`, `lucide-react`, `@react-three/fiber`, `@react-three/drei`, `framer-motion`, `gsap`.
- New marketing website target: `site/` with Vite + React + TypeScript + Tailwind, using real screenshots from `screenshots/current/`.

## `shell_web_ui/src/components/ViewSkelrton.tsx`
Shared loading panel used while lazy Shell tabs initialize.

```tsx
import { RiLoader4Line } from 'react-icons/ri'

const ViewSkeleton = () => {
  return (
    <div className="w-full h-full min-h-0 p-8">
      <div className="shell-liquid-panel w-full h-full p-6 flex flex-col gap-6 relative overflow-hidden">
        <div className="absolute inset-0 -translate-x-full shell-shimmer bg-linear-to-r from-transparent via-blue-200/10 to-transparent z-10" />

        <div className="flex items-center gap-4 border-b border-white/5 pb-6">
          <div className="w-12 h-12 rounded-xl bg-white/5 animate-pulse" />
          <div className="flex flex-col gap-2">
            <div className="w-48 h-6 bg-white/5 rounded animate-pulse" />
            <div className="w-24 h-3 bg-white/5 rounded animate-pulse" />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-6 flex-1">
          <div className="bg-white/5 rounded-xl animate-pulse h-full opacity-50" />
          <div className="flex flex-col gap-6">
            <div className="bg-white/5 rounded-xl animate-pulse h-32 opacity-50" />
            <div className="bg-white/5 rounded-xl animate-pulse flex-1 opacity-50" />
          </div>
        </div>

        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 text-blue-300/70">
          <RiLoader4Line className="animate-spin text-4xl" />
          <span className="text-[10px] tracking-[0.3em] font-mono">INITIALIZING MODULE...</span>
        </div>
      </div>
    </div>
  )
}

export default ViewSkeleton
```

## `shell_web_ui/src/components/MiniOverlay.tsx`
Compact glass control dock for voice, mic, camera/screen, and overlay expansion. Important pattern: liquid-glass dock, circular controls, active red/cyan states.

```tsx
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
    if (isVideoOn && visionMode === mode) stopVision()
    else startVision(mode)
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
```

## `shell_web_ui/src/components/Sphere.tsx`
Particle-orb visual reference. The website hero can borrow the fallback/orb language, but the required primary hero object is a 3D laptop mockup with real screenshots.

```tsx
import { Canvas, useFrame } from '@react-three/fiber'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { shellService } from '@renderer/services/shell-voice-ai'

const SphereFallback = () => (
  <div className="relative h-full w-full grid place-items-center">
    <div className="absolute h-[62%] w-[62%] rounded-full border border-white/18 shadow-[0_0_62px_rgba(185,201,238,0.16)]" />
    <div className="absolute h-[46%] w-[46%] rounded-full border border-slate-200/22 shadow-[0_0_38px_rgba(215,225,238,0.12)] animate-pulse" />
    <div className="absolute h-[28%] w-[28%] rounded-full bg-slate-200/10 blur-sm" />
    <div className="relative h-5 w-5 rounded-full bg-slate-100 shadow-[0_0_24px_rgba(215,225,238,0.55)]" />
  </div>
)

const CustomParticleSphere = ({ count = 3000 }) => {
  const mesh = useRef<THREE.Points>(null)
  const dataArray = useMemo(() => new Uint8Array(128), [])
  const colorStart = useMemo(() => new THREE.Color('#8FA8D8'), [])
  const colorEnd = useMemo(() => new THREE.Color('#EEF4FC'), [])
  const colorTarget = useMemo(() => new THREE.Color(), [])

  const { positions, originalPositions, spreadFactors } = useMemo(() => {
    const pos = new Float32Array(count * 3)
    const orig = new Float32Array(count * 3)
    const spread = new Float32Array(count)
    for (let i = 0; i < count; i++) {
      const vector = new THREE.Vector3(Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1)
      vector.normalize().multiplyScalar(2)
      pos[i * 3] = vector.x
      pos[i * 3 + 1] = vector.y
      pos[i * 3 + 2] = vector.z
      orig[i * 3] = vector.x
      orig[i * 3 + 1] = vector.y
      orig[i * 3 + 2] = vector.z
      spread[i] = Math.random()
    }
    return { positions: pos, originalPositions: orig, spreadFactors: spread }
  }, [count])

  useFrame((state, delta) => {
    if (!state.clock.running || !mesh.current) return
    mesh.current.rotation.y += delta * 0.05
    mesh.current.rotation.z += delta * 0.05
    let volume = 0
    if (shellService.analyser) {
      shellService.analyser.getByteFrequencyData(dataArray)
      volume = dataArray.reduce((sum, value) => sum + value, 0) / dataArray.length / 128
    }
    colorTarget.lerpColors(colorStart, colorEnd, volume)
    ;(mesh.current.material as THREE.PointsMaterial).color.copy(colorTarget)
  })

  return (
    <points ref={mesh}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial color="#8FA8D8" size={0.012} transparent opacity={0.9} blending={THREE.AdditiveBlending} depthWrite={false} />
    </points>
  )
}

const Sphere = () => {
  const [webglReady, setWebglReady] = useState(true)
  useEffect(() => {
    try {
      const canvas = document.createElement('canvas')
      setWebglReady(Boolean(canvas.getContext('webgl2') || canvas.getContext('webgl')))
    } catch {
      setWebglReady(false)
    }
  }, [])
  if (!webglReady) return <SphereFallback />
  return (
    <Canvas camera={{ position: [0, 0, 4.5] }} dpr={[1, 1.5]} performance={{ min: 0.5 }}>
      <ambientLight intensity={0.6} />
      <CustomParticleSphere />
    </Canvas>
  )
}

export default Sphere
```

