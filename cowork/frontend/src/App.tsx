import { useCallback, useEffect, useState } from 'react'
import { RouterProvider } from 'react-router-dom'
import { router } from './router'
import { useAuth, useOAuth } from './hooks'
import { Toaster } from './components/ui/sonner'
import { isDesktop } from './api/client'
import DesktopSplash from './components/DesktopSplash'

function App() {
  const { checkAuth } = useAuth()
  const { checkOAuthCallback } = useOAuth()
  const [backendReady, setBackendReady] = useState(!isDesktop)

  const handleBackendReady = useCallback(() => {
    setBackendReady(true)
  }, [])

  // Check for OAuth callback and auth state on mount
  useEffect(() => {
    const initAuth = async () => {
      // First check if this is an OAuth callback
      const oauthResult = await checkOAuthCallback()

      // If OAuth callback was handled (success or error), don't check regular auth
      if (oauthResult !== null) {
        return
      }

      // Otherwise, check existing auth state
      checkAuth()
    }

    initAuth()
  }, [checkAuth, checkOAuthCallback])

  // Show splash screen while desktop backend boots
  if (!backendReady) {
    return <DesktopSplash onReady={handleBackendReady} />
  }

  return (
    <>
      <RouterProvider router={router} />
      <Toaster position="bottom-right" />
    </>
  )
}

export default App
