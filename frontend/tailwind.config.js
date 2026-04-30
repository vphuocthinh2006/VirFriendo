/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Pixelify Sans"', 'Inter', 'system-ui', '-apple-system', 'sans-serif'],
        pixel: ['"Pixelify Sans"', 'monospace'],
        display: ['Cinzel', 'Georgia', 'serif'],
        vn: ['"Pixelify Sans"', 'monospace'],
      },
      colors: {
        sidebar: {
          DEFAULT: '#fff9e6',
          hover: '#fdf4d4',
          border: '#a6d17d',
          text: '#1a1a1a',
          muted: '#6b6b6b',
        },
        cream: {
          50: '#ffffff',
          100: '#fff9e6',
          200: '#fdf4d4',
        },
        accent: {
          DEFAULT: '#a6d17d',
          light: '#b8dc92',
          dark: '#7ba94f',
          hover: '#94c269',
        },
        fanhua: {
          red: '#fa6255',
          'red-bright': '#fc7d70',
          yellow: '#fdcb46',
          green: '#a6d17d',
          'green-light': '#b8dc92',
          'green-deep': '#7ba94f',
          cream: '#fff9e6',
          'cream-deep': '#fdf4d4',
        },
        chat: {
          user: '#fff0c0',
          assistant: '#ffffff',
          border: '#a6d17d',
          input: '#fff9e6',
        },
        vn: {
          stage: '#fff9e6',
          stageLight: '#ffffff',
          dialogue: '#ffffff',
          dialogueBorder: '#a6d17d',
          name: '#fa6255',
          nameGlow: '#fdcb46',
          text: '#1a1a1a',
          textDim: '#6b6b6b',
          highlight: '#fdcb46',
          cooldown: '#a6d17d',
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
        vn: '0 0 60px -12px rgba(166, 209, 125, 0.3), 0 25px 50px -12px rgba(26, 26, 26, 0.15)',
        'vn-inner': 'inset 0 2px 20px 0 rgba(166, 209, 125, 0.1)',
        portrait: '0 25px 50px -12px rgba(26, 26, 26, 0.18), 0 0 0 1px rgba(166, 209, 125, 0.2)',
      },
    },
  },
  plugins: [],
}
