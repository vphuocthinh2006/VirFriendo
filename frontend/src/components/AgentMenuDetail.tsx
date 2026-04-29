import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../services/api'
import { genreLabelsForAgent } from '../data/agentGenres'
import type { DeployedAgent } from '../data/deployedAgents'

function formatShortCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}k`
  return String(n)
}

function formatTimeAgo(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const s = Math.floor((Date.now() - d.getTime()) / 1000)
  if (s < 0) {
    return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium' }).format(d)
  }
  if (s < 45) return 'just now'
  const m = Math.floor(s / 60)
  if (m < 60) return `${m} minute${m === 1 ? '' : 's'} ago`
  const h = Math.floor(m / 60)
  if (h < 48) return `${h} hour${h === 1 ? '' : 's'} ago`
  const days = Math.floor(h / 24)
  if (days < 7) return `${days} day${days === 1 ? '' : 's'} ago`
  if (days < 30) {
    const w = Math.floor(days / 7)
    return `${w} week${w === 1 ? '' : 's'} ago`
  }
  if (days < 365) {
    const mo = Math.floor(days / 30)
    return `${mo} month${mo === 1 ? '' : 's'} ago`
  }
  const y = Math.floor(days / 365)
  return `${y} year${y === 1 ? '' : 's'} ago`
}

type TabId = 'details' | 'comments'

type Props = {
  agent: DeployedAgent
}

function IconPlay({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M8 5v14l11-7-11-7z" />
    </svg>
  )
}

function IconThumbUp({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M7 10v12"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-6.55a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2h0a3.13 3.13 0 0 1 3 3.88Z"
      />
    </svg>
  )
}

function IconBookmark({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"
      />
    </svg>
  )
}

function IconShare({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="18" cy="5" r="3" />
      <circle cx="6" cy="12" r="3" />
      <circle cx="18" cy="19" r="3" />
      <path strokeLinecap="round" d="M8.59 13.51l6.83 3.98M15.41 6.51l-6.82 3.98" />
    </svg>
  )
}

export default function AgentMenuDetail({ agent }: Props) {
  const [tab, setTab] = useState<TabId>('details')
  const [stats, setStats] = useState<api.AgentStatsResponse | null>(null)
  const [moreOpen, setMoreOpen] = useState(false)
  const moreWrapRef = useRef<HTMLDivElement>(null)
  const [bookmarkLocal, setBookmarkLocal] = useState(() =>
    typeof localStorage !== 'undefined' ? localStorage.getItem(`vf_bm_${agent.id}`) === '1' : false,
  )

  useEffect(() => {
    if (!moreOpen) return
    const close = (e: MouseEvent) => {
      if (moreWrapRef.current && !moreWrapRef.current.contains(e.target as Node)) setMoreOpen(false)
    }
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [moreOpen])

  const refreshStats = useCallback(async () => {
    try {
      setStats(await api.getAgentStats(agent.id))
    } catch {
      setStats(null)
    }
  }, [agent.id])

  useEffect(() => {
    void refreshStats()
    const id = window.setInterval(() => void refreshStats(), 8000)
    return () => window.clearInterval(id)
  }, [refreshStats])

  const handleLike = useCallback(async () => {
    if (!api.isAuthenticated()) {
      window.alert('Sign in to like')
      return
    }
    try {
      const s = await api.toggleAgentLike(agent.id)
      setStats(s)
    } catch (e) {
      window.alert(e instanceof Error ? e.message : 'Could not update like')
    }
  }, [agent.id])

  const handleShare = useCallback(async () => {
    const url = window.location.href
    try {
      await navigator.clipboard.writeText(url)
    } catch {
      window.prompt('Copy link:', url)
    }
  }, [])

  const toggleBookmark = useCallback(() => {
    const next = !bookmarkLocal
    setBookmarkLocal(next)
    try {
      localStorage.setItem(`vf_bm_${agent.id}`, next ? '1' : '0')
    } catch {
      /* ignore */
    }
  }, [agent.id, bookmarkLocal])

  const promptText = (agent.prompt ?? agent.description).trim()
  const genreTags = genreLabelsForAgent(agent.genres)
  const tags = genreTags.length > 0 ? genreTags : (agent.tags ?? [])
  const updatedIso = agent.updatedAt ?? agent.createdAt
  const rating = agent.ratingLabel ?? '—'
  const chatHref = `/chat?agent=${encodeURIComponent(agent.id)}`

  return (
    <section className="ad-agent-detail" aria-labelledby="agent-detail-heading">
      <div className="ad-agent-detail__toolbar">
        <Link to="/menu" className="ad-agent-detail__back">
          ← Back to models
        </Link>
      </div>

      <div className="ad-agent-detail__hero">
        <div className="ad-agent-detail__hero-media">
          <img src={agent.coverImageUrl} alt="" loading="lazy" width={1200} height={520} />
          <div className="ad-agent-detail__hero-scrim" aria-hidden />
          <h1 id="agent-detail-heading" className="ad-agent-detail__hero-title">
            {agent.botName}
          </h1>
        </div>
      </div>

      <div className="ad-agent-detail__action-strip">
        <div className="ad-agent-detail__engage">
          <button
            type="button"
            className={`ad-agent-detail__engage-btn${stats?.liked_by_me ? ' ad-agent-detail__engage-btn--active' : ''}`}
            onClick={() => void handleLike()}
            aria-pressed={stats?.liked_by_me ?? false}
            aria-label="Like"
          >
            <IconThumbUp className="ad-agent-detail__engage-icon" />
            <span>{formatShortCount(stats?.likes ?? 0)}</span>
          </button>
          <button
            type="button"
            className={`ad-agent-detail__engage-btn${bookmarkLocal ? ' ad-agent-detail__engage-btn--active' : ''}`}
            onClick={toggleBookmark}
            aria-label="Bookmark"
            aria-pressed={bookmarkLocal}
          >
            <IconBookmark className="ad-agent-detail__engage-icon" />
          </button>
          <button type="button" className="ad-agent-detail__engage-btn" onClick={() => void handleShare()} aria-label="Share link">
            <IconShare className="ad-agent-detail__engage-icon" />
          </button>
          <div className="ad-agent-detail__more-wrap" ref={moreWrapRef}>
            <button
              type="button"
              className="ad-agent-detail__engage-btn"
              aria-expanded={moreOpen}
              aria-haspopup="menu"
              aria-label="More"
              onClick={(e) => {
                e.stopPropagation()
                setMoreOpen((o) => !o)
              }}
            >
              <span className="ad-agent-detail__engage-more" aria-hidden>
                ···
              </span>
            </button>
            {moreOpen && (
              <div className="ad-agent-detail__more-menu" role="menu">
                <button type="button" className="ad-agent-detail__more-item" role="menuitem" onClick={() => setMoreOpen(false)}>
                  Report (coming soon)
                </button>
              </div>
            )}
          </div>
        </div>
        <Link to={chatHref} className="ad-agent-detail__play">
          <IconPlay className="ad-agent-detail__play-icon" />
          <span>Play</span>
        </Link>
      </div>

      <div className="ad-agent-detail__tabs" role="tablist" aria-label="Agent sections">
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'details'}
          className={`ad-agent-detail__tab${tab === 'details' ? ' ad-agent-detail__tab--active' : ''}`}
          onClick={() => setTab('details')}
        >
          Details
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === 'comments'}
          className={`ad-agent-detail__tab${tab === 'comments' ? ' ad-agent-detail__tab--active' : ''}`}
          onClick={() => setTab('comments')}
        >
          Comments <span className="ad-agent-detail__tab-count">0</span>
        </button>
      </div>

      {tab === 'details' && (
        <div className="ad-agent-detail__layout">
          <div className="ad-agent-detail__main">
            <p className="ad-agent-detail__eyebrow">
              <span className="ad-agent-detail__eyebrow-icon" aria-hidden>
                🔥
              </span>
              <span className="ad-agent-detail__eyebrow-name">{agent.authorName}</span>
              <span className="ad-agent-detail__eyebrow-chev" aria-hidden>
                ›
              </span>
            </p>

            <p className="ad-agent-detail__desc">{agent.description}</p>

            {tags.length > 0 && (
              <ul className="ad-agent-detail__tags">
                {tags.map((t, i) => (
                  <li key={`${t}-${i}`}>
                    <span className="ad-agent-detail__tag">#{t}</span>
                  </li>
                ))}
              </ul>
            )}

            <div className="ad-agent-detail__prompt">
              <p className="ad-agent-detail__prompt-label">Prompt</p>
              <p className="ad-agent-detail__prompt-body">{promptText}</p>
            </div>
          </div>

          <aside className="ad-agent-detail__meta" aria-label="Stats">
            <ul className="ad-agent-detail__meta-list">
              <li className="ad-agent-detail__meta-row">
                <span className="ad-agent-detail__meta-icon" aria-hidden>
                  ▶
                </span>
                <div>
                  <span className="ad-agent-detail__meta-label">Plays</span>
                  <span className="ad-agent-detail__meta-value">{formatShortCount(stats?.plays ?? 0)}</span>
                </div>
              </li>
              <li className="ad-agent-detail__meta-row">
                <span className="ad-agent-detail__meta-icon" aria-hidden>
                  👍
                </span>
                <div>
                  <span className="ad-agent-detail__meta-label">Likes</span>
                  <span className="ad-agent-detail__meta-value">{formatShortCount(stats?.likes ?? 0)}</span>
                </div>
              </li>
              <li className="ad-agent-detail__meta-row">
                <span className="ad-agent-detail__meta-icon" aria-hidden>
                  ✦
                </span>
                <div>
                  <span className="ad-agent-detail__meta-label">Model created</span>
                  <span className="ad-agent-detail__meta-value">{formatTimeAgo(agent.createdAt)}</span>
                </div>
              </li>
              <li className="ad-agent-detail__meta-row">
                <span className="ad-agent-detail__meta-icon" aria-hidden>
                  ↻
                </span>
                <div>
                  <span className="ad-agent-detail__meta-label">Last catalog update</span>
                  <span className="ad-agent-detail__meta-value">{formatTimeAgo(updatedIso)}</span>
                </div>
              </li>
              <li className="ad-agent-detail__meta-row">
                <span className="ad-agent-detail__meta-icon" aria-hidden>
                  ⚠
                </span>
                <div>
                  <span className="ad-agent-detail__meta-label">Rating</span>
                  <span className="ad-agent-detail__meta-value">{rating}</span>
                </div>
              </li>
            </ul>
            <p className="ad-agent-detail__meta-foot">
              Dates follow this app’s catalog (Pally). Plays and likes update from the server when available.
            </p>
          </aside>
        </div>
      )}

      {tab === 'comments' && (
        <p className="ad-agent-detail__placeholder">No comments yet.</p>
      )}
    </section>
  )
}
