import { createRequire } from 'node:module'

import { app, ipcMain, type BrowserWindow } from 'electron'
import type { ProgressInfo, UpdateInfo } from 'electron-updater'

const require = createRequire(import.meta.url)
const { autoUpdater } = require('electron-updater') as typeof import('electron-updater')

const updateChannel = process.arch === 'arm64' ? 'latest-arm64' : 'latest-x64'

let updateHandlersRegistered = false

function sendToRenderer(window: BrowserWindow | null, channel: string, payload?: unknown): void {
  if (!window || window.isDestroyed()) {
    return
  }
  window.webContents.send(channel, payload)
}

export function configureAutoUpdater(getWindow: () => BrowserWindow | null): void {
  autoUpdater.autoDownload = false
  autoUpdater.autoInstallOnAppQuit = false
  autoUpdater.allowDowngrade = false
  autoUpdater.channel = updateChannel

  autoUpdater.setFeedURL({
    provider: 'github',
    owner: process.env.COWORK_UPDATES_OWNER || 'rajattiwari',
    repo: process.env.COWORK_UPDATES_REPO || 'cowork',
    releaseType: 'release',
    channel: updateChannel,
  })

  autoUpdater.on('checking-for-update', () => {
    sendToRenderer(getWindow(), 'update-checking')
  })

  autoUpdater.on('update-available', (info: UpdateInfo) => {
    sendToRenderer(getWindow(), 'update-available', {
      version: info.version,
      releaseDate: info.releaseDate,
      channel: updateChannel,
    })
  })

  autoUpdater.on('update-not-available', () => {
    sendToRenderer(getWindow(), 'update-not-available')
  })

  autoUpdater.on('download-progress', (progress: ProgressInfo) => {
    sendToRenderer(getWindow(), 'download-progress', progress)
  })

  autoUpdater.on('update-downloaded', (info: UpdateInfo) => {
    sendToRenderer(getWindow(), 'update-downloaded', {
      version: info.version,
      channel: updateChannel,
    })
  })

  autoUpdater.on('error', (error: Error) => {
    sendToRenderer(getWindow(), 'update-error', {
      message: error.message,
    })
  })
}

export function registerUpdateIpcHandlers(): void {
  if (updateHandlersRegistered) {
    return
  }
  updateHandlersRegistered = true

  ipcMain.handle('check-update', async () => {
    try {
      return await autoUpdater.checkForUpdates()
    } catch (error) {
      return {
        ok: false,
        message: error instanceof Error ? error.message : 'Unknown update check error',
      }
    }
  })

  ipcMain.handle('download-update', async () => {
    try {
      await autoUpdater.downloadUpdate()
      return { ok: true }
    } catch (error) {
      return {
        ok: false,
        message: error instanceof Error ? error.message : 'Unknown update download error',
      }
    }
  })

  ipcMain.handle('quit-and-install', () => {
    autoUpdater.quitAndInstall(false, true)
    return { ok: true }
  })

  ipcMain.handle('update-channel', () => {
    return {
      channel: updateChannel,
      currentVersion: app.getVersion(),
    }
  })
}
