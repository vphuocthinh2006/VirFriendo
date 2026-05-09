import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useGoogleSignIn } from '../hooks/useGoogleSignIn'
import { useAuth } from '../hooks/useAuth'
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

function FanhuaTree() {
  return (
    <svg viewBox="0 0 480 520" className="aid-tree-svg" aria-hidden>
      <defs>
        <linearGradient id="aidTrunk" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#a07246" />
          <stop offset="50%" stopColor="#7d5230" />
          <stop offset="100%" stopColor="#5a3a1f" />
        </linearGradient>
        <radialGradient id="aidCanopy" cx="0.5" cy="0.45" r="0.6">
          <stop offset="0%" stopColor="#a6d17d" />
          <stop offset="55%" stopColor="#1B5E20" />
          <stop offset="100%" stopColor="#6ba348" />
        </radialGradient>
        <radialGradient id="aidCanopyAlt" cx="0.5" cy="0.5" r="0.6">
          <stop offset="0%" stopColor="#ff7b70" />
          <stop offset="60%" stopColor="#fa6255" />
          <stop offset="100%" stopColor="#e04a3f" />
        </radialGradient>
      </defs>

      {/* roots peeking out */}
      <path d="M180 520 Q200 500 230 504 Q260 500 280 520" fill="url(#aidTrunk)" opacity="0.85" />
      <path d="M150 520 Q170 504 200 510" fill="url(#aidTrunk)" opacity="0.7" />
      <path d="M310 520 Q290 506 270 512" fill="url(#aidTrunk)" opacity="0.7" />

      {/* massive trunk */}
      <path d="M205 520 Q190 410 200 320 Q186 230 215 140 Q230 80 240 50 Q250 80 265 140 Q294 230 280 320 Q290 410 275 520 Z" fill="url(#aidTrunk)" />
      {/* trunk inner shading */}
      <path d="M225 520 Q218 410 226 320 Q215 230 235 150" stroke="#5a3a1f" strokeWidth="1.5" fill="none" opacity="0.5" />
      <path d="M255 520 Q262 410 254 320 Q265 230 245 150" stroke="#5a3a1f" strokeWidth="1.5" fill="none" opacity="0.5" />

      {/* major branches sprawling out */}
      <path d="M230 230 Q170 210 110 190 Q80 184 60 196" stroke="#6b4828" strokeWidth="14" strokeLinecap="round" fill="none" />
      <path d="M250 200 Q310 175 380 168 Q420 165 440 178" stroke="#6b4828" strokeWidth="14" strokeLinecap="round" fill="none" />
      <path d="M232 160 Q200 130 160 118" stroke="#6b4828" strokeWidth="10" strokeLinecap="round" fill="none" />
      <path d="M250 130 Q290 100 330 88" stroke="#6b4828" strokeWidth="10" strokeLinecap="round" fill="none" />

      {/* canopy clusters — left arm */}
      <circle cx="60" cy="200" r="42" fill="url(#aidCanopy)" />
      <circle cx="90" cy="178" r="48" fill="url(#aidCanopy)" />
      <circle cx="118" cy="208" r="44" fill="url(#aidCanopy)" />
      <circle cx="50" cy="170" r="36" fill="url(#aidCanopyAlt)" />

      {/* canopy clusters — right arm */}
      <circle cx="438" cy="180" r="44" fill="url(#aidCanopy)" />
      <circle cx="408" cy="158" r="50" fill="url(#aidCanopy)" />
      <circle cx="378" cy="190" r="46" fill="url(#aidCanopy)" />
      <circle cx="448" cy="148" r="36" fill="url(#aidCanopyAlt)" />

      {/* canopy upper crown */}
      <circle cx="160" cy="118" r="48" fill="url(#aidCanopy)" />
      <circle cx="190" cy="78" r="50" fill="url(#aidCanopy)" />
      <circle cx="240" cy="46" r="58" fill="url(#aidCanopy)" />
      <circle cx="290" cy="78" r="50" fill="url(#aidCanopy)" />
      <circle cx="320" cy="118" r="48" fill="url(#aidCanopy)" />

      {/* mid canopy fill */}
      <circle cx="220" cy="120" r="46" fill="url(#aidCanopy)" />
      <circle cx="270" cy="120" r="46" fill="url(#aidCanopy)" />
      <circle cx="180" cy="158" r="44" fill="url(#aidCanopy)" />
      <circle cx="300" cy="158" r="44" fill="url(#aidCanopy)" />
      <circle cx="230" cy="170" r="42" fill="url(#aidCanopyAlt)" />
      <circle cx="265" cy="170" r="42" fill="url(#aidCanopyAlt)" />

      {/* yellow flower nuclei scattered across canopy */}
      <circle cx="70" cy="190" r="6" fill="#fa6255" />
      <circle cx="100" cy="170" r="7" fill="#fa6255" />
      <circle cx="180" cy="100" r="8" fill="#fa6255" />
      <circle cx="240" cy="40" r="9" fill="#fa6255" />
      <circle cx="300" cy="100" r="8" fill="#fa6255" />
      <circle cx="220" cy="125" r="6" fill="#fa6255" />
      <circle cx="270" cy="125" r="6" fill="#fa6255" />
      <circle cx="170" cy="160" r="6" fill="#fa6255" />
      <circle cx="310" cy="160" r="6" fill="#fa6255" />
      <circle cx="430" cy="170" r="7" fill="#fa6255" />
      <circle cx="395" cy="155" r="6" fill="#fa6255" />
    </svg>
  )
}

function FlowerBed() {
  return (
    <svg viewBox="0 0 320 90" className="aid-flowerbed-svg" aria-hidden>
      {/* grass tufts */}
      <path d="M8 82 Q14 60 20 82 M28 84 Q34 62 40 84 M50 82 Q56 60 62 82" stroke="#6ba348" strokeWidth="3" fill="none" strokeLinecap="round" />
      <path d="M260 84 Q266 62 272 84 M280 82 Q286 60 292 82 M302 84 Q308 62 314 84" stroke="#6ba348" strokeWidth="3" fill="none" strokeLinecap="round" />
      {/* red flower 1 */}
      <g transform="translate(76, 66)">
        <circle r="9" fill="#fa6255" cx="-10" cy="-3" />
        <circle r="9" fill="#fa6255" cx="10" cy="-3" />
        <circle r="9" fill="#fa6255" cx="-6" cy="8" />
        <circle r="9" fill="#fa6255" cx="6" cy="8" />
        <circle r="6" fill="#fa6255" />
      </g>
      {/* yellow flower middle */}
      <g transform="translate(160, 60)">
        <circle r="11" fill="#fa6255" cx="-12" cy="-3" />
        <circle r="11" fill="#fa6255" cx="12" cy="-3" />
        <circle r="11" fill="#fa6255" cx="-7" cy="10" />
        <circle r="11" fill="#fa6255" cx="7" cy="10" />
        <circle r="7" fill="#fa6255" />
      </g>
      {/* red flower 2 */}
      <g transform="translate(244, 66)">
        <circle r="9" fill="#fa6255" cx="-10" cy="-3" />
        <circle r="9" fill="#fa6255" cx="10" cy="-3" />
        <circle r="9" fill="#fa6255" cx="-6" cy="8" />
        <circle r="9" fill="#fa6255" cx="6" cy="8" />
        <circle r="6" fill="#fa6255" />
      </g>
      {/* small accent flowers between */}
      <g transform="translate(118, 76)">
        <circle r="6" fill="#FF6B6B" cx="-7" cy="-2" />
        <circle r="6" fill="#FF6B6B" cx="7" cy="-2" />
        <circle r="6" fill="#FF6B6B" cx="-4" cy="6" />
        <circle r="6" fill="#FF6B6B" cx="4" cy="6" />
        <circle r="4" fill="#fa6255" />
      </g>
      <g transform="translate(204, 76)">
        <circle r="6" fill="#FF6B6B" cx="-7" cy="-2" />
        <circle r="6" fill="#FF6B6B" cx="7" cy="-2" />
        <circle r="6" fill="#FF6B6B" cx="-4" cy="6" />
        <circle r="6" fill="#FF6B6B" cx="4" cy="6" />
        <circle r="4" fill="#fa6255" />
      </g>
    </svg>
  )
}

function Butterfly() {
  return (
    <svg viewBox="0 0 40 30" className="aid-butterfly-svg" aria-hidden>
      <ellipse cx="20" cy="15" rx="1.2" ry="6" fill="#2a1f12" />
      {/* left wings */}
      <g className="aid-butterfly-wing-l" style={{ transformOrigin: '20px 15px' }}>
        <ellipse cx="11" cy="11" rx="8" ry="6" fill="#1B5E20" />
        <ellipse cx="13" cy="20" rx="6" ry="4.5" fill="#a6d17d" />
        <circle cx="9" cy="10" r="1.5" fill="#fa6255" />
      </g>
      {/* right wings */}
      <g className="aid-butterfly-wing-r" style={{ transformOrigin: '20px 15px' }}>
        <ellipse cx="29" cy="11" rx="8" ry="6" fill="#1B5E20" />
        <ellipse cx="27" cy="20" rx="6" ry="4.5" fill="#a6d17d" />
        <circle cx="31" cy="10" r="1.5" fill="#fa6255" />
      </g>
      {/* antennae */}
      <path d="M20 9 Q19 5 16 4" stroke="#2a1f12" strokeWidth="0.5" fill="none" />
      <path d="M20 9 Q21 5 24 4" stroke="#2a1f12" strokeWidth="0.5" fill="none" />
    </svg>
  )
}

function LofiCat() {
  return (
    <svg viewBox="0 0 110 70" className="aid-cat-svg" aria-hidden>
      <path
        d="M14 46 Q4 40 8 28 Q10 22 14 22"
        stroke="#b8a89a"
        strokeWidth="6"
        strokeLinecap="round"
        fill="none"
        className="aid-cat-tail"
      />
      <ellipse cx="58" cy="48" rx="30" ry="13" fill="#d4c8b8" className="aid-cat-body" />
      <ellipse cx="58" cy="52" rx="24" ry="8" fill="#f5ebd6" />
      <rect x="36" y="54" width="6" height="13" rx="3" fill="#b8a89a" className="aid-cat-leg aid-cat-leg-1" />
      <rect x="48" y="55" width="6" height="12" rx="3" fill="#b8a89a" className="aid-cat-leg aid-cat-leg-2" />
      <rect x="68" y="55" width="6" height="12" rx="3" fill="#b8a89a" className="aid-cat-leg aid-cat-leg-3" />
      <rect x="80" y="54" width="6" height="13" rx="3" fill="#b8a89a" className="aid-cat-leg aid-cat-leg-4" />
      <circle cx="86" cy="38" r="14" fill="#d4c8b8" />
      <path d="M76 28 L74 18 L84 26 Z" fill="#b8a89a" />
      <path d="M96 28 L98 18 L88 26 Z" fill="#b8a89a" />
      <path d="M77 26 L78 22 L82 26 Z" fill="#fa6255" />
      <path d="M95 26 L94 22 L90 26 Z" fill="#fa6255" />
      <ellipse cx="80" cy="40" rx="1.6" ry="1.8" fill="#1a1a1a" />
      <ellipse cx="92" cy="40" rx="1.6" ry="1.8" fill="#1a1a1a" />
      <circle cx="80.5" cy="39.5" r="0.5" fill="#ffffff" />
      <circle cx="92.5" cy="39.5" r="0.5" fill="#ffffff" />
      <path d="M85 43 L87 43 L86 45 Z" fill="#fa6255" />
      <path d="M86 45 Q84 47.5 82 47" stroke="#1a1a1a" strokeWidth="0.7" fill="none" strokeLinecap="round" />
      <path d="M86 45 Q88 47.5 90 47" stroke="#1a1a1a" strokeWidth="0.7" fill="none" strokeLinecap="round" />
      <line x1="72" y1="43" x2="80" y2="43.5" stroke="#b8a89a" strokeWidth="0.4" />
      <line x1="72" y1="45" x2="80" y2="45" stroke="#b8a89a" strokeWidth="0.4" />
      <line x1="92" y1="43.5" x2="100" y2="43" stroke="#b8a89a" strokeWidth="0.4" />
      <line x1="92" y1="45" x2="100" y2="45" stroke="#b8a89a" strokeWidth="0.4" />
    </svg>
  )
}

const PETALS = Array.from({ length: 12 }, (_, i) => {
  const left = 28 + ((i * 5.3) % 44)
  const startTop = 18 + ((i * 3.1) % 35)
  const delay = (i * 0.9) % 7
  const dur = 8 + ((i * 1.2) % 5)
  const drift = ((i * 17) % 100) - 50
  const size = 8 + ((i * 1.5) % 6)
  const variant = i % 3
  const rot = (i * 53) % 360
  return { left, startTop, delay, dur, drift, size, variant, rot }
})

const BUTTERFLIES = [
  { left: 47, bottom: 160, dur: 15, delay: 0 },
]

function CatSnowScene() {
  return (
    <div className="aid-cat-scene" aria-hidden>
      <div className="aid-cloud aid-cloud-1"><CloudShape /></div>
      <div className="aid-cloud aid-cloud-2"><CloudShape /></div>
      <div className="aid-cloud aid-cloud-3"><CloudShape /></div>
      <div className="aid-petal-layer">
        {PETALS.map((p, i) => (
          <span
            key={i}
            className={`aid-petal aid-petal-v${p.variant}`}
            style={{
              left: `${p.left}%`,
              top: `${p.startTop}%`,
              width: `${p.size}px`,
              height: `${p.size}px`,
              animationDelay: `${p.delay}s`,
              animationDuration: `${p.dur}s`,
              ['--drift' as string]: `${p.drift}px`,
              ['--rot' as string]: `${p.rot}deg`,
            } as CSSProperties}
          />
        ))}
      </div>
      {BUTTERFLIES.map((b, i) => (
        <div
          key={i}
          className={`aid-butterfly aid-butterfly-${i + 1}`}
          style={{
            left: `${b.left}%`,
            bottom: `${b.bottom}px`,
            animationDuration: `${b.dur}s`,
            animationDelay: `${b.delay}s`,
          } as CSSProperties}
        >
          <Butterfly />
        </div>
      ))}
      <div className="aid-ground" />
      <div className="aid-tree"><FanhuaTree /></div>
      <div className="aid-flowerbed"><FlowerBed /></div>
      <div className="aid-cat"><LofiCat /></div>
    </div>
  )
}

export default function Landing() {
  const whatSectionRef = useRef<HTMLElement>(null)
  const [scrollHintDismissed, setScrollHintDismissed] = useState(false)
  const [whatInView, setWhatInView] = useState(false)
  const { isAuth, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const {
    ready: googleReady,
    loading: googleLoading,
    error: googleError,
    googleMountRef,
    triggerGoogleSignIn,
  } = useGoogleSignIn()

  // Redirect authenticated users to /menu
  useEffect(() => {
    if (!authLoading && isAuth) navigate('/menu', { replace: true })
  }, [isAuth, authLoading, navigate])

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
                    <span className="aid-what-title">Deploy our models</span>
                    <span className="aid-what-detail">
                      Browse the lineup and launch any model into your own chat session — each one ships with its own
                      personality, tone, and backstory, ready to go the moment you hit play.
                    </span>
                  </span>
                </li>
                <li className="aid-what-item aid-what-item--right">
                  <span className="aid-what-num">2</span>
                  <span className="aid-what-copy">
                    <span className="aid-what-title">Talk to our models</span>
                    <span className="aid-what-detail">
                      Step into a story-style chat that feels like a scene, not a search box. Ask anything, vent after a
                      rough day, or just hang — your companion stays in character and meets you where you are.
                    </span>
                  </span>
                </li>
                <li className="aid-what-item aid-what-item--left">
                  <span className="aid-what-num">3</span>
                  <span className="aid-what-copy">
                    <span className="aid-what-title">Ask to co-op &amp; upload your models</span>
                    <span className="aid-what-detail">
                      Have a character or persona you want to bring to life? Reach out and we'll work together to get
                      your model on the platform — your creation, our stage.
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
                <span className="aid-footer-team-label">Pally team</span>
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
                © {new Date().getFullYear()} Pally. All rights reserved.
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
