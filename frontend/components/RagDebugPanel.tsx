'use client'

import { useState } from 'react'
import type { RagSource } from '@/types'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RagDebugChunk {
  content: string
  vector_score: number
  keyword_score: number
  source: string
}

export interface RagDebugData {
  query: string
  chunks: RagDebugChunk[]
  tokenBudget?: {
    total: number
    used: number
    remaining: number
  }
}

interface RagDebugPanelProps {
  /** Whether RAG mode is active. Panel is hidden when false. */
  isRagMode: boolean
  /** Debug data to display. Pass null/undefined when no retrieval has run. */
  data?: RagDebugData | null
  /** RAG sources as returned from StreamEvent. Used to auto-populate chunks. */
  sources?: RagSource[]
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function scoreBar(score: number, color: string) {
  const pct = Math.min(Math.max(score, 0), 1) * 100
  return (
    <div
      className="h-1.5 rounded-sm overflow-hidden"
      style={{ background: 'var(--bg-primary)', width: '80px' }}
      title={`${(pct).toFixed(1)}%`}
    >
      <div
        className="h-full transition-all"
        style={{ width: `${pct}%`, background: color }}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function RagDebugPanel({ isRagMode, data, sources }: RagDebugPanelProps) {
  const [isOpen, setIsOpen] = useState(false)

  // Not visible unless RAG mode is on
  if (!isRagMode) return null

  // Derive chunks: prefer explicit data, fall back to sources from stream events
  const chunks: RagDebugChunk[] = data?.chunks.length
    ? data.chunks
    : (sources ?? []).map((s) => ({
        content: s.content ?? '',
        vector_score: s.vector_score ?? s.score ?? 0,
        keyword_score: s.keyword_score ?? 0,
        source: (s.metadata?.source as string | undefined) ?? s.document_id ?? 'unknown',
      }))

  const query = data?.query ?? ''
  const tokenBudget = data?.tokenBudget

  return (
    <div
      className="font-mono text-xs"
      style={{ borderTop: '1px solid var(--border-color)' }}
    >
      {/* Toggle header */}
      <button
        onClick={() => setIsOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-4 py-2 transition-all hover:opacity-80"
        style={{ background: 'var(--bg-secondary)' }}
        aria-expanded={isOpen}
        aria-controls="rag-debug-body"
      >
        <span
          className="px-2 py-0.5 rounded-sm border text-[10px] uppercase tracking-widest font-bold"
          style={{
            borderColor: 'var(--accent-cyan)',
            color: 'var(--accent-cyan)',
            background: 'color-mix(in srgb, var(--accent-cyan) 10%, transparent)',
          }}
        >
          [DEBUG]
        </span>
        <span style={{ color: 'var(--text-muted)' }}>
          RAG Inspector
          {chunks.length > 0 && (
            <span className="ml-2" style={{ color: 'var(--accent-cyan)' }}>
              — {chunks.length} chunk{chunks.length !== 1 ? 's' : ''} retrieved
            </span>
          )}
        </span>
        <span className="ml-auto" style={{ color: 'var(--text-muted)' }}>
          {isOpen ? '[-]' : '[+]'}
        </span>
      </button>

      {/* Collapsible body */}
      {isOpen && (
        <div
          id="rag-debug-body"
          className="p-4 space-y-4"
          style={{ background: 'var(--bg-primary)' }}
        >
          {/* Query */}
          {query && (
            <section>
              <p className="text-[10px] uppercase tracking-widest mb-1" style={{ color: 'var(--text-muted)' }}>
                QUERY
              </p>
              <div
                className="px-3 py-2 rounded-sm border"
                style={{
                  borderColor: 'var(--accent-cyan)',
                  background: 'color-mix(in srgb, var(--accent-cyan) 5%, transparent)',
                  color: 'var(--accent-cyan)',
                }}
              >
                {query}
              </div>
            </section>
          )}

          {/* Token budget */}
          {tokenBudget && (
            <section>
              <p className="text-[10px] uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
                TOKEN_BUDGET
              </p>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'TOTAL', value: tokenBudget.total, color: 'var(--text-muted)' },
                  { label: 'USED', value: tokenBudget.used, color: 'var(--accent-primary)' },
                  { label: 'REMAINING', value: tokenBudget.remaining, color: '#4ade80' },
                ].map(({ label, value, color }) => (
                  <div
                    key={label}
                    className="px-3 py-2 rounded-sm border text-center"
                    style={{ borderColor: 'var(--border-color)', background: 'var(--glass-bg)' }}
                  >
                    <p className="text-[10px] mb-0.5" style={{ color: 'var(--text-muted)' }}>
                      {label}
                    </p>
                    <p className="font-bold text-sm" style={{ color }}>
                      {value.toLocaleString()}
                    </p>
                  </div>
                ))}
              </div>
              {/* Usage bar */}
              <div
                className="mt-2 h-2 rounded-sm overflow-hidden"
                style={{ background: 'var(--bg-secondary)' }}
              >
                <div
                  className="h-full transition-all"
                  style={{
                    width: `${Math.min((tokenBudget.used / tokenBudget.total) * 100, 100).toFixed(1)}%`,
                    background: 'var(--accent-primary)',
                  }}
                />
              </div>
            </section>
          )}

          {/* Chunks */}
          <section>
            <p className="text-[10px] uppercase tracking-widest mb-2" style={{ color: 'var(--text-muted)' }}>
              RETRIEVED_CHUNKS ({chunks.length})
            </p>
            {chunks.length === 0 ? (
              <p style={{ color: 'var(--text-muted)' }}>// No chunks retrieved for this query</p>
            ) : (
              <div className="space-y-2">
                {chunks.map((chunk, idx) => (
                  <ChunkCard key={idx} chunk={chunk} index={idx} />
                ))}
              </div>
            )}
          </section>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Chunk card
// ---------------------------------------------------------------------------

function ChunkCard({ chunk, index }: { chunk: RagDebugChunk; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const preview = chunk.content.slice(0, 200)
  const hasMore = chunk.content.length > 200

  return (
    <div
      className="rounded-sm border"
      style={{ borderColor: 'var(--border-color)', background: 'var(--glass-bg)' }}
    >
      {/* Chunk header */}
      <div
        className="flex items-center justify-between px-3 py-2 border-b"
        style={{ borderColor: 'var(--border-color)' }}
      >
        <span className="font-bold" style={{ color: 'var(--accent-cyan)', fontSize: '10px' }}>
          CHUNK_{String(index + 1).padStart(2, '0')}
        </span>
        <span className="truncate max-w-[180px] ml-2" style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
          {chunk.source}
        </span>
      </div>

      {/* Score bars */}
      <div className="flex items-center gap-6 px-3 py-2 border-b" style={{ borderColor: 'var(--border-color)' }}>
        <div className="flex items-center gap-2">
          <span style={{ color: 'var(--text-muted)', fontSize: '10px', minWidth: '90px' }}>
            VEC_SCORE: <span style={{ color: 'var(--accent-primary)' }}>{chunk.vector_score.toFixed(3)}</span>
          </span>
          {scoreBar(chunk.vector_score, 'var(--accent-primary)')}
        </div>
        <div className="flex items-center gap-2">
          <span style={{ color: 'var(--text-muted)', fontSize: '10px', minWidth: '90px' }}>
            KW_SCORE: <span style={{ color: 'var(--accent-cyan)' }}>{chunk.keyword_score.toFixed(3)}</span>
          </span>
          {scoreBar(chunk.keyword_score, 'var(--accent-cyan)')}
        </div>
      </div>

      {/* Content preview */}
      <div className="px-3 py-2">
        <pre
          className="whitespace-pre-wrap break-words leading-relaxed"
          style={{ color: 'var(--text-secondary)', fontSize: '11px', fontFamily: 'monospace' }}
        >
          {expanded ? chunk.content : preview}
          {!expanded && hasMore && (
            <span style={{ color: 'var(--text-muted)' }}>…</span>
          )}
        </pre>
        {hasMore && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="mt-1 text-[10px] uppercase tracking-wide transition-all"
            style={{ color: 'var(--accent-cyan)' }}
          >
            {expanded ? '[COLLAPSE]' : '[EXPAND]'}
          </button>
        )}
      </div>
    </div>
  )
}
