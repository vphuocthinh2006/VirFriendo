import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import LandingTopbar from './LandingTopbar'
import { CHAT_GATE_GAMES } from '../data/chatGames'

const CHARACTER_STEP_QUESTIONS = [
  "What is your character's name?",
  "What's your gender?",
  'Describe your persona.',
] as const

function KaraokeQuestion({ text }: { text: string }) {
  const chars = useMemo(() => Array.from(text), [text])
  return (
    <h2 className="chat-entry-char-karaoke-title" aria-label={text}>
      {chars.map((ch, i) => (
        <span
          key={`${i}-${ch}`}
          className="chat-entry-karaoke-char"
          style={{ animationDelay: `${i * 0.045}s` }}
        >
          {ch === ' ' ? '\u00a0' : ch}
        </span>
      ))}
    </h2>
  )
}

function IconArrowRight({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

export type CharacterFormData = {
  name: string
  /** male | female | or free text when user picked Custom */
  gender: string
  persona: string
}

type Panel = 'main' | 'games' | 'character'

type Props = {
  agentDisplayName: string
  onQuickstart: () => void
  onCharacterComplete: (data: CharacterFormData) => void
  /** Deep-link into /chat with ?tab=game&game=… after picking a title */
  onPickGame?: (gameId: string) => void
}

function IconPlay({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <polygon points="5 3 19 12 5 21 5 3" />
    </svg>
  )
}

function IconUserPlus({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
      <circle cx="9" cy="7" r="4" />
      <line x1="19" x2="19" y1="8" y2="14" />
      <line x1="22" x2="16" y1="11" y2="11" />
    </svg>
  )
}

function IconGamepad({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <line x1="6" x2="10" y1="12" y2="12" />
      <line x1="8" x2="8" y1="10" y2="14" />
      <line x1="15" x2="15.01" y1="13" y2="13" />
      <line x1="18" x2="18.01" y1="11" y2="11" />
      <rect width="20" height="12" x="2" y="6" rx="2" />
    </svg>
  )
}

export default function ChatEntryGate({ agentDisplayName, onQuickstart, onCharacterComplete, onPickGame }: Props) {
  const [panel, setPanel] = useState<Panel>('main')
  const [step, setStep] = useState(1)
  const [name, setName] = useState('')
  const [gender, setGender] = useState<'male' | 'female' | 'custom'>('male')
  const [customGender, setCustomGender] = useState('')
  const [persona, setPersona] = useState('')

  function resetCharacter() {
    setStep(1)
    setName('')
    setGender('male')
    setCustomGender('')
    setPersona('')
  }

  function handleCharacterNext() {
    if (step === 1) {
      if (!name.trim()) return
      setStep(2)
      return
    }
    if (step === 2) {
      setStep(3)
      return
    }
    if (step === 3) {
      if (!persona.trim()) return
      const g = gender === 'custom' ? (customGender.trim() || 'custom') : gender
      onCharacterComplete({ name: name.trim(), gender: g, persona: persona.trim() })
      resetCharacter()
      setPanel('main')
    }
  }

  function handleCharacterBack() {
    if (step > 1) setStep((s) => s - 1)
    else {
      resetCharacter()
      setPanel('main')
    }
  }

  return (
    <div className="chat-entry-root">
      <LandingTopbar />

      <div className="chat-entry-body">
        {panel === 'main' && (
          <>
            <p className="chat-entry-eyebrow">Choose One…</p>
            <p className="chat-entry-agent-line">
              Chat with <span className="chat-entry-agent-name">{agentDisplayName}</span>
            </p>

            <div className="chat-entry-cards">
              <button type="button" className="chat-entry-card" onClick={onQuickstart}>
                <IconPlay className="chat-entry-card-icon" />
                <span className="chat-entry-card-label">Quickstart</span>
              </button>
              <button type="button" className="chat-entry-card" onClick={() => setPanel('games')}>
                <IconGamepad className="chat-entry-card-icon" />
                <span className="chat-entry-card-label">Play games</span>
              </button>
              <button
                type="button"
                className="chat-entry-card"
                onClick={() => {
                  resetCharacter()
                  setPanel('character')
                }}
              >
                <IconUserPlus className="chat-entry-card-icon" />
                <span className="chat-entry-card-label">Create your character</span>
              </button>
            </div>

            <Link to="/menu" className="chat-entry-back">
              ← Back to models
            </Link>
          </>
        )}

        {panel === 'games' && (
          <div className="chat-entry-subbox">
            <div className="chat-entry-subbox-head">
              <h2 className="chat-entry-subbox-title">Play games</h2>
              <button type="button" className="chat-entry-subbox-close" onClick={() => setPanel('main')}>
                ✕
              </button>
            </div>
            <p className="chat-entry-subbox-hint">Pick a game — full play stays inside chat after you start.</p>
            <ul className="chat-entry-game-grid">
              {CHAT_GATE_GAMES.map((g) => (
                <li key={g.id} className="chat-entry-game-tile">
                  <button
                    type="button"
                    className="chat-entry-game-tile-btn"
                    disabled={!onPickGame}
                    onClick={() => onPickGame?.(g.id)}
                  >
                    <div className="chat-entry-game-img-wrap">
                      <div className={`vf-game-card__art vf-game-card__art--${g.id} chat-entry-game-thumb`} aria-hidden />
                    </div>
                    <span className="chat-entry-game-name">{g.name}</span>
                  </button>
                </li>
              ))}
            </ul>
            <button type="button" className="chat-entry-subbox-done" onClick={() => setPanel('main')}>
              Back
            </button>
          </div>
        )}

        {panel === 'character' && (
          <div className="chat-entry-char-shell">
            <button
              type="button"
              className="chat-entry-char-backlink chat-entry-char-backlink--corner"
              onClick={handleCharacterBack}
            >
              {step === 1 ? 'Cancel' : 'Back'}
            </button>
            <button
              type="button"
              className="chat-entry-char-close"
              onClick={() => {
                resetCharacter()
                setPanel('main')
              }}
              aria-label="Close"
            >
              ✕
            </button>

            <div key={step} className="chat-entry-char-step">
              {(() => {
                const q = CHARACTER_STEP_QUESTIONS[step - 1]
                const fieldDelay = Math.min(q.length * 0.045 + 0.16, 1.2)
                return (
                  <>
                    <p className="chat-entry-char-step-badge">Step {step} of 3</p>
                    <KaraokeQuestion text={q} />

                    <div
                      className="chat-entry-char-after-karaoke"
                      style={{ animationDelay: `${fieldDelay}s` }}
                    >
                      {step === 1 && (
                        <div className="chat-entry-char-field">
                          <input
                            id="char-name"
                            className="chat-entry-char-input"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="Type here…"
                            autoComplete="off"
                          />
                        </div>
                      )}

                      {step === 2 && (
                        <div className="chat-entry-char-field">
                          <div className="chat-entry-gender-row chat-entry-gender-row--minimal">
                            {(['male', 'female', 'custom'] as const).map((g) => (
                              <button
                                key={g}
                                type="button"
                                className={`chat-entry-gender-btn${gender === g ? ' chat-entry-gender-btn--active' : ''}`}
                                onClick={() => setGender(g)}
                              >
                                {g === 'custom' ? 'Custom' : g.charAt(0).toUpperCase() + g.slice(1)}
                              </button>
                            ))}
                          </div>
                          {gender === 'custom' && (
                            <input
                              className="chat-entry-char-input chat-entry-char-input--mt"
                              value={customGender}
                              onChange={(e) => setCustomGender(e.target.value)}
                              placeholder="Describe (optional)"
                              autoComplete="off"
                            />
                          )}
                        </div>
                      )}

                      {step === 3 && (
                        <div className="chat-entry-char-field">
                          <textarea
                            id="char-persona"
                            className="chat-entry-char-textarea"
                            value={persona}
                            onChange={(e) => setPersona(e.target.value)}
                            placeholder="Type here…"
                            rows={6}
                          />
                        </div>
                      )}

                      <div className="chat-entry-char-actions">
                        <button type="button" className="chat-entry-char-next" onClick={handleCharacterNext}>
                          <span>{step === 3 ? 'Start chat' : 'Next'}</span>
                          <IconArrowRight className="chat-entry-char-next-icon" />
                        </button>
                      </div>
                    </div>
                  </>
                )
              })()}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
