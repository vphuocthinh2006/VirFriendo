import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/chat', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Đăng nhập thất bại')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-cream-100">
      <div className="w-full max-w-sm rounded-2xl border border-chat-border bg-cream-50 p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-stone-800 mb-6 text-center">Đăng nhập</h1>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="text-sm text-red-600 bg-red-50/80 rounded-lg px-3 py-2">{error}</div>
          )}
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Tên đăng nhập</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full rounded-xl border border-chat-border px-3 py-2.5 text-stone-800 bg-cream-50 focus:ring-2 focus:ring-accent/40 focus:border-accent/50 outline-none"
              required
              autoComplete="username"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-stone-700 mb-1">Mật khẩu</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-xl border border-chat-border px-3 py-2.5 text-stone-800 bg-cream-50 focus:ring-2 focus:ring-accent/40 focus:border-accent/50 outline-none"
              required
              autoComplete="current-password"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 rounded-xl bg-accent text-cream-50 text-sm font-medium hover:bg-accent-hover disabled:opacity-50 transition"
          >
            {loading ? 'Đang đăng nhập...' : 'Đăng nhập'}
          </button>
        </form>
        <p className="mt-6 text-center text-sm text-stone-500">
          Chưa có tài khoản?{' '}
          <Link to="/register" className="text-accent-dark font-medium hover:underline">
            Đăng ký
          </Link>
        </p>
      </div>
    </div>
  )
}
