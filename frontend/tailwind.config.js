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
          DEFAULT: '#fff8ec',
          hover: '#f5e6d0',
          border: '#b0d4cf',
          text: '#2a1f12',
          muted: '#8b7355',
        },
        cream: {
          50: '#ffffff',
          100: '#fff8ec',
          200: '#f5e6d0',
        },
        accent: {
          DEFAULT: '#66bcb4',
          light: '#88cec7',
          dark: '#3a8b82',
          hover: '#4fa89f',
        },
        petzen: {
          teal: '#66bcb4',
          'teal-bright': '#88cec7',
          'teal-deep': '#3a8b82',
          orange: '#ecb02b',
          'orange-bright': '#f5c451',
          yellow: '#edc55b',
          cream: '#fff8ec',
          'cream-2': '#f5e6d0',
          'cream-3': '#e8ccad',
        },
        chat: {
          user: '#f5e6d0',
          assistant: '#fff8ec',
          border: '#b0d4cf',
          input: '#fff8ec',
        },
        vn: {
          stage: '#fff8ec',
          stageLight: '#ffffff',
          dialogue: '#ffffff',
          dialogueBorder: '#b0d4cf',
          name: '#3a8b82',
          nameGlow: '#ecb02b',
          text: '#2a1f12',
          textDim: '#8b7355',
          highlight: '#edc55b',
          cooldown: '#66bcb4',
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
        vn: '0 0 60px -12px rgba(102, 188, 180, 0.32), 0 25px 50px -12px rgba(42, 31, 18, 0.15)',
        'vn-inner': 'inset 0 2px 20px 0 rgba(102, 188, 180, 0.1)',
        portrait: '0 25px 50px -12px rgba(42, 31, 18, 0.2), 0 0 0 1px rgba(102, 188, 180, 0.22)',
      },
    },
  },
  plugins: [],
}
