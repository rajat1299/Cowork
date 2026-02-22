import { useCallback, useEffect, useRef, useState } from 'react'

type BackendEventPayload = {
  step?: string
  percent?: number
  detail?: string
  message?: string
  [key: string]: unknown
}

type CoworkDesktop = {
  getBackendPorts?: () => Promise<{ coreApi: number; orchestrator: number } | null>
  onBackendEvent: (
    callback: (event: string, payload?: BackendEventPayload) => void,
  ) => () => void
}

declare global {
  interface Window {
    coworkDesktop?: CoworkDesktop
  }
}

/** Maps backend boot steps to mycelium-themed status language */
function getStatusText(event: string, step?: string): string {
  if (event === 'backend-error') return 'something went wrong...'

  switch (step) {
    case 'starting':
      return 'germinating...'
    case 'bootstrap:init':
      return 'germinating...'
    case 'bootstrap:uv':
      return 'taking root...'
    case 'bootstrap:python':
      return 'taking root...'
    case 'venv-create:core_api':
    case 'venv-create:orchestrator':
      return 'spreading underground...'
    case 'venv-ready:core_api':
    case 'venv-ready:orchestrator':
      return 'weaving the network...'
    case 'bootstrap:done':
      return 'weaving the network...'
    case 'spawn-core-api':
      return 'awakening...'
    case 'spawn-orchestrator':
      return 'awakening...'
    case 'health-check':
      return 'connecting...'
    default:
      return 'germinating...'
  }
}

export default function DesktopSplash({ onReady }: { onReady: () => void }) {
  const [status, setStatus] = useState('germinating...')
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [fadeOut, setFadeOut] = useState(false)
  const readyTriggeredRef = useRef(false)

  const transitionToReady = useCallback(() => {
    if (readyTriggeredRef.current) {
      return
    }
    readyTriggeredRef.current = true
    setStatus('connected')
    setProgress(100)
    // Smooth fade-out before showing app.
    setTimeout(() => setFadeOut(true), 300)
    setTimeout(() => onReady(), 800)
  }, [onReady])

  useEffect(() => {
    const desktop = window.coworkDesktop
    if (!desktop) {
      // Not in desktop — skip splash immediately
      onReady()
      return
    }

    let cancelled = false
    void desktop
      .getBackendPorts?.()
      .then((ports) => {
        if (!cancelled && ports) {
          transitionToReady()
        }
      })
      .catch(() => {
        // Ignore probe errors and rely on event stream.
      })

    const unsubscribe = desktop.onBackendEvent((event, payload) => {
      if (event === 'backend-ready') {
        transitionToReady()
        return
      }

      if (event === 'backend-error') {
        setError(payload?.message as string || 'Failed to start backend services')
        setStatus('something went wrong...')
        return
      }

      const step = payload?.step as string | undefined
      const percent = payload?.percent as number | undefined

      setStatus(getStatusText(event, step))
      if (typeof percent === 'number') {
        setProgress(percent)
      }
    })

    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [onReady, transitionToReady])

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'hsl(12, 6%, 7%)',
        transition: 'opacity 0.5s ease-out',
        opacity: fadeOut ? 0 : 1,
      }}
    >
      {/* App name */}
      <h1
        style={{
          fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: '28px',
          fontWeight: 500,
          letterSpacing: '-0.02em',
          color: 'hsl(35, 38%, 90%)',
          marginBottom: '48px',
          opacity: 0.9,
        }}
      >
        Mycelium
      </h1>

      {/* Progress bar track */}
      <div
        style={{
          width: '200px',
          height: '2px',
          borderRadius: '1px',
          background: 'hsl(12, 6%, 18%)',
          overflow: 'hidden',
          marginBottom: '16px',
        }}
      >
        {/* Progress bar fill */}
        <div
          style={{
            height: '100%',
            borderRadius: '1px',
            background: error
              ? 'hsl(0, 84%, 60%)'
              : 'hsl(35, 38%, 60%)',
            width: `${progress}%`,
            transition: 'width 0.6s cubic-bezier(0.22, 1, 0.36, 1)',
          }}
        />
      </div>

      {/* Status text */}
      <p
        style={{
          fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif",
          fontSize: '12px',
          fontWeight: 400,
          letterSpacing: '0.02em',
          color: error ? 'hsl(0, 84%, 60%)' : 'hsl(35, 20%, 50%)',
          margin: 0,
        }}
      >
        {status}
      </p>

      {/* Error details */}
      {error && (
        <p
          style={{
            fontFamily: "'DM Sans', -apple-system, BlinkMacSystemFont, sans-serif",
            fontSize: '11px',
            color: 'hsl(35, 20%, 40%)',
            marginTop: '8px',
            maxWidth: '300px',
            textAlign: 'center',
          }}
        >
          {error}
        </p>
      )}
    </div>
  )
}
