import { useEffect, useRef, useState } from 'react'
import { useAuth } from './useAuth'
import { LOADING_MIN_MS } from '../constants/loading'

/**
 * Overlay sau khi auth xong nhưng vẫn giữ tối thiểu `LOADING_MIN_MS` — không chặn render children
 * (để lazy `Chat` tải song song, giống màn chờ game / AI Dungeon).
 */
export function useAuthBootOverlay() {
  const { isAuth, loading } = useAuth()
  const [pastMin, setPastMin] = useState(false)
  const loadStartRef = useRef<number | null>(null)

  useEffect(() => {
    if (loading) {
      loadStartRef.current = Date.now()
      setPastMin(false)
      return
    }
    const t0 = loadStartRef.current ?? Date.now()
    const elapsed = Date.now() - t0
    const rest = Math.max(0, LOADING_MIN_MS - elapsed)
    const id = window.setTimeout(() => setPastMin(true), rest)
    return () => window.clearTimeout(id)
  }, [loading])

  const showOverlay = loading || (isAuth && !pastMin)
  return { isAuth, loading, showOverlay }
}
