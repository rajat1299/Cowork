import { create } from 'zustand'
import type { ArtifactInfo } from '../types/chat'
import { resolveArtifactUrl } from '../lib/artifacts'

export interface OpenArtifact extends ArtifactInfo {
  resolvedUrl?: string
}

interface ViewerState {
  artifact: OpenArtifact | null
  widthRatio: number
  openArtifact: (artifact: ArtifactInfo) => void
  closeArtifact: () => void
  setWidthRatio: (ratio: number) => void
}

function clampRatio(value: number): number {
  if (Number.isNaN(value)) return 0.46
  return Math.min(0.72, Math.max(0.3, value))
}

export const useViewerStore = create<ViewerState>((set) => ({
  artifact: null,
  widthRatio: 0.46,

  openArtifact: (artifact) => {
    set({
      artifact: {
        ...artifact,
        resolvedUrl: resolveArtifactUrl(artifact.contentUrl, artifact.path),
      },
    })
  },

  closeArtifact: () => {
    set({ artifact: null })
  },

  setWidthRatio: (ratio) => {
    set({ widthRatio: clampRatio(ratio) })
  },
}))
