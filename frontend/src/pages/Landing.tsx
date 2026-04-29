import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { useGoogleSignIn } from '../hooks/useGoogleSignIn'
import GoogleGlyph from '../components/GoogleGlyph'
import LandingTopbar from '../components/LandingTopbar'
import { LANDING_CONTACT, LANDING_SIGN_IN, LANDING_SIGN_UP, LANDING_UPDATES } from '../landingRoutes'

const KICKER = 'AI Platform'
const TITLE = 'Pally'
/** Kicker 2 chữ + title: chỉ số --s 0..12 cho delay scratch */
function ScratchKicker() {
  return (
    <p className="aid-kicker aid-kicker-scratch">
      {KICKER.split('').map((ch, i) => (
        <span key={`k-${i}`} className="aid-scratch-char" style={{ '--s': i } as CSSProperties}>
          {ch}
        </span>
      ))}
    </p>
  )
}

function ScratchTitle() {
  return (
    <span className="aid-title-text" aria-label={TITLE}>
      {TITLE.split('').map((ch, i) => (
        <span
          key={`${ch}-${i}`}
          className="aid-title-char aid-scratch-char"
          style={{ '--s': KICKER.length + i } as CSSProperties}
        >
          {ch}
        </span>
      ))}
    </span>
  )
}

const SCROLL_HINT_DISMISS_RATIO = 0.28

function CloudShape() {
  return (
    <svg viewBox="0 0 120 50" className="aid-cloud-svg" aria-hidden>
      <ellipse cx="28" cy="32" rx="20" ry="14" fill="#ffffff" />
      <ellipse cx="50" cy="24" rx="22" ry="16" fill="#ffffff" />
      <ellipse cx="72" cy="28" rx="20" ry="14" fill="#ffffff" />
      <ellipse cx="92" cy="34" rx="16" ry="12" fill="#ffffff" />
      <ellipse cx="60" cy="38" rx="40" ry="8" fill="#ffffff" opacity="0.7" />
    </svg>
  )
}

function SnowPile() {
  return (
    <svg viewBox="0 0 140 50" className="aid-snowpile-svg" aria-hidden>
      <defs>
        <linearGradient id="aidSnowPile" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="60%" stopColor="#e0ecff" />
          <stop offset="100%" stopColor="#bfdbfe" />
        </linearGradient>
      </defs>
      <path
        d="M4 46 Q18 28 36 30 Q52 14 72 22 Q92 12 110 24 Q126 28 134 38 Q138 42 136 46 Z"
        fill="url(#aidSnowPile)"
        stroke="rgba(59,130,246,0.25)"
        strokeWidth="1"
      />
      <ellipse cx="50" cy="32" rx="6" ry="2" fill="#ffffff" opacity="0.85" />
      <ellipse cx="92" cy="30" rx="5" ry="1.8" fill="#ffffff" opacity="0.8" />
      <ellipse cx="120" cy="36" rx="4" ry="1.5" fill="#ffffff" opacity="0.7" />
    </svg>
  )
}

function LofiCat() {
  return (
    <svg viewBox="0 0 110 70" className="aid-cat-svg" aria-hidden>
      <path
        d="M14 46 Q4 40 8 28 Q10 22 14 22"
        stroke="#a8b3c4"
        strokeWidth="6"
        strokeLinecap="round"
        fill="none"
        className="aid-cat-tail"
      />
      <ellipse cx="58" cy="48" rx="30" ry="13" fill="#c8d2e0" />
      <ellipse cx="58" cy="52" rx="24" ry="8" fill="#f0e8dc" />
      <rect x="36" y="54" width="6" height="13" rx="3" fill="#a8b3c4" className="aid-cat-leg aid-cat-leg-1" />
      <rect x="48" y="55" width="6" height="12" rx="3" fill="#a8b3c4" className="aid-cat-leg aid-cat-leg-2" />
      <rect x="68" y="55" width="6" height="12" rx="3" fill="#a8b3c4" className="aid-cat-leg aid-cat-leg-3" />
      <rect x="80" y="54" width="6" height="13" rx="3" fill="#a8b3c4" className="aid-cat-leg aid-cat-leg-4" />
      <circle cx="86" cy="38" r="14" fill="#c8d2e0" />
      <path d="M76 28 L74 18 L84 26 Z" fill="#a8b3c4" />
      <path d="M96 28 L98 18 L88 26 Z" fill="#a8b3c4" />
      <path d="M77 26 L78 22 L82 26 Z" fill="#f5b8c4" />
      <path d="M95 26 L94 22 L90 26 Z" fill="#f5b8c4" />
      <ellipse cx="80" cy="40" rx="1.6" ry="1.8" fill="#1e3a5f" />
      <ellipse cx="92" cy="40" rx="1.6" ry="1.8" fill="#1e3a5f" />
      <circle cx="80.5" cy="39.5" r="0.5" fill="#ffffff" />
      <circle cx="92.5" cy="39.5" r="0.5" fill="#ffffff" />
      <path d="M85 43 L87 43 L86 45 Z" fill="#f5b8c4" />
      <path d="M86 45 Q84 47.5 82 47" stroke="#1e3a5f" strokeWidth="0.7" fill="none" strokeLinecap="round" />
      <path d="M86 45 Q88 47.5 90 47" stroke="#1e3a5f" strokeWidth="0.7" fill="none" strokeLinecap="round" />
      <line x1="72" y1="43" x2="80" y2="43.5" stroke="#a8b3c4" strokeWidth="0.4" />
      <line x1="72" y1="45" x2="80" y2="45" stroke="#a8b3c4" strokeWidth="0.4" />
      <line x1="92" y1="43.5" x2="100" y2="43" stroke="#a8b3c4" strokeWidth="0.4" />
      <line x1="92" y1="45" x2="100" y2="45" stroke="#a8b3c4" strokeWidth="0.4" />
    </svg>
  )
}

const SNOWFLAKES = Array.from({ length: 18 }, (_, i) => {
  const left = (i * 5.7) % 100
  const delay = (i * 0.6) % 7
  const dur = 7 + ((i * 1.1) % 5)
  const drift = ((i * 11) % 36) - 18
  const size = 3 + ((i * 1.3) % 3)
  const opacity = 0.6 + ((i * 0.05) % 0.3)
  return { left, delay, dur, drift, size, opacity }
})

function CatSnowScene() {
  return (
    <div className="aid-cat-scene" aria-hidden>
      <div className="aid-cloud aid-cloud-1"><CloudShape /></div>
      <div className="aid-cloud aid-cloud-2"><CloudShape /></div>
      <div className="aid-cloud aid-cloud-3"><CloudShape /></div>
      <div className="aid-cloud aid-cloud-4"><CloudShape /></div>
      <div className="aid-cloud aid-cloud-5"><CloudShape /></div>
      <div className="aid-snow-layer">
        {SNOWFLAKES.map((f, i) => (
          <span
            key={i}
            className="aid-snowflake"
            style={{
              left: `${f.left}%`,
              width: `${f.size}px`,
              height: `${f.size}px`,
              animationDelay: `${f.delay}s`,
              animationDuration: `${f.dur}s`,
              opacity: f.opacity,
              ['--drift' as string]: `${f.drift}px`,
            } as CSSProperties}
          />
        ))}
      </div>
      <div className="aid-ground" />
      <div className="aid-snowpile"><SnowPile /></div>
      <div className="aid-cat"><LofiCat /></div>
    </div>
  )
}

export default function Landing() {
  const whatSectionRef = useRef<HTMLElement>(null)
  const [scrollHintDismissed, setScrollHintDismissed] = useState(false)
  const [whatInView, setWhatInView] = useState(false)
  const {
    ready: googleReady,
    loading: googleLoading,
    error: googleError,
    googleMountRef,
    triggerGoogleSignIn,
  } = useGoogleSignIn()

  useEffect(() => {
    const el = whatSectionRef.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return
        if (entry.isIntersecting && entry.intersectionRatio >= SCROLL_HINT_DISMISS_RATIO) {
          setScrollHintDismissed(true)
        }
      },
      { threshold: [0, 0.1, 0.2, 0.28, 0.4, 0.6, 0.85, 1] },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  useEffect(() => {
    const el = whatSectionRef.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return
        const show = entry.isIntersecting && entry.intersectionRatio >= 0.12
        setWhatInView(show)
      },
      { root: null, rootMargin: '0px 0px -6% 0px', threshold: [0, 0.06, 0.12, 0.18, 0.28, 0.45, 0.65] },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  return (
    <div className="aid-root" id="top">
      <LandingTopbar />

      <main>
        <section className="aid-hero" aria-label="Hero">
          <div className="aid-hero-bg" aria-hidden />
          <div className="aid-hero-aurora" aria-hidden />
          <div className="aid-particle-field" aria-hidden />
          <div className="aid-hero-noise" aria-hidden />
          <div className="aid-hero-vignette" aria-hidden />
          <CatSnowScene />
          <section className="aid-hero-content">
            <div className="aid-hero-panel">
              <div className="aid-hero-mid">
                <ScratchKicker />
                <h1 className="aid-title aid-title-animated">
                  <ScratchTitle />
                </h1>
              </div>

              <div className="aid-landing-fade">
              <p className="aid-subtitle">
                just a place to test our model
              </p>
              <div className="aid-actions">
                <Link to={LANDING_SIGN_UP} className="aid-cta-primary">
                  <span className="aid-cta-label">Sign up</span>
                </Link>
                <Link to={LANDING_SIGN_IN} className="aid-cta-secondary">
                  <span className="aid-cta-label">Sign in</span>
                </Link>
              </div>
              <div className="aid-actions mt-3 aid-actions--google-host">
                <div className="aid-google-auth-wrap">
                  <div
                    className={`aid-cta-google aid-google-gsi-decoy${!googleReady ? ' aid-google-styled-cta--pending' : ''}`}
                    aria-hidden
                  >
                    <span className="aid-cta-label aid-cta-label--row">
                      <GoogleGlyph />
                      {googleLoading ? 'CONNECTING…' : 'CONTINUE WITH GOOGLE'}
                    </span>
                  </div>
                  <div
                    ref={googleMountRef}
                    className={`aid-google-gsi-overlay${!googleReady || googleLoading ? ' aid-google-gsi-overlay--blocked' : ''}`}
                    aria-hidden
                    onClick={() => {
                      if (googleReady && !googleLoading) {
                        triggerGoogleSignIn();
                      }
                    }}
                  />
                </div>
              </div>
              {googleLoading ? (
                <p className="aid-google-loading text-[11px] text-center text-amber-100/80 mt-2">Signing in with Google…</p>
              ) : null}
              {googleError && (
                <p className="aid-google-error text-[11px] text-red-300 mt-3 text-center">{googleError}</p>
              )}
              </div>
            </div>
          </section>

          <div className="aid-landing-fade aid-hero-scroll-dock">
            <div className="aid-scroll-hint-wrap">
              <div
                className={`aid-scroll-cue aid-scroll-cue-in-hero${scrollHintDismissed ? ' aid-scroll-cue--dismissed' : ''}`}
                aria-hidden="true"
              >
                <span className="aid-scroll-cue-text">SCROLL</span>
                <span className="aid-scroll-cue-line" />
              </div>
            </div>
          </div>
        </section>

        <div className="aid-landing-fade">
          <section
            ref={whatSectionRef}
            id="what-to-do"
            className={`aid-what${whatInView ? ' aid-what--visible' : ''}`}
            aria-labelledby="what-to-do-heading"
          >
            <div className="aid-what-inner">
              <h2 id="what-to-do-heading" className="aid-what-heading">
                What to do
              </h2>
              <ol className="aid-what-list">
                <li className="aid-what-item aid-what-item--left">
                  <span className="aid-what-num">1</span>
                  <span className="aid-what-copy">
                    <span className="aid-what-title">Talk to our AI</span>
                    <span className="aid-what-detail">
                      Step into a story-style chat that feels like a scene, not a search box. Ask about anime, games, or
                      just vent after a rough day — your companion stays in character, keeps the tone warm, and meets you
                      where you are.
                    </span>
                  </span>
                </li>
                <li className="aid-what-item aid-what-item--right">
                  <span className="aid-what-num">2</span>
                  <span className="aid-what-copy">
                    <span className="aid-what-title">Play games</span>
                    <span className="aid-what-detail">
                      Take a breather from typing and play together: chess, bite-sized quizzes, and more on the way.
                      Quick rounds, low pressure — perfect between chats or when you just want to goof off for a minute.
                    </span>
                  </span>
                </li>
                <li className="aid-what-item aid-what-item--left">
                  <span className="aid-what-num">3</span>
                  <span className="aid-what-copy">
                    <span className="aid-what-title">Grow your bond</span>
                    <span className="aid-what-detail">
                      The more you show up, the more it feels like they remember you. Honest check-ins and longer
                      hangouts slowly build rapport — less like filling a form, more like leveling trust in a cozy RPG.
                    </span>
                  </span>
                </li>
              </ol>
            </div>
          </section>
        </div>

        <section className="aid-landing-menu-cta" aria-labelledby="menu-cta-heading">
          <div className="aid-landing-menu-cta-inner">
            <h2 id="menu-cta-heading" className="aid-landing-menu-cta-title">
              Browse deployed AIs
            </h2>
            <p className="aid-landing-menu-cta-copy">
              The launcher lives on its own route — sign in, then open the menu to pick a model and jump into chat.
            </p>
            <div className="aid-landing-menu-cta-actions">
              <Link to="/menu" className="aid-cta-primary">
                <span className="aid-cta-label">Open menu</span>
              </Link>
              <Link to={LANDING_SIGN_IN} className="aid-cta-secondary">
                <span className="aid-cta-label">Sign in</span>
              </Link>
            </div>
          </div>
        </section>

        <footer className="aid-footer aid-footer-compact" id="contact">
          <div className="aid-footer-stack">
            <div className="aid-footer-bar">
              <div className="aid-footer-team">
                <span className="aid-footer-team-label">Bộ Tứ Random BS Go</span>
                <span className="aid-footer-names">
                  Le Ngo Thanh Toan · Nguyen Tan Phuc Thinh · Vo Phuoc Thinh · Lien Phuc Thinh
                </span>
              </div>
              <div className="aid-footer-actions">
                <a href="#top" className="aid-footer-inline-link">
                  Pally
                </a>
                <span className="aid-footer-sep" aria-hidden>
                  |
                </span>
                <Link to={LANDING_CONTACT} className="aid-footer-inline-link aid-footer-contact-link">
                  Contact us
                </Link>
              </div>
            </div>
            <div className="aid-footer-bottom">
              <p className="aid-footer-copy">
                © {new Date().getFullYear()} Pally · Bộ Tứ Random BS Go. All rights reserved.
              </p>
              <div className="aid-footer-legal" aria-label="Legal and resources">
                <Link to={LANDING_UPDATES} className="aid-footer-legal-link">
                  Changelog
                </Link>
                <Link to={LANDING_CONTACT} className="aid-footer-legal-link">
                  Contact
                </Link>
              </div>
            </div>
          </div>
        </footer>
      </main>
    </div>
  )
}
