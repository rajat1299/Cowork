import { useState, useCallback } from 'react'
import { useAuthStore } from '../stores/authStore'
import { oauth, auth, ApiError } from '../api'
import type { OAuthProvider } from '../api'
import {
  createPKCEChallenge,
  storePKCEParams,
  getPKCEParams,
  clearPKCEParams,
} from '../lib/pkce'

export function useOAuth() {
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const { login: setAuthState } = useAuthStore()

  /**
   * Start OAuth login flow
   * Generates PKCE parameters, stores them, and opens the OAuth login URL
   */
  const startOAuthLogin = useCallback(async (provider: OAuthProvider) => {
    setIsLoading(true)
    setError(null)

    try {
      // Generate PKCE challenge
      const { state, codeVerifier, codeChallenge } = await createPKCEChallenge()

      // Store PKCE params for callback validation
      storePKCEParams(state, codeVerifier, provider)

      // Get OAuth login URL
      const loginUrl = oauth.getLoginUrl(provider, { state, codeChallenge })

      // Open in browser/new window
      // In Electron, this will be handled by shell.openExternal
      // In browser, we redirect the current window
      window.location.href = loginUrl
    } catch (err) {
      setError('Failed to start OAuth login')
      setIsLoading(false)
      console.error('OAuth login error:', err)
    }
  }, [])

  /**
   * Handle OAuth callback
   * Called when the app receives the OAuth callback with code and state
   */
  const handleOAuthCallback = useCallback(async (code: string, returnedState: string) => {
    setIsLoading(true)
    setError(null)

    try {
      // Get stored PKCE params
      const { state, codeVerifier, provider } = getPKCEParams()

      // Validate state
      if (!state || state !== returnedState) {
        throw new Error('Invalid state parameter - possible CSRF attack')
      }

      if (!provider) {
        throw new Error('OAuth provider not found')
      }

      // Exchange code for tokens
      await oauth.exchangeToken(provider as OAuthProvider, {
        code,
        state: returnedState,
        code_verifier: codeVerifier || undefined,
      })

      // Clear PKCE params
      clearPKCEParams()

      // Get user info
      const userData = await auth.me()

      // Set full auth state
      setAuthState(userData)

      return true
    } catch (err) {
      clearPKCEParams()

      if (err instanceof ApiError) {
        const data = err.data as { detail?: string }
        setError(data?.detail || 'OAuth authentication failed')
      } else if (err instanceof Error) {
        setError(err.message)
      } else {
        setError('OAuth authentication failed')
      }
      return false
    } finally {
      setIsLoading(false)
    }
  }, [setAuthState])

  /**
   * Check if we're returning from an OAuth callback
   * Parse URL parameters and handle the callback if present
   */
  const checkOAuthCallback = useCallback(async () => {
    // Check URL for OAuth callback parameters
    const urlParams = new URLSearchParams(window.location.search)
    const code = urlParams.get('code')
    const state = urlParams.get('state')
    const error = urlParams.get('error')

    if (error) {
      const errorDescription = urlParams.get('error_description')
      setError(errorDescription || `OAuth error: ${error}`)
      // Clear URL params
      window.history.replaceState({}, '', window.location.pathname)
      return false
    }

    if (code && state) {
      // Clear URL params before processing
      window.history.replaceState({}, '', window.location.pathname)
      return await handleOAuthCallback(code, state)
    }

    return null // No callback to process
  }, [handleOAuthCallback])

  return {
    startOAuthLogin,
    handleOAuthCallback,
    checkOAuthCallback,
    isLoading,
    error,
    clearError: () => setError(null),
  }
}
