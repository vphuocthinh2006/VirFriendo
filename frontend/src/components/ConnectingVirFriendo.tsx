/**
 * Full-screen loading (phong cách gần AI Dungeon): parchment + progress; WebGL 3D — FBX/GLB trong `public/`.
 * Thời gian tối thiểu overlay: `LOADING_MIN_MS` (đồng bộ App lazy + auth).
 */
import { useEffect, type CSSProperties } from 'react'
import { useLocation } from 'react-router-dom'
import { useLoader } from '@react-three/fiber'
import { useGLTF } from '@react-three/drei'
import { FBXLoader } from 'three/examples/jsm/loaders/FBXLoader.js'
import { LOADING_MIN_MS } from '../constants/loading'
import OwlbearLoadingScene from './connecting/OwlbearLoadingScene'

const DEFAULT_MODEL = '/models/untitled.fbx'

function isMarketingRoute(pathname: string) {
  return (
    pathname === '/' ||
    pathname === '/login' ||
    pathname === '/register' ||
    pathname === '/updates' ||
    pathname.startsWith('/contact')
  )
}

export default function ConnectingVirFriendo() {
  const { pathname } = useLocation()
  const overlayClass = isMarketingRoute(pathname)
    ? 'vf-connect-overlay vf-connect-overlay--marketing'
    : 'vf-connect-overlay vf-connect-overlay--app'

  const glbUrl = import.meta.env.VITE_OWLBEAR_GLB_URL?.trim() || DEFAULT_MODEL

  useEffect(() => {
    const u = glbUrl.toLowerCase()
    if (u.endsWith('.fbx')) {
      useLoader.preload(FBXLoader, glbUrl)
    } else {
      useGLTF.preload(glbUrl, true, false)
    }
  }, [glbUrl])

  return (
    <div
      className={overlayClass}
      role="status"
      aria-live="polite"
      aria-busy="true"
      style={
        {
          '--vf-connect-load-ms': `${LOADING_MIN_MS}ms`,
        } as CSSProperties
      }
    >
      <div className="vf-connect-parchment">
        <p className="vf-connect-title">Your story is loading</p>
        <p className="vf-connect-tagline">Hang tight — the next scene is almost ready.</p>
        <div className="vf-connect-stage" aria-hidden>
          <OwlbearLoadingScene glbUrl={glbUrl} />
        </div>
        <div className="vf-connect-progress" aria-hidden>
          <div className="vf-connect-progress__fill" />
        </div>
        <p className="vf-connect-caption">VirFriendo</p>
      </div>
    </div>
  )
}
