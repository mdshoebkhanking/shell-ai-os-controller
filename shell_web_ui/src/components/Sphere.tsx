import { Canvas, useFrame } from '@react-three/fiber'
import React, { useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { shellService } from '@renderer/services/shell-voice-ai'

const hasWebGLSupport = () => {
  try {
    const canvas = document.createElement('canvas')
    const gl =
      canvas.getContext('webgl2') ||
      canvas.getContext('webgl') ||
      canvas.getContext('experimental-webgl')
    return Boolean(gl)
  } catch {
    return false
  }
}

const SphereFallback = () => (
  <div className="relative h-full w-full grid place-items-center">
    <div className="absolute h-[62%] w-[62%] rounded-full border border-white/18 shadow-[0_0_62px_rgba(185,201,238,0.16)]" />
    <div className="absolute h-[46%] w-[46%] rounded-full border border-slate-200/22 shadow-[0_0_38px_rgba(215,225,238,0.12)] animate-pulse" />
    <div className="absolute h-[28%] w-[28%] rounded-full bg-slate-200/10 blur-sm" />
    <div className="relative h-5 w-5 rounded-full bg-slate-100 shadow-[0_0_24px_rgba(215,225,238,0.55)]" />
  </div>
)

class SphereCanvasBoundary extends React.Component<
  { children: React.ReactNode },
  { failed: boolean }
> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  componentDidCatch(error: unknown) {
    console.warn('Shell sphere WebGL fallback activated', error)
  }

  render() {
    if (this.state.failed) return <SphereFallback />
    return this.props.children
  }
}

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
      const x = Math.random() * 2 - 1
      const y = Math.random() * 2 - 1
      const z = Math.random() * 2 - 1

      const vector = new THREE.Vector3(x, y, z)
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

      let sum = 0
      const len = dataArray.length
      for (let i = 0; i < len; i++) {
        sum += dataArray[i]
      }
      volume = sum / len / 128
    }

    colorTarget.lerpColors(colorStart, colorEnd, volume)
    ;(mesh.current.material as THREE.PointsMaterial).color.copy(colorTarget)

    const currentPos = mesh.current.geometry.attributes.position.array as Float32Array

    for (let i = 0; i < count; i++) {
      const ix = i * 3
      const iy = i * 3 + 1
      const iz = i * 3 + 2

      const expansion = 1 + volume * spreadFactors[i] * 0.4

      currentPos[ix] = originalPositions[ix] * expansion
      currentPos[iy] = originalPositions[iy] * expansion
      currentPos[iz] = originalPositions[iz] * expansion
    }

    mesh.current.geometry.attributes.position.needsUpdate = true
  })

  return (
    <points ref={mesh}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial
        color="#8FA8D8"
        size={0.012}
        transparent={true}
        opacity={0.9}
        sizeAttenuation={true}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  )
}

const Sphere = () => {
  const [webglReady, setWebglReady] = useState(true)

  useEffect(() => {
    setWebglReady(hasWebGLSupport())
  }, [])

  if (!webglReady) return <SphereFallback />

  return (
    <SphereCanvasBoundary>
      <Canvas
        camera={{ position: [0, 0, 4.5] }}
        dpr={[1, 1.5]}
        performance={{ min: 0.5 }}
        gl={{ antialias: false, powerPreference: 'high-performance' }}
        onCreated={({ gl }) => {
          gl.domElement.addEventListener('webglcontextlost', () => setWebglReady(false), {
            once: true
          })
        }}
      >
        <ambientLight intensity={0.6} />
        <CustomParticleSphere />
      </Canvas>
    </SphereCanvasBoundary>
  )
}

export default Sphere
