import { URL } from 'node:url'

import { app, ipcMain, session, shell } from 'electron'

import type { BackendPorts } from './init'

type RuntimeConfig = {
  coreApiUrl: string
  orchestratorUrl: string
  isDesktop: boolean
  appVersion: string
}

type OAuthProvider = 'google' | 'github'

type OAuthExchangePayload = {
  provider: OAuthProvider
  code: string
  state?: string
  codeVerifier?: string
}

type RegisterIpcOptions = {
  getRuntime: () => RuntimeConfig
  getPorts: () => BackendPorts | null
  restartBackend: () => Promise<BackendPorts>
}

let handlersRegistered = false

function sameSiteToElectron(value: string): 'unspecified' | 'no_restriction' | 'lax' | 'strict' {
  const normalized = value.toLowerCase()
  if (normalized === 'none') {
    return 'no_restriction'
  }
  if (normalized === 'lax' || normalized === 'strict') {
    return normalized
  }
  return 'unspecified'
}

function splitSetCookieHeader(value: string): string[] {
  const chunks: string[] = []
  let current = ''
  let inExpires = false

  for (let i = 0; i < value.length; i += 1) {
    const char = value[i]
    const suffix = value.slice(i)

    if (!inExpires && suffix.toLowerCase().startsWith('expires=')) {
      inExpires = true
    }

    if (char === ';' && inExpires) {
      inExpires = false
      current += char
      continue
    }

    if (char === ',' && !inExpires) {
      chunks.push(current.trim())
      current = ''
      continue
    }

    current += char
  }

  if (current.trim()) {
    chunks.push(current.trim())
  }

  return chunks.filter(Boolean)
}

function getSetCookieHeaders(headers: Headers): string[] {
  const maybeGetter = headers as Headers & { getSetCookie?: () => string[] }
  if (typeof maybeGetter.getSetCookie === 'function') {
    return maybeGetter.getSetCookie()
  }
  const fallback = headers.get('set-cookie')
  return fallback ? splitSetCookieHeader(fallback) : []
}

async function applyResponseCookies(headers: Headers, targetUrl: string): Promise<void> {
  const cookieHeaders = getSetCookieHeaders(headers)
  for (const cookieHeader of cookieHeaders) {
    const sections = cookieHeader.split(';').map((part) => part.trim())
    const [nameValue, ...attributes] = sections
    const eqIndex = nameValue.indexOf('=')
    if (eqIndex <= 0) {
      continue
    }

    const name = nameValue.slice(0, eqIndex)
    const value = nameValue.slice(eqIndex + 1)

    const details: Electron.CookiesSetDetails = {
      url: targetUrl,
      name,
      value,
      path: '/',
      sameSite: 'unspecified',
    }

    for (const attribute of attributes) {
      const [rawKey, ...rawValue] = attribute.split('=')
      const key = rawKey.toLowerCase()
      const attrValue = rawValue.join('=')

      if (key === 'path' && attrValue) {
        details.path = attrValue
      } else if (key === 'domain' && attrValue) {
        details.domain = attrValue
      } else if (key === 'httponly') {
        details.httpOnly = true
      } else if (key === 'secure') {
        details.secure = true
      } else if (key === 'samesite' && attrValue) {
        details.sameSite = sameSiteToElectron(attrValue)
      } else if (key === 'expires' && attrValue) {
        const expiresAt = Date.parse(attrValue)
        if (!Number.isNaN(expiresAt)) {
          details.expirationDate = Math.floor(expiresAt / 1000)
        }
      } else if (key === 'max-age' && attrValue) {
        const maxAgeSeconds = Number.parseInt(attrValue, 10)
        if (!Number.isNaN(maxAgeSeconds)) {
          details.expirationDate = Math.floor(Date.now() / 1000) + maxAgeSeconds
        }
      }
    }

    await session.defaultSession.cookies.set(details)
  }
}

async function exchangeOAuthCode(runtime: RuntimeConfig, payload: OAuthExchangePayload): Promise<unknown> {
  const response = await fetch(`${runtime.coreApiUrl}/oauth/${payload.provider}/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
    },
    body: JSON.stringify({
      code: payload.code,
      state: payload.state,
      code_verifier: payload.codeVerifier,
    }),
  })

  const data = await response.json().catch(() => null)
  if (!response.ok) {
    throw new Error(
      `OAuth token exchange failed (${response.status} ${response.statusText}): ${JSON.stringify(data)}`
    )
  }

  await applyResponseCookies(response.headers, runtime.coreApiUrl)
  return data
}

export function registerIpcHandlers(options: RegisterIpcOptions): void {
  if (handlersRegistered) {
    return
  }
  handlersRegistered = true

  ipcMain.handle('get-backend-ports', async () => {
    return options.getPorts()
  })

  ipcMain.handle('get-app-version', async () => {
    return app.getVersion()
  })

  ipcMain.handle('desktop:get-runtime', async () => {
    return options.getRuntime()
  })

  ipcMain.handle('restart-backend', async () => {
    return options.restartBackend()
  })

  ipcMain.handle('oauth-open-login', async (_event, payload: { provider: OAuthProvider; state: string; codeChallenge: string }) => {
    const runtime = options.getRuntime()
    const url = new URL(`${runtime.coreApiUrl}/oauth/${payload.provider}/login`)
    url.searchParams.set('state', payload.state)
    url.searchParams.set('code_challenge', payload.codeChallenge)
    url.searchParams.set('code_challenge_method', 'S256')

    await shell.openExternal(url.toString())
    return { ok: true }
  })

  ipcMain.handle('oauth-exchange-code', async (_event, payload: OAuthExchangePayload) => {
    const runtime = options.getRuntime()
    const tokenData = await exchangeOAuthCode(runtime, payload)
    return {
      ok: true,
      tokenData,
    }
  })
}
