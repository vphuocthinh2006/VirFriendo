import { Component, type ReactNode, Suspense, useEffect, useMemo, useRef } from 'react'
import { Canvas, useFrame, useLoader } from '@react-three/fiber'
import * as THREE from 'three'
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js'
import { Box3, Vector3 } from 'three'
import { Center, ContactShadows, useAnimations, useGLTF } from '@react-three/drei'
import type { Mesh } from 'three'

type Props = {
  /** GLB/GLTF hoặc FBX trong `public/` — không còn model procedural; chỉ file thật (vd. thỏ `untitled.fbx`). */
  glbUrl: string | undefined
}

/** Khi đang tải / lỗi: không vẽ gì (không cub procedural). */
function EmptyScene() {
  return <group />
}

function fitScaleToMaxDim(group: THREE.Object3D, targetMax = 1.35) {
  const box = new Box3().setFromObject(group)
  const size = new Vector3()
  box.getSize(size)
  const max = Math.max(size.x, size.y, size.z, 1e-6)
  const fit = targetMax / max
  group.scale.setScalar(fit)
}

/** FBX (vd. Untitled.fbx / thỏ): có clip thì phát; không có clip vẫn vẽ mesh + chạy vòng (code). */
function BakedFbxLoop({ url }: { url: string }) {
  const fbx = useLoader(FBXLoader, url)
  const sceneRef = useRef<THREE.Group>(null)
  const outerRef = useRef<THREE.Group>(null)
  const scene = useMemo(() => {
    const g = fbx.clone(true)
    g.traverse((obj) => {
      const m = obj as Mesh
      if (m.isMesh) {
        m.castShadow = true
        m.receiveShadow = true
      }
    })
    fitScaleToMaxDim(g)
    return g
  }, [fbx])

  const clips = scene.animations?.length ? scene.animations : fbx.animations
  const hasAnim = clips.length > 0
  const { actions, names, mixer } = useAnimations(clips, sceneRef)

  useEffect(() => {
    if (!hasAnim || !names.length) return
    const a = actions[names[0]]
    if (!a) return
    a.reset()
    a.setLoop(THREE.LoopRepeat, Infinity)
    a.clampWhenFinished = false
    a.play()
    return () => {
      a.stop()
    }
  }, [hasAnim, actions, names])

  useFrame((state, delta) => {
    if (hasAnim) {
      mixer.update(delta)
      return
    }
    const outer = outerRef.current
    if (!outer) return
    const t = state.clock.elapsedTime
    const speed = 0.52
    const r = 1.22
    outer.position.x = Math.cos(t * speed) * r
    outer.position.z = Math.sin(t * speed) * r
    outer.position.y = 0.12 + Math.sin(t * speed * 6) * 0.04
    outer.rotation.y = -t * speed + Math.PI / 2
  })

  return (
    <group ref={outerRef}>
      <primitive ref={sceneRef} object={scene} />
    </group>
  )
}

/** GLB: có animation thì phát; không thì quỹ đạo tròn + nhún (code). */
function GltfAssetLoop({ url }: { url: string }) {
  const gltf = useGLTF(url, true, false)
  const ref = useRef<THREE.Group>(null)
  const scene = useMemo(() => {
    const g = gltf.scene.clone(true)
    g.traverse((obj) => {
      const m = obj as Mesh
      if (m.isMesh) {
        m.castShadow = true
        m.receiveShadow = true
      }
    })
    fitScaleToMaxDim(g)
    return g
  }, [gltf])

  const clips = gltf.animations ?? []
  const { actions, names, mixer } = useAnimations(clips, ref)

  useEffect(() => {
    if (!clips.length || !names.length) return
    const a = actions[names[0]]
    a?.reset().setLoop(THREE.LoopRepeat, Infinity).play()
    return () => {
      a?.stop()
    }
  }, [clips.length, actions, names])

  useFrame((state, delta) => {
    if (clips.length) {
      mixer.update(delta)
      return
    }
    const t = state.clock.elapsedTime
    const speed = 0.52
    const r = 1.22
    const g = ref.current
    if (!g) return
    g.position.x = Math.cos(t * speed) * r
    g.position.z = Math.sin(t * speed) * r
    g.position.y = 0.12 + Math.sin(t * speed * 6) * 0.04
    g.rotation.y = -t * speed + Math.PI / 2
  })

  return (
    <group ref={ref}>
      <Center>
        <primitive object={scene} />
      </Center>
    </group>
  )
}

function RouteAsset({ url }: { url: string }) {
  const lower = url.split('?')[0].toLowerCase()
  if (lower.endsWith('.fbx')) {
    return <BakedFbxLoop url={url} />
  }
  if (lower.endsWith('.glb') || lower.endsWith('.gltf')) {
    return <GltfAssetLoop url={url} />
  }
  return <EmptyScene />
}

export default function OwlbearLoadingScene({ glbUrl }: Props) {
  return (
    <Canvas
      className="vf-connect-canvas"
      style={{ background: 'transparent' }}
      shadows
      camera={{ position: [0, 1.25, 3.65], fov: 36 }}
      gl={{
        antialias: true,
        alpha: true,
        premultipliedAlpha: false,
        powerPreference: 'high-performance',
      }}
      dpr={[1, 2]}
      onCreated={({ gl, scene }) => {
        const canvas = gl.domElement
        canvas.style.background = 'transparent'
        gl.setClearColor(0x000000, 0)
        scene.background = null
      }}
    >
      <ambientLight intensity={0.55} />
      <directionalLight castShadow position={[3.5, 6, 4]} intensity={1.15} shadow-mapSize={[1024, 1024]} />
      <directionalLight position={[-3, 2.5, -2]} intensity={0.35} color="#b8c8ff" />
      <hemisphereLight args={['#e8ecf5', '#2a2218', 0.35]} />

      {glbUrl ? (
        <Suspense fallback={<EmptyScene />}>
          <LoadingModelErrorBoundary fallback={<EmptyScene />}>
            <RouteAsset url={glbUrl} />
          </LoadingModelErrorBoundary>
        </Suspense>
      ) : (
        <EmptyScene />
      )}

      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.001, 0]} receiveShadow>
        <planeGeometry args={[16, 16]} />
        <shadowMaterial opacity={0.45} transparent />
      </mesh>
      <ContactShadows
        position={[0, 0.01, 0]}
        opacity={0.42}
        scale={9}
        blur={2.2}
        far={4}
        color="#000000"
      />
    </Canvas>
  )
}

class LoadingModelErrorBoundary extends Component<
  { children: ReactNode; fallback: ReactNode },
  { err: Error | null }
> {
  state = { err: null as Error | null }

  static getDerivedStateFromError(err: Error) {
    return { err }
  }

  render() {
    if (this.state.err) return this.props.fallback
    return this.props.children
  }
}
