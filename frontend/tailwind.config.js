/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        vn: ['"Noto Serif"', 'Georgia', 'serif'],
      },
      colors: {
        sidebar: {
          DEFAULT: '#060504',
          hover: '#0f0c08',
          border: '#2a2418',
          text: '#e7edf7',
          muted: '#9aa7bc',
        },
        cream: {
          50: '#060504',
          100: '#0a0806',
          200: '#0f0c08',
        },
        accent: {
          DEFAULT: '#c9a227',
          light: '#e8c547',
          dark: '#8b6914',
          hover: '#ddb92e',
        },
        chat: {
          user: '#0f0d08',
          assistant: '#060504',
          border: '#2a2418',
          input: '#080602',
        },
        vn: {
          stage: '#060504',
          stageLight: '#0f0c08',
          dialogue: '#080602',
          dialogueBorder: '#2a2418',
          name: '#f5e6c8',
          nameGlow: '#c9a227',
          text: '#f0ebe0',
          textDim: '#8f8575',
          highlight: '#e8c547',
          cooldown: '#c9a227',
        },
      },
      maxWidth: { chat: '48rem' },
      animation: {
        'vn-fade-in': 'vn-fade-in 0.5s ease-out forwards',
        'vn-slide-up': 'vn-slide-up 0.4s ease-out forwards',
        'vn-portrait-in': 'vn-portrait-in 0.6s ease-out forwards',
        'vn-glow': 'vn-glow 2.5s ease-in-out infinite',
        'vn-shimmer': 'vn-shimmer 0.6s ease-out forwards',
      },
      keyframes: {
        'vn-fade-in': { '0%': { opacity: 0 }, '100%': { opacity: 1 } },
        'vn-slide-up': { '0%': { opacity: 0, transform: 'translateY(12px)' }, '100%': { opacity: 1, transform: 'translateY(0)' } },
        'vn-portrait-in': { '0%': { opacity: 0, transform: 'scale(0.92)' }, '100%': { opacity: 1, transform: 'scale(1)' } },
        'vn-glow': { '0%, 100%': { opacity: 0.6 }, '50%': { opacity: 1 } },
        'vn-shimmer': { '0%': { opacity: 0.5 }, '100%': { opacity: 1 } },
      },
      boxShadow: {
        vn: '0 0 60px -12px rgba(0,0,0,0.4), 0 25px 50px -12px rgba(0,0,0,0.25)',
        'vn-inner': 'inset 0 2px 20px 0 rgba(0,0,0,0.15)',
        portrait: '0 25px 50px -12px rgba(0,0,0,0.35), 0 0 0 1px rgba(255,255,255,0.06)',
      },
    },
  },
  plugins: [],
}
