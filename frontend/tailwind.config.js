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
          DEFAULT: '#f0f6ff',
          hover: '#e0ecff',
          border: '#bfdbfe',
          text: '#1e3a5f',
          muted: '#64748b',
        },
        cream: {
          50: '#ffffff',
          100: '#f0f6ff',
          200: '#e0ecff',
        },
        accent: {
          DEFAULT: '#3b82f6',
          light: '#60a5fa',
          dark: '#1e40af',
          hover: '#2563eb',
        },
        chat: {
          user: '#dbeafe',
          assistant: '#ffffff',
          border: '#bfdbfe',
          input: '#f0f6ff',
        },
        vn: {
          stage: '#f0f6ff',
          stageLight: '#ffffff',
          dialogue: '#ffffff',
          dialogueBorder: '#bfdbfe',
          name: '#1e40af',
          nameGlow: '#3b82f6',
          text: '#1e3a5f',
          textDim: '#64748b',
          highlight: '#60a5fa',
          cooldown: '#3b82f6',
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
        vn: '0 0 60px -12px rgba(59, 130, 246, 0.25), 0 25px 50px -12px rgba(30, 58, 95, 0.15)',
        'vn-inner': 'inset 0 2px 20px 0 rgba(59, 130, 246, 0.08)',
        portrait: '0 25px 50px -12px rgba(30, 58, 95, 0.18), 0 0 0 1px rgba(59, 130, 246, 0.1)',
      },
    },
  },
  plugins: [],
}
