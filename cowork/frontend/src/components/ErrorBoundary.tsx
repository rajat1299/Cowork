import { Component, type ReactNode } from 'react'
import { AlertCircle, RefreshCw } from 'lucide-react'

interface Props {
  children: ReactNode
  fallback?: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

/**
 * Error boundary to catch React errors and show a fallback UI
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error boundary caught error:', error, errorInfo)
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null })
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
          <div className="w-16 h-16 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
            <AlertCircle size={32} className="text-red-400" />
          </div>
          <h2 className="text-lg font-medium text-foreground mb-2">Something went wrong</h2>
          <p className="text-[14px] text-muted-foreground mb-6 max-w-md">
            An unexpected error occurred. Please try refreshing the page.
          </p>
          {this.state.error && (
            <pre className="text-[12px] text-muted-foreground bg-secondary p-4 rounded-lg mb-6 max-w-lg overflow-auto">
              {this.state.error.message}
            </pre>
          )}
          <div className="flex items-center gap-3">
            <button
              onClick={this.handleRetry}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-secondary border border-border text-foreground text-[14px] hover:bg-accent transition-colors"
            >
              <RefreshCw size={16} />
              Try again
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 rounded-lg bg-burnt text-white text-[14px] font-medium hover:bg-burnt/90 transition-colors"
            >
              Refresh page
            </button>
          </div>
        </div>
      )
    }

    return this.props.children
  }
}

/**
 * Wrapper component for pages that might error
 */
export function withErrorBoundary<P extends object>(
  Component: React.ComponentType<P>,
  fallback?: ReactNode
) {
  return function WrappedComponent(props: P) {
    return (
      <ErrorBoundary fallback={fallback}>
        <Component {...props} />
      </ErrorBoundary>
    )
  }
}
