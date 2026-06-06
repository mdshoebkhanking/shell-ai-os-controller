import { Canvas, useFrame } from '@react-three/fiber'
import { useRef, useMemo } from 'react'
import * as THREE from 'three'
import { shellService } from '@renderer/services/shell-voice-ai'

const ORB_BASE_COLOR = '#00F0FF'
const ORB_AUDIO_COLOR = '#33db12'
const ORB_PEAK_COLOR = '#FFFFFF'
const ORB_PARTICLE_SIZE = 0.012
const ORB_OPACITY = 0.9
const ORB_EXPANSION_STRENGTH = 0.4

type SphereProps = {
  voiceLevel?: number
  active?: boolean
  speaking?: boolean
}

const ORB_VERTEX_SHADER = `
  attribute float spreadFactor;

  uniform float uVolume;
  uniform float uSize;
  uniform float uScale;
  uniform float uExpansionStrength;

  void main() {
    vec3 reactivePosition = position * (1.0 + uVolume * spreadFactor * uExpansionStrength);
    vec4 mvPosition = modelViewMatrix * vec4(reactivePosition, 1.0);

    gl_PointSize = uSize * (uScale / max(0.001, -mvPosition.z));
    gl_Position = projectionMatrix * mvPosition;
  }
`

const ORB_FRAGMENT_SHADER = `
  uniform vec3 uColor;
  uniform float uOpacity;

  void main() {
    gl_FragColor = vec4(uColor, uOpacity);
  }
`

const CustomParticleSphere = ({
  count = 2000,
  voiceLevel = 0,
  active = false,
  speaking = false
}: SphereProps & { count?: number }) => {
  const mesh = useRef<THREE.Points>(null)
  const materialRef = useRef<THREE.ShaderMaterial>(null)
  const smoothedVolumeRef = useRef(0)

  const dataArray = useMemo(() => new Uint8Array(128), [])

  const colorStart = useMemo(() => new THREE.Color(ORB_AUDIO_COLOR), [])
  const colorEnd = useMemo(() => new THREE.Color(ORB_PEAK_COLOR), [])
  const colorTarget = useMemo(() => new THREE.Color(), [])

  const shaderUniforms = useMemo(
    () => ({
      uVolume: { value: 0 },
      uColor: { value: new THREE.Color(ORB_BASE_COLOR) },
      uSize: { value: ORB_PARTICLE_SIZE },
      uScale: { value: 1 },
      uOpacity: { value: ORB_OPACITY },
      uExpansionStrength: { value: ORB_EXPANSION_STRENGTH },
    }),
    [],
  )

  const { positions, spreadFactors } = useMemo(() => {
    const pos = new Float32Array(count * 3)
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

      spread[i] = Math.random()
    }
    return { positions: pos, spreadFactors: spread }
  }, [count])

  useFrame((state, delta) => {
    if (!state.clock.running || !mesh.current || !materialRef.current) return
    if (document.hidden) return

    mesh.current.rotation.y += delta * 0.05
    mesh.current.rotation.z += delta * 0.05

    let liveVolume = 0
    if (shellService.analyser) {
      shellService.analyser.getByteFrequencyData(dataArray)

      let sum = 0
      const len = dataArray.length
      for (let i = 0; i < len; i++) {
        sum += dataArray[i]
      }
      liveVolume = sum / len / 128
    }

    const backendLevel = Math.min(1, Math.max(0, voiceLevel || 0))
    const idlePulse = active ? 0.035 + Math.sin(state.clock.elapsedTime * 2.4) * 0.018 : 0
    const speechPulse = speaking ? 0.18 + Math.sin(state.clock.elapsedTime * 8) * 0.08 : 0
    const targetVolume = Math.min(1, Math.max(liveVolume, backendLevel, idlePulse, speechPulse))
    smoothedVolumeRef.current += (targetVolume - smoothedVolumeRef.current) * Math.min(1, delta * 9)
    const volume = smoothedVolumeRef.current

    colorTarget.lerpColors(colorStart, colorEnd, volume)

    const uniforms = materialRef.current.uniforms
    uniforms.uVolume.value = volume
    uniforms.uSize.value = ORB_PARTICLE_SIZE * state.gl.getPixelRatio()
    uniforms.uScale.value = state.size.height * 0.5
    ;(uniforms.uColor.value as THREE.Color).copy(colorTarget)
  })

  return (
    <points ref={mesh}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
        <bufferAttribute attach="attributes-spreadFactor" args={[spreadFactors, 1]} />
      </bufferGeometry>
      <shaderMaterial
        ref={materialRef}
        uniforms={shaderUniforms}
        vertexShader={ORB_VERTEX_SHADER}
        fragmentShader={ORB_FRAGMENT_SHADER}
        transparent={true}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </points>
  )
}

const Sphere = (props: SphereProps) => {
  return (
    <Canvas
      camera={{ position: [0, 0, 4.5] }}
      dpr={[1, 1.5]}
      performance={{ min: 0.5 }}
      gl={{ antialias: false, powerPreference: 'high-performance' }}
    >
      <ambientLight intensity={0.6} />
      <CustomParticleSphere {...props} />
    </Canvas>
  )
}

export default Sphere
