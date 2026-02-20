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
      await auth.login({ email, password })
      const userData = await auth.me()
      setAuthState(userData)
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
      await auth.login({ email, password })
      const userData = await auth.me()
      setAuthState(userData)
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
    void auth.logout().catch(() => undefined)
    clearAuthState()
  }, [clearAuthState])

  const checkAuth = useCallback(async () => {
    const { setLoading } = useAuthStore.getState()

    try {
      const userData = await auth.me()
      useAuthStore.getState().login(userData)
      return true
    } catch {
      clearAuthState()
      return false
    } finally {
      setLoading(false)
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
