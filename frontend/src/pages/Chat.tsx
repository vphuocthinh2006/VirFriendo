import { useState, useRef, useEffect, useLayoutEffect, useCallback, useMemo } from 'react'
import ConnectingVirFriendo from '../components/ConnectingVirFriendo'
import ChatEntryGate from '../components/ChatEntryGate'
import ChatRabbitWait from '../components/ChatRabbitWait'
import AppTopbar from '../components/AppTopbar'
import { ChatMarkdown } from '../components/ChatMarkdown'
import { useNavigate, useSearchParams, Navigate } from 'react-router-dom'
import { DEPLOYED_AGENTS } from '../data/deployedAgents'
import { useAuth } from '../hooks/useAuth'
import * as api from '../services/api'
import type { MessageItem } from '../types/chat'
import type { ConversationSummary } from '../types/chat'
import AncientRtsGame from '../games/ancientRts/AncientRtsGame'

const CHARACTER_NAME = 'tuq27'
const CHARACTER_SUBTITLE = 'ur dearest friend'
const GAME_OPTIONS = ['Chess', 'Caro', 'Story choice mini game', 'Ancient RTS'] as const
type GameOption = (typeof GAME_OPTIONS)[number]

const GAME_GRID_ITEMS: readonly {
  option: GameOption
  label: string
  art: 'chess' | 'caro' | 'story' | 'zeroad'
}[] = [
  { option: 'Chess', label: 'CHESS', art: 'chess' },
  { option: 'Caro', label: 'CARO', art: 'caro' },
  { option: 'Story choice mini game', label: 'STORY CHOICE', art: 'story' },
  { option: 'Ancient RTS', label: 'ANCIENT RTS', art: 'zeroad' },
]

/** `game` query param (chat entry gate) → tab Game option */
const GATE_GAME_ID_TO_OPTION: Record<string, GameOption> = {
  chess: 'Chess',
  caro: 'Caro',
  story: 'Story choice mini game',
  zeroad: 'Ancient RTS',
}

/** Bot ELO range in the UI — fixed 350–1250 (matches backend). */
const CHESS_ELO_MIN = 350
const CHESS_ELO_MAX = 1250

type ChessBotTier = 'adaptive' | 'beginner' | 'intermediate' | 'advanced'

const CHESS_TIER_ELO: Record<ChessBotTier, number> = {
  adaptive: 900,
  beginner: 450,
  intermediate: 800,
  advanced: 1150,
}

const CHESS_TIER_ORDER: ChessBotTier[] = ['adaptive', 'beginner', 'intermediate', 'advanced']

const CHESS_TIER_META: Record<ChessBotTier, { title: string; hint: string }> = {
  adaptive: {
    title: 'Adaptive',
    hint: 'Tries to match your pace when you play sharply — still within 350–1250.',
  },
  beginner: {
    title: 'Beginner',
    hint: 'Gentle opponent; good for learning the board.',
  },
  intermediate: {
    title: 'Intermediate',
    hint: 'Balanced; needs basic tactics and decent openings.',
  },
  advanced: {
    title: 'Advanced',
    hint: 'More pressure; best if you already know openings and combinations.',
  },
}

function GameHubPanel({
  onSelectGame,
  onClose,
  className = '',
}: {
  onSelectGame: (game: GameOption) => void
  onClose?: () => void
  className?: string
}) {
  return (
    <div className={`vf-game-hub ${className}`.trim()}>
      <div className="vf-game-hub__head">
        <h2 className="vf-game-hub__title">PLAY GAMES</h2>
        {onClose ? (
          <button type="button" className="vf-game-hub__close" onClick={onClose} aria-label="Close">
            ✕
          </button>
        ) : null}
      </div>
      <p className="vf-game-hub__sub">Pick a game — full play stays inside chat after you start.</p>
      <div className="vf-game-hub__grid" role="list">
        {GAME_GRID_ITEMS.map((item) => (
          <button
            key={item.option}
            type="button"
            role="listitem"
            className="vf-game-card"
            onClick={() => onSelectGame(item.option)}
          >
            <div className={`vf-game-card__art vf-game-card__art--${item.art}`} aria-hidden />
            <span className="vf-game-card__label">{item.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
const CHESS_FILES = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h'] as const
const CHESS_PIECE_TEXT: Record<string, string> = {
  K: '♔',
  Q: '♕',
  R: '♖',
  B: '♗',
  N: '♘',
  P: '♙',
  k: '♚',
  q: '♛',
  r: '♜',
  b: '♝',
  n: '♞',
  p: '♟',
}

/** Starting position — shown before Play (avoids an empty 8/8/… board). */
const CHESS_START_FEN = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'

const CHESS_PROMOTION_ORDER = ['q', 'r', 'b', 'n'] as const

const CHESS_PROMOTION_META: Record<string, { label: string; glyph: string }> = {
  q: { label: 'Queen', glyph: '♕' },
  r: { label: 'Rook', glyph: '♖' },
  b: { label: 'Bishop', glyph: '♗' },
  n: { label: 'Knight', glyph: '♘' },
}

function sortPromotionUcis(ucis: string[]): string[] {
  return [...ucis].sort(
    (a, b) =>
      CHESS_PROMOTION_ORDER.indexOf(a.slice(-1) as (typeof CHESS_PROMOTION_ORDER)[number]) -
      CHESS_PROMOTION_ORDER.indexOf(b.slice(-1) as (typeof CHESS_PROMOTION_ORDER)[number]),
  )
}

const CARO_GRID_SIZES = [3, 5, 7, 9, 11, 15] as const
type CaroGridSize = (typeof CARO_GRID_SIZES)[number]

/** Matches server: n≤3 → n in a row; larger boards → 5 in a row (capped at n). */
function caroServerDefaultK(n: number): number {
  if (n <= 3) return n
  return Math.min(5, n)
}

function caroRuleSummary(n: number, k: number): string {
  if (n <= 3) return `Win with ${k} in a row (classic).`
  return `Win with ${k} in a row — standard Caro rules.`
}

function caroRuleShort(k: number): string {
  return `${k} in a row`
}

function caroTurnLabel(turn: api.CaroStateResponse['turn']): string {
  if (turn === 'user') return 'You'
  if (turn === 'bot') return 'Opponent'
  return '—'
}

function caroStatusLabel(status: api.CaroStateResponse['status']): string {
  return status === 'finished' ? 'Finished' : 'In progress'
}

function caroResultLabel(s: api.CaroStateResponse): string {
  if (s.status !== 'finished') return '—'
  if (s.winner === 'user') return 'You win'
  if (s.winner === 'bot') return 'Opponent wins'
  if (s.winner === 'draw') return 'Draw'
  return s.result ?? '—'
}

/** Rough sentence split (punctuation / newlines) — internal use for semantic blocks. */
function splitRawSentences(text: string): string[] {
  const t = (text || '').trim()
  if (!t) return []
  const out: string[] = []
  let buf = ''
  for (let i = 0; i < t.length; i += 1) {
    const ch = t[i]
    buf += ch
    if (/[.!?…]/.test(ch)) {
      const next = t[i + 1]
      if (next === undefined || /\s/.test(next) || next === '\n') {
        const trimmed = buf.trim()
        if (trimmed) out.push(trimmed)
        buf = ''
      }
    } else if (ch === '\n' && buf.replace(/\s/g, '').length > 0) {
      const trimmed = buf.trim()
      if (trimmed) out.push(trimmed)
      buf = ''
    }
  }
  const rest = buf.trim()
  if (rest) out.push(rest)
  return out.length ? out : [t]
}

const SEM_MIN_BLOCK = 100
const SEM_MAX_BLOCK = 520
/** Short paragraphs stay one block (avoid splitting every sentence). */
const PARAGRAPH_AS_ONE_MAX = 520

function normSentenceHead(s: string): string {
  return s.trim().replace(/^[\s"'«»[\]()]+/u, '').slice(0, 96)
}

/**
 * Topic shift / new-branch start. Matches English and Vietnamese discourse markers
 * (assistant text may be either language).
 */
function isTopicShiftStart(sentence: string, prevBlockLen: number): boolean {
  const h = normSentenceHead(sentence)
  if (h.length === 0) return false
  if (
    /^(tuy nhiên|ngoài ra|mặt khác|however|meanwhile|on the other hand|in contrast)\b/i.test(h)
  ) {
    return prevBlockLen >= 48
  }
  if (
    /^(còn về|về phần|về chủ đề|đối với|regarding|as for|speaking of|turning to)\b/i.test(h)
  ) {
    return prevBlockLen >= 48
  }
  if (
    /^(về|about)\s+(eren|mikasa|levi|armin|zeke|yeager|nhân vật|character)/i.test(h)
  ) {
    return prevBlockLen >= SEM_MIN_BLOCK
  }
  if (
    /^(eren|mikasa|levi|armin|zeke)\b/i.test(h) ||
    /^yeager\b/i.test(h)
  ) {
    return prevBlockLen >= SEM_MIN_BLOCK
  }
  return false
}

function mergeSentencesIntoSemanticBlocks(sentences: string[]): string[] {
  if (sentences.length === 0) return []
  const blocks: string[] = []
  let buf = ''
  for (let i = 0; i < sentences.length; i += 1) {
    const s = sentences[i]
    if (!buf) {
      buf = s
      continue
    }
    const prevLen = buf.length
    const combined = `${buf} ${s}`
    const shift = isTopicShiftStart(s, prevLen)
    const overMax = combined.length > SEM_MAX_BLOCK && prevLen >= SEM_MIN_BLOCK
    if (shift) {
      blocks.push(buf.trim())
      buf = s
    } else if (overMax) {
      blocks.push(buf.trim())
      buf = s
    } else {
      buf = combined
    }
  }
  if (buf.trim()) blocks.push(buf.trim())
  return blocks
}

/**
 * Clickable blocks: prefer paragraph breaks (\\n\\n), merge sentences in the same thread;
 * split on topic shift (connector / character name) or when a block is too long.
 */
function splitIntoSemanticBlocks(text: string): string[] {
  const t = (text || '').trim()
  if (!t) return []
  const paras = t.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean)
  if (paras.length === 0) return [t]
  const out: string[] = []
  for (const para of paras) {
    const raw = splitRawSentences(para)
    if (raw.length === 0) continue
    if (para.length <= PARAGRAPH_AS_ONE_MAX) {
      out.push(para)
      continue
    }
    const merged = mergeSentencesIntoSemanticBlocks(raw)
    out.push(...merged)
  }
  return out.length ? out : [t]
}

/** Strip legacy chunk metadata from history API. */
function normalizeHistoryForDisplay(history: MessageItem[]): MessageItem[] {
  return history.map(({ chunks: _c, visibleChunkIndex: _v, ...msg }) => msg)
}

function fenBoard(fen: string): (string | null)[][] {
  const boardPart = (fen || '').split(' ')[0] || ''
  const rows = boardPart.split('/')
  const out: (string | null)[][] = []
  for (let r = 0; r < 8; r += 1) {
    const row = rows[r] || ''
    const parsed: (string | null)[] = []
    for (const ch of row) {
      const n = Number(ch)
      if (!Number.isNaN(n)) {
        for (let i = 0; i < n; i += 1) parsed.push(null)
      } else {
        parsed.push(ch)
      }
    }
    while (parsed.length < 8) parsed.push(null)
    out.push(parsed.slice(0, 8))
  }
  while (out.length < 8) out.push(Array(8).fill(null))
  return out
}

/** Piece color by side (FEN P vs p), not by square — avoids a zebra look. */
function chessPieceSideClass(piece: string | null): string {
  if (!piece) return ''
  return /[PNBRQK]/.test(piece)
    ? 'vf-chess-piece vf-chess-piece--white-army'
    : 'vf-chess-piece vf-chess-piece--black-army'
}

/** Destination squares from selected square in UCI (e2e4 → e4, e7e8q → e8). */
function uciDestinationSquares(from: string, leg: string[]): Set<string> {
  const out = new Set<string>()
  for (const m of leg) {
    if (!m.startsWith(from) || m.length < 4) continue
    out.add(m.slice(2, 4))
  }
  return out
}

function isOpponentPiece(piece: string | null, userColor: 'white' | 'black'): boolean {
  if (!piece) return false
  if (userColor === 'white') return /[pnbrqk]/.test(piece)
  return /[PNBRQK]/.test(piece)
}

/** White view: rank 8 at top; black: flipped like chess.com (your pieces at bottom). */
function displayToFenRC(
  r: number,
  c: number,
  view: 'white' | 'black',
): [number, number] {
  if (view === 'white') return [r, c]
  return [7 - r, 7 - c]
}

function isUserPiece(piece: string | null, userColor: 'white' | 'black'): boolean {
  if (!piece) return false
  if (userColor === 'white') return /[PNBRQK]/.test(piece)
  return /[pnbrqk]/.test(piece)
}

function normalizeChessState(s: api.ChessStateResponse): api.ChessStateResponse {
  const raw = s as unknown as Record<string, unknown>
  const session_id = String(s.session_id ?? raw.sessionId ?? '')
  const turn = String(s.turn ?? raw.turn).toLowerCase() === 'black' ? 'black' : 'white'
  const user_color =
    String(s.user_color ?? raw.userColor).toLowerCase() === 'black' ? 'black' : 'white'
  const legal_moves = Array.isArray(s.legal_moves)
    ? s.legal_moves.map((m) => String(m).toLowerCase())
    : Array.isArray(raw.legalMoves)
      ? (raw.legalMoves as string[]).map((m) => String(m).toLowerCase())
      : []
  const fen = String(s.fen ?? raw.fen ?? '')
  return { ...s, session_id, turn, user_color, legal_moves, fen }
}

function squareName(row: number, col: number): string {
  const file = CHESS_FILES[col] ?? 'a'
  const rank = 8 - row
  return `${file}${rank}`
}

// Icons as components for reuse
function IconAvatar({ className = 'w-9 h-9' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <circle cx="12" cy="10" r="3" />
      <path d="M6.168 18.849A4 4 0 0 1 10 16h4a4 4 0 0 1 3.834 2.855" />
    </svg>
  )
}

function IconMic({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3Z" />
      <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
      <line x1="12" x2="12" y1="19" y2="22" />
    </svg>
  )
}

function IconSend({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d="M22 2L11 13" />
      <path d="M22 2L15 22L11 13L2 9L22 2Z" />
    </svg>
  )
}

/** Small corner icon for popup (green UI accent). */
function IconBotCorner({ className = 'w-8 h-8' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden>
      <circle cx="16" cy="16" r="14" fill="#22c55e" />
      <circle cx="16" cy="14" r="5" fill="white" opacity="0.95" />
      <circle cx="13.5" cy="13.5" r="1.1" fill="#1a1a18" />
      <circle cx="18.5" cy="13.5" r="1.1" fill="#1a1a18" />
      <path d="M12 18.5c1.2 1.4 2.8 2.2 4 2.2s2.8-.8 4-2.2" stroke="#1a1a18" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  )
}

const RELATIONSHIP_HEART_SLOTS = 5

function RelationshipHeartIcon({ filled, size = 22 }: { filled: boolean; size?: number }) {
  return (
    <svg
      className={filled ? 'vf-chat-rheart vf-chat-rheart--on' : 'vf-chat-rheart vf-chat-rheart--off'}
      viewBox="0 0 24 24"
      width={size}
      height={size}
      aria-hidden
    >
      <path
        d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.41 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.41 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
        fill={filled ? 'currentColor' : 'none'}
        stroke={filled ? 'none' : 'currentColor'}
        strokeWidth={filled ? 0 : 1.45}
        strokeLinejoin="round"
      />
    </svg>
  )
}

function heartsFilledFromLevel(level: number): number {
  return Math.min(Math.max(level, 0), RELATIONSHIP_HEART_SLOTS)
}

function memoryKindForUpdates(mtype: string): 'feature' | 'fix' | 'update' | 'docs' {
  const t = (mtype || '').toLowerCase()
  if (t.includes('goal') || t.includes('pref')) return 'feature'
  if (t.includes('fix') || t.includes('error')) return 'fix'
  if (t.includes('doc')) return 'docs'
  return 'update'
}

function memoryKindLabel(mtype: string): string {
  const t = (mtype || '').trim() || 'memory'
  return t.length > 24 ? `${t.slice(0, 24)}…` : t.toUpperCase()
}

function messagesUntilNextLevel(count: number): number {
  if (count === 0) return 1000
  const r = count % 1000
  return r === 0 ? 1000 : 1000 - r
}

export default function Chat() {
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [conversationsLoading, setConversationsLoading] = useState(true)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  /** After stream_start, wait for first token (hide composer, show rabbit). */
  const [streamingAwaiting, setStreamingAwaiting] = useState(false)
  const [error, setError] = useState('')
  const [conversationsPanelOpen, setConversationsPanelOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyMessages, setHistoryMessages] = useState<MessageItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const [gamePickerOpen, setGamePickerOpen] = useState(false)
  const [activeGame, setActiveGame] = useState<GameOption | null>(null)
  const [chessSession, setChessSession] = useState<api.ChessStateResponse | null>(null)
  const [chessBotTier, setChessBotTier] = useState<ChessBotTier>('intermediate')
  const [chessSideChoice, setChessSideChoice] = useState<'white' | 'black' | 'random'>('white')
  const [chessLoading, setChessLoading] = useState(false)
  const [chessSelectedSquare, setChessSelectedSquare] = useState<string | null>(null)
  const [chessPromotionUcis, setChessPromotionUcis] = useState<string[] | null>(null)
  const [chessReview, setChessReview] = useState<api.ChessReviewResponse | null>(null)
  const [chessBotMeta, setChessBotMeta] = useState<api.ChessBotInfo | null>(null)
  const [caroGridSize, setCaroGridSize] = useState<CaroGridSize>(5)
  const [caroStone, setCaroStone] = useState<'x' | 'o'>('x')
  const [caroSession, setCaroSession] = useState<api.CaroStateResponse | null>(null)
  const [caroLoading, setCaroLoading] = useState(false)
  const [caroReview, setCaroReview] = useState<api.CaroReviewResponse | null>(null)
  const [chatPanelTab, setChatPanelTab] = useState<'chat' | 'game' | 'memory' | 'diary' | 'relationship'>('chat')
  const [memories, setMemories] = useState<api.MemoryItem[]>([])
  const [memoriesLoading, setMemoriesLoading] = useState(false)
  const [diaryEntries, setDiaryEntries] = useState<api.DiaryEntryRow[]>([])
  const [diaryDraft, setDiaryDraft] = useState('')
  const [diarySaving, setDiarySaving] = useState(false)
  const [diaryLoading, setDiaryLoading] = useState(false)
  const [diaryError, setDiaryError] = useState('')
  const [userMessageCount, setUserMessageCount] = useState(0)
  const [relationshipLevel, setRelationshipLevel] = useState(1)
  const [funFactOpen, setFunFactOpen] = useState(false)
  const [funFactLevel, setFunFactLevel] = useState(1)
  /** Focused assistant sentence (popup) — key `msgId|idx`. */
  const [activeSentenceKey, setActiveSentenceKey] = useState<string | null>(null)
  const [sentencePopup, setSentencePopup] = useState<{ text: string } | null>(null)
  const messagesScrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (chatPanelTab !== 'game' || activeGame !== 'Chess') return
    let cancelled = false
    void (async () => {
      try {
        const meta = await api.chessBotInfo()
        if (!cancelled) setChessBotMeta(meta)
      } catch {
        if (!cancelled) setChessBotMeta(null)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [chatPanelTab, activeGame])

  useEffect(() => {
    if (!chessSession || chessSession.status === 'finished') {
      setChessSelectedSquare(null)
      setChessPromotionUcis(null)
      return
    }
    if (chessSession.turn !== chessSession.user_color) {
      setChessSelectedSquare(null)
      setChessPromotionUcis(null)
    }
  }, [chessSession?.session_id, chessSession?.turn, chessSession?.user_color, chessSession?.status])

  useEffect(() => {
    if (!chessPromotionUcis) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setChessPromotionUcis(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [chessPromotionUcis])

  const wsRef = useRef<WebSocket | null>(null)
  const streamBufRef = useRef('')
  const streamMsgIdRef = useRef<string | null>(null)
  const awaitingFirstTokenRef = useRef(false)
  const { isAuth, loading: authLoading } = useAuth()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const agentId = searchParams.get('agent')
  const entry = searchParams.get('entry')

  const agentMeta = useMemo(
    () => (agentId ? DEPLOYED_AGENTS.find((a) => a.id === agentId) : undefined),
    [agentId],
  )

  const chatSession = useMemo((): api.ChatSessionContext | null => {
    if (!agentId) return null
    const em = entry === 'quickstart' || entry === 'character' ? entry : null
    if (!em) return null
    if (em === 'quickstart') return { agent_id: agentId, entry_mode: 'quickstart' }
    const raw = sessionStorage.getItem(`vf_chat_persona_${agentId}`)
    if (!raw) return { agent_id: agentId, entry_mode: 'character' }
    try {
      const p = JSON.parse(raw) as { name: string; gender: string; persona: string }
      return {
        agent_id: agentId,
        entry_mode: 'character',
        persona: p.persona,
        character_name: p.name,
        gender: p.gender,
      }
    } catch {
      return { agent_id: agentId, entry_mode: 'character' }
    }
  }, [agentId, entry])

  const showGate = Boolean(agentId && !entry && agentMeta)

  const displayName = agentMeta?.botName ?? CHARACTER_NAME

  const descParagraphs = useMemo(() => {
    const raw = (agentMeta?.description ?? '').trim() || CHARACTER_SUBTITLE
    return raw.split(/\n\n+/).map((p) => p.trim()).filter(Boolean)
  }, [agentMeta])

  useEffect(() => {
    if (!authLoading && !isAuth) navigate('/login', { replace: true })
  }, [isAuth, authLoading, navigate])

  useEffect(() => {
    if (entry === 'character' && agentId && !sessionStorage.getItem(`vf_chat_persona_${agentId}`)) {
      setSearchParams({ agent: agentId })
    }
  }, [entry, agentId, setSearchParams])

  /** Deep link: ?entry=quickstart&tab=game&game=chess — open tab + game after gate. */
  useLayoutEffect(() => {
    if (authLoading || showGate) return
    const tab = searchParams.get('tab')
    const gameId = searchParams.get('game')
    if (!tab && !gameId) return
    const validTabs = new Set(['chat', 'game', 'memory', 'diary', 'relationship'])
    if (tab && validTabs.has(tab)) {
      setChatPanelTab(tab as 'chat' | 'game' | 'memory' | 'diary' | 'relationship')
    }
    if (gameId && GATE_GAME_ID_TO_OPTION[gameId]) {
      setActiveGame(GATE_GAME_ID_TO_OPTION[gameId])
    }
    if (tab || gameId) {
      setSearchParams(
        (prev) => {
          const p = new URLSearchParams(prev.toString())
          p.delete('tab')
          p.delete('game')
          return p
        },
        { replace: true },
      )
    }
  }, [authLoading, showGate, searchParams, setSearchParams])

  useEffect(() => {
    const agent = searchParams.get('agent')
    const ent = searchParams.get('entry')
    if (!agent || !isAuth || !ent) return
    const key = `vf_play_tracked_${agent}`
    if (sessionStorage.getItem(key)) return
    sessionStorage.setItem(key, '1')
    void api.recordAgentPlay(agent).catch(() => {
      sessionStorage.removeItem(key)
    })
  }, [searchParams, isAuth])

  useEffect(() => {
    if (!agentId || !isAuth) return
    void api
      .getAgentRelationship(agentId)
      .then((r) => {
        setUserMessageCount(r.user_message_count)
        setRelationshipLevel(r.relationship_level)
        if (r.pending_fun_fact) {
          setFunFactLevel(r.relationship_level)
          setFunFactOpen(true)
        }
      })
      .catch(() => {
        /* keep defaults */
      })
  }, [agentId, isAuth])

  useEffect(() => {
    const el = messagesScrollRef.current
    if (!el || chatPanelTab !== 'chat') return
    el.scrollTop = el.scrollHeight
  }, [messages, chatPanelTab, loading])

  useEffect(() => {
    if (chatPanelTab !== 'memory' || !isAuth) return
    setMemoriesLoading(true)
    void api
      .getMemories()
      .then((list) => setMemories(list))
      .catch(() => setMemories([]))
      .finally(() => setMemoriesLoading(false))
  }, [chatPanelTab, isAuth])

  useEffect(() => {
    if (chatPanelTab !== 'diary' || !isAuth) return
    setDiaryLoading(true)
    void api
      .getDiaryEntries(agentId)
      .then(setDiaryEntries)
      .catch(() => setDiaryEntries([]))
      .finally(() => setDiaryLoading(false))
  }, [chatPanelTab, isAuth, agentId])

  useEffect(() => {
    if (!historyOpen) return
    if (!conversationId) {
      setHistoryMessages([])
      return
    }
    setHistoryLoading(true)
    void api
      .getHistory(conversationId)
      .then((list) => setHistoryMessages((list as MessageItem[]) || []))
      .catch(() => setHistoryMessages([]))
      .finally(() => setHistoryLoading(false))
  }, [historyOpen, conversationId])

  // --- WebSocket connection management ---
  const handleWsMessage = useCallback((msg: api.WsMessage) => {
    if (msg.type === 'stream_start') {
      setConversationId(msg.conversation_id)
      streamBufRef.current = ''
      const id = crypto.randomUUID()
      streamMsgIdRef.current = id
      const placeholder: MessageItem = {
        id,
        role: 'assistant',
        content: '',
      }
      setMessages((prev) => [...prev, placeholder])
      setLoading(false)
      awaitingFirstTokenRef.current = true
      setStreamingAwaiting(true)
    } else if (msg.type === 'token') {
      if (awaitingFirstTokenRef.current) {
        awaitingFirstTokenRef.current = false
        setStreamingAwaiting(false)
      }
      streamBufRef.current += msg.content
      const text = streamBufRef.current
      const msgId = streamMsgIdRef.current
      if (msgId) {
        setMessages((prev) =>
          prev.map((m) => (m.id === msgId ? { ...m, content: text } : m))
        )
      }
    } else if (msg.type === 'stream_end') {
      const msgId = streamMsgIdRef.current
      let finalText = streamBufRef.current
      if (!finalText.trim()) {
        finalText =
          "I didn't get a reply — please try sending your message again."
        setError('Empty response (temporary). Please try again.')
      }
      if (msgId) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === msgId
              ? {
                  ...m,
                  content: finalText,
                  detected_intent: msg.detected_intent,
                  detected_emotion: msg.detected_emotion,
                  avatar_action: msg.avatar_action,
                }
              : m
          )
        )
      }
      streamMsgIdRef.current = null
      streamBufRef.current = ''
      awaitingFirstTokenRef.current = false
      setStreamingAwaiting(false)
      if (typeof msg.user_message_count === 'number') setUserMessageCount(msg.user_message_count)
      if (typeof msg.relationship_level === 'number') setRelationshipLevel(msg.relationship_level)
      if (
        msg.relationship_level_up &&
        typeof msg.new_relationship_level === 'number' &&
        msg.new_relationship_level >= 2
      ) {
        setFunFactLevel(msg.new_relationship_level)
        setFunFactOpen(true)
      }
      fetchConversations()
    } else if (msg.type === 'error') {
      setError(msg.detail)
      setLoading(false)
      awaitingFirstTokenRef.current = false
      setStreamingAwaiting(false)
    }
  }, [])

  const connectWs = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState <= WebSocket.OPEN) return
    const ws = api.createChatWs(handleWsMessage, () => {
      wsRef.current = null
    })
    wsRef.current = ws
  }, [handleWsMessage])

  useEffect(() => {
    if (isAuth) connectWs()
    return () => {
      wsRef.current?.close()
      wsRef.current = null
    }
  }, [isAuth, connectWs])

  async function fetchConversations() {
    try {
      const list = await api.getConversations() as ConversationSummary[]
      setConversations(list)
    } catch {
      setConversations([])
    } finally {
      setConversationsLoading(false)
    }
  }

  useEffect(() => {
    if (isAuth) fetchConversations()
  }, [isAuth])

  useEffect(() => {
    if (!sentencePopup) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSentencePopup(null)
        setActiveSentenceKey(null)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [sentencePopup])

  function startNewChat() {
    setConversationId(null)
    setMessages([])
    setActiveSentenceKey(null)
    setSentencePopup(null)
    setError('')
  }

  async function selectConversation(id: string) {
    if (id === conversationId) return
    setError('')
    setConversationId(id)
    setMessages([])
    setActiveSentenceKey(null)
    setSentencePopup(null)
    try {
      const history = (await api.getHistory(id)) as MessageItem[]
      const normalized = normalizeHistoryForDisplay(history)
      setMessages(normalized)
    } catch {
      setError('Could not load conversation history')
    }
  }

  function chooseGame(game: GameOption) {
    setActiveGame(game)
    setGamePickerOpen(false)
    setChatPanelTab('game')
    if (game !== 'Chess') {
      setChessSession(null)
      setChessSelectedSquare(null)
      setChessPromotionUcis(null)
      setChessReview(null)
    }
    if (game !== 'Caro') {
      setCaroSession(null)
      setCaroReview(null)
    }
  }

  async function handleChessNewGame() {
    setChessLoading(true)
    setChessReview(null)
    setChessSelectedSquare(null)
    setChessPromotionUcis(null)
    try {
      const userColor: 'white' | 'black' =
        chessSideChoice === 'random' ? (Math.random() < 0.5 ? 'white' : 'black') : chessSideChoice
      const session = normalizeChessState(await api.chessNew(userColor, CHESS_TIER_ELO[chessBotTier]))
      setChessSession(session)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start chess game')
    } finally {
      setChessLoading(false)
    }
  }

  async function handleChessMove(moveUci: string) {
    if (!chessSession) return
    setChessLoading(true)
    try {
      const updated = normalizeChessState(await api.chessMove(chessSession.session_id, moveUci))
      setChessSession(updated)
      setChessSelectedSquare(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not play that move')
    } finally {
      setChessLoading(false)
      setChessPromotionUcis(null)
    }
  }

  async function handleChessReview() {
    if (!chessSession) return
    setChessLoading(true)
    try {
      const r = await api.chessReview(chessSession.session_id)
      setChessReview(r)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load post-game review')
    } finally {
      setChessLoading(false)
    }
  }

  async function handleCaroNew() {
    setCaroLoading(true)
    setCaroReview(null)
    setError('')
    try {
      const s = await api.caroNew(caroGridSize, caroStone)
      setCaroSession(s)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start Caro game')
    } finally {
      setCaroLoading(false)
    }
  }

  async function handleCaroCell(r: number, c: number) {
    if (!caroSession || caroLoading || caroSession.status === 'finished') return
    if (caroSession.turn !== 'user') return
    if (caroSession.board[r]?.[c] != null) return
    setCaroLoading(true)
    try {
      const s = await api.caroMove(caroSession.session_id, r, c)
      setCaroSession(s)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Move failed')
    } finally {
      setCaroLoading(false)
    }
  }

  async function handleCaroReview() {
    if (!caroSession) return
    setCaroLoading(true)
    try {
      const r = await api.caroReview(caroSession.session_id)
      setCaroReview(r)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not load review')
    } finally {
      setCaroLoading(false)
    }
  }

  function onChessSquareClick(sq: string, pieceOnSq: string | null) {
    if (chessPromotionUcis) return
    if (!chessSession || chessLoading || chessSession.status === 'finished') return
    if (chessSession.turn !== chessSession.user_color) return
    const uc = chessSession.user_color
    const leg = chessSession.legal_moves
    if (chessSelectedSquare) {
      if (chessSelectedSquare === sq) {
        setChessSelectedSquare(null)
        return
      }
      const maybeMove = `${chessSelectedSquare}${sq}`
      const candidates = leg.filter((m) => m.startsWith(maybeMove))
      if (candidates.length > 0) {
        if (candidates.length > 1) {
          setChessPromotionUcis(sortPromotionUcis(candidates))
          return
        }
        void handleChessMove(candidates[0])
        return
      }
      if (isUserPiece(pieceOnSq, uc)) {
        setChessSelectedSquare(sq)
      } else {
        setChessSelectedSquare(null)
      }
      return
    }
    if (isUserPiece(pieceOnSq, uc)) {
      setChessSelectedSquare(sq)
    }
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setError('')
    awaitingFirstTokenRef.current = false
    setStreamingAwaiting(false)

    const userMsg: MessageItem = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
    }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    // Try WebSocket first, fall back to REST
    const ws = wsRef.current
    if (ws && ws.readyState === WebSocket.OPEN) {
      api.sendWsMessage(ws, text, conversationId, chatSession)
      // stream_start callback will set loading=false and create the assistant message
    } else {
      // Reconnect for next time
      connectWs()
      // Fall back to REST
      try {
        const res = (await api.sendMessage(text, conversationId, chatSession)) as import('../types/chat').ChatResponse
        setConversationId(res.conversation_id)
        if (typeof res.user_message_count === 'number') setUserMessageCount(res.user_message_count)
        if (typeof res.relationship_level === 'number') setRelationshipLevel(res.relationship_level)
        if (res.relationship_level_up && res.new_relationship_level && res.new_relationship_level >= 2) {
          setFunFactLevel(res.new_relationship_level)
          setFunFactOpen(true)
        }
        const assistantMsg: MessageItem = {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: res.reply,
          detected_intent: res.detected_intent,
          detected_emotion: res.detected_emotion,
          avatar_action: res.avatar_action,
        }
        setMessages((prev) => [...prev, assistantMsg])
        await fetchConversations()
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to send message')
      } finally {
        setLoading(false)
      }
    }
  }

  function sentenceKey(msgId: string, idx: number) {
    return `${msgId}|${idx}`
  }

  function renderAssistantNarrative(msg: MessageItem, index: number) {
    const isLast = index === messages.length - 1
    const streaming = isLast && streamMsgIdRef.current === msg.id
    const text = msg.content || ''
    const blocks = splitIntoSemanticBlocks(text)
    if (!text.trim()) {
      return streaming ? (
        <p className="vf-chat-narrative-pending">
          <span className="vf-chat-narrative-dots">…</span>
          <span className="vn-cursor-blink">▌</span>
        </p>
      ) : null
    }
    return (
      <div className="vf-chat-narrative-body">
        {blocks.map((s, i) => {
          const sk = sentenceKey(msg.id, i)
          const isActive = activeSentenceKey === sk
          return (
            <div
              key={sk}
              role="button"
              tabIndex={0}
              className={`vf-chat-narrative-block${isActive ? ' vf-chat-narrative-block--active' : ''}`}
              onClick={() => {
                setActiveSentenceKey(sk)
                setSentencePopup({ text: s })
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  setActiveSentenceKey(sk)
                  setSentencePopup({ text: s })
                }
              }}
            >
              <ChatMarkdown text={s} variant="narrative" />
            </div>
          )
        })}
        {streaming ? <span className="vn-cursor-blink vf-chat-narrative-cursor">▌</span> : null}
      </div>
    )
  }

  async function closeFunFactModal() {
    if (!agentId) {
      setFunFactOpen(false)
      return
    }
    try {
      await api.ackAgentFunFact(agentId, funFactLevel)
    } catch {
      /* still close UI */
    }
    setFunFactOpen(false)
  }

  async function saveDiary() {
    const t = diaryDraft.trim()
    if (!t) return
    setDiaryError('')
    setDiarySaving(true)
    try {
      await api.postDiaryEntry(t, agentId ?? undefined)
      setDiaryDraft('')
      const list = await api.getDiaryEntries(agentId ?? undefined)
      setDiaryEntries(list)
    } catch (e) {
      setDiaryError(e instanceof Error ? e.message : 'Could not save diary')
    } finally {
      setDiarySaving(false)
    }
  }

  if (authLoading) {
    return <ConnectingVirFriendo />
  }

  if (agentId && !agentMeta) {
    return <Navigate to="/menu" replace />
  }

  if (showGate && agentMeta) {
    return (
      <ChatEntryGate
        agentDisplayName={agentMeta.botName}
        onQuickstart={() => setSearchParams({ agent: agentId!, entry: 'quickstart' }, { replace: true })}
        onCharacterComplete={(data) => {
          sessionStorage.setItem(`vf_chat_persona_${agentId!}`, JSON.stringify(data))
          setSearchParams({ agent: agentId!, entry: 'character' }, { replace: true })
        }}
        onPickGame={(gameId) =>
          setSearchParams({ agent: agentId!, entry: 'quickstart', tab: 'game', game: gameId }, { replace: true })
        }
      />
    )
  }

  const lastBot = [...messages].reverse().find((m) => m.role === 'assistant')
  const action = (lastBot as MessageItem | undefined)?.avatar_action
  const expressionClass =
    action === 'serious_alert'
      ? 'vf-chat-model-ring--alert'
      : action === 'comfort_sit'
        ? 'vf-chat-model-ring--calm'
        : action === 'shocked_face'
          ? 'vf-chat-model-ring--shock'
          : action === 'excited_wave'
            ? 'vf-chat-model-ring--wave'
            : 'vf-chat-model-ring--idle'

  /** Composer pill only: busy while searching / first token — messages stay visible. */
  const composerBusy = chatPanelTab === 'chat' && (loading || streamingAwaiting)

  return (
    <div className="ad-shell vf-chat-shell" id="top">
      <AppTopbar />
      <div className="vf-chat-stage">
        <div className="vf-chat-body">
        <aside className="vf-chat-sidebar">
          <div className="vf-chat-sidebar-frame">
            <div className="vf-chat-sidebar-label">{displayName}</div>
            <div className="vf-chat-sidebar-bond" aria-label={`Bond level ${relationshipLevel}`}>
              <div className="vf-chat-hearts-row vf-chat-hearts-row--sidebar">
                {Array.from({ length: RELATIONSHIP_HEART_SLOTS }).map((_, i) => (
                  <RelationshipHeartIcon key={i} filled={i < heartsFilledFromLevel(relationshipLevel)} size={20} />
                ))}
              </div>
              <p className="vf-chat-sidebar-bond-level">Relationship level {relationshipLevel}</p>
              <p className="vf-chat-sidebar-bond-meta">
                {userMessageCount} messages sent · {messagesUntilNextLevel(userMessageCount)} until next level
              </p>
            </div>
            <div className="vf-chat-sidebar-primary">
              <div className={`vf-chat-panel vf-chat-panel--model ${expressionClass}`}>
                <div className="vf-chat-model-vtuber">
                  <IconAvatar className="vf-chat-model-icon" />
                </div>
                <p className="vf-chat-model-hint">VTuber slot · waist-up</p>
              </div>
              <div className="vf-chat-panel vf-chat-panel--desc">
                {descParagraphs.map((para, i) => (
                  <p key={i} className="vf-chat-desc-para">
                    {para}
                  </p>
                ))}
              </div>
            </div>
          </div>
        </aside>

        <main className="vf-chat-main">
          <nav className="vf-chat-tabs" aria-label="Chat sections">
            <div className="vf-chat-tabs-primary">
              {(['chat', 'game', 'memory', 'diary', 'relationship'] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  className={`vf-chat-tab${chatPanelTab === tab ? ' vf-chat-tab--active' : ''}`}
                  onClick={() => setChatPanelTab(tab)}
                >
                  {tab === 'chat'
                    ? 'Chat'
                    : tab === 'game'
                      ? 'Game'
                      : tab === 'memory'
                        ? 'Memory'
                        : tab === 'diary'
                          ? 'Diary'
                          : 'Relationship'}
                </button>
              ))}
            </div>
            <div className="vf-chat-tabs-actions" role="group" aria-label="Session">
              <button type="button" className="vf-chat-tab vf-chat-tab--ghost" onClick={() => setConversationsPanelOpen(true)}>
                Conversations
              </button>
              <button type="button" className="vf-chat-tab vf-chat-tab--ghost" onClick={() => setHistoryOpen(true)}>
                History
              </button>
            </div>
          </nav>

          <div className="vf-chat-pane">
            {chatPanelTab === 'chat' && (
              <>
        <div className="vf-chat-chat-inner relative flex flex-col flex-1 min-h-0 vn-stage-bg">
              <div className="absolute inset-0 vn-stage-vignette pointer-events-none" aria-hidden />
              <div ref={messagesScrollRef} className="vf-chat-messages flex-1 overflow-y-auto px-2 sm:px-4 py-3 space-y-6 min-h-0">
                {messages.map((msg, index) => {
                  if (msg.role === 'user') {
                    return (
                      <div key={msg.id} className="vf-chat-user-row">
                        <div className="vf-chat-bubble vf-chat-bubble--user vf-chat-msg-pop">
                          <div className="vf-chat-user-head">
                            <div className="vf-chat-user-avatar-wrap vf-chat-user-avatar-wrap--inline" aria-hidden>
                              <IconAvatar className="vf-chat-user-avatar-icon" />
                            </div>
                            <span className="vf-chat-bubble-who">You</span>
                          </div>
                          <div className="vf-chat-bubble-text-wrap vf-chat-user-text">
                            <div className="vf-chat-bubble-text vf-chat-bubble-text--md">
                              <ChatMarkdown text={msg.content} variant="user" />
                            </div>
                          </div>
                        </div>
                      </div>
                    )
                  }
                  return (
                    <div key={msg.id} className="vf-chat-narrative-row">
                      <div className="vf-chat-narrative-inner">{renderAssistantNarrative(msg, index)}</div>
                    </div>
                  )
                })}
              </div>

              {error && (
          <div className="flex-shrink-0 mx-auto max-w-3xl w-full px-4 pb-2 animate-vn-slide-up">
            <div className="rounded-xl bg-red-500/15 border border-red-400/40 text-red-300 text-sm px-4 py-2.5">
              {error}
            </div>
          </div>
              )}

              <div className="flex-shrink-0 border-t border-vn-dialogueBorder/50 bg-vn-dialogue/60 backdrop-blur-sm p-4">
          <div className="mx-auto max-w-3xl w-full px-2">
            {composerBusy ? (
              <div
                className="vf-chat-rabbit-only flex w-full min-h-[3rem] items-center justify-center py-2"
                aria-busy="true"
              >
                <ChatRabbitWait variant="inline" phase={loading ? 'search' : 'writing'} />
              </div>
            ) : (
              <form
                onSubmit={handleSend}
                className="flex h-12 w-full shrink-0 items-center gap-2 rounded-2xl border border-vn-dialogueBorder bg-vn-stage/80 pl-2 pr-2 shadow-vn-inner animate-vn-fade-in focus-within:ring-2 focus-within:ring-vn-nameGlow/40 focus-within:border-vn-nameGlow/50 motion-reduce:animate-none"
              >
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Type a message..."
                  className="flex-1 min-w-0 bg-transparent px-3 py-2 text-vn-text placeholder-vn-textDim outline-none rounded-2xl text-[0.9375rem] leading-snug"
                  disabled={loading || streamingAwaiting}
                />
                <button type="button" className="flex-shrink-0 p-2 rounded-xl text-vn-textDim hover:bg-white/10 hover:text-vn-text transition" title="Voice (coming soon)">
                  <IconMic className="w-5 h-5" />
                </button>
                <button type="submit" disabled={loading || !input.trim() || streamingAwaiting} className="flex-shrink-0 p-2 rounded-xl text-vn-name hover:bg-vn-nameGlow/20 disabled:opacity-40 disabled:hover:bg-transparent transition" title="Send">
                  <IconSend className="w-5 h-5" />
                </button>
              </form>
            )}
          </div>
        </div>
        </div>
              </>
            )}
            {chatPanelTab === 'game' && (
              <div className="vf-chat-subpane flex flex-col flex-1 min-h-0 overflow-auto p-3 sm:p-4 vn-stage-bg">
                {activeGame === 'Chess' ? (
                  <div className="vf-chess-play w-full max-w-6xl mx-auto">
                    <div className="vf-chess-play__toolbar flex flex-wrap items-center justify-between gap-3 mb-4 px-1">
                      <div>
                        <h2 className="text-lg font-semibold text-vn-text tracking-tight">Play Bots</h2>
                        <p className="text-xs text-vn-textDim mt-0.5">
                          Bot ELO {CHESS_ELO_MIN}–{CHESS_ELO_MAX}.
                          {chessBotMeta?.stockfish_configured ? (
                            <span className="text-emerald-300/85"> · Stockfish UCI_Elo</span>
                          ) : chessBotMeta ? (
                            <span className="text-amber-200/85"> · Set STOCKFISH_PATH on the server for accurate ELO</span>
                          ) : null}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setActiveGame(null)
                          setChessSession(null)
                          setChessSelectedSquare(null)
                          setChessPromotionUcis(null)
                          setChessReview(null)
                          setChessBotMeta(null)
                        }}
                        className="px-3 py-1.5 rounded-lg text-sm text-vn-textDim hover:text-vn-text hover:bg-white/10 transition shrink-0"
                      >
                        Exit game
                      </button>
                    </div>

                    <div className="vf-chess-play__grid grid lg:grid-cols-[minmax(260px,420px)_minmax(300px,1fr)] gap-6 items-start">
                      <div className="vf-chess-play__board-wrap relative min-w-0 rounded-xl border border-slate-700/80 bg-slate-950/55 p-3 sm:p-4 shadow-lg">
                        <div className="vf-chess-play__bar flex items-center justify-between gap-2 mb-2 px-2 rounded-lg bg-slate-900/85 py-2 border border-slate-700/60">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-lg leading-none" aria-hidden>
                              ♟
                            </span>
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-slate-100 truncate">Bot</p>
                              <p className="text-xs text-slate-400 tabular-nums">
                                ~{chessSession?.bot_elo ?? CHESS_TIER_ELO[chessBotTier]} ELO
                              </p>
                            </div>
                          </div>
                        </div>
                        <div className="w-full max-w-[min(100%,400px)] mx-auto min-w-0">
                          {(() => {
                            const board = fenBoard(chessSession?.fen ?? CHESS_START_FEN)
                            const view: 'white' | 'black' =
                              chessSession?.user_color ??
                              (chessSideChoice === 'black' ? 'black' : 'white')
                            const leg = chessSession?.legal_moves ?? []
                            const side = chessSession?.user_color ?? 'white'
                            const hintDests =
                              chessSession &&
                              chessSelectedSquare &&
                              !chessPromotionUcis &&
                              chessSession.turn === chessSession.user_color &&
                              !chessLoading
                                ? uciDestinationSquares(chessSelectedSquare, leg)
                                : new Set<string>()
                            const rankLabels =
                              view === 'white'
                                ? ([8, 7, 6, 5, 4, 3, 2, 1] as const)
                                : ([1, 2, 3, 4, 5, 6, 7, 8] as const)
                            return (
                              <div className="flex gap-1 items-stretch">
                                <div
                                  className="flex shrink-0 w-5 flex-col justify-around py-0.5 text-[10px] font-medium text-slate-500 tabular-nums text-right pr-0.5 select-none leading-none"
                                  aria-hidden
                                >
                                  {rankLabels.map((n) => (
                                    <span key={n} className="block py-[2px]">
                                      {n}
                                    </span>
                                  ))}
                                </div>
                                <div className="relative flex-1 aspect-square min-w-0 overflow-hidden rounded-md vf-chess-board-frame bg-[#3d5a2f]/55">
                                  <div className="absolute inset-0 grid grid-cols-8 grid-rows-8 gap-0">
                                    {[0, 1, 2, 3, 4, 5, 6, 7].flatMap((rDisp) =>
                                      [0, 1, 2, 3, 4, 5, 6, 7].map((cDisp) => {
                                        const [rF, cF] = displayToFenRC(rDisp, cDisp, view)
                                        const piece = board[rF]?.[cF] ?? null
                                        const sq = squareName(rF, cF)
                                        const isLight = (rF + cF) % 2 === 0
                                        const isSelected = chessSelectedSquare === sq
                                        const isHintDest =
                                          hintDests.has(sq) && chessSelectedSquare && sq !== chessSelectedSquare
                                        const showCaptureRing =
                                          isHintDest && !!piece && isOpponentPiece(piece, side)
                                        const showMoveDot = isHintDest && !piece
                                        return (
                                          <button
                                            key={sq}
                                            type="button"
                                            onClick={() => onChessSquareClick(sq, piece)}
                                            className={`vf-chess-square min-h-0 min-w-0 flex items-center justify-center text-[clamp(0.95rem,4.2vw,1.75rem)] leading-none transition cursor-pointer hover:brightness-[1.03] active:brightness-[0.98] ${
                                              isLight ? 'vf-chess-square--light' : 'vf-chess-square--dark'
                                            } ${isSelected ? 'vf-chess-selected z-[1]' : ''}`}
                                            title={sq}
                                            disabled={!chessSession || chessLoading}
                                          >
                                            {showCaptureRing ? (
                                              <span className="vf-chess-hint-capture" aria-hidden />
                                            ) : null}
                                            {showMoveDot ? <span className="vf-chess-hint-dot" aria-hidden /> : null}
                                            <span className={`relative z-[3] select-none ${chessPieceSideClass(piece)}`}>
                                              {piece ? CHESS_PIECE_TEXT[piece] : ''}
                                            </span>
                                          </button>
                                        )
                                      }),
                                    )}
                                  </div>
                                </div>
                              </div>
                            )
                          })()}
                          <div className="flex gap-1 pt-1 w-full">
                            <div className="w-5 shrink-0" aria-hidden />
                            <div className="flex flex-1 min-w-0">
                              {(
                                (chessSession?.user_color ??
                                  (chessSideChoice === 'black' ? 'black' : 'white')) === 'black'
                                  ? [...CHESS_FILES].reverse()
                                  : CHESS_FILES
                              ).map((f) => (
                                <span
                                  key={f}
                                  className="flex-1 text-center text-[10px] font-medium text-slate-400 uppercase tracking-tight"
                                >
                                  {f}
                                </span>
                              ))}
                            </div>
                          </div>
                        </div>
                        <div className="vf-chess-play__bar flex items-center justify-between gap-2 mt-3 px-2 rounded-lg bg-slate-900/85 py-2 border border-slate-700/60">
                          <div className="flex items-center gap-2">
                            <span className="text-lg leading-none" aria-hidden>
                              ♙
                            </span>
                            <div>
                              <p className="text-sm font-medium text-slate-100">You</p>
                              <p className="text-xs text-slate-400">
                                {chessSession
                                  ? chessSession.user_color === 'white'
                                    ? 'White'
                                    : 'Black'
                                  : chessSideChoice === 'random'
                                    ? 'Random side'
                                    : chessSideChoice === 'white'
                                      ? 'White'
                                      : 'Black'}
                              </p>
                            </div>
                          </div>
                        </div>
                        <p className="mt-2 text-[11px] text-slate-500 text-center leading-snug">
                          {chessSession ? (
                            <>Pick a piece, then a destination. Promotion: choose Queen / Rook / Bishop / Knight.</>
                          ) : (
                            <>
                              Press <span className="text-emerald-400/95 font-medium">Play</span> to start a game. The board shows the standard start — you cannot move until a game exists.
                            </>
                          )}
                        </p>
                        {chessPromotionUcis && chessPromotionUcis.length > 0 ? (
                          <div
                            className="absolute inset-0 z-[60] flex items-center justify-center rounded-xl bg-black/60 px-3 py-6 backdrop-blur-[2px]"
                            role="dialog"
                            aria-modal="true"
                            aria-labelledby="vf-chess-promo-title"
                            onClick={() => setChessPromotionUcis(null)}
                          >
                            <div
                              className="w-full max-w-[280px] rounded-xl border border-amber-500/45 bg-slate-900/98 p-4 shadow-2xl"
                              onClick={(e) => e.stopPropagation()}
                            >
                              <p
                                id="vf-chess-promo-title"
                                className="text-center text-sm font-semibold text-slate-100 mb-1"
                              >
                                Promotion
                              </p>
                              <p className="text-center text-[11px] text-slate-500 mb-3">Choose the replacement piece</p>
                              <div className="grid grid-cols-2 gap-2">
                                {chessPromotionUcis.map((uci) => {
                                  const suf = uci.slice(-1).toLowerCase()
                                  const meta = CHESS_PROMOTION_META[suf] ?? {
                                    label: suf,
                                    glyph: '?',
                                  }
                                  return (
                                    <button
                                      key={uci}
                                      type="button"
                                      onClick={() => {
                                        void handleChessMove(uci)
                                      }}
                                      disabled={chessLoading}
                                      className="flex flex-col items-center gap-1 rounded-lg border border-slate-600/80 bg-slate-800/90 py-3 px-2 text-slate-100 hover:bg-amber-500/15 hover:border-amber-500/50 transition disabled:opacity-50"
                                    >
                                      <span className="text-2xl leading-none" aria-hidden>
                                        {meta.glyph}
                                      </span>
                                      <span className="text-xs font-medium">{meta.label}</span>
                                    </button>
                                  )
                                })}
                              </div>
                              <button
                                type="button"
                                onClick={() => setChessPromotionUcis(null)}
                                className="mt-3 w-full rounded-lg border border-slate-600/70 py-2 text-xs text-slate-400 hover:bg-white/5 transition"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : null}
                      </div>

                      <aside className="vf-chess-play__sidebar space-y-4 min-w-0">
                        <div className="rounded-xl border border-slate-700/80 bg-slate-950/45 p-4 shadow-md">
                          <div className="flex items-center gap-2 mb-1">
                            <svg
                              className="w-5 h-5 text-emerald-400/90 shrink-0"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              aria-hidden
                            >
                              <rect x="2" y="3" width="20" height="14" rx="2" />
                              <path d="M8 21h8" />
                              <path d="M12 17v4" />
                            </svg>
                            <h3 className="text-sm font-semibold text-slate-100 tracking-wide">Play Bots</h3>
                          </div>
                          <p className="text-[11px] text-slate-500 mb-3">Pick a tier — no avatar in this mode.</p>
                          <div className="space-y-2">
                            {CHESS_TIER_ORDER.map((tier) => {
                              const meta = CHESS_TIER_META[tier]
                              const isOn = chessBotTier === tier
                              return (
                                <button
                                  key={tier}
                                  type="button"
                                  onClick={() => setChessBotTier(tier)}
                                  className={`w-full text-left rounded-lg border px-3 py-2.5 transition ${
                                    isOn
                                      ? 'border-emerald-500/70 bg-emerald-500/10 ring-1 ring-emerald-500/35'
                                      : 'border-slate-700/80 bg-slate-900/50 hover:bg-slate-800/55'
                                  }`}
                                >
                                  <div className="flex items-baseline justify-between gap-2">
                                    <span className="text-sm font-semibold text-slate-100">{meta.title}</span>
                                    <span className="text-xs tabular-nums text-emerald-400/90 shrink-0">
                                      {CHESS_TIER_ELO[tier]} ELO
                                    </span>
                                  </div>
                                  <p className="text-[11px] text-slate-500 mt-1 leading-snug">{meta.hint}</p>
                                </button>
                              )
                            })}
                          </div>
                          <div className="mt-4 pt-3 border-t border-slate-700/60">
                            <p className="text-[10px] uppercase tracking-wider text-slate-500 mb-2">Play as</p>
                            <div className="flex flex-wrap gap-2">
                              {(['white', 'random', 'black'] as const).map((side) => (
                                <button
                                  key={side}
                                  type="button"
                                  onClick={() => setChessSideChoice(side)}
                                  className={`flex-1 min-w-[5.5rem] px-2 py-2 rounded-lg text-xs font-medium border transition ${
                                    chessSideChoice === side
                                      ? 'border-emerald-500/60 bg-emerald-500/15 text-slate-100'
                                      : 'border-slate-700/80 text-slate-400 hover:bg-slate-800/50'
                                  }`}
                                >
                                  {side === 'white' ? 'White' : side === 'black' ? 'Black' : 'Random'}
                                </button>
                              ))}
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={handleChessNewGame}
                            disabled={chessLoading}
                            className="mt-4 w-full rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white font-semibold py-3 text-sm shadow-md disabled:opacity-50 transition"
                          >
                            {chessLoading ? '…' : 'Play'}
                          </button>
                        </div>
                        <div className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/70 p-4 text-sm shadow-sm">
                          <h3 className="text-xs font-semibold uppercase tracking-wider text-vn-textDim mb-2">Match</h3>
                          {!chessSession ? (
                            <p className="text-vn-textDim text-sm">No active game.</p>
                          ) : (
                            <>
                            <dl className="space-y-1.5 text-vn-textDim text-sm">
                              <div className="flex justify-between gap-2">
                                <dt className="text-vn-text">Opponent ELO</dt>
                                <dd className="tabular-nums">{chessSession.bot_elo}</dd>
                              </div>
                              <div className="flex justify-between gap-2">
                                <dt className="text-vn-text">Status</dt>
                                <dd>
                                  <span
                                    className={`px-2 py-0.5 rounded-md text-xs ${
                                      chessSession.status === 'finished'
                                        ? 'bg-emerald-500/20 text-emerald-200'
                                        : 'bg-amber-500/20 text-amber-200'
                                    }`}
                                  >
                                    {chessSession.status}
                                  </span>
                                </dd>
                              </div>
                              <div className="flex justify-between gap-2">
                                <dt className="text-vn-text">Turn</dt>
                                <dd>{chessSession.turn}</dd>
                              </div>
                              <div className="flex justify-between gap-2">
                                <dt className="text-vn-text">Result</dt>
                                <dd>{chessSession.result || '—'}</dd>
                              </div>
                              <div className="flex justify-between gap-2">
                                <dt className="text-vn-text">Half-moves</dt>
                                <dd>{chessSession.moves_count}</dd>
                              </div>
                              <div className="flex justify-between gap-2">
                                <dt className="text-vn-text">Last</dt>
                                <dd className="text-right">{chessSession.last_move?.san || '—'}</dd>
                              </div>
                            </dl>
                            {chessSession.moves_log && chessSession.moves_log.length > 0 ? (
                              <div className="mt-3 rounded-lg border border-vn-dialogueBorder/80 bg-black/20 px-2 py-2 max-h-36 overflow-y-auto">
                                <p className="text-[10px] uppercase tracking-wider text-vn-textDim mb-1.5">Move log</p>
                                <ol className="text-[11px] font-mono text-vn-textDim leading-relaxed list-decimal pl-4 space-y-0.5">
                                  {chessSession.moves_log.map((m) => (
                                    <li key={`${m.ply}-${m.uci}`}>
                                      <span className={m.side === 'user' ? 'text-cyan-200/90' : 'text-amber-200/85'}>
                                        [{m.side}]
                                      </span>{' '}
                                      {m.san}
                                    </li>
                                  ))}
                                </ol>
                              </div>
                            ) : null}
                            </>
                          )}
                          <button
                            type="button"
                            onClick={handleChessReview}
                            disabled={!chessSession || chessLoading}
                            className="mt-3 w-full rounded-lg border border-vn-dialogueBorder px-3 py-2 text-sm text-vn-text hover:bg-white/10 disabled:opacity-50 transition"
                          >
                            Post-game review (AI)
                          </button>
                        </div>
                        {chessReview && (
                          <div className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/70 p-4 text-sm shadow-sm">
                            <h3 className="text-xs font-semibold uppercase tracking-wider text-vn-textDim mb-2">Post-game review</h3>
                            <p className="text-vn-text whitespace-pre-wrap leading-relaxed">{chessReview.review_text}</p>
                            {chessReview.stats.engine_analysis_available === false ? (
                              <p className="mt-2 text-[11px] text-amber-200/85 leading-snug">
                                Full engine analysis needs <span className="font-mono">STOCKFISH_PATH</span> on the server —
                                showing heuristic stats only (material / patterns) for now.
                              </p>
                            ) : null}
                            {chessReview.stats.engine_insights && chessReview.stats.engine_insights.length > 0 && (
                              <div className="mt-3 rounded-lg border border-vn-nameGlow/20 bg-vn-nameGlow/5 p-3">
                                <p className="text-xs font-semibold text-vn-text mb-2">
                                  Engine (Stockfish) — moves that lost ≥50 cp
                                </p>
                                <ul className="space-y-2">
                                  {chessReview.stats.engine_insights.map((ins, idx) => (
                                    <li key={idx} className="text-xs text-vn-textDim leading-snug">
                                      {ins.ply != null ? (
                                        <span className="text-vn-textDim tabular-nums">#{ins.ply} </span>
                                      ) : null}
                                      <span className="text-vn-text">You:</span> {ins.your_move_san ?? '—'}
                                      {ins.best_move_san != null ? (
                                        <>
                                          {' '}
                                          · <span className="text-vn-text">Best:</span> {ins.best_move_san}
                                        </>
                                      ) : null}
                                      {ins.cp_loss != null ? (
                                        <span className="text-amber-200/90"> · −{ins.cp_loss} cp</span>
                                      ) : null}
                                      {ins.classification ? (
                                        <span className="text-vn-textDim"> · {ins.classification}</span>
                                      ) : null}
                                      {ins.engine_top_moves?.[0] && (
                                        <>
                                          {' '}
                                          · <span className="text-vn-text">Top1:</span> {ins.engine_top_moves[0].san}
                                          {ins.engine_top_moves[0].eval_hint && (
                                            <span className="text-vn-textDim"> ({ins.engine_top_moves[0].eval_hint})</span>
                                          )}
                                        </>
                                      )}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
                              <div className="rounded-lg border border-vn-dialogueBorder px-2 py-1 text-vn-textDim">
                                Inaccuracy: <span className="text-vn-text">{chessReview.stats.inaccuracy_like_moves}</span>
                              </div>
                              <div className="rounded-lg border border-vn-dialogueBorder px-2 py-1 text-vn-textDim">
                                Mistake: <span className="text-vn-text">{chessReview.stats.mistake_like_moves}</span>
                              </div>
                              <div className="rounded-lg border border-vn-dialogueBorder px-2 py-1 text-vn-textDim">
                                Blunder: <span className="text-vn-text">{chessReview.stats.blunder_like_moves}</span>
                              </div>
                              <div className="rounded-lg border border-vn-dialogueBorder px-2 py-1 text-vn-textDim">
                                {chessReview.stats.avg_cp_loss != null ? (
                                  <>
                                    Avg cp loss:{' '}
                                    <span className="text-vn-text tabular-nums">{chessReview.stats.avg_cp_loss}</span>
                                  </>
                                ) : (
                                  <>
                                    Avg Δcp (heuristic):{' '}
                                    <span className="text-vn-text tabular-nums">{chessReview.stats.avg_eval_delta_cp}</span>
                                  </>
                                )}
                              </div>
                            </div>
                            {chessReview.stats.key_mistakes.length > 0 && (
                              <div className="mt-3">
                                <p className="text-vn-text text-xs font-semibold mb-1">Worst moves (engine)</p>
                                <ul className="space-y-1">
                                  {chessReview.stats.key_mistakes.map((m) => (
                                    <li
                                      key={`${m.uci}-${m.san}`}
                                      className="text-xs text-vn-textDim rounded-lg border border-vn-dialogueBorder px-2 py-1"
                                    >
                                      <span className="text-vn-text">{m.san}</span> ({m.uci})
                                      {m.best_move_san != null ? (
                                        <>
                                          {' '}
                                          · better: <span className="text-vn-text">{m.best_move_san}</span>
                                        </>
                                      ) : null}
                                      {m.cp_loss != null ? (
                                        <span> · loss {m.cp_loss} cp</span>
                                      ) : m.eval_delta_cp != null ? (
                                        <span> · Δ {m.eval_delta_cp}</span>
                                      ) : null}
                                      {m.classification ? <span className="text-vn-textDim"> · {m.classification}</span> : null}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                            {chessReview.stats.training_focus.length > 0 && (
                              <div className="mt-3">
                                <p className="text-vn-text text-xs font-semibold mb-1">Training focus</p>
                                <ul className="space-y-1">
                                  {chessReview.stats.training_focus.map((focus) => (
                                    <li key={focus} className="text-xs text-vn-textDim">
                                      · {focus}
                                    </li>
                                  ))}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                      </aside>
                    </div>
                  </div>
                ) : activeGame === 'Caro' ? (
                  <div className="vf-caro-play w-full max-w-6xl mx-auto relative">
                    <div className="vf-caro-play__glow pointer-events-none" aria-hidden />
                    <div className="relative z-[1]">
                      <div className="vf-caro-play__head flex flex-wrap items-start justify-between gap-4 mb-6">
                        <div className="vf-caro-play__titleblock text-center sm:text-left flex-1 min-w-[12rem]">
                          <div className="vf-caro-play__ornament mx-auto sm:mx-0" aria-hidden />
                          <h2 className="vf-caro-play__title">Caro</h2>
                          <p className="vf-caro-play__tagline">
                            X moves first. If you play O, the opponent opens. Rules scale with the board size you pick.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() => {
                            setActiveGame(null)
                            setCaroSession(null)
                            setCaroReview(null)
                          }}
                          className="vf-caro-play__exit shrink-0"
                        >
                          Exit
                        </button>
                      </div>

                      <div className="grid lg:grid-cols-[minmax(280px,1fr)_minmax(280px,1fr)] gap-6 lg:gap-8 items-start">
                        <div className="min-w-0 space-y-5">
                          {!caroSession ? (
                            <div className="vf-caro-panel vf-caro-panel--setup">
                              <span className="vf-caro-panel__corner vf-caro-panel__corner--tl" aria-hidden />
                              <span className="vf-caro-panel__corner vf-caro-panel__corner--tr" aria-hidden />
                              <span className="vf-caro-panel__corner vf-caro-panel__corner--bl" aria-hidden />
                              <span className="vf-caro-panel__corner vf-caro-panel__corner--br" aria-hidden />
                              <div className="relative z-[1] space-y-5">
                                <div>
                                  <p className="vf-caro-field-label">Board size</p>
                                  <div className="vf-caro-grid-pills">
                                    {CARO_GRID_SIZES.map((sz) => (
                                      <button
                                        key={sz}
                                        type="button"
                                        onClick={() => setCaroGridSize(sz)}
                                        className={`vf-caro-grid-pill ${caroGridSize === sz ? 'vf-caro-grid-pill--on' : ''}`}
                                      >
                                        {sz}×{sz}
                                      </button>
                                    ))}
                                  </div>
                                  <p className="vf-caro-hint mt-3">
                                    {caroRuleSummary(caroGridSize, caroServerDefaultK(caroGridSize))}
                                  </p>
                                </div>
                                <div>
                                  <p className="vf-caro-field-label">Your side</p>
                                  <div className="flex gap-3">
                                    {(['x', 'o'] as const).map((s) => (
                                      <button
                                        key={s}
                                        type="button"
                                        onClick={() => setCaroStone(s)}
                                        className={`vf-caro-stone ${caroStone === s ? 'vf-caro-stone--on' : ''}`}
                                        aria-pressed={caroStone === s}
                                      >
                                        <span className="vf-caro-stone__glyph">{s.toUpperCase()}</span>
                                        <span className="vf-caro-stone__hint">
                                          {s === 'x' ? 'First' : 'Second'}
                                        </span>
                                      </button>
                                    ))}
                                  </div>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => void handleCaroNew()}
                                  disabled={caroLoading}
                                  className="vf-caro-cta"
                                >
                                  {caroLoading ? 'Setting up…' : 'Start game'}
                                </button>
                              </div>
                            </div>
                          ) : null}

                          {caroSession ? (
                            <div className="vf-caro-panel vf-caro-panel--board">
                              <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
                                <div>
                                  <p className="vf-caro-live-title">
                                    Board {caroSession.n}×{caroSession.n}
                                    <span className="vf-caro-live-dot" aria-hidden />
                                    You play{' '}
                                    <span className="text-[color:var(--bg3-gold-bright)] font-semibold">
                                      {caroSession.user_stone.toUpperCase()}
                                    </span>
                                  </p>
                                  <p className="vf-caro-hint mt-1">{caroRuleSummary(caroSession.n, caroSession.k)}</p>
                                </div>
                                <button
                                  type="button"
                                  onClick={() => void handleCaroNew()}
                                  disabled={caroLoading}
                                  className="vf-caro-secondary-btn"
                                >
                                  New game
                                </button>
                              </div>
                              <div className="vf-caro-board-frame">
                                <div
                                  className="vf-caro-board-grid"
                                  style={{
                                    gridTemplateColumns: `repeat(${caroSession.n}, minmax(0, 1fr))`,
                                  }}
                                >
                                  {caroSession.board.map((row, r) =>
                                    row.map((cell, c) => {
                                      const isUser = cell === caroSession.user_stone
                                      const isEmpty = cell == null
                                      const canClick =
                                        caroSession.status === 'active' &&
                                        caroSession.turn === 'user' &&
                                        isEmpty &&
                                        !caroLoading
                                      return (
                                        <button
                                          key={`${r}-${c}`}
                                          type="button"
                                          disabled={!canClick}
                                          onClick={() => void handleCaroCell(r, c)}
                                          className={`vf-caro-cell ${isEmpty ? 'vf-caro-cell--empty' : ''} ${
                                            !isEmpty && isUser ? 'vf-caro-cell--yours' : ''
                                          } ${!isEmpty && !isUser ? 'vf-caro-cell--foe' : ''}`}
                                        >
                                          {cell ? (
                                            <span className="vf-caro-cell__mark">{cell.toUpperCase()}</span>
                                          ) : null}
                                        </button>
                                      )
                                    }),
                                  )}
                                </div>
                              </div>
                              <p className="vf-caro-statusline">
                                {caroSession.status === 'finished' ? (
                                  caroSession.winner === 'user' ? (
                                    <span className="text-emerald-300/95">You win — nice game!</span>
                                  ) : caroSession.winner === 'bot' ? (
                                    <span className="text-amber-200/95">Opponent wins — try again.</span>
                                  ) : (
                                    <span className="text-[color:var(--bg3-text)]">Draw.</span>
                                  )
                                ) : caroSession.turn === 'user' ? (
                                  <span>Your turn — pick an empty cell.</span>
                                ) : (
                                  <span>Opponent is thinking…</span>
                                )}
                              </p>
                            </div>
                          ) : null}
                        </div>

                        <aside className="space-y-4 min-w-0">
                          <div className="vf-caro-panel vf-caro-panel--aside">
                            <div className="vf-caro-aside-head">
                              <span className="vf-caro-aside-icon" aria-hidden>
                                ◈
                              </span>
                              <h3 className="vf-caro-aside-title">Match</h3>
                            </div>
                            {!caroSession ? (
                              <div className="vf-caro-empty">
                                <div className="vf-caro-empty__grid" aria-hidden />
                                <p className="vf-caro-empty__text">Pick a board size on the left, then press Start game.</p>
                              </div>
                            ) : (
                              <>
                                <dl className="vf-caro-dl">
                                  <div className="vf-caro-dl__row">
                                    <dt>Board</dt>
                                    <dd>
                                      {caroSession.n} × {caroSession.n}
                                    </dd>
                                  </div>
                                  <div className="vf-caro-dl__row">
                                    <dt>Rule</dt>
                                    <dd className="text-right leading-snug">Win with {caroRuleShort(caroSession.k)}</dd>
                                  </div>
                                  <div className="vf-caro-dl__row">
                                    <dt>Status</dt>
                                    <dd>
                                      <span
                                        className={`vf-caro-badge ${caroSession.status === 'finished' ? 'vf-caro-badge--done' : 'vf-caro-badge--live'}`}
                                      >
                                        {caroStatusLabel(caroSession.status)}
                                      </span>
                                    </dd>
                                  </div>
                                  <div className="vf-caro-dl__row">
                                    <dt>Turn</dt>
                                    <dd>{caroTurnLabel(caroSession.turn)}</dd>
                                  </div>
                                  <div className="vf-caro-dl__row">
                                    <dt>Result</dt>
                                    <dd>{caroResultLabel(caroSession)}</dd>
                                  </div>
                                  <div className="vf-caro-dl__row">
                                    <dt>Total plies</dt>
                                    <dd className="tabular-nums">{caroSession.moves_count}</dd>
                                  </div>
                                </dl>
                                {caroSession.moves_log && caroSession.moves_log.length > 0 ? (
                                  <div className="vf-caro-movelog">
                                    <p className="vf-caro-movelog__label">Moves</p>
                                    <ol className="vf-caro-movelog__list">
                                      {caroSession.moves_log.map((m, idx) => (
                                        <li key={`${idx}-${m.row}-${m.col}`}>
                                          <span className={m.side === 'user' ? 'text-teal-200/95' : 'text-amber-200/90'}>
                                            {m.side === 'user' ? 'You' : 'Opponent'}
                                          </span>
                                          <span className="text-[color:rgba(200,180,140,0.55)]"> · </span>
                                          row {m.row + 1}, col {m.col + 1}
                                        </li>
                                      ))}
                                    </ol>
                                  </div>
                                ) : null}
                                <button
                                  type="button"
                                  onClick={() => void handleCaroReview()}
                                  disabled={!caroSession || caroLoading}
                                  className="vf-caro-review-btn"
                                >
                                  Post-game review (AI)
                                </button>
                              </>
                            )}
                          </div>
                          {caroReview ? (
                            <div className="vf-caro-panel vf-caro-panel--review">
                              <h3 className="vf-caro-review-head">Post-game review</h3>
                              <p className="vf-caro-review-body whitespace-pre-wrap leading-relaxed">{caroReview.review_text}</p>
                              <div className="vf-caro-stats">
                                <div className="vf-caro-stat">
                                  <span className="vf-caro-stat__k">Your moves</span>
                                  <span className="vf-caro-stat__v tabular-nums">{caroReview.stats.user_moves}</span>
                                </div>
                                <div className="vf-caro-stat">
                                  <span className="vf-caro-stat__k">Opponent moves</span>
                                  <span className="vf-caro-stat__v tabular-nums">{caroReview.stats.bot_moves}</span>
                                </div>
                                <div className="vf-caro-stat">
                                  <span className="vf-caro-stat__k">Longest run (you)</span>
                                  <span className="vf-caro-stat__v tabular-nums">{caroReview.stats.user_best_run}</span>
                                </div>
                                <div className="vf-caro-stat">
                                  <span className="vf-caro-stat__k">Opening near center</span>
                                  <span className="vf-caro-stat__v">
                                    {caroReview.stats.opening_near_center ? 'Yes' : 'No'}
                                  </span>
                                </div>
                              </div>
                            </div>
                          ) : null}
                        </aside>
                      </div>
                    </div>
                  </div>
                ) : activeGame === 'Tetris' ? (
                  <TetrisGame onExit={() => setActiveGame(null)} />
                ) : activeGame === 'Snake' ? (
                  <SnakeGame onExit={() => setActiveGame(null)} />
                ) : activeGame === 'Ancient RTS' ? (
                  <AncientRtsGame onExit={() => setActiveGame(null)} />
                ) : activeGame ? (
                  <div className="flex flex-col flex-1 min-h-[200px] items-center justify-center gap-4 px-2">
                    <div className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/70 min-h-[160px] w-full max-w-md flex flex-col items-center justify-center text-center px-4 py-6">
                      <p className="text-vn-text text-sm md:text-base">
                        Gameplay for <span className="font-semibold">{activeGame}</span>
                      </p>
                      <p className="mt-2 text-vn-textDim text-sm">Coming soon.</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => {
                        setActiveGame(null)
                        setChessSession(null)
                        setChessSelectedSquare(null)
                        setChessPromotionUcis(null)
                        setChessReview(null)
                        setCaroSession(null)
                        setCaroReview(null)
                      }}
                      className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/80 px-4 py-2 text-sm text-vn-text hover:bg-white/10 transition"
                    >
                      Back to games
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-1 min-h-0 flex-col items-stretch justify-start w-full max-w-xl mx-auto pt-1 pb-2">
                    <GameHubPanel onSelectGame={chooseGame} onClose={() => setChatPanelTab('chat')} />
                  </div>
                )}
              </div>
            )}
            {chatPanelTab === 'memory' && (
              <div className="vf-chat-subpane vf-chat-memory-pane flex flex-col flex-1 min-h-0 overflow-hidden p-4 vn-stage-bg">
                <h2 className="vf-chat-memory-headline text-sm font-semibold text-vn-name mb-1">
                  <span className="vf-chat-memory-head-pale">MEMORY</span>{' '}
                  <span className="vf-chat-memory-head-gold">SUMMARY</span>
                </h2>
                <p className="aid-updates-meta text-xs mb-3">Facts and preferences extracted from your chats (stored in the database).</p>
                <div className="aid-updates-scroll flex-1 min-h-0 pr-1" role="region" aria-label="Memory list">
                  {memoriesLoading ? (
                    <p className="text-vn-textDim text-sm">Loading…</p>
                  ) : memories.length === 0 ? (
                    <p className="text-vn-textDim text-sm">No saved memories yet. Chat more and summaries will appear here.</p>
                  ) : (
                    <ul className="aid-updates-list">
                      {memories.map((m) => {
                        const kind = memoryKindForUpdates(m.type)
                        return (
                          <li key={m.id} className="aid-updates-item">
                            <div className="aid-updates-item-head">
                              <span className={`aid-updates-kind aid-updates-kind--${kind}`}>{memoryKindLabel(m.type)}</span>
                              <span className="aid-updates-id">#{m.id.slice(0, 8)}</span>
                            </div>
                            <p className="aid-updates-subject whitespace-pre-wrap">{m.content}</p>
                            <div className="aid-updates-foot">
                              {m.created_at ? (
                                <time className="aid-updates-time" dateTime={m.created_at}>
                                  {new Date(m.created_at).toLocaleString()}
                                </time>
                              ) : null}
                            </div>
                          </li>
                        )
                      })}
                    </ul>
                  )}
                </div>
              </div>
            )}
            {chatPanelTab === 'diary' && (
              <div className="vf-chat-subpane flex flex-col flex-1 min-h-0 overflow-auto p-4 vn-stage-bg">
                <h2 className="text-sm font-semibold text-vn-name mb-2">Diary</h2>
                <p className="text-xs text-vn-textDim mb-3">Private notes about this AI — saved to your account.</p>
                <textarea
                  value={diaryDraft}
                  onChange={(e) => setDiaryDraft(e.target.value)}
                  rows={5}
                  placeholder="How is the AI doing? Write anything..."
                  className="w-full rounded-xl border border-vn-dialogueBorder bg-vn-stage/80 px-3 py-2 text-sm text-vn-text placeholder-vn-textDim outline-none focus:ring-2 focus:ring-vn-nameGlow/30 mb-3"
                />
                {diaryError ? <p className="text-sm text-red-300 mb-2">{diaryError}</p> : null}
                <button
                  type="button"
                  onClick={() => void saveDiary()}
                  disabled={diarySaving || !diaryDraft.trim()}
                  className="mb-6 rounded-xl border border-vn-nameGlow/50 bg-vn-nameGlow/15 px-4 py-2 text-sm text-vn-name hover:bg-vn-nameGlow/25 disabled:opacity-40 transition"
                >
                  {diarySaving ? 'Saving…' : 'Save entry'}
                </button>
                <h3 className="text-xs font-semibold text-vn-textDim uppercase tracking-wide mb-2">Past entries</h3>
                {diaryLoading ? (
                  <p className="text-vn-textDim text-sm">Loading…</p>
                ) : diaryEntries.length === 0 ? (
                  <p className="text-vn-textDim text-sm">No diary entries yet.</p>
                ) : (
                  <ul className="space-y-3">
                    {diaryEntries.map((d) => (
                      <li
                        key={d.id}
                        className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/50 px-3 py-2 text-sm text-vn-text whitespace-pre-wrap"
                      >
                        <p className="text-xs text-vn-textDim mb-1">{new Date(d.created_at).toLocaleString()}</p>
                        {d.content}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            {chatPanelTab === 'relationship' && (
              <div className="vf-chat-subpane vf-chat-relationship-pane flex flex-col flex-1 min-h-0 overflow-auto p-4 sm:p-6 vn-stage-bg">
                <h2 className="vf-chat-relationship-title">Relationship</h2>
                <p className="vf-chat-relationship-sub">with {displayName}</p>
                <div className="vf-chat-hearts-row vf-chat-hearts-row--detail" aria-label={`Bond: ${heartsFilledFromLevel(relationshipLevel)} of ${RELATIONSHIP_HEART_SLOTS} hearts`}>
                  {Array.from({ length: RELATIONSHIP_HEART_SLOTS }).map((_, i) => (
                    <RelationshipHeartIcon key={i} filled={i < heartsFilledFromLevel(relationshipLevel)} size={32} />
                  ))}
                </div>
                <p className="vf-chat-relationship-level">Level {relationshipLevel}</p>
                <p className="vf-chat-relationship-progress">
                  {userMessageCount} messages sent · {messagesUntilNextLevel(userMessageCount)} until next level
                </p>
                {relationshipLevel > RELATIONSHIP_HEART_SLOTS ? (
                  <p className="vf-chat-relationship-note text-xs text-vn-textDim mt-2">
                    Max hearts shown — your bond continues to grow beyond level {RELATIONSHIP_HEART_SLOTS}.
                  </p>
                ) : null}
              </div>
            )}
          </div>
        </main>
        </div>
      </div>

      {sentencePopup && (
        <div
          className="vf-chat-sentence-popup-backdrop"
          onClick={() => {
            setSentencePopup(null)
            setActiveSentenceKey(null)
          }}
          role="presentation"
        >
          <div
            className="vf-chat-sentence-popup"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
            aria-label="Highlighted line"
          >
            <div className="vf-chat-sentence-popup-text vf-chat-sentence-popup-text--md">
              <ChatMarkdown text={sentencePopup.text} variant="popup" />
            </div>
            <div className="vf-chat-sentence-popup-foot">
              <IconBotCorner className="vf-chat-sentence-popup-bot" />
            </div>
          </div>
        </div>
      )}

      {funFactOpen && agentId && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm animate-vn-fade-in px-4"
          onClick={() => void closeFunFactModal()}
          role="presentation"
        >
          <div
            className="bg-vn-dialogue rounded-2xl shadow-vn border border-vn-nameGlow/35 w-full max-w-md vn-dialogue-in p-6 text-center"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-labelledby="vf-funfact-title"
          >
            <div className="text-3xl mb-2" aria-hidden>
              ♥
            </div>
            <h2 id="vf-funfact-title" className="text-lg font-semibold text-vn-name mb-2">
              Relationship level {funFactLevel}
            </h2>
            <p className="text-sm text-vn-textDim leading-relaxed mb-6">
              Fun facts about this character&apos;s creators will appear here — you can add custom copy later. This moment is
              saved when you continue.
            </p>
            <button
              type="button"
              onClick={() => void closeFunFactModal()}
              className="w-full rounded-xl border border-vn-nameGlow/50 bg-vn-nameGlow/15 px-4 py-2.5 text-sm font-semibold text-vn-name hover:bg-vn-nameGlow/25 transition"
            >
              Continue
            </button>
          </div>
        </div>
      )}

      {/* Conversation list panel */}
      {conversationsPanelOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-vn-fade-in" onClick={() => setConversationsPanelOpen(false)}>
          <div className="bg-vn-dialogue rounded-2xl shadow-vn border border-vn-dialogueBorder w-full max-w-lg max-h-[80vh] flex flex-col vn-dialogue-in" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-vn-dialogueBorder">
              <h2 className="font-semibold text-vn-text">Conversations</h2>
              <button type="button" onClick={() => setConversationsPanelOpen(false)} className="p-2 rounded-lg text-vn-textDim hover:bg-white/10 hover:text-vn-text transition">✕</button>
            </div>
            <div className="p-4 border-b border-vn-dialogueBorder">
              <button
                type="button"
                onClick={() => {
                  startNewChat()
                  setConversationsPanelOpen(false)
                }}
                className="w-full rounded-lg border border-vn-dialogueBorder px-3 py-2 text-sm text-vn-text hover:bg-white/10 transition"
              >
                + New conversation
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              {conversationsLoading ? (
                <p className="text-vn-textDim text-sm">Loading...</p>
              ) : conversations.length === 0 ? (
                <p className="text-vn-textDim text-sm">No conversations yet.</p>
              ) : (
                <ul className="space-y-2">
                  {conversations.map((c) => (
                    <li key={c.id}>
                      <button
                        type="button"
                        onClick={() => {
                          selectConversation(c.id)
                          setConversationsPanelOpen(false)
                        }}
                        className={`w-full rounded-lg px-3 py-2.5 text-left text-sm truncate transition ${
                          conversationId === c.id ? 'bg-vn-nameGlow/20 text-vn-text border border-vn-nameGlow/40' : 'text-vn-textDim border border-vn-dialogueBorder hover:bg-white/10 hover:text-vn-text'
                        }`}
                      >
                        {c.title || `Conversation ${c.id.slice(0, 8)}`}
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Game picker modal — same UI as Game tab */}
      {gamePickerOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 backdrop-blur-sm animate-vn-fade-in px-3 sm:px-4"
          onClick={() => setGamePickerOpen(false)}
        >
          <div className="w-full max-w-md max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <GameHubPanel
              onSelectGame={(g) => {
                chooseGame(g)
                setGamePickerOpen(false)
              }}
              onClose={() => setGamePickerOpen(false)}
              className="vf-game-hub--modal"
            />
          </div>
        </div>
      )}

      {/* Conversation history panel (from DB) */}
      {historyOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-vn-fade-in" onClick={() => setHistoryOpen(false)}>
          <div className="bg-vn-dialogue rounded-2xl shadow-vn border border-vn-dialogueBorder w-full max-w-lg max-h-[80vh] flex flex-col vn-dialogue-in" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-vn-dialogueBorder">
              <h2 className="font-semibold text-vn-text">Conversation history</h2>
              <button type="button" onClick={() => setHistoryOpen(false)} className="p-2 rounded-lg text-vn-textDim hover:bg-white/10 hover:text-vn-text transition">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {!conversationId ? (
                <p className="text-vn-textDim text-sm">Select or start a conversation to see history.</p>
              ) : historyLoading ? (
                <p className="text-vn-textDim text-sm">Loading...</p>
              ) : historyMessages.length === 0 ? (
                <p className="text-vn-textDim text-sm">No messages in this conversation yet.</p>
              ) : (
                historyMessages.map((msg) => (
                  <div key={msg.id} className={`rounded-xl px-3 py-2 text-sm ${msg.role === 'user' ? 'bg-vn-nameGlow/15 ml-8 border border-vn-nameGlow/30' : 'bg-vn-stageLight/80 mr-8 border border-vn-dialogueBorder'}`}>
                    <p className="font-medium vn-name-tag mb-0.5">{msg.role === 'user' ? 'You' : displayName}</p>
                    <p className="whitespace-pre-wrap text-vn-text">{msg.content}</p>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
