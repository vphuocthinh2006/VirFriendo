import { Link, useLocation } from 'react-router-dom'
import { LANDING_UPDATES } from '../landingRoutes'

export default function LandingTopbar() {
  const { pathname } = useLocation()
  const onHome = pathname === '/'
  const onUpdates = pathname === LANDING_UPDATES

  return (
    <header className="aid-topbar">
      <div className="aid-top-left">
        <Link to="/" className="aid-brand aid-topbar-brand-link">
          VIRFRIENDØ
        </Link>
        <Link
          to="/"
          className={`aid-nav-link${onHome ? ' aid-nav-link-active' : ''}`}
        >
          <svg
            className="aid-nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
            <polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          Home
        </Link>
        <Link
          to={LANDING_UPDATES}
          className={`aid-nav-link${onUpdates ? ' aid-nav-link-active' : ''}`}
        >
          <svg
            className="aid-nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
          >
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 0 1-3.46 0" />
          </svg>
          Updates
        </Link>
      </div>
    </header>
  )
}
