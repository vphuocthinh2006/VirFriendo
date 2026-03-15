const API_BASE = import.meta.env.VITE_API_URL || ''

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

export function logout() {
  localStorage.removeItem('access_token')
}

export function isAuthenticated(): boolean {
  return !!getToken()
}

// --- Chat ---
export async function sendMessage(message: string, conversationId: string | null) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ message, conversation_id: conversationId }),
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
