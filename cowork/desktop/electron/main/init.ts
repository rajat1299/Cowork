import type { ChildProcessWithoutNullStreams } from 'node:child_process'

import { app } from 'electron'
import log from 'electron-log'

import { buildDesktopDatabaseUrl, ensureDesktopBootstrap } from './utils/bootstrap'
import {
  type ServiceName,
  findAvailablePort,
  getServicePath,
  getVenvPath,
  gracefulKill,
  spawnServiceProcess,
  waitForHealth,
  writePortsFile,
} from './utils/process'

export type BackendPorts = {
  coreApi: number
  orchestrator: number
}

export type BackendEventName = 'backend-starting' | 'backend-progress' | 'backend-ready' | 'backend-error'

export type BackendEventEmitter = (event: BackendEventName, payload?: unknown) => void

type ManagedProcess = {
  service: ServiceName
  child: ChildProcessWithoutNullStreams
  logFile: string
}

let currentPorts: BackendPorts | null = null
let managedProcesses: ManagedProcess[] = []

function emit(emitEvent: BackendEventEmitter | undefined, event: BackendEventName, payload?: unknown): void {
  emitEvent?.(event, payload)
}

function buildServiceEnv(base: NodeJS.ProcessEnv, overrides: Record<string, string>): NodeJS.ProcessEnv {
  return {
    ...base,
    ...overrides,
  }
}

async function spawnBackendService(params: {
  service: ServiceName
  uvPath: string
  venvPath: string
  port: number
  env: NodeJS.ProcessEnv
}): Promise<ManagedProcess> {
  const servicePath = getServicePath(params.service)

  const spawned = spawnServiceProcess({
    command: params.uvPath,
    args: ['run', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(params.port)],
    cwd: servicePath,
    env: buildServiceEnv(params.env, {
      UV_PROJECT_ENVIRONMENT: params.venvPath,
      PYTHONUNBUFFERED: '1',
      PYTHONIOENCODING: 'utf-8',
    }),
    logName: params.service,
  })

  spawned.child.on('exit', (code, signal) => {
    log.info(`${params.service} exited (code=${code}, signal=${signal})`)
  })

  return {
    service: params.service,
    child: spawned.child,
    logFile: spawned.logFile,
  }
}

export function getBackendPorts(): BackendPorts | null {
  return currentPorts
}

export async function startBackendServices(emitEvent?: BackendEventEmitter): Promise<BackendPorts> {
  if (currentPorts) {
    return currentPorts
  }

  emit(emitEvent, 'backend-starting', {
    step: 'starting',
    message: 'Starting Cowork backend services',
  })

  try {
    const appVersion = app.getVersion()
    const bootstrap = await ensureDesktopBootstrap({
      appVersion,
      onProgress: (progress) => emit(emitEvent, 'backend-progress', progress),
    })

    const coreApiPort = await findAvailablePort(3001)
    const orchestratorPort = await findAvailablePort(coreApiPort === 5001 ? 5002 : 5001)

    emit(emitEvent, 'backend-progress', {
      step: 'spawn-core-api',
      percent: 90,
      detail: `Starting core_api on port ${coreApiPort}`,
    })

    const desktopDatabaseUrl = buildDesktopDatabaseUrl()

    const coreApi = await spawnBackendService({
      service: 'core_api',
      uvPath: bootstrap.uvPath,
      venvPath: bootstrap.coreApiVenvPath || getVenvPath('core_api', appVersion),
      port: coreApiPort,
      env: {
        ...process.env,
        APP_ENV: 'desktop',
        DATABASE_URL: desktopDatabaseUrl,
        AUTO_CREATE_TABLES: 'true',
      },
    })

    emit(emitEvent, 'backend-progress', {
      step: 'spawn-orchestrator',
      percent: 93,
      detail: `Starting orchestrator on port ${orchestratorPort}`,
    })

    const orchestrator = await spawnBackendService({
      service: 'orchestrator',
      uvPath: bootstrap.uvPath,
      venvPath: bootstrap.orchestratorVenvPath || getVenvPath('orchestrator', appVersion),
      port: orchestratorPort,
      env: {
        ...process.env,
        APP_ENV: 'desktop',
        CORE_API_URL: `http://127.0.0.1:${coreApiPort}`,
        CORE_API_INTERNAL_KEY: process.env.CORE_API_INTERNAL_KEY || '',
      },
    })

    managedProcesses = [coreApi, orchestrator]

    emit(emitEvent, 'backend-progress', {
      step: 'health-check',
      percent: 96,
      detail: 'Waiting for backend health checks',
    })

    await Promise.all([
      waitForHealth(`http://127.0.0.1:${coreApiPort}/health`),
      waitForHealth(`http://127.0.0.1:${orchestratorPort}/health`),
    ])

    currentPorts = {
      coreApi: coreApiPort,
      orchestrator: orchestratorPort,
    }

    await writePortsFile(currentPorts)

    emit(emitEvent, 'backend-ready', currentPorts)
    return currentPorts
  } catch (error) {
    await stopBackendServices()
    const message = error instanceof Error ? error.message : 'Unknown backend startup error'
    emit(emitEvent, 'backend-error', { message })
    throw error
  }
}

export async function stopBackendServices(): Promise<void> {
  const toStop = [...managedProcesses]
  managedProcesses = []
  currentPorts = null

  await Promise.all(
    toStop.map(async (proc) => {
      await gracefulKill(proc.child, proc.service)
    })
  )
}

export async function restartBackendServices(emitEvent?: BackendEventEmitter): Promise<BackendPorts> {
  await stopBackendServices()
  return startBackendServices(emitEvent)
}
