/**
 * Writes frontend/src/data/changelog.json from `git log`.
 * Run from repo root: node scripts/generate-changelog.mjs
 */
import { execSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const repoRoot = join(__dirname, '..')
const outPath = join(repoRoot, 'frontend', 'src', 'data', 'changelog.json')

/**
 * Changelog-style categories (Keep a Changelog / conventional commits–friendly).
 * Order: hotpatch first (urgent fixes), then typed commits, then keyword fallbacks, then "update".
 *
 * @param {string} subject
 * @returns {'release'|'hotpatch'|'feature'|'fix'|'docs'|'chore'|'update'}
 */
function inferKind(subject) {
  const raw = (subject || '').trim()
  if (!raw) return 'update'

  const lower = raw.toLowerCase()

  /** @type {RegExp} — feat(scope)!: or feat: (space after : optional) */
  const conv = /^(\w+)(?:\([^)]*\))?!?:\s*/.exec(raw)
  const ctype = conv ? conv[1].toLowerCase() : null

  // Git / tooling convention
  if (ctype === 'hotfix') return 'hotpatch'

  // Body-line keywords (hotpatch before everything else)
  if (
    /\bhotfix\b/i.test(raw) ||
    /\bhot[\s-]?patch\b/i.test(raw) ||
    /\bhotpatch\b/i.test(raw) ||
    /\burgent[\s-]?(fix|patch)\b/i.test(lower) ||
    /\bcritical[\s-]?(hot)?fix\b/i.test(lower) ||
    /\[\s*hotpatch\s*\]/i.test(raw)
  ) {
    return 'hotpatch'
  }

  // Conventional commit types
  if (ctype === 'feat' || ctype === 'feature') return 'feature'
  if (ctype === 'fix' || ctype === 'bugfix') return 'fix'
  if (ctype === 'docs') return 'docs'
  if (
    ctype === 'chore' ||
    ctype === 'ci' ||
    ctype === 'build' ||
    ctype === 'refactor' ||
    ctype === 'style' ||
    ctype === 'test' ||
    ctype === 'perf'
  ) {
    return 'chore'
  }
  if (ctype === 'revert') return 'fix'

  // Release / version lines (semver, tagged drops)
  if (/^\[?\s*v?\d+\.\d+(\.\d+)?(-[\w.]+)?\s*\]?(\s|$)/.test(raw)) return 'release'
  if (/^release(\s+v?\d|\s*[:=]|\s+notes?\b)/i.test(raw)) return 'release'
  if (/^version\s+v?\d+\.\d+/i.test(raw)) return 'release'
  if (/\bchangelog\b/i.test(lower) && /\b(release|version)\b/i.test(lower)) return 'release'

  // Non-conventional fallbacks (title-style)
  if (/^(feat|feature|add(ing)?|implement|introduce)\b/i.test(lower)) return 'feature'
  if (/^(fix|fixes|fixed|resolve[sd]?|correct(ing)?)\b/i.test(lower)) return 'fix'
  if (/^(docs?|readme|document(ation)?)\b/i.test(lower)) return 'docs'
  if (/^(chore|ci|build|refactor|bump|deps?)\b/i.test(lower)) return 'chore'

  // Keywords anywhere in the line (still reads like a changelog line)
  if (/\breadme\b|\bdocumentation\b|\bmarkdown\b|\bwiki\b/i.test(lower)) return 'docs'
  if (/\bconsolidat(e|ion)\b|\bmilestone\b|\bphase\s+\d+/i.test(lower)) return 'release'

  return 'update'
}

function main() {
  mkdirSync(dirname(outPath), { recursive: true })

  let raw = ''
  try {
    raw = execSync(
      'git log -n 500 --reverse --pretty=format:%H%x1f%h%x1f%aI%x1f%s%x1e',
      { cwd: repoRoot, encoding: 'utf8', maxBuffer: 50 * 1024 * 1024 }
    )
  } catch (e) {
    const err = e instanceof Error ? e.message : String(e)
    console.warn('generate-changelog: git log failed —', err)
    writeFileSync(
      outPath,
      JSON.stringify({ generatedAt: new Date().toISOString(), entries: [] }, null, 2) + '\n'
    )
    return
  }

  const chunks = raw.split('\x1e').filter((c) => c.trim())
  const entries = chunks.map((chunk, idx) => {
    const parts = chunk.split('\x1f').map((p) => p.trim())
    const [hash, short, date, subject] = parts
    const id = idx + 1
    return {
      id,
      hash: hash || '',
      short: short || '',
      date: date || '',
      subject: subject || '',
      kind: inferKind(subject || ''),
    }
  })

  const payload = {
    generatedAt: new Date().toISOString(),
    entries,
  }
  writeFileSync(outPath, JSON.stringify(payload, null, 2) + '\n')
  console.log(`generate-changelog: wrote ${entries.length} entries → ${outPath}`)
}

main()
