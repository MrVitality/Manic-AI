'use client'

import { useState, useEffect } from 'react'
import GlassPanel from '@/components/ui/GlassPanel'
import AnimatedCounter from '@/components/ui/AnimatedCounter'
import Badge from '@/components/ui/Badge'
import { fetchSearchHistory, type SearchLogEntry } from '@/lib/api'

function latencyVariant(ms: number): 'healthy' | 'degraded' | 'offline' {
  if (ms < 200) return 'healthy'
  if (ms < 500) return 'degraded'
  return 'offline'
}

function scoreVariant(score: number): 'healthy' | 'degraded' | 'offline' {
  if (score > 0.7) return 'healthy'
  if (score > 0.4) return 'degraded'
  return 'offline'
}

function avg(arr: number[]): number {
  if (arr.length === 0) return 0
  return arr.reduce((a, b) => a + b, 0) / arr.length
}

function formatTime(ts: string | null): string {
  if (!ts) return '—'
  const d = new Date(ts)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export default function RagEval() {
  const [history, setHistory] = useState<SearchLogEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    fetchSearchHistory(100)
      .then(setHistory)
      .catch(() => {})
      .finally(() => setIsLoading(false))
  }, [])

  const totalSearches = history.length
  const avgLatency = avg(history.map((e) => e.latency_ms))
  const avgResults = avg(history.map((e) => e.result_count))
  const avgScore = avg(history.map((e) => e.avg_score))

  const summaryCards = [
    { label: 'Total Searches', value: totalSearches, decimals: 0, suffix: '' },
    { label: 'Avg Latency', value: avgLatency, decimals: 0, suffix: ' ms' },
    { label: 'Avg Results', value: avgResults, decimals: 1, suffix: '' },
    { label: 'Avg Score', value: avgScore, decimals: 3, suffix: '' },
  ]

  return (
    <div className="space-y-6">
      {/* Summary Stats */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {summaryCards.map((card) => (
          <GlassPanel key={card.label} padding="md">
            <p className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>{card.label}</p>
            <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
              <AnimatedCounter
                value={card.value}
                decimals={card.decimals}
                suffix={card.suffix}
              />
            </p>
          </GlassPanel>
        ))}
      </div>

      {/* Search History Table */}
      <GlassPanel padding="none">
        <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--glass-border)' }}>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Search History
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            Last {totalSearches} searches logged by the evaluation API
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
            Loading search history…
          </div>
        ) : history.length === 0 ? (
          <div className="flex items-center justify-center py-16 text-sm" style={{ color: 'var(--text-muted)' }}>
            No search history found. Run some RAG searches first.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--glass-border)' }}>
                  {['Query', 'Backend', 'Hybrid', 'Reranked', 'Results', 'Avg Score', 'Latency', 'Time'].map((col) => (
                    <th
                      key={col}
                      className="px-4 py-2 text-left font-medium"
                      style={{ color: 'var(--text-muted)' }}
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {history.map((entry) => (
                  <tr
                    key={entry.id}
                    className="transition-colors"
                    style={{ borderBottom: '1px solid var(--glass-border)' }}
                    onMouseEnter={(e) => {
                      ;(e.currentTarget as HTMLTableRowElement).style.background = 'var(--bg-elevated)'
                    }}
                    onMouseLeave={(e) => {
                      ;(e.currentTarget as HTMLTableRowElement).style.background = ''
                    }}
                  >
                    <td className="px-4 py-2 max-w-[200px]" style={{ color: 'var(--text-primary)' }}>
                      <span
                        className="block truncate"
                        title={entry.query}
                      >
                        {entry.query}
                      </span>
                    </td>
                    <td className="px-4 py-2" style={{ color: 'var(--text-secondary)' }}>
                      {entry.backend}
                    </td>
                    <td className="px-4 py-2">
                      <Badge variant={entry.use_hybrid ? 'healthy' : 'unknown'}>
                        {entry.use_hybrid ? 'Yes' : 'No'}
                      </Badge>
                    </td>
                    <td className="px-4 py-2">
                      <Badge variant={entry.reranked ? 'healthy' : 'unknown'}>
                        {entry.reranked ? 'Yes' : 'No'}
                      </Badge>
                    </td>
                    <td className="px-4 py-2" style={{ color: 'var(--text-secondary)' }}>
                      {entry.result_count}
                    </td>
                    <td className="px-4 py-2">
                      <Badge variant={scoreVariant(entry.avg_score)}>
                        {entry.avg_score.toFixed(3)}
                      </Badge>
                    </td>
                    <td className="px-4 py-2">
                      <Badge variant={latencyVariant(entry.latency_ms)}>
                        {entry.latency_ms} ms
                      </Badge>
                    </td>
                    <td className="px-4 py-2" style={{ color: 'var(--text-muted)' }}>
                      {formatTime(entry.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </GlassPanel>
    </div>
  )
}
