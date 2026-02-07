import { useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { FileCode2, Eye, FolderOpen, Download, RotateCcw, X } from 'lucide-react'
import { cn } from '../../lib/utils'
import { getArtifactPreviewType, resolveArtifactUrl } from '../../lib/artifacts'
import { useViewerStore } from '../../stores/viewerStore'

function detectLanguage(fileName: string): string {
  const extension = fileName.split('.').pop()?.toLowerCase() || ''
  return extension || 'txt'
}

export function ArtifactViewerPane() {
  const artifact = useViewerStore((state) => state.artifact)
  const closeArtifact = useViewerStore((state) => state.closeArtifact)
  const [content, setContent] = useState<string>('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [refreshTick, setRefreshTick] = useState(0)

  const resolvedUrl = useMemo(() => {
    if (!artifact) return undefined
    return artifact.resolvedUrl || resolveArtifactUrl(artifact.contentUrl, artifact.path)
  }, [artifact])

  const previewType = useMemo(() => {
    if (!artifact) return 'unsupported'
    return getArtifactPreviewType(artifact)
  }, [artifact])

  useEffect(() => {
    if (!artifact) return undefined
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeArtifact()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [artifact, closeArtifact])

  useEffect(() => {
    if (!artifact || !resolvedUrl || previewType === 'unsupported' || previewType === 'image') return undefined

    const controller = new AbortController()
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    setError(null)

    void fetch(resolvedUrl, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Failed to load preview (${response.status})`)
        }
        const text = await response.text()
        setContent(text.slice(0, 250_000))
        setLoading(false)
      })
      .catch((fetchError: unknown) => {
        if (controller.signal.aborted) return
        setLoading(false)
        setError(fetchError instanceof Error ? fetchError.message : 'Unable to preview this file.')
      })

    return () => controller.abort()
  }, [artifact, resolvedUrl, previewType, refreshTick])

  if (!artifact) return null

  return (
    <aside className="h-full border-l border-border/70 bg-card/90 backdrop-blur-xl flex flex-col min-w-0">
      <header className="h-14 px-4 border-b border-border/70 flex items-center justify-between gap-3">
        <div className="min-w-0 flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg border border-border bg-secondary/60 flex items-center justify-center">
            {previewType === 'image' ? (
              <Eye size={15} className="text-muted-foreground" />
            ) : (
              <FileCode2 size={15} className="text-muted-foreground" />
            )}
          </div>
          <div className="min-w-0">
            <p className="text-[14px] font-medium text-foreground truncate">{artifact.name}</p>
            <p className="text-[12px] text-muted-foreground truncate uppercase">{previewType}</p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {resolvedUrl ? (
            <a
              href={resolvedUrl}
              target="_blank"
              rel="noreferrer"
              className="h-8 px-2.5 inline-flex items-center gap-1 rounded-md border border-border text-[12px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
            >
              <FolderOpen size={13} />
              Open
            </a>
          ) : null}
          {resolvedUrl ? (
            <a
              href={resolvedUrl}
              download={artifact.name}
              className="h-8 px-2.5 inline-flex items-center gap-1 rounded-md border border-border text-[12px] text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors"
            >
              <Download size={13} />
              Download
            </a>
          ) : null}
          {(previewType === 'markdown' || previewType === 'text') && resolvedUrl ? (
            <button
              onClick={() => setRefreshTick((tick) => tick + 1)}
              className="h-8 w-8 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors inline-flex items-center justify-center"
              aria-label="Reload preview"
            >
              <RotateCcw size={13} />
            </button>
          ) : null}
          <button
            onClick={closeArtifact}
            className="h-8 w-8 rounded-md border border-border text-muted-foreground hover:text-foreground hover:border-foreground/30 transition-colors inline-flex items-center justify-center"
            aria-label="Close preview"
          >
            <X size={13} />
          </button>
        </div>
      </header>

      <div className="flex-1 overflow-auto p-8">
        {previewType === 'image' && resolvedUrl ? (
          <img
            src={resolvedUrl}
            alt={artifact.name}
            className="w-full max-h-full object-contain rounded-xl border border-border/70 bg-background/40"
          />
        ) : null}

        {(previewType === 'markdown' || previewType === 'text') && loading ? (
          <p className="text-[13px] text-muted-foreground">Loading preview...</p>
        ) : null}

        {(previewType === 'markdown' || previewType === 'text') && error ? (
          <p className="text-[13px] text-destructive">{error}</p>
        ) : null}

        {previewType === 'markdown' && !loading && !error ? (
          <article className="max-w-none text-foreground">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                h1: ({ children }) => <h1 className="text-[40px] font-semibold tracking-tight mt-0 mb-6">{children}</h1>,
                h2: ({ children }) => <h2 className="text-[30px] font-semibold tracking-tight mt-8 mb-4">{children}</h2>,
                h3: ({ children }) => <h3 className="text-[22px] font-semibold mt-6 mb-3">{children}</h3>,
                p: ({ children }) => <p className="text-[18px] leading-9 text-foreground/95 my-3">{children}</p>,
                ul: ({ children }) => <ul className="my-4 list-disc pl-7 space-y-1.5">{children}</ul>,
                ol: ({ children }) => <ol className="my-4 list-decimal pl-7 space-y-1.5">{children}</ol>,
                li: ({ children }) => <li className="text-[18px] leading-9 text-foreground/95">{children}</li>,
                code: ({ className, children }) => (
                  <code
                    className={cn(
                      className
                        ? 'block text-[14px] leading-6 rounded-lg border border-border bg-secondary/40 p-3 overflow-x-auto'
                        : 'px-1.5 py-0.5 rounded bg-secondary/70 border border-border text-[14px]'
                    )}
                  >
                    {children}
                  </code>
                ),
                pre: ({ children }) => <pre className="m-0">{children}</pre>,
                blockquote: ({ children }) => (
                  <blockquote className="my-4 border-l-2 border-border pl-4 text-muted-foreground">{children}</blockquote>
                ),
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noreferrer"
                    className="text-foreground underline decoration-muted-foreground/40 hover:decoration-foreground"
                  >
                    {children}
                  </a>
                ),
                table: ({ children }) => (
                  <div className="my-4 overflow-x-auto">
                    <table className="w-full border-collapse text-[14px]">{children}</table>
                  </div>
                ),
                tr: ({ children }) => <tr className="border-b border-border/60">{children}</tr>,
                th: ({ children }) => <th className="px-2 py-1.5 text-left font-medium">{children}</th>,
                td: ({ children }) => <td className="px-2 py-1.5 text-muted-foreground">{children}</td>,
              }}
            >
              {content}
            </ReactMarkdown>
          </article>
        ) : null}

        {previewType === 'text' && !loading && !error ? (
          <pre className="text-[13px] leading-6 text-foreground whitespace-pre-wrap break-words rounded-xl border border-border/70 bg-secondary/25 p-5 overflow-auto">
            <code className={`language-${detectLanguage(artifact.name)}`}>{content}</code>
          </pre>
        ) : null}

        {previewType === 'unsupported' ? (
          <div className="rounded-xl border border-border/70 bg-secondary/20 p-4">
            <p className="text-[14px] text-foreground">Preview not available for this file type.</p>
            <p className="mt-1 text-[13px] text-muted-foreground">
              Use Open or Download to view it in your default app.
            </p>
          </div>
        ) : null}
      </div>
    </aside>
  )
}
