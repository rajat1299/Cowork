import { useEffect } from 'react'
import { RouterProvider } from 'react-router-dom'
import { router } from './router'
import { useAuth, useOAuth } from './hooks'

function App() {
  const { checkAuth } = useAuth()
  const { checkOAuthCallback } = useOAuth()

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
  }, [])

  return <RouterProvider router={router} />
}

export default App
