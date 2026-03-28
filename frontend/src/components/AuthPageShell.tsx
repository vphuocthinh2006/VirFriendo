import { Link } from 'react-router-dom'
import LandingTopbar from './LandingTopbar'

type Props = {
  title: string
  subtitle?: string
  children: React.ReactNode
}

export default function AuthPageShell({ title, subtitle, children }: Props) {
  return (
    <div className="aid-root aid-auth-page" id="top">
      <LandingTopbar />

      <main className="aid-auth-layout">
        <div className="aid-auth-back-row">
          <Link to="/" className="aid-auth-back-link">
            ← Home
          </Link>
        </div>

        <div className="aid-auth-card">
          <div className="aid-auth-card__rim" aria-hidden />
          <h1 className="aid-auth-title">{title}</h1>
          {subtitle ? <p className="aid-auth-subtitle">{subtitle}</p> : null}
          {children}
        </div>
      </main>
    </div>
  )
}
