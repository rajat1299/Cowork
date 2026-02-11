export interface TelemetryEventPayload {
  event: string
  attributes?: Record<string, string | number | boolean>
  timestamp: number
}

const TELEMETRY_EVENT_NAME = 'cowork:telemetry'

export function emitTelemetryEvent(
  event: string,
  attributes?: Record<string, string | number | boolean>
): void {
  const payload: TelemetryEventPayload = {
    event,
    attributes,
    timestamp: Date.now(),
  }

  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    window.dispatchEvent(new CustomEvent<TelemetryEventPayload>(TELEMETRY_EVENT_NAME, { detail: payload }))
  }

  if (import.meta.env.DEV) {
    console.warn('[telemetry]', payload)
  }
}
