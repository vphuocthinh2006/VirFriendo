import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../services/api'
import type { DeployedAgent } from '../data/deployedAgents'
import { DEPLOYED_AGENTS } from '../data/deployedAgents'
import { LANDING_UPDATES } from '../landingRoutes'
import MenuAgentFilterBar from './MenuAgentFilterBar'

function formatShortCount(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(n % 1000 === 0 ? 0 : 1)}k`
  return String(n)
}

function formatListedDate(iso: string): string {
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return new Intl.DateTimeFormat('en-US', { dateStyle: 'medium' }).format(d)
  } catch {
    return iso
  }
}

function IconThumbUp({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" aria-hidden>
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

function IconPlay({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 5v14l11-7-11-7z" />
    </svg>
  )
}

function IconChat({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"
      />
    </svg>
  )
}

function IconSparkSection({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M12 2l1.2 4.2L17 8l-3.8 1.8L12 14l-1.2-4.2L7 8l3.8-1.8L12 2zM5 13l.8 2.8L9 17l-2.5 1.2L5 21l-.8-2.8L2 17l2.5-1.2L5 13zm14 0l.8 2.8L23 17l-2.5 1.2L18 21l-.8-2.8L15 17l2.5-1.2L19 13z" />
    </svg>
  )
}

type Props = {
  /** AI Dungeon–style cards + section (use on /menu) */
  variant?: 'bg3' | 'aidungeon'
}

function agentMatchesGenre(agent: DeployedAgent, genreId: string): boolean {
  if (genreId === 'all') return true
  const g = agent.genres ?? []
  return g.includes(genreId)
}

function timeCutoffMs(range: 'all' | 'week' | 'month' | 'year'): number | null {
  if (range === 'all') return null
  const now = Date.now()
  if (range === 'week') return now - 7 * 86400000
  if (range === 'month') return now - 30 * 86400000
  return now - 365 * 86400000
}

export default function DeployedAiGrid({ variant = 'bg3' }: Props) {
  const sectionRef = useRef<HTMLElement>(null)
  const [visible, setVisible] = useState(false)
  const [statsByAgent, setStatsByAgent] = useState<Record<string, api.AgentStatsResponse>>({})
  const [genreId, setGenreId] = useState('all')
  const [sortBy, setSortBy] = useState<'trending' | 'newest'>('trending')
  const [timeRange, setTimeRange] = useState<'all' | 'week' | 'month' | 'year'>('all')
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')

  const refreshStats = useCallback(async () => {
    const next: Record<string, api.AgentStatsResponse> = {}
    await Promise.all(
      DEPLOYED_AGENTS.map(async (a) => {
        try {
          next[a.id] = await api.getAgentStats(a.id)
        } catch {
          /* offline / API down */
        }
      }),
    )
    setStatsByAgent((prev) => ({ ...prev, ...next }))
  }, [])

  useEffect(() => {
    void refreshStats()
    const id = window.setInterval(() => void refreshStats(), 8000)
    return () => window.clearInterval(id)
  }, [refreshStats])

  const handleLike = useCallback(async (agentId: string) => {
    if (!api.isAuthenticated()) {
      window.alert('Sign in to like')
      return
    }
    try {
      const s = await api.toggleAgentLike(agentId)
      setStatsByAgent((prev) => ({ ...prev, [agentId]: s }))
    } catch (e) {
      window.alert(e instanceof Error ? e.message : 'Could not update like')
    }
  }, [])

  useEffect(() => {
    const el = sectionRef.current
    if (!el) return
    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry) return
        setVisible(entry.isIntersecting && entry.intersectionRatio >= 0.08)
      },
      { root: null, rootMargin: '0px 0px -8% 0px', threshold: [0, 0.08, 0.15, 0.3] },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])

  const filteredAgents = useMemo(() => {
    let list = DEPLOYED_AGENTS.filter((a) => agentMatchesGenre(a, genreId))
    const cutoff = timeCutoffMs(timeRange)
    if (cutoff !== null) {
      list = list.filter((a) => new Date(a.createdAt).getTime() >= cutoff)
    }
    list = [...list].sort((a, b) => {
      if (sortBy === 'trending') {
        return (statsByAgent[b.id]?.plays ?? 0) - (statsByAgent[a.id]?.plays ?? 0)
      }
      return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    })
    return list
  }, [genreId, timeRange, sortBy, statsByAgent])

  const shell =
    variant === 'aidungeon'
      ? {
          section: `ad-deployed${visible ? ' ad-deployed--visible' : ''}`,
          inner: 'ad-deployed__inner',
          heading: 'ad-deployed__title',
          headingIcon: 'ad-deployed__title-icon',
          headingText: 'ad-deployed__title-text',
          grid: 'ad-deployed__grid',
          card: 'ad-card',
          head: 'ad-card__head',
          avatar: 'ad-card__avatar',
          authorBlock: 'ad-card__author-meta',
          authorRow: 'ad-card__author-row',
          authorName: 'ad-card__author-name',
          badge: 'ad-card__badge',
          date: 'ad-card__date',
          menu: 'ad-card__menu',
          media: 'ad-card__media',
          body: 'ad-card__body',
          title: 'ad-card__bot-title',
          desc: 'ad-card__desc',
          foot: 'ad-card__foot',
          stats: 'ad-card__stats',
          stat: 'ad-card__stat',
          statIcon: 'ad-card__stat-icon',
          chat: 'ad-card__chat',
          chatIcon: 'ad-card__chat-icon',
          hint: 'ad-deployed__hint',
          hintLink: 'ad-deployed__hint-link',
        }
      : {
          section: `aid-deployed${visible ? ' aid-deployed--visible' : ''}`,
          inner: 'aid-deployed-inner',
          heading: 'aid-deployed-heading',
          headingIcon: 'aid-deployed-heading-icon',
          headingText: 'aid-deployed-heading-text',
          grid: 'aid-deployed-grid',
          card: 'aid-ai-card',
          head: 'aid-ai-card__head',
          avatar: 'aid-ai-card__author-avatar',
          authorBlock: 'aid-ai-card__author-block',
          authorRow: 'aid-ai-card__author-row',
          authorName: 'aid-ai-card__author-name',
          badge: 'aid-ai-card__author-badge',
          date: 'aid-ai-card__date',
          menu: 'aid-ai-card__menu',
          media: 'aid-ai-card__media',
          body: 'aid-ai-card__body',
          title: 'aid-ai-card__title',
          desc: 'aid-ai-card__desc',
          foot: 'aid-ai-card__foot',
          stats: 'aid-ai-card__stats',
          stat: 'aid-ai-card__stat',
          statIcon: 'aid-ai-card__stat-icon',
          chat: 'aid-ai-card__chat',
          chatIcon: 'aid-ai-card__chat-icon',
          hint: 'aid-deployed-hint',
          hintLink: 'aid-deployed-hint-link',
        }

  return (
    <section
      ref={sectionRef}
      id="deployed-ai"
      className={shell.section}
      aria-labelledby="deployed-ai-heading"
    >
      <div className={shell.inner}>
        <h2 id="deployed-ai-heading" className={shell.heading}>
          <IconSparkSection className={shell.headingIcon} />
          <span className={shell.headingText}>Our currently deployed AI right now</span>
        </h2>

        {variant === 'aidungeon' && (
          <MenuAgentFilterBar
            genreId={genreId}
            onGenreChange={setGenreId}
            sortBy={sortBy}
            onSortChange={setSortBy}
            timeRange={timeRange}
            onTimeRangeChange={setTimeRange}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
          />
        )}

        <div
          className={`${shell.grid}${variant === 'aidungeon' && viewMode === 'list' ? ' ad-deployed__grid--list' : ''}`}
          role="list"
        >
          {filteredAgents.length === 0 && (
            <p className="ad-deployed__empty" role="status">
              No models match these filters.
            </p>
          )}
          {filteredAgents.map((agent) => {
            const st = statsByAgent[agent.id]
            return (
            <article key={agent.id} className={shell.card} role="listitem">
              <Link
                to={`/menu?agent=${encodeURIComponent(agent.id)}`}
                className={variant === 'aidungeon' ? 'ad-card__main-link' : 'aid-ai-card__main-link'}
              >
                <header className={shell.head}>
                  <img
                    className={shell.avatar}
                    src={agent.authorAvatarUrl}
                    alt=""
                    width={40}
                    height={40}
                    loading="lazy"
                  />
                  <div className={shell.authorBlock}>
                    <div className={shell.authorRow}>
                      <span className={shell.authorName}>{agent.authorName}</span>
                      <span className={shell.badge} aria-hidden title="Creator">
                        ◆
                      </span>
                    </div>
                    <time className={shell.date} dateTime={agent.createdAt}>
                      {formatListedDate(agent.createdAt)}
                    </time>
                  </div>
                  <span className={shell.menu} aria-hidden>
                    ⋯
                  </span>
                </header>

                <div className={shell.media}>
                  <img src={agent.coverImageUrl} alt="" loading="lazy" width={800} height={450} />
                </div>

                <div className={shell.body}>
                  <h3 className={shell.title}>{agent.botName}</h3>
                  <p className={shell.desc}>{agent.description}</p>
                </div>
              </Link>

              <footer className={shell.foot}>
                <div className={shell.stats} aria-label="Engagement">
                  <button
                    type="button"
                    className={`${shell.stat} ${variant === 'aidungeon' ? 'ad-card__like-btn' : 'aid-ai-card__like-btn'}${st?.liked_by_me ? ' is-liked' : ''}`}
                    onClick={() => void handleLike(agent.id)}
                    aria-pressed={st?.liked_by_me ?? false}
                    aria-label="Like"
                  >
                    <IconThumbUp className={shell.statIcon} />
                    <span>{formatShortCount(st?.likes ?? 0)}</span>
                  </button>
                  <span className={shell.stat}>
                    <IconPlay className={shell.statIcon} />
                    <span>{formatShortCount(st?.plays ?? 0)}</span>
                  </span>
                </div>
                <Link to={`/chat?agent=${encodeURIComponent(agent.id)}`} className={shell.chat}>
                  <IconChat className={shell.chatIcon} />
                  <span>Chat</span>
                </Link>
              </footer>
            </article>
            )
          })}
        </div>

        <p className={shell.hint}>
          Want yours listed here? Ship a fine-tuned model and we will wire it to this roster — see{' '}
          <Link to={LANDING_UPDATES} className={shell.hintLink}>
            Updates
          </Link>
          .
        </p>
      </div>
    </section>
  )
}
