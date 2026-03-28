import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { LANDING_UPDATES } from '../landingRoutes'

function IconHome() {
  return (
    <svg className="aid-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      <polyline points="9 22 9 12 15 12 15 22" />
    </svg>
  )
}

function IconCompass() {
  return (
    <svg className="aid-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="12" cy="12" r="10" />
      <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
    </svg>
  )
}

function IconSearch() {
  return (
    <svg className="aid-app-search-glyph" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  )
}

function IconPlay() {
  return (
    <svg className="aid-app-play-icon" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M8 5v14l11-7-11-7z" />
    </svg>
  )
}

function IconUser() {
  return (
    <svg className="aid-app-user-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="12" cy="8" r="4" />
      <path d="M4 20c1.5-4 14.5-4 16 0" />
    </svg>
  )
}

function IconLogout() {
  return (
    <svg className="aid-app-dd-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
      <polyline points="16 17 21 12 16 7" />
      <line x1="21" x2="9" y1="12" y2="12" />
    </svg>
  )
}

function IconBell() {
  return (
    <svg className="aid-nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </svg>
  )
}

function navLinkClass({ isActive }: { isActive: boolean }) {
  return `aid-nav-link${isActive ? ' aid-nav-link-active' : ''}`
}

export default function AppTopbar() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userWrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!userMenuOpen) return
    function close(e: MouseEvent) {
      if (userWrapRef.current && !userWrapRef.current.contains(e.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [userMenuOpen])

  function handleLogout() {
    setUserMenuOpen(false)
    logout()
    navigate('/', { replace: true })
  }

  return (
    <header className="aid-topbar aid-topbar--sticky" role="banner">
      <div className="aid-app-topbar">
        <div className="aid-app-topbar-left">
          <Link to="/" className="aid-brand aid-topbar-brand-link">
            VIRFRIENDØ
          </Link>
          <nav className="aid-app-nav" aria-label="Main">
            <NavLink to="/" className={navLinkClass} end>
              <IconHome />
              Home
            </NavLink>
            <NavLink to="/menu" className={navLinkClass}>
              <IconCompass />
              Discover
            </NavLink>
            <NavLink to={LANDING_UPDATES} className={navLinkClass}>
              <IconBell />
              Updates
            </NavLink>
          </nav>
        </div>

        <div className="aid-app-topbar-center">
          <label className="aid-app-search-wrap">
            <span className="sr-only">Search</span>
            <IconSearch />
            <input type="search" className="aid-app-search" placeholder="Search" autoComplete="off" />
          </label>
        </div>

        <div className="aid-app-topbar-right">
          <NavLink
            to="/chat"
            className={({ isActive }) => `aid-app-play${isActive ? ' aid-app-play--here' : ''}`}
            title="Play"
          >
            <IconPlay />
            <span>Play</span>
          </NavLink>
          <div className="aid-app-user-wrap" ref={userWrapRef}>
            <button
              type="button"
              className="aid-app-user-btn"
              aria-expanded={userMenuOpen}
              aria-haspopup="menu"
              onClick={() => setUserMenuOpen((v) => !v)}
              title="Account"
            >
              <IconUser />
            </button>
            {userMenuOpen ? (
              <div className="aid-app-user-dd" role="menu">
                <button type="button" className="aid-app-user-dd-item" role="menuitem" onClick={handleLogout}>
                  <IconLogout />
                  Log out
                </button>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </header>
  )
}
