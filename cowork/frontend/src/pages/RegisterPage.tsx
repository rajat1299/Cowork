import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { cn } from '../lib/utils'

export function RegisterPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)
  const { register, isLoading, error, clearError } = useAuth()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLocalError(null)

    if (password !== confirmPassword) {
      setLocalError('Passwords do not match')
      return
    }

    if (password.length < 6) {
      setLocalError('Password must be at least 6 characters')
      return
    }

    const success = await register(email, password)
    if (success) {
      navigate('/')
    }
  }

  const displayError = localError || error

  return (
    <div className="min-h-screen bg-dark-bg flex items-center justify-center p-6">
      <div className="w-full max-w-sm">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-medium text-ink mb-2">Create account</h1>
          <p className="text-ink-subtle text-[14px]">Get started with Cowork</p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          {displayError && (
            <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-[13px]">
              {displayError}
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
                setLocalError(null)
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
                setLocalError(null)
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

          <div>
            <label className="block text-[13px] text-ink-muted mb-2">Confirm password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value)
                setLocalError(null)
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
            {isLoading ? 'Creating account...' : 'Create account'}
          </button>
        </form>

        {/* Footer */}
        <p className="text-center mt-6 text-[13px] text-ink-subtle">
          Already have an account?{' '}
          <Link
            to="/login"
            className="text-ink hover:text-burnt transition-colors"
          >
            Sign in
          </Link>
        </p>
      </div>
    </div>
  )
}
