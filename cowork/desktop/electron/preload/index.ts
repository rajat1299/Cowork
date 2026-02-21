import { contextBridge, ipcRenderer } from 'electron'

type RuntimeConfig = {
  coreApiUrl: string
  orchestratorUrl: string
  isDesktop: boolean
  appVersion: string
}

type BackendEventPayload = {
  [key: string]: unknown
}

function getArgumentValue(prefix: string): string | undefined {
  const arg = process.argv.find((entry) => entry.startsWith(prefix))
  return arg?.slice(prefix.length)
}

const coreApiPort = Number.parseInt(getArgumentValue('--core-api-port=') ?? '3001', 10)
const orchestratorPort = Number.parseInt(getArgumentValue('--orchestrator-port=') ?? '5001', 10)
const appVersion = getArgumentValue('--app-version=') ?? '0.0.0'

const runtime: RuntimeConfig = {
  coreApiUrl: `http://127.0.0.1:${coreApiPort}`,
  orchestratorUrl: `http://127.0.0.1:${orchestratorPort}`,
  isDesktop: true,
  appVersion,
}

contextBridge.exposeInMainWorld('__COWORK_RUNTIME__', runtime)

contextBridge.exposeInMainWorld('coworkDesktop', {
  getRuntime: (): Promise<RuntimeConfig> => ipcRenderer.invoke('desktop:get-runtime'),
  getBackendPorts: (): Promise<{ coreApi: number; orchestrator: number } | null> =>
    ipcRenderer.invoke('get-backend-ports'),
  restartBackend: (): Promise<{ coreApi: number; orchestrator: number }> =>
    ipcRenderer.invoke('restart-backend'),
  getAppVersion: (): Promise<string> => ipcRenderer.invoke('get-app-version'),
  openOAuthLogin: (payload: { provider: 'google' | 'github'; state: string; codeChallenge: string }) =>
    ipcRenderer.invoke('oauth-open-login', payload),
  exchangeOAuthCode: (payload: {
    provider: 'google' | 'github'
    code: string
    state?: string
    codeVerifier?: string
  }) => ipcRenderer.invoke('oauth-exchange-code', payload),
  checkForUpdates: (): Promise<unknown> => ipcRenderer.invoke('check-update'),
  downloadUpdate: (): Promise<unknown> => ipcRenderer.invoke('download-update'),
  quitAndInstall: (): Promise<unknown> => ipcRenderer.invoke('quit-and-install'),
  onBackendEvent: (callback: (event: string, payload?: BackendEventPayload) => void) => {
    const channels = ['backend-starting', 'backend-progress', 'backend-ready', 'backend-error']
    const listeners = channels.map((channel) => {
      const listener = (_event: Electron.IpcRendererEvent, payload?: BackendEventPayload) => {
        callback(channel, payload)
      }
      ipcRenderer.on(channel, listener)
      return { channel, listener }
    })

    return () => {
      for (const entry of listeners) {
        ipcRenderer.removeListener(entry.channel, entry.listener)
      }
    }
  },
  onUpdateEvent: (callback: (event: string, payload?: unknown) => void) => {
    const channels = [
      'update-checking',
      'update-available',
      'update-not-available',
      'download-progress',
      'update-downloaded',
      'update-error',
    ]

    const listeners = channels.map((channel) => {
      const listener = (_event: Electron.IpcRendererEvent, payload?: unknown) => {
        callback(channel, payload)
      }
      ipcRenderer.on(channel, listener)
      return { channel, listener }
    })

    return () => {
      for (const entry of listeners) {
        ipcRenderer.removeListener(entry.channel, entry.listener)
      }
    }
  },
})
