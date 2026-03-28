import { useEffect, useRef, useState } from 'react'
import { MENU_GENRE_PILLS } from '../data/agentGenres'

type SortKey = 'trending' | 'newest'
type TimeKey = 'all' | 'week' | 'month' | 'year'

type Props = {
  genreId: string
  onGenreChange: (id: string) => void
  sortBy: SortKey
  onSortChange: (v: SortKey) => void
  timeRange: TimeKey
  onTimeRangeChange: (v: TimeKey) => void
  viewMode: 'grid' | 'list'
  onViewModeChange: (v: 'grid' | 'list') => void
}

function IconBook({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"
      />
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"
      />
      <path strokeLinecap="round" d="M12 6h4" />
    </svg>
  )
}

function IconSliders({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" aria-hidden>
      <path strokeLinecap="round" d="M4 21v-7" />
      <path strokeLinecap="round" d="M4 10V3" />
      <path strokeLinecap="round" d="M12 21v-9" />
      <path strokeLinecap="round" d="M12 8V3" />
      <path strokeLinecap="round" d="M20 21v-5" />
      <path strokeLinecap="round" d="M20 12V3" />
      <path strokeLinecap="round" d="M2 14h4" />
      <path strokeLinecap="round" d="M10 8h4" />
      <path strokeLinecap="round" d="M18 16h4" />
    </svg>
  )
}

function IconGrid({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M3 3h8v8H3V3zm10 0h8v8h-8V3zM3 13h8v8H3v-8zm10 0h8v8h-8v-8z" />
    </svg>
  )
}

function IconList({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
      <path d="M4 6h16v2H4V6zm0 5h16v2H4v-2zm0 5h16v2H4v-2z" />
    </svg>
  )
}

export default function MenuAgentFilterBar({
  genreId,
  onGenreChange,
  sortBy,
  onSortChange,
  timeRange,
  onTimeRangeChange,
  viewMode,
  onViewModeChange,
}: Props) {
  const [filtersOpen, setFiltersOpen] = useState(false)
  const filtersRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!filtersOpen) return
    const close = (e: MouseEvent) => {
      if (filtersRef.current && !filtersRef.current.contains(e.target as Node)) setFiltersOpen(false)
    }
    document.addEventListener('click', close)
    return () => document.removeEventListener('click', close)
  }, [filtersOpen])

  return (
    <div className="ad-menu-filters" aria-label="Browse AI by genre">
      <div className="ad-menu-filters__pills">
        {MENU_GENRE_PILLS.map((pill) => {
          const active = genreId === pill.id
          return (
            <button
              key={pill.id}
              type="button"
              className={`ad-menu-filters__pill${active ? ' ad-menu-filters__pill--active' : ''}`}
              onClick={() => onGenreChange(pill.id)}
              aria-pressed={active}
            >
              {'icon' in pill && pill.icon === 'book' ? (
                <IconBook className="ad-menu-filters__pill-icon" />
              ) : null}
              <span>{pill.label}</span>
            </button>
          )
        })}
      </div>

      <div className="ad-menu-filters__row2">
        <div className="ad-menu-filters__selects">
          <label className="ad-menu-filters__select-wrap">
            <span className="ad-menu-filters__sr-only">Sort by</span>
            <select
              className="ad-menu-filters__select"
              value={sortBy}
              onChange={(e) => onSortChange(e.target.value as SortKey)}
              aria-label="Sort by"
            >
              <option value="trending">Trending</option>
              <option value="newest">Newest</option>
            </select>
          </label>

          <label className="ad-menu-filters__select-wrap">
            <span className="ad-menu-filters__sr-only">Time range</span>
            <select
              className="ad-menu-filters__select"
              value={timeRange}
              onChange={(e) => onTimeRangeChange(e.target.value as TimeKey)}
              aria-label="Time range"
            >
              <option value="all">All time</option>
              <option value="year">Past year</option>
              <option value="month">Past month</option>
              <option value="week">Past week</option>
            </select>
          </label>

          <div className="ad-menu-filters__filters-wrap" ref={filtersRef}>
            <button
              type="button"
              className={`ad-menu-filters__filters-btn${filtersOpen ? ' ad-menu-filters__filters-btn--open' : ''}`}
              aria-expanded={filtersOpen}
              onClick={(e) => {
                e.stopPropagation()
                setFiltersOpen((o) => !o)
              }}
            >
              <IconSliders className="ad-menu-filters__filters-icon" />
              <span>Filters</span>
              <span className="ad-menu-filters__chev" aria-hidden>
                ▾
              </span>
            </button>
            {filtersOpen && (
              <div className="ad-menu-filters__popover" role="dialog" aria-label="Extra filters">
                <p className="ad-menu-filters__popover-hint">
                  More filters (tags, safety, length) can plug in here later.
                </p>
              </div>
            )}
          </div>
        </div>

        <div className="ad-menu-filters__view" role="group" aria-label="View layout">
          <button
            type="button"
            className={`ad-menu-filters__view-btn${viewMode === 'grid' ? ' ad-menu-filters__view-btn--active' : ''}`}
            onClick={() => onViewModeChange('grid')}
            aria-pressed={viewMode === 'grid'}
            aria-label="Grid view"
          >
            <IconGrid className="ad-menu-filters__view-icon" />
          </button>
          <button
            type="button"
            className={`ad-menu-filters__view-btn${viewMode === 'list' ? ' ad-menu-filters__view-btn--active' : ''}`}
            onClick={() => onViewModeChange('list')}
            aria-pressed={viewMode === 'list'}
            aria-label="List view"
          >
            <IconList className="ad-menu-filters__view-icon" />
          </button>
        </div>
      </div>
    </div>
  )
}
