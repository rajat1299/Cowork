import { copyFile, rm, stat } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'

import log from 'electron-log'

import {
  type ServiceName,
  ensureExecutable,
  ensureRuntimeDirectories,
  getBundledUvPath,
  getManagedUvPath,
  getServicePath,
  getVenvPath,
  getVenvPythonPath,
  runCommand,
} from './process'

export type InstallProgress = {
  step: string
  percent: number
  detail?: string
}

type BootstrapOptions = {
  appVersion: string
  onProgress?: (progress: InstallProgress) => void
}

function emitProgress(options: BootstrapOptions, progress: InstallProgress): void {
  options.onProgress?.(progress)
}

async function fileExists(filePath: string): Promise<boolean> {
  try {
    await stat(filePath)
    return true
  } catch {
    return false
  }
}

async function findSystemUvBinary(): Promise<string | null> {
  const lookupCommand = process.platform === 'win32' ? 'where' : 'which'
  try {
    const result = await runCommand(lookupCommand, ['uv'])
    const first = result.stdout.split(/\r?\n/).map((item) => item.trim()).find(Boolean)
    return first ?? null
  } catch {
    return null
  }
}

async function ensureUvBinary(): Promise<string> {
  const managedPath = getManagedUvPath()
  if (await fileExists(managedPath)) {
    await ensureExecutable(managedPath)
    return managedPath
  }

  const systemUv = await findSystemUvBinary()
  if (systemUv) {
    await copyFile(systemUv, managedPath)
    await ensureExecutable(managedPath)
    log.info(`Copied system uv binary from ${systemUv} -> ${managedPath}`)
    return managedPath
  }

  const bundledPath = getBundledUvPath()
  if (await fileExists(bundledPath)) {
    await copyFile(bundledPath, managedPath)
    await ensureExecutable(managedPath)
    log.info(`Copied bundled uv binary from ${bundledPath} -> ${managedPath}`)
    return managedPath
  }

  throw new Error(
    `Unable to install uv: no system binary found and no bundled binary at ${bundledPath}. ` +
      'Place a uv binary in desktop/resources/uv before packaging.'
  )
}

async function ensurePython310(uvPath: string): Promise<void> {
  try {
    await runCommand(uvPath, ['python', 'find', '3.10'])
  } catch {
    log.info('Python 3.10 runtime not found in uv cache, installing now')
    await runCommand(uvPath, ['python', 'install', '3.10'])
  }
}

async function ensureServiceEnvironment(
  service: ServiceName,
  appVersion: string,
  uvPath: string,
  onProgress?: (progress: InstallProgress) => void,
  percent = 50
): Promise<string> {
  const servicePath = getServicePath(service)
  const venvPath = getVenvPath(service, appVersion)
  const venvPython = getVenvPythonPath(venvPath)

  if (await fileExists(venvPython)) {
    onProgress?.({
      step: `venv-ready:${service}`,
      percent,
      detail: `Using existing environment at ${venvPath}`,
    })
    return venvPath
  }

  onProgress?.({
    step: `venv-create:${service}`,
    percent,
    detail: `Installing Python dependencies for ${service}`,
  })

  await runCommand(uvPath, ['sync', '--frozen', '--project', servicePath], {
    cwd: servicePath,
    env: {
      ...process.env,
      UV_PROJECT_ENVIRONMENT: venvPath,
    },
  })

  return venvPath
}

export async function repairServiceVenv(service: ServiceName, appVersion: string): Promise<void> {
  const venvPath = getVenvPath(service, appVersion)
  await rm(venvPath, { recursive: true, force: true })
}

export async function ensureDesktopBootstrap(options: BootstrapOptions): Promise<{
  uvPath: string
  coreApiVenvPath: string
  orchestratorVenvPath: string
}> {
  await ensureRuntimeDirectories()

  emitProgress(options, { step: 'bootstrap:init', percent: 5, detail: 'Preparing desktop runtime directories' })

  emitProgress(options, { step: 'bootstrap:uv', percent: 15, detail: 'Checking uv binary' })
  const uvPath = await ensureUvBinary()

  emitProgress(options, { step: 'bootstrap:python', percent: 30, detail: 'Checking Python 3.10+' })
  await ensurePython310(uvPath)

  const coreApiVenvPath = await ensureServiceEnvironment(
    'core_api',
    options.appVersion,
    uvPath,
    options.onProgress,
    60
  )

  const orchestratorVenvPath = await ensureServiceEnvironment(
    'orchestrator',
    options.appVersion,
    uvPath,
    options.onProgress,
    85
  )

  emitProgress(options, { step: 'bootstrap:done', percent: 100, detail: 'Desktop dependencies are ready' })

  return {
    uvPath,
    coreApiVenvPath,
    orchestratorVenvPath,
  }
}

export function buildDesktopDatabaseUrl(): string {
  const dbPath = path.join(os.homedir(), '.cowork', 'data', 'cowork.db')
  return `sqlite:///${dbPath}`
}
