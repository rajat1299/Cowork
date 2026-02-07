import { ORCHESTRATOR_URL } from '../api/client'
import type { ArtifactInfo } from '../types/chat'

export type ArtifactPreviewType = 'markdown' | 'text' | 'image' | 'unsupported'

const MARKDOWN_EXTENSIONS = new Set(['md', 'markdown', 'mdx'])
const TEXT_EXTENSIONS = new Set([
  'txt',
  'log',
  'json',
  'yaml',
  'yml',
  'xml',
  'csv',
  'ts',
  'tsx',
  'js',
  'jsx',
  'mjs',
  'cjs',
  'py',
  'go',
  'rs',
  'java',
  'kt',
  'swift',
  'rb',
  'php',
  'html',
  'css',
  'scss',
  'sql',
  'sh',
  'bash',
  'zsh',
  'toml',
  'ini',
  'conf',
])
const IMAGE_EXTENSIONS = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp'])

function extensionFromPath(path: string): string {
  const clean = path.split('?')[0].split('#')[0]
  const fileName = clean.split('/').pop() || clean
  const dot = fileName.lastIndexOf('.')
  if (dot < 0 || dot === fileName.length - 1) return ''
  return fileName.slice(dot + 1).toLowerCase()
}

function normalizeLegacyWorkdirPath(pathValue: string): string | undefined {
  const normalized = pathValue.replace(/^file:\/\//i, '').trim()
  const matcher = normalized.match(/(?:^|\/)workdir\/([^/]+)\/(.+)$/)
  if (!matcher) return undefined

  const projectId = matcher[1]
  const relativePath = matcher[2]
  if (!projectId || !relativePath) return undefined

  return `/files/generated/${encodeURIComponent(projectId)}/download?path=${encodeURIComponent(relativePath)}`
}

export function normalizeArtifactUrl(url?: string, path?: string): string | undefined {
  const primary = (url || '').trim()
  const secondary = (path || '').trim()
  const candidates = [primary, secondary].filter(Boolean)
  if (candidates.length === 0) return undefined

  for (const candidate of candidates) {
    if (candidate.startsWith('http://') || candidate.startsWith('https://')) return candidate
    if (candidate.startsWith('/files/')) return candidate
    const normalizedLegacy = normalizeLegacyWorkdirPath(candidate)
    if (normalizedLegacy) return normalizedLegacy
  }

  return primary || secondary || undefined
}

export function resolveArtifactUrl(url?: string, path?: string): string | undefined {
  const normalized = normalizeArtifactUrl(url, path)
  if (!normalized) return undefined
  if (normalized.startsWith('http://') || normalized.startsWith('https://')) return normalized
  return `${ORCHESTRATOR_URL}${normalized.startsWith('/') ? '' : '/'}${normalized}`
}

export function getArtifactExtension(artifact: Pick<ArtifactInfo, 'name' | 'path' | 'contentUrl'>): string {
  return (
    extensionFromPath(artifact.name || '') ||
    extensionFromPath(artifact.path || '') ||
    extensionFromPath(artifact.contentUrl || '')
  )
}

export function getArtifactPreviewType(
  artifact: Pick<ArtifactInfo, 'name' | 'path' | 'contentUrl' | 'type'>
): ArtifactPreviewType {
  if (artifact.type === 'image') return 'image'

  const extension = getArtifactExtension(artifact)
  if (IMAGE_EXTENSIONS.has(extension)) return 'image'
  if (MARKDOWN_EXTENSIONS.has(extension)) return 'markdown'
  if (TEXT_EXTENSIONS.has(extension) || artifact.type === 'code') return 'text'
  return 'unsupported'
}

export function canPreviewArtifact(
  artifact: Pick<ArtifactInfo, 'name' | 'path' | 'contentUrl' | 'type'>
): boolean {
  return getArtifactPreviewType(artifact) !== 'unsupported'
}
