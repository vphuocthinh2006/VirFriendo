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
          DEFAULT: '#f5f9ff',
          hover: '#e8efff',
          border: '#abc4ff',
          text: '#1a1a1a',
          muted: '#6b6b6b',
        },
        cream: {
          50: '#ffffff',
          100: '#f5f9ff',
          200: '#e8efff',
        },
        accent: {
          DEFAULT: '#4849e8',
          light: '#6c6dee',
          dark: '#2e2fc9',
          hover: '#3a3bd8',
        },
        onme: {
          blue: '#4849e8',
          'blue-bright': '#6c6dee',
          'blue-deep': '#2e2fc9',
          lime: '#ddf344',
          'lime-bright': '#ecf566',
          periwinkle: '#abc4ff',
          bg: '#f5f9ff',
          'bg-2': '#e8efff',
        },
        chat: {
          user: '#e8efff',
          assistant: '#ffffff',
          border: '#abc4ff',
          input: '#f5f9ff',
        },
        vn: {
          stage: '#f5f9ff',
          stageLight: '#ffffff',
          dialogue: '#ffffff',
          dialogueBorder: '#abc4ff',
          name: '#4849e8',
          nameGlow: '#ddf344',
          text: '#1a1a1a',
          textDim: '#6b6b6b',
          highlight: '#ddf344',
          cooldown: '#4849e8',
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
        vn: '0 0 60px -12px rgba(72, 73, 232, 0.3), 0 25px 50px -12px rgba(26, 26, 26, 0.15)',
        'vn-inner': 'inset 0 2px 20px 0 rgba(72, 73, 232, 0.1)',
        portrait: '0 25px 50px -12px rgba(26, 26, 26, 0.18), 0 0 0 1px rgba(72, 73, 232, 0.2)',
      },
    },
  },
  plugins: [],
}
