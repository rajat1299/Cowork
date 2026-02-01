import { useState, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'
import { auth, ApiError } from '../api'

export function useAuth() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const setAuthState = useAuthStore((s) => s.login)
  const clearAuthState = useAuthStore((s) => s.logout)
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated)
  const user = useAuthStore((s) => s.user)

  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true)
    setError(null)

    try {
      const tokens = await auth.login({ email, password })
      // Store tokens FIRST so auth.me() can use them
      useAuthStore.getState().setTokens(tokens.access_token, tokens.refresh_token)
      const userData = await auth.me()
      setAuthState(tokens.access_token, tokens.refresh_token, userData)
      return true
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 401 ? 'Invalid email or password' : 'Login failed')
      } else {
        setError('Network error. Please try again.')
      }
      return false
    } finally {
      setIsLoading(false)
    }
  }, [setAuthState])

  const register = useCallback(async (email: string, password: string) => {
    setIsLoading(true)
    setError(null)

    try {
      await auth.register({ email, password })
      // Auto-login after registration
      const tokens = await auth.login({ email, password })
      useAuthStore.getState().setTokens(tokens.access_token, tokens.refresh_token)
      const userData = await auth.me()
      setAuthState(tokens.access_token, tokens.refresh_token, userData)
      return true
    } catch (err) {
      if (err instanceof ApiError) {
        const data = err.data as { detail?: string }
        setError(data?.detail || 'Registration failed')
      } else {
        setError('Network error. Please try again.')
      }
      return false
    } finally {
      setIsLoading(false)
    }
  }, [setAuthState])

  const logout = useCallback(() => {
    clearAuthState()
  }, [clearAuthState])

  const checkAuth = useCallback(async () => {
    const { accessToken, setLoading } = useAuthStore.getState()

    if (!accessToken) {
      setLoading(false)
      return false
    }

    try {
      const userData = await auth.me()
      useAuthStore.getState().setUser(userData)
      setLoading(false)
      return true
    } catch {
      clearAuthState()
      return false
    }
  }, [clearAuthState])

  return {
    login,
    register,
    logout,
    checkAuth,
    isLoading,
    error,
    isAuthenticated,
    user,
    clearError: () => setError(null),
  }
}
