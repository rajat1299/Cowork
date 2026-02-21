import { app, BrowserWindow, globalShortcut } from 'electron'

/**
 * Register global keyboard shortcuts.
 * - Option+Space (macOS) / Alt+Space (Windows/Linux): Show/focus the main window
 */
export function registerGlobalShortcuts(getMainWindow: () => BrowserWindow | null): void {
  app.whenReady().then(() => {
    const accelerator = process.platform === 'darwin' ? 'Alt+Space' : 'Alt+Space'

    globalShortcut.register(accelerator, () => {
      const win = getMainWindow() ?? BrowserWindow.getAllWindows()[0]
      if (!win) return

      if (win.isMinimized()) {
        win.restore()
      }
      if (!win.isVisible()) {
        win.show()
      }
      win.focus()
    })
  })

  app.on('will-quit', () => {
    globalShortcut.unregisterAll()
  })
}
