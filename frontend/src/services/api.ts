/** Dev defaults to :8000 so the API (and chat WS) do not go through Vite’s proxy. */
function resolveApiBase(): string {
  const v = typeof import.meta.env.VITE_API_URL === 'string' ? import.meta.env.VITE_API_URL.trim() : ''
  if (v !== '') {
    // Common mistake: pointing at the Vite dev server instead of FastAPI
    if (import.meta.env.DEV && /:5173\b/.test(v)) return 'http://localhost:8000'
    return v
  }
  if (import.meta.env.DEV) return 'http://localhost:8000'
  return ''
}

const API_BASE = resolveApiBase()

function getToken(): string | null {
  return localStorage.getItem('access_token')
}

function headers(withAuth = true): HeadersInit {
  const h: HeadersInit = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (withAuth && token) h['Authorization'] = `Bearer ${token}`
  return h
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({})))?.detail ?? res.statusText
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json()
}

// ---------------------------------------------------------------------------
// WebSocket
// ---------------------------------------------------------------------------
export type WsMessage =
  | { type: 'stream_start'; conversation_id: string }
  | { type: 'token'; content: string }
  | {
      type: 'stream_end'
      detected_intent: string | null
      detected_emotion: string | null
      avatar_action: string | null
      user_message_count?: number | null
      relationship_level?: number | null
      relationship_level_up?: boolean
      new_relationship_level?: number | null
    }
  | { type: 'error'; detail: string }

export function createChatWs(onMessage: (msg: WsMessage) => void, onClose?: () => void): WebSocket | null {
  const token = getToken()
  if (!token) return null

  // Never fall back to Vite’s origin (5173) for chat WS — that hits the broken proxy.
  const httpBase =
    API_BASE || (import.meta.env.DEV ? 'http://localhost:8000' : window.location.origin)
  const wsBase = httpBase.replace(/^http/, 'ws')
  const url = `${wsBase}/chat/ws?token=${encodeURIComponent(token)}`

  const ws = new WebSocket(url)
  ws.onmessage = (ev) => {
    try {
      onMessage(JSON.parse(ev.data))
    } catch { /* ignore malformed */ }
  }
  ws.onclose = (ev) => {
    if (import.meta.env.DEV) {
      const hint =
        ev.code === 1006
          ? ' (abnormal — often refused, invalid JWT, or API not on this port)'
          : ev.code === 4001 || ev.reason?.includes('token')
            ? ' (log out and log in again if SECRET_KEY changed or token expired)'
            : ''
      console.warn(`[chat WS] closed code=${ev.code} reason=${ev.reason || '(none)'}${hint}`)
    }
    onClose?.()
  }
  ws.onerror = () => onClose?.()
  return ws
}

export type ChatSessionContext = {
  agent_id?: string | null
  entry_mode?: 'quickstart' | 'character' | null
  persona?: string | null
  character_name?: string | null
  gender?: string | null
}

export function sendWsMessage(
  ws: WebSocket,
  content: string,
  conversationId: string | null,
  session?: ChatSessionContext | null,
) {
  const payload: Record<string, unknown> = {
    type: 'message',
    content,
    conversation_id: conversationId,
  }
  if (session?.agent_id) payload.agent_id = session.agent_id
  if (session?.entry_mode) payload.entry_mode = session.entry_mode
  if (session?.persona) payload.persona = session.persona
  if (session?.character_name) payload.character_name = session.character_name
  if (session?.gender) payload.gender = session.gender
  ws.send(JSON.stringify(payload))
}

// --- Chess game ---
export type ChessStateResponse = {
  session_id: string
  status: 'active' | 'finished'
  user_color: 'white' | 'black'
  bot_elo: number
  turn: 'white' | 'black'
  fen: string
  legal_moves: string[]
  moves_count: number
  moves_log?: Array<{ ply: number; side: 'user' | 'bot'; san: string; uci: string }>
  last_move: {
    side: 'user' | 'bot'
    uci: string
    san: string
    material_delta: number
    fen_after: string
  } | null
  result: string | null
  winner: 'user' | 'bot' | 'draw' | null
}

export type ChessReviewResponse = {
  session_id: string
  status: 'active' | 'finished'
  review_text: string
  stats: {
    result: string
    user_moves: number
    captures: number
    checks: number
    castles: number
    inaccuracy_like_moves: number
    mistake_like_moves: number
    blunder_like_moves: number
    avg_eval_delta_cp: number
    /** Trung bình centipawn loss (khi có Stockfish phân tích từng nước). */
    avg_cp_loss?: number
    engine_analysis_available?: boolean
    eval_method?: 'stockfish_cp_loss' | 'material_delta_heuristic' | string
    best_move_san: string | null
    best_move_gain: number | null
    key_mistakes: Array<{
      san: string
      uci: string
      eval_delta_cp?: number
      cp_loss?: number
      material_delta?: number
      best_move_san?: string
      best_move_uci?: string
      classification?: string
    }>
    training_focus: string[]
    user_move_analysis?: Array<{
      ply: number
      san: string
      uci: string
      cp_loss: number
      classification: string
      best_move_san: string
      best_move_uci: string
      eval_after_played_cp: number
      eval_after_best_cp: number
    }>
    engine_insights?: Array<{
      ply?: number
      your_move_san?: string | null
      your_move_uci?: string
      best_move_san?: string
      best_move_uci?: string
      cp_loss?: number
      classification?: string
      engine_top_moves: Array<{ rank: number; san: string; eval_hint: string | null }>
    }>
    move_sequence?: Array<{ ply: number; side: string; san: string }>
    move_sequence_text?: string
  }
}

// --- Caro (gomoku-style) ---
export type CaroStateResponse = {
  session_id: string
  status: 'active' | 'finished'
  n: number
  k: number
  user_stone: 'x' | 'o'
  bot_stone: 'x' | 'o'
  turn: 'user' | 'bot' | 'none'
  board: (string | null)[][]
  winner: 'user' | 'bot' | 'draw' | null
  result: string | null
  moves_count: number
  moves_log: Array<{ side: string; row: number; col: number; stone?: string }>
}

/** Mirrors `services/core/api/caro.py` `_review_stats_caro` (+ optional `move_sequence_text`). */
export type CaroReviewStats = {
  grid_n: number
  win_k: number
  user_moves: number
  bot_moves: number
  total_moves: number
  winner: string | null
  result: string | null
  user_best_run: number
  opening_near_center: boolean
  move_sequence: Array<{ ply: number; side?: string; row?: number; col?: number }>
  move_sequence_text?: string
}

export type CaroReviewResponse = {
  session_id: string
  status: string
  review_text: string
  stats: CaroReviewStats
}

export async function caroNew(gridSize: number, userStone: 'x' | 'o', winLength?: number) {
  const body: Record<string, unknown> = { grid_size: gridSize, user_stone: userStone }
  if (winLength != null && winLength > 0) body.win_length = winLength
  const res = await fetch(`${API_BASE}/games/caro/new`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  })
  return handleResponse<CaroStateResponse>(res)
}

export async function caroMove(sessionId: string, row: number, col: number) {
  const res = await fetch(`${API_BASE}/games/caro/move`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ session_id: sessionId, row, col }),
  })
  return handleResponse<CaroStateResponse>(res)
}

export async function caroState(sessionId: string) {
  const res = await fetch(`${API_BASE}/games/caro/state/${sessionId}`, {
    headers: headers(),
  })
  return handleResponse<CaroStateResponse>(res)
}

export async function caroReview(sessionId: string) {
  const res = await fetch(`${API_BASE}/games/caro/review`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ session_id: sessionId }),
  })
  return handleResponse<CaroReviewResponse>(res)
}

export async function chessNew(userColor: 'white' | 'black', botElo = 800) {
  const res = await fetch(`${API_BASE}/games/chess/new`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ user_color: userColor, bot_elo: botElo }),
  })
  return handleResponse<ChessStateResponse>(res)
}

export async function chessState(sessionId: string) {
  const res = await fetch(`${API_BASE}/games/chess/state/${sessionId}`, {
    headers: headers(),
  })
  return handleResponse<ChessStateResponse>(res)
}

export async function chessMove(sessionId: string, moveUci: string) {
  const res = await fetch(`${API_BASE}/games/chess/move`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ session_id: sessionId, move_uci: moveUci }),
  })
  return handleResponse<ChessStateResponse>(res)
}

export async function chessReview(sessionId: string) {
  const res = await fetch(`${API_BASE}/games/chess/review`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ session_id: sessionId }),
  })
  return handleResponse<ChessReviewResponse>(res)
}

export type ChessBotInfo = {
  engine: string
  stockfish_configured: boolean
  elo_range: { min: number; max: number }
  play: Record<string, string>
  note: string
}

export type GamePlatformsResponse = {
  integrations: Array<{
    id: string
    kind: string
    description: string
    docs: string
    endpoint?: string
    endpoints?: Record<string, string>
  }>
  local_bot: ChessBotInfo
}

export async function chessBotInfo() {
  const res = await fetch(`${API_BASE}/games/chess/bot`, { headers: headers() })
  return handleResponse<ChessBotInfo>(res)
}

export async function gamePlatforms() {
  const res = await fetch(`${API_BASE}/games/platforms`, { headers: headers() })
  return handleResponse<GamePlatformsResponse>(res)
}

// --- Auth ---
export async function register(username: string, email: string, password: string) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: headers(false),
    body: JSON.stringify({ username, email, password }),
  })
  return handleResponse(res)
}

export async function login(username: string, password: string) {
  const form = new URLSearchParams({ username, password })
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  })
  const data = await handleResponse<{ access_token: string; token_type: string }>(res)
  localStorage.setItem('access_token', data.access_token)
  return data
}

export async function loginWithGoogle(idToken: string) {
  const res = await fetch(`${API_BASE}/auth/google`, {
    method: 'POST',
    headers: headers(false),
    body: JSON.stringify({ id_token: idToken }),
  })
  const data = await handleResponse<{ access_token: string; token_type: string }>(res)
  localStorage.setItem('access_token', data.access_token)
  return data
}

export async function forgotPassword(email: string) {
  const res = await fetch(`${API_BASE}/auth/forgot-password`, {
    method: 'POST',
    headers: headers(false),
    body: JSON.stringify({ email: email.trim().toLowerCase() }),
  })
  return handleResponse<{ message: string }>(res)
}

export function logout() {
  localStorage.removeItem('access_token')
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

// --- Agent engagement (likes / plays) ---
export type AgentStatsResponse = {
  likes: number
  plays: number
  liked_by_me: boolean
}

export async function getAgentStats(agentId: string): Promise<AgentStatsResponse> {
  const res = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/stats`, {
    headers: headers(),
  })
  return handleResponse<AgentStatsResponse>(res)
}

export async function toggleAgentLike(agentId: string): Promise<AgentStatsResponse> {
  const res = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/like`, {
    method: 'POST',
    headers: headers(),
  })
  return handleResponse<AgentStatsResponse>(res)
}

/** Call when user opens chat for this agent (once per browser tab session). */
export async function recordAgentPlay(agentId: string): Promise<AgentStatsResponse> {
  const res = await fetch(`${API_BASE}/agents/${encodeURIComponent(agentId)}/play`, {
    method: 'POST',
    headers: headers(),
  })
  return handleResponse<AgentStatsResponse>(res)
}

// --- Chat ---
export async function sendMessage(
  message: string,
  conversationId: string | null,
  session?: ChatSessionContext | null,
) {
  const body: Record<string, unknown> = { message, conversation_id: conversationId }
  if (session?.agent_id) body.agent_id = session.agent_id
  if (session?.entry_mode) body.entry_mode = session.entry_mode
  if (session?.persona) body.persona = session.persona
  if (session?.character_name) body.character_name = session.character_name
  if (session?.gender) body.gender = session.gender
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify(body),
  })
  return handleResponse(res)
}

export async function getConversations() {
  const res = await fetch(`${API_BASE}/chat/conversations`, { headers: headers() })
  return handleResponse(res)
}

export async function getHistory(conversationId: string) {
  const res = await fetch(`${API_BASE}/chat/history/${conversationId}`, { headers: headers() })
  return handleResponse(res)
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/conversations/${conversationId}`, {
    method: 'DELETE',
    headers: headers(),
  })
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({})))?.detail ?? res.statusText
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
}

export type MemoryItem = {
  id: string
  type: string
  content: string
  created_at?: string | null
}

export async function getMemories(): Promise<MemoryItem[]> {
  const res = await fetch(`${API_BASE}/chat/memories`, { headers: headers() })
  return handleResponse<MemoryItem[]>(res)
}

export type DiaryEntryRow = {
  id: string
  content: string
  agent_id: string | null
  created_at: string
}

export async function getDiaryEntries(agentId?: string | null): Promise<DiaryEntryRow[]> {
  const q = agentId ? `?agent_id=${encodeURIComponent(agentId)}` : ''
  const res = await fetch(`${API_BASE}/diary${q}`, { headers: headers() })
  return handleResponse<DiaryEntryRow[]>(res)
}

export async function postDiaryEntry(content: string, agentId?: string | null): Promise<DiaryEntryRow> {
  const res = await fetch(`${API_BASE}/diary`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ content, agent_id: agentId ?? null }),
  })
  return handleResponse<DiaryEntryRow>(res)
}

export type AgentRelationship = {
  user_message_count: number
  relationship_level: number
  last_fun_fact_level_ack: number
  pending_fun_fact: boolean
}

export async function getAgentRelationship(agentId: string): Promise<AgentRelationship> {
  const res = await fetch(
    `${API_BASE}/chat/relationship?agent_id=${encodeURIComponent(agentId)}`,
    { headers: headers() },
  )
  return handleResponse<AgentRelationship>(res)
}

export async function ackAgentFunFact(agentId: string, level: number): Promise<void> {
  const res = await fetch(`${API_BASE}/chat/relationship/ack-fun-fact`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ agent_id: agentId, level }),
  })
  if (!res.ok) {
    const detail = (await res.json().catch(() => ({})))?.detail ?? res.statusText
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
}
