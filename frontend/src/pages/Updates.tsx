import { useEffect } from 'react'
import { useLocation } from 'react-router-dom'
import LandingTopbar from '../components/LandingTopbar'
import changelog from '../data/changelog.json'

type ChangelogKind = 'release' | 'hotpatch' | 'feature' | 'fix' | 'docs' | 'chore' | 'update'

type ChangelogEntry = {
  id: number
  hash: string
  short: string
  date: string
  subject: string
  kind: string
}

const data = changelog as { generatedAt: string; entries: ChangelogEntry[] }

function normalizeKind(raw: string): ChangelogKind {
  if (raw === 'version') return 'release'
  if (raw === 'commit') return 'update'
  switch (raw) {
    case 'release':
    case 'hotpatch':
    case 'feature':
    case 'fix':
    case 'docs':
    case 'chore':
    case 'update':
      return raw
    default:
      return 'update'
  }
}

function kindLabel(kind: ChangelogKind): string {
  switch (kind) {
    case 'release':
      return 'RELEASE'
    case 'hotpatch':
      return 'HOTPATCH'
    case 'feature':
      return 'FEATURE'
    case 'fix':
      return 'FIX'
    case 'docs':
      return 'DOCS'
    case 'chore':
      return 'CHORE'
    default:
      return 'UPDATE'
  }
}

function formatDate(iso: string): string {
  try {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return iso
    return new Intl.DateTimeFormat('en-US', {
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(d)
  } catch {
    return iso
  }
}

export default function Updates() {
  const { hash } = useLocation()
  const ordered = [...data.entries].reverse()

  useEffect(() => {
    if (!hash || hash.length < 2) return
    const id = hash.replace(/^#/, '')
    if (!/^changelog-\d+$/.test(id)) return
    const t = window.requestAnimationFrame(() => {
      const el = document.getElementById(id)
      if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
    })
    return () => window.cancelAnimationFrame(t)
  }, [hash])

  return (
    <div className="aid-root aid-contact-root aid-updates-root" id="top">
      <LandingTopbar />

      <main className="aid-updates-main">
        <h1 className="aid-contact-headline">
          <span className="aid-contact-headline-pale">UP</span>
          <span className="aid-contact-headline-yellow">DATES</span>
        </h1>
        <p className="aid-contact-tagline">CHANGELOG</p>
        <p className="aid-updates-meta">
          {data.entries.length > 0
            ? `ID #1 — #${data.entries.length} · updated ${new Date(data.generatedAt).toLocaleString('en-US')}`
            : 'No data yet — run npm run changelog in the frontend folder'}
        </p>

        <div className="aid-updates-scroll" role="region" aria-label="Changelog">
          <ul className="aid-updates-list">
            {ordered.map((e) => {
              const kind = normalizeKind(e.kind)
              return (
                <li key={`${e.id}-${e.short}`} id={`changelog-${e.id}`} className="aid-updates-item">
                  <div className="aid-updates-item-head">
                    <span className={`aid-updates-kind aid-updates-kind--${kind}`}>{kindLabel(kind)}</span>
                    <span className="aid-updates-id">#{e.id}</span>
                  </div>
                  <p className="aid-updates-subject">{e.subject}</p>
                  <div className="aid-updates-foot">
                    <time className="aid-updates-time" dateTime={e.date}>
                      {formatDate(e.date)}
                    </time>
                    <code className="aid-updates-hash">{e.short}</code>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>
      </main>
    </div>
  )
}
