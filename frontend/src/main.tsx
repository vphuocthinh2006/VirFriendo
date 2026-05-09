import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ThemeContext, useThemeProvider } from './hooks/useTheme'

function Root() {
  const themeCtx = useThemeProvider()
  return (
    <ThemeContext.Provider value={themeCtx}>
      <App />
    </ThemeContext.Provider>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <Root />
    </ErrorBoundary>
  </StrictMode>
)
