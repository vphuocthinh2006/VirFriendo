/**
 * Full-screen loading: parchment + CSS progress only (no WebGL / FBX / GLB).
 * Thời gian tối thiểu overlay: `LOADING_MIN_MS` (đồng bộ App lazy + auth).
 */
import { type CSSProperties } from 'react'
import { useLocation } from 'react-router-dom'
import { LOADING_MIN_MS } from '../constants/loading'

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
        <div className="vf-connect-stage vf-connect-stage--css" aria-hidden>
          <div className="vf-connect-css-spinner" />
        </div>
        <div className="vf-connect-progress" aria-hidden>
          <div className="vf-connect-progress__fill" />
        </div>
        <p className="vf-connect-caption">VirFriendo</p>
      </div>
    </div>
  )
}
