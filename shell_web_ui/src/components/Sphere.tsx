import { Canvas, useFrame } from '@react-three/fiber'
import { useRef, useMemo, type CSSProperties } from 'react'
import * as THREE from 'three'

const ORB_BASE_COLOR = '#7ED3BA'
const ORB_AUDIO_COLOR = '#5EEAD4'
const ORB_PEAK_COLOR = '#ECFDF5'
const ORB_PARTICLE_RADIUS = 1.93
const ORB_PARTICLE_SIZE = 0.011
const ORB_OPACITY = 0.9
const ORB_EXPANSION_STRENGTH = 0.32
const ORB_TARGET_FRAME_MS = 1000 / 30
const ORB_ROTATION_X_SPEED = 0.01
const ORB_ROTATION_Y_SPEED = 0.05
const ORB_ROTATION_Z_SPEED = 0.05

type SphereProps = {
  voiceLevel?: number
  active?: boolean
  speaking?: boolean
}

const CustomParticleSphere = ({
  count = 1600,
  voiceLevel = 0,
  active = false,
  speaking = false
}: SphereProps & { count?: number }) => {
  const mesh = useRef<THREE.Points>(null)
  const materialRef = useRef<THREE.PointsMaterial>(null)
  const smoothedVolumeRef = useRef(0)
  const lastFrameMsRef = useRef(0)

  const dataArray = useMemo(() => new Uint8Array(128), [])

  const colorStart = useMemo(() => new THREE.Color(ORB_BASE_COLOR), [])
  const colorMid = useMemo(() => new THREE.Color(ORB_AUDIO_COLOR), [])
  const colorEnd = useMemo(() => new THREE.Color(ORB_PEAK_COLOR), [])
  const colorTarget = useMemo(() => new THREE.Color(), [])

  const { positions, originalPositions, spreadFactors } = useMemo(() => {
    const base = new Float32Array(count * 3)
    const pos = new Float32Array(count * 3)
    const spread = new Float32Array(count)

    for (let i = 0; i < count; i++) {
      const x = Math.random() * 2 - 1
      const y = Math.random() * 2 - 1
      const z = Math.random() * 2 - 1

      const vector = new THREE.Vector3(x, y, z)
      vector.normalize().multiplyScalar(ORB_PARTICLE_RADIUS)

      base[i * 3] = vector.x
      base[i * 3 + 1] = vector.y
      base[i * 3 + 2] = vector.z
      pos[i * 3] = vector.x
      pos[i * 3 + 1] = vector.y
      pos[i * 3 + 2] = vector.z

      spread[i] = 0.45 + Math.random() * 0.55
    }
    return { positions: pos, originalPositions: base, spreadFactors: spread }
  }, [count])

  useFrame((state, delta) => {
    if (!state.clock.running || !mesh.current || !materialRef.current) return
    if (document.hidden) return
    const nowMs = state.clock.elapsedTime * 1000
    if (nowMs - lastFrameMsRef.current < ORB_TARGET_FRAME_MS) return
    lastFrameMsRef.current = nowMs

    mesh.current.rotation.x += delta * ORB_ROTATION_X_SPEED
    mesh.current.rotation.y += delta * ORB_ROTATION_Y_SPEED
    mesh.current.rotation.z += delta * ORB_ROTATION_Z_SPEED

    let liveVolume = 0
    const analyser = (window as any).__shellVoiceService?.analyser as AnalyserNode | undefined
    if (speaking && analyser) {
      analyser.getByteFrequencyData(dataArray)

      let sum = 0
      const len = dataArray.length
      for (let i = 0; i < len; i++) {
        sum += dataArray[i]
      }
      liveVolume = sum / len / 128
    }

    const backendLevel = Math.min(1, Math.max(0, voiceLevel || 0))
    // Keep queued/idle states visually honest: only actual speech/audio amplitude drives expansion.
    const targetVolume = speaking ? Math.min(1, Math.max(liveVolume, backendLevel)) : 0
    smoothedVolumeRef.current += (targetVolume - smoothedVolumeRef.current) * Math.min(1, delta * 9)
    const volume = smoothedVolumeRef.current

    const geometry = mesh.current.geometry
    const positionAttribute = geometry.getAttribute('position') as THREE.BufferAttribute
    const currentPos = positionAttribute.array as Float32Array
    for (let i = 0; i < spreadFactors.length; i++) {
      const ix = i * 3
      const scale = 1 + volume * spreadFactors[i] * ORB_EXPANSION_STRENGTH
      currentPos[ix] = originalPositions[ix] * scale
      currentPos[ix + 1] = originalPositions[ix + 1] * scale
      currentPos[ix + 2] = originalPositions[ix + 2] * scale
    }
    positionAttribute.needsUpdate = true

    if (volume < 0.55) {
      colorTarget.lerpColors(colorStart, colorMid, volume / 0.55)
    } else {
      colorTarget.lerpColors(colorMid, colorEnd, (volume - 0.55) / 0.45)
    }

    materialRef.current.size = ORB_PARTICLE_SIZE * state.gl.getPixelRatio()
    materialRef.current.color.copy(colorTarget)
  })

  return (
    <points ref={mesh}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        ref={materialRef}
        color={ORB_BASE_COLOR}
        size={ORB_PARTICLE_SIZE}
        opacity={ORB_OPACITY}
        transparent={true}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
        sizeAttenuation={true}
      />
    </points>
  )
}

const Sphere = ({ voiceLevel = 0, active = false, speaking = false }: SphereProps) => {
  const fallbackLevel = speaking ? Math.min(1, Math.max(0, voiceLevel || 0)) : 0
  const fallbackScale = 0.92 + fallbackLevel * 0.1
  const stageStyle = {
    '--shell-orb-level': fallbackLevel.toFixed(3),
    '--shell-orb-scale': fallbackScale.toFixed(3),
    '--shell-orb-peak-scale': (fallbackScale + fallbackLevel * 0.055).toFixed(3),
    '--shell-orb-particle-scale': (1 + fallbackLevel * 0.08).toFixed(3),
  } as CSSProperties

  return (
    <div
      className={`shell-orb-stage ${active ? 'shell-orb-stage-active' : ''} ${speaking ? 'shell-orb-stage-speaking' : ''}`}
      style={stageStyle}
      aria-hidden="true"
    >
      <div className="shell-orb-fallback" />
      <Canvas
        className="shell-orb-canvas"
        camera={{ position: [0, 0, 4.5] }}
        dpr={[1, 1.2]}
        performance={{ min: 0.5 }}
        gl={{ antialias: false, powerPreference: 'default', alpha: true }}
        resize={{ scroll: false, debounce: { scroll: 80, resize: 160 } }}
      >
        <ambientLight intensity={0.6} />
        <CustomParticleSphere active={active} speaking={speaking} voiceLevel={voiceLevel} />
      </Canvas>
    </div>
  )
}

export default Sphere
