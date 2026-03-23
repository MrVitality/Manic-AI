'use client'

import { useState, useCallback, useEffect } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type ChunkStrategy = 'simple' | 'semantic'

interface ChunkPreview {
  index: number
  content: string
  token_count: number
  char_count: number
  start_char: number
  end_char: number
}

interface PreviewResponse {
  chunks: ChunkPreview[]
  total_chunks: number
  avg_tokens: number
  min_tokens: number
  max_tokens: number
  strategy: string
}

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------

async function previewChunks(
  content: string,
  strategy: ChunkStrategy,
  chunkSize: number,
  overlap: number,
): Promise<PreviewResponse> {
  const apiUrl = (() => {
    if (typeof window === 'undefined') return 'http://localhost:8081'
    try {
      const raw = localStorage.getItem('manic-ai-ui')
      if (raw) {
        const parsed = JSON.parse(raw) as { state?: { settings?: { apiUrl?: string } } }
        const candidate = parsed?.state?.settings?.apiUrl
        if (candidate) return candidate
      }
    } catch { /* ignore */ }
    return process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8081'
  })()

  const response = await fetch(`${apiUrl}/v1/ingest/preview-chunks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      content,
      strategy,
      chunk_size: chunkSize,
      overlap,
    }),
  })

  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`)
  }

  const envelope = await response.json() as { success?: boolean; data?: PreviewResponse; error?: string }
  if (envelope.success === false) {
    throw new Error(envelope.error ?? 'Preview failed')
  }
  return (envelope.data ?? envelope) as PreviewResponse
}

// ---------------------------------------------------------------------------
// Alternating chunk card colors
// ---------------------------------------------------------------------------

const CHUNK_ACCENTS = [
  { border: 'var(--accent-primary)', bg: 'color-mix(in srgb, var(--accent-primary) 6%, transparent)' },
  { border: 'var(--accent-cyan)', bg: 'color-mix(in srgb, var(--accent-cyan) 6%, transparent)' },
]

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function ToolsPage() {
  const [docContent, setDocContent] = useState('')
  const [strategy, setStrategy] = useState<ChunkStrategy>('simple')
  const [chunkSize, setChunkSize] = useState(512)
  const [overlap, setOverlap] = useState(64)
  const [isLoading, setIsLoading] = useState(false)
  const [result, setResult] = useState<PreviewResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { document.title = 'Tools — Manic AI' }, [])

  const handlePreview = useCallback(async () => {
    if (!docContent.trim() || isLoading) return
    setError(null)
    setResult(null)
    setIsLoading(true)
    try {
      const data = await previewChunks(docContent, strategy, chunkSize, overlap)
      setResult(data)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setIsLoading(false)
    }
  }, [docContent, strategy, chunkSize, overlap, isLoading])

  const charCount = docContent.length
  const wordCount = docContent.trim() ? docContent.trim().split(/\s+/).length : 0

  return (
    <div
      className="flex flex-col h-full min-h-0 font-mono overflow-y-auto"
      style={{ background: 'var(--bg-primary)' }}
    >
      {/* Page header */}
      <div
        className="flex items-center gap-3 px-6 py-3 border-b shrink-0"
        style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
      >
        <span className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--accent-primary)' }}>
          [TOOLS]
        </span>
        <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
          // Developer utilities &amp; inspectors
        </span>
      </div>

      <div className="flex-1 p-6 space-y-6 max-w-5xl w-full mx-auto">
        {/* Section header */}
        <div>
          <h2 className="text-sm font-bold uppercase tracking-widest mb-1" style={{ color: 'var(--accent-cyan)' }}>
            [CHUNKING_COMPARATOR]
          </h2>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            // Preview how your documents will be split before ingestion. Adjust strategy and parameters.
          </p>
        </div>

        {/* Controls row */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Strategy */}
          <div
            className="p-4 rounded-sm border"
            style={{ borderColor: 'var(--border-color)', background: 'var(--glass-bg)' }}
          >
            <label className="block text-[10px] uppercase tracking-widest mb-3" style={{ color: 'var(--text-muted)' }}>
              [STRATEGY]
            </label>
            <div className="flex gap-2">
              {(['simple', 'semantic'] as ChunkStrategy[]).map((s) => (
                <button
                  key={s}
                  onClick={() => setStrategy(s)}
                  className="flex-1 py-2 text-xs rounded-sm border transition-all uppercase tracking-wide"
                  style={{
                    borderColor: strategy === s ? 'var(--accent-primary)' : 'var(--border-color)',
                    color: strategy === s ? 'var(--accent-primary)' : 'var(--text-muted)',
                    background:
                      strategy === s
                        ? 'color-mix(in srgb, var(--accent-primary) 10%, transparent)'
                        : 'transparent',
                  }}
                >
                  [{s}]
                </button>
              ))}
            </div>
            <p className="text-[10px] mt-2" style={{ color: 'var(--text-muted)' }}>
              {strategy === 'simple'
                ? '// Fixed-size character splitting with overlap'
                : '// Sentence-boundary aware semantic chunking'}
            </p>
          </div>

          {/* Sliders */}
          <div
            className="p-4 rounded-sm border space-y-4"
            style={{ borderColor: 'var(--border-color)', background: 'var(--glass-bg)' }}
          >
            <SliderField
              label="CHUNK_SIZE"
              value={chunkSize}
              min={64}
              max={2048}
              step={64}
              unit="chars"
              onChange={setChunkSize}
            />
            <SliderField
              label="OVERLAP"
              value={overlap}
              min={0}
              max={512}
              step={16}
              unit="chars"
              onChange={setOverlap}
            />
          </div>
        </div>

        {/* Document textarea */}
        <div
          className="p-4 rounded-sm border"
          style={{ borderColor: 'var(--border-color)', background: 'var(--glass-bg)' }}
        >
          <div className="flex items-center justify-between mb-2">
            <label className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
              [DOCUMENT_CONTENT]
            </label>
            <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
              {charCount.toLocaleString()} chars · {wordCount.toLocaleString()} words
            </span>
          </div>
          <textarea
            value={docContent}
            onChange={(e) => setDocContent(e.target.value)}
            placeholder="// Paste your document content here to preview chunking..."
            rows={10}
            className="w-full p-3 text-xs rounded-sm resize-none focus:outline-none"
            style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              fontFamily: 'monospace',
            }}
            onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent-primary)')}
            onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-color)')}
          />
          <div className="mt-3 flex items-center justify-between">
            <div />
            <button
              onClick={handlePreview}
              disabled={!docContent.trim() || isLoading}
              className="px-5 py-2 text-xs rounded-sm border transition-all uppercase tracking-wide disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                borderColor: 'var(--accent-primary)',
                color: 'var(--accent-primary)',
                background: 'color-mix(in srgb, var(--accent-primary) 10%, transparent)',
              }}
            >
              {isLoading ? '[PROCESSING...]' : '[PREVIEW_CHUNKS]'}
            </button>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div
            className="px-4 py-3 rounded-sm border text-xs"
            style={{ borderColor: '#ef444488', background: 'color-mix(in srgb, #ef4444 8%, transparent)', color: '#ef4444' }}
          >
            ERR: {error}
          </div>
        )}

        {/* Stats bar */}
        {result && (
          <div
            className="grid grid-cols-2 md:grid-cols-5 gap-3 p-4 rounded-sm border"
            style={{ borderColor: 'var(--border-color)', background: 'var(--glass-bg)' }}
          >
            {[
              { label: 'TOTAL_CHUNKS', value: result.total_chunks, color: 'var(--accent-primary)' },
              { label: 'AVG_TOKENS', value: Math.round(result.avg_tokens), color: 'var(--accent-cyan)' },
              { label: 'MIN_TOKENS', value: result.min_tokens, color: '#4ade80' },
              { label: 'MAX_TOKENS', value: result.max_tokens, color: '#f59e0b' },
              { label: 'STRATEGY', value: result.strategy.toUpperCase(), color: 'var(--text-secondary)', isText: true },
            ].map(({ label, value, color, isText }) => (
              <div key={label} className="text-center">
                <p className="text-[10px] mb-1" style={{ color: 'var(--text-muted)' }}>
                  {label}
                </p>
                <p className={`font-bold ${isText ? 'text-xs' : 'text-lg'}`} style={{ color }}>
                  {value}
                </p>
              </div>
            ))}
          </div>
        )}

        {/* Chunk cards */}
        {result && result.chunks.length > 0 && (
          <div>
            <p className="text-[10px] uppercase tracking-widest mb-3" style={{ color: 'var(--text-muted)' }}>
              [CHUNKS: {result.chunks.length}]
            </p>
            <div className="space-y-2">
              {result.chunks.map((chunk) => {
                const accent = CHUNK_ACCENTS[chunk.index % CHUNK_ACCENTS.length]
                return (
                  <div
                    key={chunk.index}
                    className="rounded-sm border p-3"
                    style={{ borderColor: accent.border, background: accent.bg }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span
                        className="font-bold text-[10px] uppercase tracking-widest"
                        style={{ color: accent.border }}
                      >
                        CHUNK_{String(chunk.index + 1).padStart(3, '0')}
                      </span>
                      <div className="flex items-center gap-4 text-[10px]" style={{ color: 'var(--text-muted)' }}>
                        <span>
                          TOKENS:{' '}
                          <span style={{ color: accent.border }}>{chunk.token_count}</span>
                        </span>
                        <span>
                          CHARS:{' '}
                          <span style={{ color: 'var(--text-secondary)' }}>{chunk.char_count}</span>
                        </span>
                        <span>
                          [{chunk.start_char}:{chunk.end_char}]
                        </span>
                      </div>
                    </div>
                    <pre
                      className="whitespace-pre-wrap break-words leading-relaxed text-xs"
                      style={{ color: 'var(--text-primary)', fontFamily: 'monospace' }}
                    >
                      {chunk.content}
                    </pre>
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Reusable slider field
// ---------------------------------------------------------------------------

function SliderField({
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  unit: string
  onChange: (v: number) => void
}) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <label className="text-[10px] uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
          {label}
        </label>
        <span className="text-[10px]" style={{ color: 'var(--accent-primary)' }}>
          {value} {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-1.5 rounded-sm appearance-none cursor-pointer"
        style={{
          accentColor: 'var(--accent-primary)',
          background: `linear-gradient(to right, var(--accent-primary) 0%, var(--accent-primary) ${((value - min) / (max - min)) * 100}%, var(--border-color) ${((value - min) / (max - min)) * 100}%, var(--border-color) 100%)`,
        }}
      />
      <div className="flex justify-between text-[10px] mt-0.5" style={{ color: 'var(--text-muted)' }}>
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  )
}
