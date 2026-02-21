import { createWriteStream, existsSync, mkdirSync } from 'node:fs'
import { access, mkdir, writeFile } from 'node:fs/promises'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process'

import { app } from 'electron'
import log from 'electron-log'
import kill from 'tree-kill'

export type ServiceName = 'core_api' | 'orchestrator'

export type SpawnedService = {
  child: ChildProcessWithoutNullStreams
  logFile: string
}

export type RunCommandResult = {
  stdout: string
  stderr: string
}

const UV_BINARY = process.platform === 'win32' ? 'uv.exe' : 'uv'

export function getCoworkRootDir(): string {
  return path.join(os.homedir(), '.cowork')
}

export function getCoworkBinDir(): string {
  return path.join(getCoworkRootDir(), 'bin')
}

export function getCoworkDataDir(): string {
  return path.join(getCoworkRootDir(), 'data')
}

export function getCoworkRuntimeDir(): string {
  return path.join(getCoworkRootDir(), 'runtime')
}

export function getCoworkLogsDir(): string {
  return path.join(getCoworkRootDir(), 'logs')
}

export function getPortsFilePath(): string {
  return path.join(getCoworkRuntimeDir(), 'ports.json')
}

export function getDesktopAppPath(): string {
  return app.getAppPath()
}

export function getRepoRootPath(): string {
  return path.resolve(getDesktopAppPath(), '..')
}

export function getServicePath(service: ServiceName): string {
  if (app.isPackaged) {
    return path.join(process.resourcesPath, service)
  }
  return path.join(getRepoRootPath(), service)
}

export function getDesktopResourcesPath(): string {
  if (app.isPackaged) {
    return process.resourcesPath
  }
  return path.join(getDesktopAppPath(), 'resources')
}

export function getBundledUvPath(): string {
  return path.join(getDesktopResourcesPath(), 'uv', UV_BINARY)
}

export function getManagedUvPath(): string {
  return path.join(getCoworkBinDir(), UV_BINARY)
}

export function getVenvPath(service: ServiceName, appVersion: string): string {
  const slug = service === 'core_api' ? 'core-api' : 'orchestrator'
  return path.join(getCoworkRootDir(), 'venvs', `${slug}-${appVersion}`)
}

export function getVenvPythonPath(venvPath: string): string {
  const relative = process.platform === 'win32' ? path.join('Scripts', 'python.exe') : path.join('bin', 'python')
  return path.join(venvPath, relative)
}

export function ensureDirSync(dirPath: string): void {
  if (!existsSync(dirPath)) {
    mkdirSync(dirPath, { recursive: true })
  }
}

export async function ensureRuntimeDirectories(): Promise<void> {
  await Promise.all([
    mkdir(getCoworkRootDir(), { recursive: true }),
    mkdir(getCoworkBinDir(), { recursive: true }),
    mkdir(getCoworkDataDir(), { recursive: true }),
    mkdir(getCoworkRuntimeDir(), { recursive: true }),
    mkdir(getCoworkLogsDir(), { recursive: true }),
  ])
}

export async function writePortsFile(ports: { coreApi: number; orchestrator: number }): Promise<void> {
  await ensureRuntimeDirectories()
  await writeFile(getPortsFilePath(), JSON.stringify(ports, null, 2), 'utf-8')
}

export async function runCommand(
  command: string,
  args: string[],
  options: {
    cwd?: string
    env?: NodeJS.ProcessEnv
  } = {}
): Promise<RunCommandResult> {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, {
      cwd: options.cwd,
      env: options.env,
      stdio: ['ignore', 'pipe', 'pipe'],
    })

    let stdout = ''
    let stderr = ''

    child.stdout.on('data', (chunk: Buffer) => {
      stdout += chunk.toString('utf-8')
    })
    child.stderr.on('data', (chunk: Buffer) => {
      stderr += chunk.toString('utf-8')
    })

    child.on('error', reject)
    child.on('close', (code) => {
      if (code === 0) {
        resolve({ stdout, stderr })
        return
      }
      reject(new Error(`Command failed (${command} ${args.join(' ')}) with code ${code}: ${stderr || stdout}`))
    })
  })
}

export function spawnServiceProcess(params: {
  command: string
  args: string[]
  cwd: string
  env: NodeJS.ProcessEnv
  logName: string
}): SpawnedService {
  ensureDirSync(getCoworkLogsDir())
  const logFile = path.join(getCoworkLogsDir(), `${params.logName}.log`)
  const logStream = createWriteStream(logFile, { flags: 'a' })

  const child = spawn(params.command, params.args, {
    cwd: params.cwd,
    env: params.env,
    stdio: ['pipe', 'pipe', 'pipe'],
  })

  child.stdout.on('data', (chunk: Buffer) => {
    const line = chunk.toString('utf-8')
    log.info(`[${params.logName}] ${line.trimEnd()}`)
    logStream.write(line)
  })

  child.stderr.on('data', (chunk: Buffer) => {
    const line = chunk.toString('utf-8')
    log.error(`[${params.logName}] ${line.trimEnd()}`)
    logStream.write(line)
  })

  child.on('close', () => {
    logStream.end()
  })

  return { child, logFile }
}

async function canBind(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', () => {
      resolve(false)
    })
    server.once('listening', () => {
      server.close(() => resolve(true))
    })
    server.listen(port, '127.0.0.1')
  })
}

export async function findAvailablePort(startPort: number, attempts = 100): Promise<number> {
  for (let offset = 0; offset <= attempts; offset += 1) {
    const candidate = startPort + offset
    if (await canBind(candidate)) {
      return candidate
    }
  }
  throw new Error(`Unable to find available port starting from ${startPort}`)
}

export async function waitForHealth(url: string, timeoutMs = 30_000, intervalMs = 500): Promise<void> {
  const startedAt = Date.now()
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url)
      if (response.ok) {
        return
      }
    } catch {
      // Ignore transient startup errors.
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs))
  }
  throw new Error(`Health check timed out for ${url} after ${timeoutMs}ms`)
}

export async function gracefulKill(child: ChildProcessWithoutNullStreams | null, name: string, graceMs = 3_000): Promise<void> {
  if (!child?.pid) {
    return
  }

  const pid = child.pid
  await new Promise<void>((resolve) => {
    kill(pid, 'SIGTERM', (error) => {
      if (error) {
        log.warn(`Failed to SIGTERM ${name} (${pid}): ${error.message}`)
      }
      resolve()
    })
  })

  await new Promise((resolve) => setTimeout(resolve, graceMs))

  if (child.exitCode === null) {
    await new Promise<void>((resolve) => {
      kill(pid, 'SIGKILL', (error) => {
        if (error) {
          log.warn(`Failed to SIGKILL ${name} (${pid}): ${error.message}`)
        }
        resolve()
      })
    })
  }
}

export async function ensureExecutable(filePath: string): Promise<void> {
  try {
    await access(filePath)
  } catch {
    return
  }
  if (process.platform !== 'win32') {
    await runCommand('chmod', ['755', filePath])
  }
}
