import { Link, Navigate, useSearchParams } from 'react-router-dom'
import AppTopbar from '../components/AppTopbar'
import AgentMenuDetail from '../components/AgentMenuDetail'
import DeployedAiGrid from '../components/DeployedAiGrid'
import { DEPLOYED_AGENTS } from '../data/deployedAgents'
import { LANDING_CONTACT, LANDING_UPDATES } from '../landingRoutes'

type HeroRailItem = {
  kicker: string
  title: string
  icon: string
  href?: string
}

const HERO_SIDEBAR: HeroRailItem[] = [
  { kicker: 'Welcome', title: 'Pick an AI and hit Play to chat', icon: '🔥' },
  { kicker: 'Discover', title: 'Browse every deployed model below', icon: '◎' },
  { kicker: 'Updates', title: 'Patch notes & roadmap', href: LANDING_UPDATES, icon: '➜' },
]

export default function Menu() {
  const [searchParams] = useSearchParams()
  const agentId = searchParams.get('agent')
  const selectedAgent = agentId ? DEPLOYED_AGENTS.find((a) => a.id === agentId) : null
  const invalidAgent = Boolean(agentId && !selectedAgent)
  const heroCover = DEPLOYED_AGENTS[0]?.coverImageUrl ?? ''

  return (
    <div className="ad-shell" id="top">
      <AppTopbar />

      <main className="ad-main">
        {invalidAgent && <Navigate to="/menu" replace />}
        {!invalidAgent && selectedAgent && <AgentMenuDetail agent={selectedAgent} />}
        {!invalidAgent && !selectedAgent && (
          <>
            <section className="ad-hero" aria-label="Featured">
              <div className="ad-hero__banner">
                <img className="ad-hero__banner-img" src={heroCover} alt="" />
                <div className="ad-hero__banner-scrim" aria-hidden />
                <div className="ad-hero__banner-inner">
                  <p className="ad-hero__eyebrow">Featured</p>
                  <h1 className="ad-hero__headline">Start your next session</h1>
                  <p className="ad-hero__lede">
                    Scroll to <strong>Our currently deployed AI</strong> — choose a card, then <strong>Chat</strong> or use{' '}
                    <strong>Play</strong> in the header to jump into the session view.
                  </p>
                  <a href="#deployed-ai" className="ad-hero__cta">
                    Jump to models
                  </a>
                </div>
              </div>
              <aside className="ad-hero__rail" aria-label="Highlights">
                <ul className="ad-hero__rail-list">
                  {HERO_SIDEBAR.map((row) => (
                    <li key={row.kicker}>
                      {row.href ? (
                        <Link to={row.href} className="ad-hero__rail-item ad-hero__rail-item--link">
                          <div className="ad-hero__rail-text">
                            <span className="ad-hero__rail-kicker">{row.kicker}</span>
                            <span className="ad-hero__rail-title">{row.title}</span>
                          </div>
                          <span className="ad-hero__rail-icon" aria-hidden>
                            {row.icon}
                          </span>
                        </Link>
                      ) : (
                        <div className="ad-hero__rail-item">
                          <div className="ad-hero__rail-text">
                            <span className="ad-hero__rail-kicker">{row.kicker}</span>
                            <span className="ad-hero__rail-title">{row.title}</span>
                          </div>
                          <span className="ad-hero__rail-icon" aria-hidden>
                            {row.icon}
                          </span>
                        </div>
                      )}
                    </li>
                  ))}
                </ul>
              </aside>
            </section>

            <DeployedAiGrid variant="aidungeon" />
          </>
        )}
      </main>

      <footer className="ad-page-footer" id="contact">
        <div className="ad-page-footer__inner">
          <div className="ad-page-footer__row">
            <div className="ad-page-footer__team">
              <span className="ad-page-footer__label">Bộ Tứ Random BS Go</span>
              <span className="ad-page-footer__names">
                Le Ngo Thanh Toan · Nguyen Tan Phuc Thinh · Vo Phuoc Thinh · Lien Phuc Thinh
              </span>
            </div>
            <div className="ad-page-footer__links">
              <Link to="/">Pally</Link>
              <span aria-hidden>·</span>
              <Link to={LANDING_CONTACT}>Contact</Link>
            </div>
          </div>
          <div className="ad-page-footer__legal">
            <p>© {new Date().getFullYear()} Pally · Bộ Tứ Random BS Go</p>
            <div className="ad-page-footer__legal-links">
              <Link to={LANDING_UPDATES}>Changelog</Link>
              <Link to={LANDING_CONTACT}>Contact</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
