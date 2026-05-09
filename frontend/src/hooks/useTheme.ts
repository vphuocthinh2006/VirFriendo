import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'pally-theme'

function getSystemTheme(): Theme {
  if (typeof window === 'undefined') return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function getInitialTheme(): Theme {
  if (typeof window === 'undefined') return 'light'
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored === 'dark' || stored === 'light') return stored
  } catch {}
  return getSystemTheme()
}

function applyTheme(theme: Theme) {
  document.documentElement.dataset.theme = theme
  // Update meta theme-color
  const meta = document.querySelector('meta[name="theme-color"]')
  if (meta) {
    meta.setAttribute('content', theme === 'dark' ? '#121212' : '#fff8ec')
  }
}

function applyThemeWithTransition(theme: Theme) {
  document.documentElement.classList.add('theme-transition')
  applyTheme(theme)
  // Remove transition class after animation completes
  setTimeout(() => {
    document.documentElement.classList.remove('theme-transition')
  }, 300)
}

interface ThemeContextValue {
  theme: Theme
  toggleTheme: () => void
  setTheme: (t: Theme) => void
}

export const ThemeContext = createContext<ThemeContextValue>({
  theme: 'light',
  toggleTheme: () => {},
  setTheme: () => {},
})

export function useThemeProvider() {
  const [theme, setThemeState] = useState<Theme>(getInitialTheme)

  // Apply on mount only (subsequent changes handled by setTheme with transition)
  useEffect(() => {
    applyTheme(theme)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Listen for system preference changes (only if no explicit choice stored)
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    function handler(e: MediaQueryListEvent) {
      try {
        if (!localStorage.getItem(STORAGE_KEY)) {
          const next = e.matches ? 'dark' : 'light'
          setThemeState(next)
        }
      } catch {}
    }
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  const setTheme = useCallback((t: Theme) => {
    setThemeState(t)
    applyThemeWithTransition(t)
    try {
      localStorage.setItem(STORAGE_KEY, t)
    } catch {}
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }, [theme, setTheme])

  return useMemo(() => ({ theme, toggleTheme, setTheme }), [theme, toggleTheme, setTheme])
}

export function useTheme() {
  return useContext(ThemeContext)
}
