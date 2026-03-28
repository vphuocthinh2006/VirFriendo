/** Google “G” mark for custom-styled Sign in with Google buttons */
export default function GoogleGlyph({ className }: { className?: string }) {
  return (
    <svg className={className ?? 'aid-auth-google-icon'} viewBox="0 0 48 48" aria-hidden focusable="false">
      <path
        fill="#EA4335"
        d="M24 9.5c3.1 0 5.9 1.1 8.1 3.1l6-6C34.5 3.2 29.6 1 24 1 14.6 1 6.5 6.4 2.6 14.3l7 5.4C11.4 13.8 17.2 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h12.7c-.5 2.8-2.1 5.3-4.5 6.9l7 5.4c4.1-3.8 6.3-9.4 6.3-16.3z"
      />
      <path
        fill="#FBBC05"
        d="M9.6 28.3c-.5-1.4-.8-2.8-.8-4.3s.3-2.9.8-4.3l-7-5.4C1 17.2 0 20.5 0 24s1 6.8 2.6 9.7l7-5.4z"
      />
      <path
        fill="#34A853"
        d="M24 47c6.5 0 11.9-2.1 15.9-5.8l-7-5.4c-2 1.4-4.5 2.2-8.9 2.2-6.8 0-12.6-4.3-14.7-10.2l-7 5.4C6.5 41.6 14.6 47 24 47z"
      />
    </svg>
  )
}
