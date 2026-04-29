/**
 * Full-pane loading: rabbit runs a circular path while the backend searches / streams.
 * `variant="inline"` — compact composer row (see `.vf-chat-rabbit-inline` in index.css).
 */
export default function ChatRabbitWait({
  phase,
  variant = 'overlay',
}: {
  phase: 'search' | 'writing'
  variant?: 'overlay' | 'inline'
}) {
  const label =
    phase === 'search'
      ? 'Đang tìm kiếm & chuẩn bị…'
      : 'Đang viết câu trả lời…'

  const rootClass =
    variant === 'inline'
      ? 'vf-chat-rabbit-inline vf-chat-rabbit-inline--only'
      : 'vf-chat-rabbit-overlay'

  return (
    <div
      className={rootClass}
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div className="vf-chat-rabbit-stage">
        <div className="vf-chat-rabbit-track" aria-hidden>
          <div className="vf-chat-rabbit-orbit">
            <div className="vf-chat-rabbit-sprite">
              <svg
                viewBox="0 0 64 64"
                className="vf-chat-rabbit-svg"
                xmlns="http://www.w3.org/2000/svg"
              >
                <ellipse cx="32" cy="38" rx="18" ry="14" fill="#e8dcc8" />
                <circle cx="32" cy="22" r="14" fill="#f5ebe0" />
                <ellipse cx="22" cy="14" rx="5" ry="12" fill="#f5ebe0" transform="rotate(-18 22 14)" />
                <ellipse cx="42" cy="14" rx="5" ry="12" fill="#f5ebe0" transform="rotate(18 42 14)" />
                <ellipse cx="26" cy="22" rx="3" ry="4" fill="#1a1510" />
                <ellipse cx="38" cy="22" rx="3" ry="4" fill="#1a1510" />
                <ellipse cx="32" cy="28" rx="4" ry="2.5" fill="#3b82f6" />
                <circle cx="28" cy="36" r="4" fill="#f0e6d8" />
                <circle cx="36" cy="36" r="4" fill="#f0e6d8" />
              </svg>
            </div>
          </div>
        </div>
        {variant === 'inline' ? (
          <span className="sr-only">{label}</span>
        ) : (
          <p className="vf-chat-rabbit-label">{label}</p>
        )}
      </div>
    </div>
  )
}
