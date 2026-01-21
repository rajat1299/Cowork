/**
 * PKCE (Proof Key for Code Exchange) utilities for OAuth security
 *
 * PKCE prevents authorization code interception attacks in public clients
 * (desktop/mobile apps that can't securely store a client secret).
 */

/**
 * Generate a cryptographically random string for state or code_verifier
 */
function generateRandomString(length: number): string {
  const array = new Uint8Array(length)
  crypto.getRandomValues(array)
  return base64UrlEncode(array)
}

/**
 * Base64 URL encode (RFC 4648 Section 5)
 * Replaces + with -, / with _, and removes = padding
 */
function base64UrlEncode(buffer: Uint8Array): string {
  const base64 = btoa(String.fromCharCode(...buffer))
  return base64
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '')
}

/**
 * Generate a random state parameter for CSRF protection
 * State is sent to the OAuth provider and returned in the callback
 */
export function generateState(): string {
  return generateRandomString(32)
}

/**
 * Generate a code_verifier for PKCE
 * Must be between 43-128 characters (RFC 7636)
 */
export function generateCodeVerifier(): string {
  return generateRandomString(32)
}

/**
 * Generate a code_challenge from a code_verifier using S256 method
 * code_challenge = BASE64URL(SHA256(code_verifier))
 */
export async function generateCodeChallenge(codeVerifier: string): Promise<string> {
  const encoder = new TextEncoder()
  const data = encoder.encode(codeVerifier)
  const digest = await crypto.subtle.digest('SHA-256', data)
  return base64UrlEncode(new Uint8Array(digest))
}

/**
 * Storage keys for PKCE parameters
 * These are stored temporarily during the OAuth flow
 */
const STORAGE_KEYS = {
  state: 'oauth_state',
  codeVerifier: 'oauth_code_verifier',
  provider: 'oauth_provider',
} as const

/**
 * Store PKCE parameters before redirecting to OAuth provider
 */
export function storePKCEParams(state: string, codeVerifier: string, provider: string): void {
  sessionStorage.setItem(STORAGE_KEYS.state, state)
  sessionStorage.setItem(STORAGE_KEYS.codeVerifier, codeVerifier)
  sessionStorage.setItem(STORAGE_KEYS.provider, provider)
}

/**
 * Retrieve stored PKCE parameters after OAuth callback
 */
export function getPKCEParams(): { state: string | null; codeVerifier: string | null; provider: string | null } {
  return {
    state: sessionStorage.getItem(STORAGE_KEYS.state),
    codeVerifier: sessionStorage.getItem(STORAGE_KEYS.codeVerifier),
    provider: sessionStorage.getItem(STORAGE_KEYS.provider),
  }
}

/**
 * Clear PKCE parameters after OAuth flow completes
 */
export function clearPKCEParams(): void {
  sessionStorage.removeItem(STORAGE_KEYS.state)
  sessionStorage.removeItem(STORAGE_KEYS.codeVerifier)
  sessionStorage.removeItem(STORAGE_KEYS.provider)
}

/**
 * Generate all PKCE parameters for starting an OAuth flow
 */
export async function createPKCEChallenge(): Promise<{
  state: string
  codeVerifier: string
  codeChallenge: string
}> {
  const state = generateState()
  const codeVerifier = generateCodeVerifier()
  const codeChallenge = await generateCodeChallenge(codeVerifier)

  return { state, codeVerifier, codeChallenge }
}
