import { Link, useLocation } from 'react-router-dom'
import { LANDING_UPDATES } from '../landingRoutes'
import { useAuth } from '../hooks/useAuth'

export default function LandingTopbar() {
  const { pathname } = useLocation()
  const { isAuth, loading } = useAuth()
  const onHome = pathname === '/'
  const onUpdates = pathname === LANDING_UPDATES
  const onMenu = pathname === '/menu'

  return (
    <header className="aid-topbar">
      <div className="aid-top-left">
        <Link to="/" className="aid-brand aid-topbar-brand-link">
          PALLY
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
        {!loading && isAuth && (
          <Link
            to="/menu"
            className={`aid-nav-link${onMenu ? ' aid-nav-link-active' : ''}`}
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
              <line x1="3" y1="6" x2="21" y2="6" />
              <line x1="3" y1="12" x2="21" y2="12" />
              <line x1="3" y1="18" x2="21" y2="18" />
            </svg>
            Menu
          </Link>
        )}
      </div>
    </header>
  )
}
