'use client'

import { useState, useEffect } from 'react'
import GlassPanel from '@/components/ui/GlassPanel'
import AnimatedCounter from '@/components/ui/AnimatedCounter'
import Badge from '@/components/ui/Badge'
import { fetchSearchHistory, runEval, type SearchLogEntry, type EvalMetrics } from '@/lib/api'

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

function metricVariant(score: number): 'healthy' | 'degraded' | 'offline' {
  if (score > 0.8) return 'healthy'
  if (score > 0.5) return 'degraded'
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

const TOP_K_OPTIONS = [1, 3, 5, 10, 20]

export default function RagEval() {
  const [history, setHistory] = useState<SearchLogEntry[]>([])
  const [isLoading, setIsLoading] = useState(true)

  // Run Eval state
  const [evalQuery, setEvalQuery] = useState('')
  const [expectedDocIds, setExpectedDocIds] = useState('')
  const [evalTopK, setEvalTopK] = useState(5)
  const [isRunningEval, setIsRunningEval] = useState(false)
  const [evalResult, setEvalResult] = useState<EvalMetrics | null>(null)
  const [evalError, setEvalError] = useState<string | null>(null)

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

  async function handleRunEval() {
    setEvalError(null)
    setEvalResult(null)

    const trimmedQuery = evalQuery.trim()
    if (!trimmedQuery) {
      setEvalError('Please enter a query.')
      return
    }

    const docIds = expectedDocIds
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)

    if (docIds.length === 0) {
      setEvalError('Please enter at least one expected document ID.')
      return
    }

    setIsRunningEval(true)
    try {
      const result = await runEval({
        query: trimmedQuery,
        expected_doc_ids: docIds,
        top_k: evalTopK,
      })
      setEvalResult(result)
    } catch (e) {
      setEvalError(e instanceof Error ? e.message : 'Eval request failed.')
    } finally {
      setIsRunningEval(false)
    }
  }

  const evalMetricRows: Array<{ label: string; key: keyof EvalMetrics }> = [
    { label: 'Precision', key: 'precision' },
    { label: 'Recall', key: 'recall' },
    { label: 'NDCG', key: 'ndcg' },
    { label: 'MRR', key: 'mrr' },
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

      {/* Run Eval Section */}
      <GlassPanel padding="none">
        <div className="px-4 py-3 border-b" style={{ borderColor: 'var(--glass-border)' }}>
          <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
            Run Eval
          </h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
            Evaluate retrieval quality against known relevant documents
          </p>
        </div>

        <div className="p-4 space-y-4">
          {/* Query input */}
          <div>
            <label className="block text-xs mb-1 font-medium" style={{ color: 'var(--text-secondary)' }}>
              Query
            </label>
            <input
              type="text"
              value={evalQuery}
              onChange={(e) => setEvalQuery(e.target.value)}
              placeholder="Enter the search query to evaluate..."
              className="input-base text-sm w-full"
            />
          </div>

          {/* Expected doc IDs */}
          <div>
            <label className="block text-xs mb-1 font-medium" style={{ color: 'var(--text-secondary)' }}>
              Expected Document IDs
              <span className="ml-1 font-normal" style={{ color: 'var(--text-muted)' }}>(comma-separated)</span>
            </label>
            <input
              type="text"
              value={expectedDocIds}
              onChange={(e) => setExpectedDocIds(e.target.value)}
              placeholder="doc-id-1, doc-id-2, ..."
              className="input-base text-sm w-full font-mono"
            />
          </div>

          {/* Top K + Run button row */}
          <div className="flex items-end gap-3">
            <div>
              <label className="block text-xs mb-1 font-medium" style={{ color: 'var(--text-secondary)' }}>
                Top K
              </label>
              <select
                value={evalTopK}
                onChange={(e) => setEvalTopK(parseInt(e.target.value))}
                className="px-2 py-1.5 rounded text-xs"
                style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
              >
                {TOP_K_OPTIONS.map((k) => (
                  <option key={k} value={k}>{k}</option>
                ))}
              </select>
            </div>

            <button
              onClick={handleRunEval}
              disabled={isRunningEval}
              className="px-4 py-1.5 rounded text-xs font-medium transition-opacity disabled:opacity-50 flex items-center gap-2"
              style={{ background: 'var(--accent-blue)', color: '#fff' }}
            >
              {isRunningEval && (
                <span className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin" />
              )}
              {isRunningEval ? 'Running…' : 'Run Eval'}
            </button>
          </div>

          {/* Error */}
          {evalError && (
            <p className="text-xs px-3 py-2 rounded" style={{ background: 'rgba(239,68,68,0.1)', color: 'var(--status-error)', border: '1px solid rgba(239,68,68,0.2)' }}>
              {evalError}
            </p>
          )}

          {/* Results */}
          {evalResult && (
            <div>
              <p className="text-xs font-semibold mb-2" style={{ color: 'var(--text-secondary)' }}>Results</p>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {evalMetricRows.map(({ label, key }) => {
                  const raw = evalResult[key]
                  const value = typeof raw === 'number' ? raw : 0
                  return (
                    <div
                      key={key}
                      className="rounded-lg p-3 text-center"
                      style={{ background: 'var(--bg-elevated)', border: '1px solid var(--glass-border)' }}
                    >
                      <p className="text-xs mb-1" style={{ color: 'var(--text-muted)' }}>{label}</p>
                      <Badge variant={metricVariant(value)} size="sm">
                        {value.toFixed(3)}
                      </Badge>
                    </div>
                  )
                })}
              </div>
              <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
                Green &gt; 0.8, yellow &gt; 0.5, red &le; 0.5
              </p>
            </div>
          )}
        </div>
      </GlassPanel>

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
            Loading search history...
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
