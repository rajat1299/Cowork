import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { app, BrowserWindow } from 'electron'
import log from 'electron-log'

import {
  getBackendPorts,
  restartBackendServices,
  startBackendServices,
  stopBackendServices,
  type BackendEventName,
  type BackendPorts,
} from './init'
import { registerIpcHandlers } from './ipc'
import { registerDeepLinkProtocol } from './protocol'
import { registerGlobalShortcuts } from './shortcuts'
import { createTray, destroyTray } from './tray'
import { configureAutoUpdater, registerUpdateIpcHandlers } from './update'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const MAIN_DIST = path.join(__dirname, '../..')
const RENDERER_DIST = path.join(MAIN_DIST, 'dist')
const PRELOAD_PATH = path.join(__dirname, '../preload/index.mjs')
const VITE_DEV_SERVER_URL = process.env.VITE_DEV_SERVER_URL

// Enforce single instance — deep links on Windows/Linux arrive via second-instance event
const gotTheLock = app.requestSingleInstanceLock()
if (!gotTheLock) {
  app.quit()
}

let mainWindow: BrowserWindow | null = null

let runtimeConfig = {
  coreApiUrl: 'http://127.0.0.1:3001',
  orchestratorUrl: 'http://127.0.0.1:5001',
  isDesktop: true,
  appVersion: app.getVersion(),
}

function emitToRenderer(event: BackendEventName | string, payload?: unknown): void {
  for (const window of BrowserWindow.getAllWindows()) {
    if (!window.isDestroyed()) {
      window.webContents.send(event, payload)
    }
  }
}

function resolveDevServerUrl(): string | undefined {
  if (!VITE_DEV_SERVER_URL) {
    return undefined
  }
  try {
    const url = new URL(VITE_DEV_SERVER_URL)
    if (url.hostname === 'localhost' || url.hostname === '::1') {
      url.hostname = '127.0.0.1'
    }
    return url.toString()
  } catch {
    return VITE_DEV_SERVER_URL
  }
}

function buildRuntimeConfig(ports: BackendPorts): void {
  runtimeConfig = {
    coreApiUrl: `http://127.0.0.1:${ports.coreApi}`,
    orchestratorUrl: `http://127.0.0.1:${ports.orchestrator}`,
    isDesktop: true,
    appVersion: app.getVersion(),
  }
}

function createMainWindow(ports: BackendPorts | null): BrowserWindow {
  const resolvedPorts = ports ?? { coreApi: 3001, orchestrator: 5001 }

  const window = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 980,
    minHeight: 700,
    show: false,
    titleBarStyle: 'hiddenInset',
    backgroundColor: '#0f1115',
    webPreferences: {
      preload: PRELOAD_PATH,
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [
        `--core-api-port=${resolvedPorts.coreApi}`,
        `--orchestrator-port=${resolvedPorts.orchestrator}`,
        `--app-version=${app.getVersion()}`,
      ],
    },
  })

  if (process.platform === 'darwin') {
    window.setWindowButtonPosition({ x: 14, y: 14 })
  }

  if (VITE_DEV_SERVER_URL) {
    window.loadURL(resolveDevServerUrl() || VITE_DEV_SERVER_URL)
  } else {
    window.loadFile(path.join(RENDERER_DIST, 'index.html'))
  }

  window.once('ready-to-show', () => {
    window.show()
  })

  window.on('closed', () => {
    if (mainWindow === window) {
      mainWindow = null
    }
  })

  return window
}

async function bootstrapAndCreateWindow(): Promise<void> {
  let startupError: Error | null = null
  let ports: BackendPorts | null = null

  try {
    ports = await startBackendServices((event, payload) => {
      if (event === 'backend-ready' && payload && typeof payload === 'object') {
        const maybePorts = payload as BackendPorts
        buildRuntimeConfig(maybePorts)
      }
      emitToRenderer(event, payload)
    })
  } catch (error) {
    startupError = error instanceof Error ? error : new Error('Unknown backend startup error')
    log.error(`Backend startup failed: ${startupError.message}`)
  }

  mainWindow = createMainWindow(ports)

  mainWindow.webContents.once('did-finish-load', () => {
    if (ports) {
      // Backend may become ready before the renderer subscribes, so replay once.
      emitToRenderer('backend-ready', ports)
      return
    }

    if (startupError) {
      emitToRenderer('backend-error', { message: startupError.message })
    }
  })
}

app.whenReady().then(async () => {
  await bootstrapAndCreateWindow()

  registerIpcHandlers({
    getRuntime: () => runtimeConfig,
    getPorts: () => getBackendPorts(),
    restartBackend: async () => {
      const ports = await restartBackendServices((event, payload) => emitToRenderer(event, payload))
      buildRuntimeConfig(ports)
      return ports
    },
  })

  configureAutoUpdater(() => mainWindow)
  registerUpdateIpcHandlers()

  registerGlobalShortcuts(() => mainWindow)
  registerDeepLinkProtocol(() => mainWindow)
  createTray(() => mainWindow)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      mainWindow = createMainWindow(getBackendPorts())
    }
  })
})

app.on('before-quit', async () => {
  destroyTray()
  await stopBackendServices()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
