'use client'

import { useMemo } from 'react'

interface EmbeddingPoint {
  x: number
  y: number
  collectionIndex: number
  size: number
}

// Deterministic seeded pseudo-random to avoid hydration mismatch
function seededRandom(seed: number): () => number {
  let s = seed
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff
    return (s >>> 0) / 0xffffffff
  }
}

// Generate cluster of points around a center
function makeCluster(
  cx: number,
  cy: number,
  count: number,
  spread: number,
  collectionIndex: number,
  rand: () => number,
): EmbeddingPoint[] {
  return Array.from({ length: count }, () => {
    const angle = rand() * 2 * Math.PI
    const dist = rand() * spread
    return {
      x: cx + Math.cos(angle) * dist,
      y: cy + Math.sin(angle) * dist,
      collectionIndex,
      size: 3 + rand() * 4,
    }
  })
}

const COLLECTION_COLORS = [
  { name: 'Research', color: 'var(--accent-blue)' },
  { name: 'Technical', color: 'var(--accent-cyan)' },
  { name: 'General', color: 'var(--accent-purple)' },
]

const CANVAS_W = 800
const CANVAS_H = 420
const DOT_GRID_ID = 'emb-dot-grid'

export default function RagEmbeddings() {
  const points = useMemo<EmbeddingPoint[]>(() => {
    const rand = seededRandom(42)
    return [
      ...makeCluster(200, 150, 22, 65, 0, rand),
      ...makeCluster(540, 130, 18, 55, 1, rand),
      ...makeCluster(370, 310, 25, 70, 2, rand),
    ]
  }, [])

  return (
    <div className="space-y-6">
      {/* Description card */}
      <div
        className="p-4 rounded-xl text-sm"
        style={{
          background: 'var(--glass-bg)',
          border: '1px solid var(--glass-border)',
          color: 'var(--text-secondary)',
        }}
      >
        <p className="mb-1 font-medium" style={{ color: 'var(--text-primary)' }}>
          Embedding Space Explorer
        </p>
        <p style={{ color: 'var(--text-muted)' }}>
          2D projection of your document embeddings. Coming soon: UMAP dimensionality reduction.
        </p>
      </div>

      {/* Controls placeholder */}
      <div
        className="flex flex-wrap items-center gap-4 p-3 rounded-xl"
        style={{
          background: 'var(--glass-bg)',
          border: '1px solid var(--glass-border)',
        }}
      >
        <span className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>
          Projection controls
        </span>

        <label className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Perplexity</span>
          <input
            type="range"
            min={5}
            max={50}
            defaultValue={30}
            disabled
            className="w-24 opacity-40 cursor-not-allowed"
            aria-label="Perplexity"
          />
          <span className="text-xs font-mono w-5" style={{ color: 'var(--text-muted)' }}>30</span>
        </label>

        <label className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Min Distance</span>
          <input
            type="range"
            min={0}
            max={100}
            defaultValue={10}
            disabled
            className="w-24 opacity-40 cursor-not-allowed"
            aria-label="Min Distance"
          />
          <span className="text-xs font-mono w-8" style={{ color: 'var(--text-muted)' }}>0.1</span>
        </label>

        <span
          className="ml-auto px-2 py-1 rounded text-[10px] uppercase tracking-wider font-medium"
          style={{
            background: 'rgba(234,179,8,0.08)',
            color: 'rgba(234,179,8,0.7)',
            border: '1px solid rgba(234,179,8,0.15)',
          }}
        >
          Coming Soon
        </span>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 flex-wrap">
        {COLLECTION_COLORS.map((col) => (
          <div key={col.name} className="flex items-center gap-1.5">
            <div
              className="w-2.5 h-2.5 rounded-full"
              style={{ background: col.color, opacity: 0.7 }}
            />
            <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {col.name}
            </span>
          </div>
        ))}
      </div>

      {/* SVG scatter plot */}
      <div
        className="rounded-xl overflow-hidden"
        style={{
          border: '1px solid var(--glass-border)',
          background: 'var(--bg-secondary)',
        }}
      >
        <svg
          width="100%"
          viewBox={`0 0 ${CANVAS_W} ${CANVAS_H}`}
          style={{ display: 'block', maxHeight: '420px' }}
          aria-label="Embedding space scatter plot placeholder"
          role="img"
        >
          <defs>
            <pattern
              id={DOT_GRID_ID}
              x="0"
              y="0"
              width="20"
              height="20"
              patternUnits="userSpaceOnUse"
            >
              <circle cx="1" cy="1" r="0.8" fill="rgba(255,255,255,0.04)" />
            </pattern>
          </defs>

          {/* Dot-grid background */}
          <rect width={CANVAS_W} height={CANVAS_H} fill={`url(#${DOT_GRID_ID})`} />

          {/* Axis labels */}
          <text x={CANVAS_W / 2} y={CANVAS_H - 8} textAnchor="middle" fontSize="10"
            fill="rgba(255,255,255,0.2)" fontFamily="ui-monospace, monospace" letterSpacing="0.08em">
            UMAP DIM 1
          </text>
          <text x={14} y={CANVAS_H / 2} textAnchor="middle" fontSize="10"
            fill="rgba(255,255,255,0.2)" fontFamily="ui-monospace, monospace" letterSpacing="0.08em"
            transform={`rotate(-90, 14, ${CANVAS_H / 2})`}>
            UMAP DIM 2
          </text>

          {/* Scatter points */}
          {points.map((pt, i) => {
            const col = COLLECTION_COLORS[pt.collectionIndex]
            return (
              <circle
                key={i}
                cx={pt.x}
                cy={pt.y}
                r={pt.size}
                fill={col.color}
                opacity="0.55"
                stroke={col.color}
                strokeWidth="0.5"
                strokeOpacity="0.3"
              />
            )
          })}

          {/* Cluster label overlays */}
          {[
            { label: 'Research', x: 200, y: 80 },
            { label: 'Technical', x: 540, y: 65 },
            { label: 'General', x: 370, y: 245 },
          ].map((lbl) => (
            <text
              key={lbl.label}
              x={lbl.x}
              y={lbl.y}
              textAnchor="middle"
              fontSize="10"
              fill="rgba(255,255,255,0.25)"
              fontFamily="ui-monospace, monospace"
              letterSpacing="0.06em"
            >
              {lbl.label.toUpperCase()}
            </text>
          ))}
        </svg>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'Total Embeddings', value: '--' },
          { label: 'Dimensions', value: '--' },
          { label: 'Collections', value: String(COLLECTION_COLORS.length) },
          { label: 'Projection', value: 'UMAP' },
        ].map((stat) => (
          <div
            key={stat.label}
            className="rounded-xl p-3 text-center"
            style={{
              background: 'var(--glass-bg)',
              border: '1px solid var(--glass-border)',
            }}
          >
            <div
              className="text-xl font-bold font-mono mb-0.5"
              style={{ color: 'var(--accent-cyan)' }}
            >
              {stat.value}
            </div>
            <div className="text-xs" style={{ color: 'var(--text-muted)' }}>
              {stat.label}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
