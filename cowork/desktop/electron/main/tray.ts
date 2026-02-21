import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { app, BrowserWindow, Menu, Tray } from 'electron'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

let tray: Tray | null = null

export function createTray(getMainWindow: () => BrowserWindow | null): Tray | null {
  // Tray icon path — expects a 16x16 or Template image in the resources folder
  // During dev, fall back gracefully if icon doesn't exist yet
  const iconName = process.platform === 'darwin' ? 'trayTemplate.png' : 'tray.png'
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, iconName)
    : path.join(__dirname, '../../resources', iconName)

  try {
    tray = new Tray(iconPath)
  } catch {
    // Icon not available yet — skip tray creation (dev mode)
    return null
  }

  tray.setToolTip('Cowork')

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show Cowork',
      click: () => {
        const win = getMainWindow() ?? BrowserWindow.getAllWindows()[0]
        if (win) {
          if (win.isMinimized()) win.restore()
          win.show()
          win.focus()
        }
      },
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        app.quit()
      },
    },
  ])

  tray.setContextMenu(contextMenu)

  tray.on('click', () => {
    const win = getMainWindow() ?? BrowserWindow.getAllWindows()[0]
    if (win) {
      if (win.isMinimized()) win.restore()
      win.show()
      win.focus()
    }
  })

  return tray
}

export function destroyTray(): void {
  if (tray) {
    tray.destroy()
    tray = null
  }
}
