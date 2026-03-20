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
          DEFAULT: '#201417', // deep wine
          hover: '#2a1a1f',
          border: '#3a232a',
          text: '#fff5f2',
          muted: '#c7a7a8',
        },
        cream: {
          50: '#fef9f7',
          100: '#fbeee9',
          200: '#f3ddd6',
        },
        accent: {
          DEFAULT: '#d46b6b', // soft rose red
          light: '#f2b0b0',
          dark: '#9b4346',
          hover: '#e07c7c',
        },
        chat: {
          user: '#f7e3de',
          assistant: '#fef9f7',
          border: '#f0d4ce',
          input: '#f3ddd6',
        },
        vn: {
          stage: '#1b1114', // dark wine base
          stageLight: '#2b171c',
          dialogue: '#140f12',
          dialogueBorder: '#3a232a',
          name: '#ffd8c2',
          nameGlow: '#ff9b7c',
          text: '#fff4ec',
          textDim: '#b19191',
          highlight: '#ffd0b3',
          cooldown: '#ffb28a',
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
