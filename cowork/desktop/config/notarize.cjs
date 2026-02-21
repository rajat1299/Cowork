const path = require('node:path')
const { notarize } = require('@electron/notarize')

module.exports = async function notarizeBuild(context) {
  if (process.platform !== 'darwin') {
    return
  }

  const appleId = process.env.APPLE_ID
  const appleIdPassword = process.env.APPLE_APP_SPECIFIC_PASSWORD
  const teamId = process.env.APPLE_TEAM_ID

  if (!appleId || !appleIdPassword || !teamId) {
    console.warn(
      '[notarize] Skipping notarization because APPLE_ID, APPLE_APP_SPECIFIC_PASSWORD, or APPLE_TEAM_ID is missing'
    )
    return
  }

  const appName = context.packager.appInfo.productFilename
  const appPath = path.join(context.appOutDir, `${appName}.app`)

  await notarize({
    appBundleId: 'com.cowork.app',
    appPath,
    appleId,
    appleIdPassword,
    teamId,
  })
}
