import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useGoogleSignIn } from '../hooks/useGoogleSignIn'
import AuthPageShell from '../components/AuthPageShell'
import GoogleGlyph from '../components/GoogleGlyph'

export default function Register() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { register } = useAuth()
  const navigate = useNavigate()
  const {
    ready: googleReady,
    loading: googleLoading,
    error: googleError,
    googleMountRef,
  } = useGoogleSignIn()

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await register({ username, email, password })
      navigate('/menu', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthPageShell title="Create account" subtitle="Sign up to chat and play games with AI">
      <div className="aid-auth-stack">
        <div className="aid-google-auth-wrap aid-auth-google-full">
          <div
            className={`aid-cta-google aid-auth-google-full aid-google-gsi-decoy${!googleReady ? ' aid-google-styled-cta--pending' : ''}`}
            aria-hidden
          >
            <span className="aid-cta-label aid-cta-label--row">
              <GoogleGlyph />
              {googleLoading ? 'CONNECTING…' : 'CONTINUE WITH GOOGLE'}
            </span>
          </div>
          <div
            ref={googleMountRef}
            className={`aid-google-gsi-overlay${!googleReady || googleLoading ? ' aid-google-gsi-overlay--blocked' : ''}`}
            aria-hidden
          />
        </div>
        {googleLoading ? <p className="aid-auth-msg">Signing in with Google…</p> : null}
        {googleError ? <p className="aid-auth-msg aid-auth-msg--error">{googleError}</p> : null}

        <div className="aid-auth-or" role="separator">
          <span className="aid-auth-or__line" aria-hidden />
          <span className="aid-auth-or__text">or sign up with email</span>
          <span className="aid-auth-or__line" aria-hidden />
        </div>

        <form onSubmit={handleSubmit} className="aid-auth-form">
          {error ? <div className="aid-auth-msg aid-auth-msg--error">{error}</div> : null}

          <div className="aid-auth-field">
            <label htmlFor="reg-user">Username</label>
            <input
              id="reg-user"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="aid-auth-input"
              required
              autoComplete="username"
            />
          </div>

          <div className="aid-auth-field">
            <label htmlFor="reg-email">Email</label>
            <input
              id="reg-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="aid-auth-input"
              required
              autoComplete="email"
            />
          </div>

          <div className="aid-auth-field">
            <label htmlFor="reg-pass">Password</label>
            <input
              id="reg-pass"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="aid-auth-input"
              required
              autoComplete="new-password"
            />
          </div>

          <button type="submit" disabled={loading} className="aid-cta-primary aid-auth-submit">
            {loading ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        <p className="aid-auth-footer-text">
          Already have an account?{' '}
          <Link to="/login" className="aid-auth-footer-link">
            Sign in
          </Link>
        </p>
      </div>
    </AuthPageShell>
  )
}
