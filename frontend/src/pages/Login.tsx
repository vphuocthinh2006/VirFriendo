import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useGoogleSignIn } from '../hooks/useGoogleSignIn'
import AuthPageShell from '../components/AuthPageShell'
import GoogleGlyph from '../components/GoogleGlyph'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
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
      await login(username, password)
      navigate('/menu', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthPageShell title="Sign in" subtitle="Welcome back to VirFriendo">
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
          <span className="aid-auth-or__text">or</span>
          <span className="aid-auth-or__line" aria-hidden />
        </div>

        <form onSubmit={handleSubmit} className="aid-auth-form">
          {error ? <div className="aid-auth-msg aid-auth-msg--error">{error}</div> : null}

          <div className="aid-auth-field">
            <label htmlFor="login-user">Username</label>
            <input
              id="login-user"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="aid-auth-input"
              required
              autoComplete="username"
            />
          </div>

          <div className="aid-auth-field">
            <div className="aid-auth-label-row">
              <label htmlFor="login-pass">Password</label>
              <Link to="/forgot-password" className="aid-auth-forgot">
                Forgot password?
              </Link>
            </div>
            <input
              id="login-pass"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="aid-auth-input"
              required
              autoComplete="current-password"
            />
          </div>

          <button type="submit" disabled={loading} className="aid-cta-primary aid-auth-submit">
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <p className="aid-auth-footer-text">
          No account?{' '}
          <Link to="/register" className="aid-auth-footer-link">
            Create account
          </Link>
        </p>
      </div>
    </AuthPageShell>
  )
}
