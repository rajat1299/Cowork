import { useState, useEffect } from 'react'
import { Sidebar, RightSidebar } from './components/layout'
import { ChatContainer } from './components/chat'
import { LoginPage, RegisterPage } from './pages'
import { useAuthStore } from './stores'
import { useAuth } from './hooks'

type AuthView = 'login' | 'register'

function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [authView, setAuthView] = useState<AuthView>('login')
  const { isAuthenticated, isLoading } = useAuthStore()
  const { checkAuth } = useAuth()

  // Check auth state on mount
  useEffect(() => {
    checkAuth()
  }, [])

  // Show loading state while checking auth
  if (isLoading) {
    return (
      <div className="h-screen bg-dark-bg flex items-center justify-center">
        <div className="text-ink-subtle text-[14px]">Loading...</div>
      </div>
    )
  }

  // Show auth pages if not authenticated
  if (!isAuthenticated) {
    if (authView === 'login') {
      return (
        <LoginPage
          onSwitchToRegister={() => setAuthView('register')}
          onSuccess={() => {}}
        />
      )
    }
    return (
      <RegisterPage
        onSwitchToLogin={() => setAuthView('login')}
        onSuccess={() => {}}
      />
    )
  }

  // Main app when authenticated
  return (
    <div className="h-screen flex bg-dark-bg">
      {/* Left Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      {/* Main content */}
      <main className="flex-1 flex flex-col min-w-0">
        <div className="flex-1 overflow-hidden">
          <ChatContainer />
        </div>
      </main>

      {/* Right Sidebar */}
      <RightSidebar />
    </div>
  )
}

export default App
