import { useState } from 'react'
import { Link } from 'react-router-dom'
import * as api from '../services/api'
import AuthPageShell from '../components/AuthPageShell'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setMessage('')
    setLoading(true)
    try {
      const res = await api.forgotPassword(email)
      setMessage(res.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not send request')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthPageShell
      title="Forgot password"
      subtitle="Enter the email you registered with — we will send instructions when email delivery is enabled."
    >
      <div className="aid-auth-stack">
        <form onSubmit={handleSubmit} className="aid-auth-form">
          {error ? <div className="aid-auth-msg aid-auth-msg--error">{error}</div> : null}
          {message ? <div className="aid-auth-msg aid-auth-msg--ok">{message}</div> : null}

          <div className="aid-auth-field">
            <label htmlFor="forgot-email">Email</label>
            <input
              id="forgot-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="aid-auth-input"
              required
              autoComplete="email"
            />
          </div>

          <button type="submit" disabled={loading} className="aid-cta-primary aid-auth-submit">
            {loading ? 'Sending...' : 'Send request'}
          </button>
        </form>

        <p className="aid-auth-footer-text">
          <Link to="/login" className="aid-auth-footer-link">
            ← Back to sign in
          </Link>
          {' · '}
          <Link to="/register" className="aid-auth-footer-link">
            Create account
          </Link>
        </p>
      </div>
    </AuthPageShell>
  )
}
