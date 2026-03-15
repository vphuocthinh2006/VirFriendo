import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import * as api from '../services/api'
import type { ChatResponse, MessageItem } from '../types/chat'
import type { ConversationSummary } from '../types/chat'

const CHARACTER_NAME = 'tuq27'
const CHARACTER_SUBTITLE = 'ur dearest friend'

/** Cắt reply thành các đoạn ngắn (câu hoặc ~60 ký tự) để hiển thị từ từ như người thật. */
function splitIntoChunks(text: string): string[] {
  const t = (text || '').trim()
  if (!t) return []
  // Tách theo câu (. ! ? \n), giữ dấu
  const parts: string[] = []
  let rest = t
  const sentenceEnd = /([.!?]+\s*|\n+)/
  while (rest.length > 0) {
    const m = rest.match(sentenceEnd)
    if (m && m.index !== undefined) {
      const chunk = rest.slice(0, m.index + m[1].length).trim()
      if (chunk) parts.push(chunk)
      rest = rest.slice(m.index + m[1].length).trim()
    } else {
      if (rest.length > 60) {
        const space = rest.slice(0, 60).lastIndexOf(' ')
        const cut = space > 20 ? space : 60
        parts.push(rest.slice(0, cut).trim())
        rest = rest.slice(cut).trim()
      } else {
        if (rest) parts.push(rest)
        break
      }
    }
  }
  return parts.length ? parts : [t]
}

/** Chuẩn hóa tin từ history (DB): assistant có chunks + chỉ hiện chunk cuối (tin nhắn cuối khi bị split). */
function normalizeHistoryForDisplay(history: MessageItem[]): MessageItem[] {
  return history.map((msg) => {
    if (msg.role !== 'assistant' || !msg.content) return msg
    const chunks = splitIntoChunks(msg.content)
    const lastIdx = chunks.length > 0 ? chunks.length - 1 : 0
    return {
      ...msg,
      chunks: chunks.length > 0 ? chunks : undefined,
      visibleChunkIndex: chunks.length > 0 ? lastIdx : undefined,
    }
  })
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

function IconCall({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />
    </svg>
  )
}

function IconMenu({ className = 'w-5 h-5' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="1" />
      <circle cx="12" cy="5" r="1" />
      <circle cx="12" cy="19" r="1" />
    </svg>
  )
}

function IconGame({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M6 9h.01M6 15h.01M10 12h.01M15 9h.01M15 15h.01M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z" />
    </svg>
  )
}

function IconTrash({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
      <line x1="10" y1="11" x2="10" y2="17" />
      <line x1="14" y1="11" x2="14" y2="17" />
    </svg>
  )
}

function IconSparkle({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
    </svg>
  )
}

function IconInfo({ className = 'w-4 h-4' }: { className?: string }) {
  return (
    <svg className={className} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4M12 8h.01" />
    </svg>
  )
}

export default function Chat() {
  const [messages, setMessages] = useState<MessageItem[]>([])
  const [conversationId, setConversationId] = useState<string | null>(null)
  const [conversations, setConversations] = useState<ConversationSummary[]>([])
  const [conversationsLoading, setConversationsLoading] = useState(true)
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [menuOpen, setMenuOpen] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyMessages, setHistoryMessages] = useState<MessageItem[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  /** Số ký tự đã "nói" (đổi màu) trong câu hiện tại — kiểu karaoke, hết thì auto sang câu tiếp. */
  const [dialogueCharIndex, setDialogueCharIndex] = useState(0)
  const menuRef = useRef<HTMLDivElement>(null)
  const firstChunkTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const dialogueCharIndexRef = useRef(0)
  const messagesRef = useRef<MessageItem[]>([])

  const COOLDOWN_MS = 5000
  const CHAR_MS = 45
  messagesRef.current = messages
  dialogueCharIndexRef.current = dialogueCharIndex
  const { isAuth, loading: authLoading, logout } = useAuth()
  const navigate = useNavigate()

  useEffect(() => {
    if (!authLoading && !isAuth) navigate('/login', { replace: true })
  }, [isAuth, authLoading, navigate])

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
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false)
    }
    if (menuOpen) {
      document.addEventListener('click', handleClickOutside)
      return () => document.removeEventListener('click', handleClickOutside)
    }
  }, [menuOpen])

  // Sau 5s mới hiện chunk đầu (visibleChunkIndex -1 -> 0)
  useEffect(() => {
    const waiting = messages.find((m) => m.role === 'assistant' && m.chunks && m.visibleChunkIndex === -1)
    if (!waiting) return
    firstChunkTimeoutRef.current = setTimeout(() => {
      firstChunkTimeoutRef.current = null
      setMessages((prev) =>
        prev.map((m) =>
          m.id === waiting.id ? { ...m, visibleChunkIndex: 0 } : m
        )
      )
      setDialogueCharIndex(0)
      dialogueCharIndexRef.current = 0
    }, COOLDOWN_MS)
    return () => {
      if (firstChunkTimeoutRef.current) clearTimeout(firstChunkTimeoutRef.current)
      firstChunkTimeoutRef.current = null
    }
  }, [messages, COOLDOWN_MS])

  // Karaoke: từng chữ đổi màu, hết câu thì auto sang câu tiếp
  useEffect(() => {
    const list = messagesRef.current
    const last = list.length ? list[list.length - 1] : null
    if (!last || last.role !== 'assistant' || !last.chunks || last.visibleChunkIndex === undefined || last.visibleChunkIndex < 0) return
    const chunk = last.chunks[last.visibleChunkIndex]
    if (!chunk) return
    const len = chunk.length
    const current = dialogueCharIndexRef.current
    if (current >= len) {
      if (last.visibleChunkIndex < last.chunks.length - 1) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === last.id ? { ...m, visibleChunkIndex: last.visibleChunkIndex! + 1 } : m
          )
        )
        setDialogueCharIndex(0)
        dialogueCharIndexRef.current = 0
      }
      return
    }
    const t = setInterval(() => {
      const list2 = messagesRef.current
      const last2 = list2.length ? list2[list2.length - 1] : null
      if (!last2 || last2.id !== last.id || last2.role !== 'assistant' || !last2.chunks || last2.visibleChunkIndex === undefined || last2.visibleChunkIndex < 0) {
        clearInterval(t)
        return
      }
      const chunk2 = last2.chunks[last2.visibleChunkIndex]
      if (!chunk2) { clearInterval(t); return }
      const cur = dialogueCharIndexRef.current
      if (cur >= chunk2.length) {
        clearInterval(t)
        if (last2.visibleChunkIndex < last2.chunks.length - 1) {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === last2.id ? { ...m, visibleChunkIndex: last2.visibleChunkIndex! + 1 } : m
            )
          )
          setDialogueCharIndex(0)
          dialogueCharIndexRef.current = 0
        }
        return
      }
      dialogueCharIndexRef.current = cur + 1
      setDialogueCharIndex(cur + 1)
    }, CHAR_MS)
    return () => clearInterval(t)
  }, [messages, dialogueCharIndex])

  function revealNextChunk(messageId: string) {
    setMessages((prev) =>
      prev.map((m) => {
        if (m.id !== messageId || m.role !== 'assistant' || !m.chunks || m.visibleChunkIndex === undefined) return m
        if (m.visibleChunkIndex >= m.chunks.length - 1) return m
        return { ...m, visibleChunkIndex: m.visibleChunkIndex + 1 }
      })
    )
  }

  /** Click vùng dialogue: skip cooldown 5s và advance (chunk đầu hoặc chunk tiếp). Cursor không dùng pointer. */
  function handleDialogueClick() {
    if (messages.length === 0 || loading) return
    const last = messages[messages.length - 1]
    if (last.role !== 'assistant' || !last.chunks) return
    if (firstChunkTimeoutRef.current) {
      clearTimeout(firstChunkTimeoutRef.current)
      firstChunkTimeoutRef.current = null
    }
    if (last.visibleChunkIndex === -1) {
      setMessages((prev) =>
        prev.map((m) => (m.id === last.id ? { ...m, visibleChunkIndex: 0 } : m))
      )
      setDialogueCharIndex(0)
      dialogueCharIndexRef.current = 0
      return
    }
    if (last.visibleChunkIndex !== undefined && last.visibleChunkIndex < last.chunks.length - 1) {
      revealNextChunk(last.id)
      setDialogueCharIndex(0)
      dialogueCharIndexRef.current = 0
    }
  }

  function startNewChat() {
    setConversationId(null)
    setMessages([])
    setDialogueCharIndex(0)
    dialogueCharIndexRef.current = 0
    setError('')
    setMenuOpen(false)
  }

  async function selectConversation(id: string) {
    if (id === conversationId) return
    setError('')
    setConversationId(id)
    setMessages([])
    try {
      const history = (await api.getHistory(id)) as MessageItem[]
      const normalized = normalizeHistoryForDisplay(history)
      setMessages(normalized)
      const last = normalized[normalized.length - 1]
      if (last?.role === 'assistant' && last.chunks && last.visibleChunkIndex !== undefined) {
        const lastChunk = last.chunks[last.visibleChunkIndex]
        if (lastChunk) {
          setDialogueCharIndex(lastChunk.length)
          dialogueCharIndexRef.current = lastChunk.length
        }
      } else {
        setDialogueCharIndex(0)
        dialogueCharIndexRef.current = 0
      }
    } catch {
      setError('Không tải được lịch sử hội thoại')
    }
  }

  function openMenu(e: React.MouseEvent) {
    e.stopPropagation()
    setMenuOpen((v) => !v)
  }

  function handleMenuAction(action: string) {
    if (action === 'new-chat') {
      startNewChat()
      return
    }
    if (action === 'play-game') {
      setMenuOpen(false)
      // TODO: navigate to /game when game page exists
      alert('Tính năng Chơi game sẽ sớm có mặt!')
      return
    }
    if (action === 'delete') {
      if (!conversationId) {
        startNewChat()
        setMenuOpen(false)
        return
      }
      if (!window.confirm('Bạn có chắc muốn xóa hội thoại này? Không thể hoàn tác.')) {
        setMenuOpen(false)
        return
      }
      api.deleteConversation(conversationId).then(() => {
        setConversations((prev) => prev.filter((c) => c.id !== conversationId))
        startNewChat()
        setMenuOpen(false)
      }).catch((err) => {
        setError(err instanceof Error ? err.message : 'Không xóa được hội thoại')
        setMenuOpen(false)
      })
      return
    }
    if (action === 'mood') {
      setMenuOpen(false)
      alert('Nhật ký cảm xúc (Mood) sẽ sớm có mặt!')
      return
    }
    if (action === 'about') {
      setMenuOpen(false)
      alert(`${CHARACTER_NAME} — ${CHARACTER_SUBTITLE}. AI Anime Companion, luôn lắng nghe và đồng hành cùng bạn.`)
      return
    }
    if (action === 'history') {
      setMenuOpen(false)
      setHistoryOpen(true)
      if (conversationId) {
        setHistoryLoading(true)
        api.getHistory(conversationId)
          .then((list) => setHistoryMessages((list as MessageItem[]) || []))
          .catch(() => setHistoryMessages([]))
          .finally(() => setHistoryLoading(false))
      } else {
        setHistoryMessages([])
      }
      return
    }
    setMenuOpen(false)
  }

  async function handleSend(e: React.FormEvent) {
    e.preventDefault()
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setError('')

    const userMsg: MessageItem = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
    }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    try {
      const res = await api.sendMessage(text, conversationId) as ChatResponse
      setConversationId(res.conversation_id)
      const chunks = splitIntoChunks(res.reply)
      const assistantMsg: MessageItem = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: res.reply,
        chunks: chunks.length > 1 ? chunks : undefined,
        visibleChunkIndex: chunks.length > 1 ? -1 : undefined,
        detected_intent: res.detected_intent,
        detected_emotion: res.detected_emotion,
        avatar_action: res.avatar_action,
      }
      setMessages((prev) => [...prev, assistantMsg])
      setDialogueCharIndex(0)
      dialogueCharIndexRef.current = 0
      await fetchConversations()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Gửi tin nhắn thất bại')
    } finally {
      setLoading(false)
    }
  }

  function handleLogout() {
    logout()
    navigate('/', { replace: true })
  }

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-vn-stage">
        <div className="text-vn-textDim animate-vn-glow">Đang tải...</div>
      </div>
    )
  }

  return (
    <div className="flex h-screen bg-vn-stage">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 flex flex-col bg-sidebar border-r border-sidebar-border">
        <button
          onClick={startNewChat}
          className="mx-3 mt-3 flex items-center gap-2 rounded-lg border border-sidebar-border px-3 py-2.5 text-left text-sm text-sidebar-text hover:bg-sidebar-hover transition"
        >
          <span className="text-lg">+</span>
          New chat
        </button>
        <div className="flex-1 overflow-y-auto mt-2 px-2">
          {conversationsLoading ? (
            <div className="px-3 py-2 text-sidebar-muted text-sm">Đang tải...</div>
          ) : conversations.length === 0 ? (
            <div className="px-3 py-2 text-sidebar-muted text-sm">Chưa có hội thoại</div>
          ) : (
            <ul className="space-y-0.5">
              {conversations.map((c) => (
                <li key={c.id}>
                  <button
                    onClick={() => selectConversation(c.id)}
                    className={`w-full rounded-lg px-3 py-2.5 text-left text-sm truncate transition ${
                      conversationId === c.id ? 'bg-sidebar-hover text-sidebar-text' : 'text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-text'
                    }`}
                  >
                    {c.title || `Hội thoại ${c.id.slice(0, 8)}`}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="p-2 border-t border-sidebar-border">
          <button
            onClick={handleLogout}
            className="w-full rounded-lg px-3 py-2 text-left text-sm text-sidebar-muted hover:bg-sidebar-hover hover:text-sidebar-text transition"
          >
            Đăng xuất
          </button>
        </div>
      </aside>

      {/* Main chat area */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Header: compact, tone VN */}
        <header className="flex-shrink-0 flex items-center justify-between px-4 py-2.5 border-b border-vn-dialogueBorder/50 bg-vn-dialogue/80 backdrop-blur-sm">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex-shrink-0 w-9 h-9 rounded-full bg-vn-stageLight flex items-center justify-center text-vn-name ring-1 ring-white/10">
              <IconAvatar className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <h1 className="font-semibold text-vn-text truncate text-sm">{CHARACTER_NAME}</h1>
              <p className="text-xs text-vn-textDim truncate">{CHARACTER_SUBTITLE}</p>
            </div>
          </div>
          <div className="flex items-center gap-0.5">
            <button type="button" className="p-2 rounded-lg text-vn-textDim hover:bg-white/10 hover:text-vn-text transition" title="Gọi (sắp có)">
              <IconCall />
            </button>
            <div className="relative" ref={menuRef}>
              <button type="button" onClick={openMenu} className="p-2 rounded-lg text-vn-textDim hover:bg-white/10 hover:text-vn-text transition" title="Menu">
                <IconMenu />
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-full mt-1 z-50 min-w-[200px] rounded-xl border border-vn-dialogueBorder bg-vn-dialogue py-1 shadow-vn animate-vn-fade-in">
                  <button type="button" onClick={() => handleMenuAction('new-chat')} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-vn-text hover:bg-white/10 transition">
                    <span className="text-lg">+</span>
                    Tạo hội thoại mới
                  </button>
                  <button type="button" onClick={() => handleMenuAction('play-game')} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-vn-text hover:bg-white/10 transition">
                    <IconGame />
                    Chơi game
                  </button>
                  <button type="button" onClick={() => handleMenuAction('mood')} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-vn-text hover:bg-white/10 transition">
                    <IconSparkle />
                    Nhật ký cảm xúc
                  </button>
                  <button type="button" onClick={() => handleMenuAction('about')} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-vn-text hover:bg-white/10 transition">
                    <IconInfo />
                    Giới thiệu {CHARACTER_NAME}
                  </button>
                  <button type="button" onClick={() => handleMenuAction('history')} disabled={!conversationId} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-vn-text hover:bg-white/10 disabled:opacity-50 disabled:cursor-not-allowed transition">
                    <span aria-hidden>📜</span>
                    Lịch sử hội thoại
                  </button>
                  <hr className="my-1 border-vn-dialogueBorder" />
                  <button type="button" onClick={() => handleMenuAction('delete')} className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-red-400 hover:bg-red-500/20 transition"
                  >
                    <IconTrash />
                    Xóa hội thoại này
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Visual Novel: stage + portrait */}
        <div className="flex-1 flex flex-col items-center justify-end relative overflow-hidden vn-stage-bg">
              <div className="absolute inset-0 vn-stage-vignette" aria-hidden />
              {/* Portrait: avatar lớn, đổi “expression” theo avatar_action */}
              {(() => {
                const lastBot = [...messages].reverse().find((m) => m.role === 'assistant')
                const action = (lastBot as MessageItem | undefined)?.avatar_action
                const expressionClass =
                  action === 'serious_alert'
                    ? 'ring-2 ring-amber-400/70'
                    : action === 'comfort_sit'
                      ? 'ring-2 ring-sky-400/50'
                      : action === 'shocked_face'
                        ? 'ring-2 ring-rose-400/50'
                        : action === 'excited_wave'
                          ? 'ring-2 ring-amber-300/60'
                          : 'ring-2 ring-vn-nameGlow/40'
                return (
                  <div
                    className={`flex-shrink-0 w-44 h-44 rounded-full bg-vn-stageLight flex items-center justify-center text-vn-name shadow-portrait vn-portrait-glow transition-all duration-500 animate-vn-portrait-in ${expressionClass}`}
                  >
                    <IconAvatar className="w-28 h-28 drop-shadow-md" />
                  </div>
                )
              })()}
            </div>
            {/* Dialogue box — glass VN, click để skip (không pointer) */}
            <div
              className={`flex-shrink-0 vn-dialogue-glass border-t border-vn-dialogueBorder text-vn-text vn-dialogue-in ${messages.length > 0 && !loading && (() => {
                const last = messages[messages.length - 1]
                const canAdvance = last?.role === 'assistant' && last.chunks && (last.visibleChunkIndex === -1 || (last.visibleChunkIndex !== undefined && last.visibleChunkIndex < last.chunks.length - 1))
                return canAdvance ? 'cursor-default' : ''
              })()}`}
              onClick={handleDialogueClick}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleDialogueClick() } }}
            >
              <div className="mx-auto max-w-3xl px-5 pt-4 pb-3">
                <p className="text-sm font-semibold vn-name-tag mb-1.5">
                  {messages.length === 0
                    ? CHARACTER_NAME
                    : loading
                      ? CHARACTER_NAME
                      : messages[messages.length - 1].role === 'assistant'
                        ? CHARACTER_NAME
                        : 'Bạn'}
                </p>
                <p className="text-[15px] leading-relaxed min-h-[2.5rem] whitespace-pre-wrap font-vn">
                  {messages.length === 0
                    ? <span className="vn-text-pending">Nhập tin nhắn bên dưới để bắt đầu...</span>
                    : loading
                      ? <span className="vn-text-pending">đang trả lời...</span>
                      : (() => {
                          const last = messages[messages.length - 1]
                          if (last.role === 'user') return <span className="vn-text-spoken">{last.content}</span>
                          if (last.chunks && last.visibleChunkIndex === -1) return <span className="vn-text-pending">đang trả lời...</span>
                          if (last.chunks && last.visibleChunkIndex !== undefined && last.visibleChunkIndex >= 0) {
                            const idx = last.visibleChunkIndex
                            const chunkText = last.chunks[idx] ?? ''
                            const n = Math.min(dialogueCharIndex, chunkText.length)
                            return (
                              <>
                                <span className="vn-text-spoken">{chunkText.slice(0, n)}</span>
                                <span className="vn-text-pending">{chunkText.slice(n)}</span>
                              </>
                            )
                          }
                          return <span className="vn-text-spoken">{last.content}</span>
                        })()}
                </p>
                {(() => {
                  const last = messages[messages.length - 1]
                  const isInCooldown = last?.role === 'assistant' && last.chunks && last.visibleChunkIndex === -1
                  const cooldownKey = last?.id + '-first'
                  if (!isInCooldown) return null
                  return (
                    <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-vn-dialogueBorder/60">
                      <div key={cooldownKey} className="cooldown-bar h-full rounded-full bg-vn-cooldown/90" />
                    </div>
                  )
                })()}
              </div>
            </div>

        {error && (
          <div className="mx-auto max-w-3xl w-full px-4 pb-2 animate-vn-slide-up">
            <div className="rounded-xl bg-red-500/15 border border-red-400/40 text-red-300 text-sm px-4 py-2.5">
              {error}
            </div>
          </div>
        )}

        <div className="border-t border-vn-dialogueBorder/50 bg-vn-dialogue/60 backdrop-blur-sm p-4">
          <div className="mx-auto max-w-3xl w-full px-2">
            {messages.length === 0 && (
              <div className="flex flex-wrap gap-2 justify-center mb-3 animate-vn-fade-in">
                {['Chào bạn!', 'Kể cho mình nghe về One Piece', 'Hôm nay mình hơi mệt...'].map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => setInput(s)}
                    className="rounded-xl border border-vn-dialogueBorder bg-vn-stageLight/80 px-4 py-2.5 text-sm text-vn-text hover:bg-white/10 hover:border-vn-nameGlow/40 transition-all duration-200"
                  >
                    {s}
                  </button>
                ))}
              </div>
            )}
            <form onSubmit={handleSend} className="flex items-center gap-2 rounded-2xl border border-vn-dialogueBorder bg-vn-stage/80 focus-within:ring-2 focus-within:ring-vn-nameGlow/40 focus-within:border-vn-nameGlow/50 shadow-vn-inner pl-2 pr-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Nhập tin nhắn..."
                className="flex-1 min-w-0 bg-transparent px-3 py-3 text-vn-text placeholder-vn-textDim outline-none rounded-2xl"
                disabled={loading}
              />
              <button type="button" className="flex-shrink-0 p-2.5 rounded-xl text-vn-textDim hover:bg-white/10 hover:text-vn-text transition" title="Ghi âm (sắp có)">
                <IconMic className="w-5 h-5" />
              </button>
              <button type="submit" disabled={loading || !input.trim()} className="flex-shrink-0 p-2.5 rounded-xl text-vn-name hover:bg-vn-nameGlow/20 disabled:opacity-40 disabled:hover:bg-transparent transition" title="Gửi">
                <IconSend className="w-5 h-5" />
              </button>
            </form>
          </div>
        </div>
      </main>

      {/* Panel Lịch sử hội thoại (từ DB) */}
      {historyOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm animate-vn-fade-in" onClick={() => setHistoryOpen(false)}>
          <div className="bg-vn-dialogue rounded-2xl shadow-vn border border-vn-dialogueBorder w-full max-w-lg max-h-[80vh] flex flex-col vn-dialogue-in" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between px-4 py-3 border-b border-vn-dialogueBorder">
              <h2 className="font-semibold text-vn-text">Lịch sử hội thoại</h2>
              <button type="button" onClick={() => setHistoryOpen(false)} className="p-2 rounded-lg text-vn-textDim hover:bg-white/10 hover:text-vn-text transition">✕</button>
            </div>
            <div className="flex-1 overflow-y-auto p-4 space-y-3">
              {!conversationId ? (
                <p className="text-vn-textDim text-sm">Chọn hoặc bắt đầu một hội thoại để xem lịch sử.</p>
              ) : historyLoading ? (
                <p className="text-vn-textDim text-sm">Đang tải...</p>
              ) : historyMessages.length === 0 ? (
                <p className="text-vn-textDim text-sm">Chưa có tin nhắn trong hội thoại này.</p>
              ) : (
                historyMessages.map((msg) => (
                  <div key={msg.id} className={`rounded-xl px-3 py-2 text-sm ${msg.role === 'user' ? 'bg-vn-nameGlow/15 ml-8 border border-vn-nameGlow/30' : 'bg-vn-stageLight/80 mr-8 border border-vn-dialogueBorder'}`}>
                    <p className="font-medium vn-name-tag mb-0.5">{msg.role === 'user' ? 'Bạn' : CHARACTER_NAME}</p>
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
