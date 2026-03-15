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
          DEFAULT: '#1a1917',
          hover: '#252320',
          border: '#2d2a27',
          text: '#f5f0eb',
          muted: '#9c958c',
        },
        cream: {
          50: '#fdfbf9',
          100: '#faf6f2',
          200: '#f2ebe3',
        },
        accent: {
          DEFAULT: '#c4a092',
          light: '#e8d9d2',
          dark: '#9a7b6f',
          hover: '#b08f82',
        },
        chat: {
          user: '#e8dfda',
          assistant: '#fdfbf9',
          border: '#e5ded8',
          input: '#f2ebe3',
        },
        vn: {
          stage: '#2c2520',
          stageLight: '#3d342e',
          dialogue: '#1e1b18',
          dialogueBorder: '#3d3630',
          name: '#e8c4a8',
          nameGlow: '#d4a574',
          text: '#f0e6dc',
          textDim: '#8a7f75',
          highlight: '#e8c4a0',
          cooldown: '#c9a078',
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
