import { app, BrowserWindow } from 'electron'

const PROTOCOL = 'cowork'

/**
 * Register the `cowork://` deep-link protocol.
 *
 * Handles URLs like:
 *   cowork://oauth/callback?code=xxx&state=yyy
 *   cowork://open/project/abc
 */
export function registerDeepLinkProtocol(getMainWindow: () => BrowserWindow | null): void {
  // Set as default protocol client (works for macOS .app bundles and Windows)
  if (!app.isDefaultProtocolClient(PROTOCOL)) {
    app.setAsDefaultProtocolClient(PROTOCOL)
  }

  // macOS: open-url fires when the app is already running or launched via URL
  app.on('open-url', (event, url) => {
    event.preventDefault()
    handleDeepLink(url, getMainWindow)
  })

  // Windows/Linux: deep link URL arrives as a command-line argument
  app.on('second-instance', (_event, argv) => {
    const url = argv.find((arg) => arg.startsWith(`${PROTOCOL}://`))
    if (url) {
      handleDeepLink(url, getMainWindow)
    }

    // Focus the existing window
    const win = getMainWindow() ?? BrowserWindow.getAllWindows()[0]
    if (win) {
      if (win.isMinimized()) win.restore()
      win.show()
      win.focus()
    }
  })
}

function handleDeepLink(url: string, getMainWindow: () => BrowserWindow | null): void {
  const win = getMainWindow() ?? BrowserWindow.getAllWindows()[0]
  if (!win || win.isDestroyed()) return

  // Forward the deep link URL to the renderer so the React app can handle routing
  win.webContents.send('deep-link', url)

  if (win.isMinimized()) win.restore()
  win.show()
  win.focus()
}
