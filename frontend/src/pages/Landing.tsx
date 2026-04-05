import { useEffect, useRef, useState, type CSSProperties } from 'react'
import { Link } from 'react-router-dom'
import { useGoogleSignIn } from '../hooks/useGoogleSignIn'
import GoogleGlyph from '../components/GoogleGlyph'
import LandingTopbar from '../components/LandingTopbar'
import { LANDING_CONTACT, LANDING_SIGN_IN, LANDING_SIGN_UP, LANDING_UPDATES } from '../landingRoutes'

const KICKER = 'AI'
const TITLE = 'VIRFRIENDØ'
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

export default function Landing() {
  const whatSectionRef = useRef<HTMLElement>(null)
  const [scrollHintDismissed, setScrollHintDismissed] = useState(false)
  const [whatInView, setWhatInView] = useState(false)
  const {
    ready: googleReady,
    loading: googleLoading,
    error: googleError,
    googleMountRef,
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
                A platform where the tuq developers create their own reality
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
                <span className="aid-footer-team-label">Team TUQ</span>
                <span className="aid-footer-names">
                  Le Ngo Thanh Toan · Nguyen Tan Phuc Thinh · Vo Phuoc Thinh · Lien Phuc Thinh
                </span>
              </div>
              <div className="aid-footer-actions">
                <a href="#top" className="aid-footer-inline-link">
                  VirFriendo
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
                © {new Date().getFullYear()} VirFriendo · Team TUQ. All rights reserved.
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
