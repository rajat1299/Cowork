import { useState } from 'react'
import { useAuth } from '../hooks/useAuth'
import { cn } from '../lib/utils'

interface LoginPageProps {
  onSwitchToRegister: () => void
  onSuccess: () => void
}

export function LoginPage({ onSwitchToRegister, onSuccess }: LoginPageProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const { login, isLoading, error, clearError } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const success = await login(email, password)
    if (success) {
      onSuccess()
    }
  }

  return (
    <div className="min-h-screen bg-dark-bg flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-medium text-ink mb-2">Welcome back</h1>
          <p className="text-ink-subtle text-[14px]">Sign in to continue to Cowork</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-[13px]">
              {error}
            </div>
          )}

          <div>
            <label className="block text-[13px] text-ink-muted mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value)
                clearError()
              }}
              placeholder="you@example.com"
              required
              className={cn(
                'w-full px-4 py-3 rounded-xl',
                'bg-dark-surface border border-dark-border',
                'text-ink text-[14px] placeholder:text-ink-subtle',
                'focus:outline-none focus:border-burnt/50',
                'transition-colors'
              )}
            />
          </div>

          <div>
            <label className="block text-[13px] text-ink-muted mb-2">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value)
                clearError()
              }}
              placeholder="••••••••"
              required
              className={cn(
                'w-full px-4 py-3 rounded-xl',
                'bg-dark-surface border border-dark-border',
                'text-ink text-[14px] placeholder:text-ink-subtle',
                'focus:outline-none focus:border-burnt/50',
                'transition-colors'
              )}
            />
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className={cn(
              'w-full py-3 rounded-xl',
              'bg-burnt text-white font-medium text-[14px]',
              'hover:bg-burnt/90 transition-colors',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {isLoading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        {/* Footer */}
        <p className="text-center mt-6 text-[13px] text-ink-subtle">
          Don't have an account?{' '}
          <button
            onClick={onSwitchToRegister}
            className="text-ink hover:text-burnt transition-colors"
          >
            Sign up
          </button>
        </p>
      </div>
    </div>
  )
}
