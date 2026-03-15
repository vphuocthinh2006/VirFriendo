import { useState, useCallback, useEffect } from 'react'
import * as api from '../services/api'
import type { RegisterInput } from '../types/auth'

export function useAuth() {
  const [isAuth, setIsAuth] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setIsAuth(api.isAuthenticated())
    setLoading(false)
  }, [])

  const login = useCallback(async (username: string, password: string) => {
    await api.login(username, password)
    setIsAuth(true)
  }, [])

  const register = useCallback(async (input: RegisterInput) => {
    await api.register(input.username, input.email, input.password)
    const token = await api.login(input.username, input.password)
    setIsAuth(true)
    return token
  }, [])

  const logout = useCallback(() => {
    api.logout()
    setIsAuth(false)
  }, [])

  return { isAuth, loading, login, register, logout }
}
