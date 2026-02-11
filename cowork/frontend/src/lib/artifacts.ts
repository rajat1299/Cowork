import { ORCHESTRATOR_URL } from '../api/client'
import type { ArtifactInfo } from '../types/chat'

export type ArtifactPreviewType = 'markdown' | 'text' | 'image' | 'unsupported'

const BLOCKED_ARTIFACT_PATH_SEGMENTS = new Set([
  '.initial_env',
  '.venv',
  'venv',
  'site-packages',
  'dist-info',
  '__pycache__',
  '.git',
  'node_modules',
])
const BLOCKED_ARTIFACT_METADATA_NAMES = new Set([
  'top_level.txt',
  'entry_points.txt',
  'dependency_links.txt',
  'sources.txt',
  'api_tests.txt',
])

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

function normalizeNameForDenylist(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_')
    .replace(/_+/g, '_')
}

function safeDecode(value: string): string {
  try {
    return decodeURIComponent(value)
  } catch {
    return value
  }
}

function splitPathSegments(value: string): string[] {
  const normalized = safeDecode(value)
    .replace(/^file:\/\//i, '')
    .replace(/[?#].*$/, '')
    .replace(/\\/g, '/')
  return normalized
    .split('/')
    .map((segment) => segment.trim().toLowerCase())
    .filter(Boolean)
}

function hasBlockedPathSegment(value: string): boolean {
  const segments = splitPathSegments(value)
  return segments.some((segment) => {
    if (BLOCKED_ARTIFACT_PATH_SEGMENTS.has(segment)) return true
    if (segment.endsWith('.dist-info')) return true
    return segment.includes('site-packages')
  })
}

function basenameFromPath(value: string): string {
  const normalized = safeDecode(value).replace(/[?#].*$/, '').replace(/\\/g, '/')
  const fileName = normalized.split('/').pop() || normalized
  return fileName.trim()
}

function hasBlockedMetadataName(value: string | undefined): boolean {
  if (!value) return false
  const normalized = normalizeNameForDenylist(value)
  return BLOCKED_ARTIFACT_METADATA_NAMES.has(normalized)
}

function extractPathFromContentUrl(url: string): string | undefined {
  const trimmed = url.trim()
  if (!trimmed) return undefined
  const queryIndex = trimmed.indexOf('?')
  if (queryIndex < 0) return undefined
  const query = trimmed.slice(queryIndex + 1)
  const params = new URLSearchParams(query)
  const path = params.get('path')
  return path ? safeDecode(path) : undefined
}

export function isBlockedArtifact(
  artifact: Pick<ArtifactInfo, 'name' | 'path' | 'contentUrl'>
): boolean {
  if (hasBlockedMetadataName(artifact.name)) return true

  const candidates = [artifact.path, artifact.contentUrl].filter(
    (value): value is string => Boolean(value && value.trim())
  )
  for (const candidate of candidates) {
    if (hasBlockedPathSegment(candidate)) return true
    if (hasBlockedMetadataName(basenameFromPath(candidate))) return true

    const extractedPath = extractPathFromContentUrl(candidate)
    if (extractedPath) {
      if (hasBlockedPathSegment(extractedPath)) return true
      if (hasBlockedMetadataName(basenameFromPath(extractedPath))) return true
    }
  }
  return false
}

export function filterUserArtifacts<T extends Pick<ArtifactInfo, 'name' | 'path' | 'contentUrl'>>(
  artifacts: T[]
): T[] {
  return artifacts.filter((artifact) => !isBlockedArtifact(artifact))
}

function normalizeFamilySegment(value: string): string {
  return safeDecode(value)
    .trim()
    .toLowerCase()
    .replace(/[\s_-]+/g, '')
    .replace(/[^a-z0-9.]/g, '')
}

function basenameAndExtension(value: string): { stem: string; extension: string } {
  const fileName = basenameFromPath(value)
  const dot = fileName.lastIndexOf('.')
  if (dot < 0 || dot === fileName.length - 1) {
    return { stem: fileName, extension: '' }
  }
  return {
    stem: fileName.slice(0, dot),
    extension: fileName.slice(dot + 1),
  }
}

function candidateArtifactPath(artifact: Pick<ArtifactInfo, 'name' | 'path' | 'contentUrl'>): string {
  if (artifact.path && artifact.path.trim()) return artifact.path
  if (artifact.contentUrl && artifact.contentUrl.trim()) {
    const extracted = extractPathFromContentUrl(artifact.contentUrl)
    if (extracted) return extracted
    return artifact.contentUrl
  }
  return artifact.name || ''
}

export function artifactFamilyKey(
  artifact: Pick<ArtifactInfo, 'name' | 'path' | 'contentUrl'>
): string {
  const candidate = candidateArtifactPath(artifact)
  const normalizedPath = safeDecode(candidate)
    .replace(/^file:\/\//i, '')
    .replace(/[?#].*$/, '')
    .replace(/\\/g, '/')
  const segments = normalizedPath.split('/').filter(Boolean)
  const fileName = segments.pop() || artifact.name || ''
  const parentKey = segments.map(normalizeFamilySegment).join('/')
  const { stem, extension } = basenameAndExtension(fileName)
  const normalizedStem = normalizeFamilySegment(stem)
  const normalizedExtension = normalizeFamilySegment(extension)
  return `${parentKey}|${normalizedStem}.${normalizedExtension}`
}

function artifactScore(
  artifact: Pick<ArtifactInfo, 'createdAt' | 'action' | 'path' | 'contentUrl'>,
  index: number
): number {
  const createdAtScore = artifact.createdAt || 0
  const modifiedScore = artifact.action === 'modified' ? 1 : 0
  const pathScore = artifact.path || artifact.contentUrl ? 1 : 0
  return createdAtScore * 1000 + modifiedScore * 10 + pathScore + index / 100000
}

export function dedupeArtifactsByCanonicalName<
  T extends Pick<ArtifactInfo, 'id' | 'name' | 'path' | 'contentUrl' | 'createdAt' | 'action'>
>(artifacts: T[]): T[] {
  const filtered = filterUserArtifacts(artifacts)
  const byId = new Map<string, { artifact: T; score: number }>()
  const idless: T[] = []

  filtered.forEach((artifact, index) => {
    const id = String(artifact.id || '').trim()
    const score = artifactScore(artifact, index)
    if (!id) {
      idless.push(artifact)
      return
    }
    const existing = byId.get(id)
    if (!existing || score >= existing.score) {
      byId.set(id, { artifact, score })
    }
  })

  const merged = [...Array.from(byId.values(), (item) => item.artifact), ...idless]
  const byFamily = new Map<string, { artifact: T; score: number }>()
  merged.forEach((artifact, index) => {
    const key = artifactFamilyKey(artifact)
    const score = artifactScore(artifact, index)
    const existing = byFamily.get(key)
    if (!existing || score >= existing.score) {
      byFamily.set(key, { artifact, score })
    }
  })

  return Array.from(byFamily.values(), (item) => item.artifact).sort(
    (a, b) => (a.createdAt || 0) - (b.createdAt || 0)
  )
}

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
