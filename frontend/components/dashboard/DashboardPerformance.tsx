'use client'

import { useMemo, useState } from 'react'
import GlassPanel from '@/components/ui/GlassPanel'
import AreaChart from '@/components/ui/AreaChart'
import BarChart from '@/components/ui/BarChart'
import Heatmap from '@/components/ui/Heatmap'
import LoadingSkeleton from '@/components/LoadingSkeleton'
import type { UsageAnalyticsData, ModelAnalyticsData, ServiceHealthSnapshot, HeatmapCell } from '@/types'

interface DashboardPerformanceProps {
  usageAnalytics: UsageAnalyticsData | null
  modelAnalytics: ModelAnalyticsData | null
  serviceHistory: ServiceHealthSnapshot[]
  isLoading?: boolean
}

export default function DashboardPerformance({
  usageAnalytics,
  modelAnalytics,
  serviceHistory,
  isLoading,
}: DashboardPerformanceProps) {
  if (isLoading && !usageAnalytics && !modelAnalytics) {
    return <LoadingSkeleton rows={5} title="Loading performance data..." />
  }
  const [sortKey, setSortKey] = useState<'requests' | 'latency' | 'tokens'>('requests')

  // Heatmap data: 24 columns (hours) x N rows (services)
  const heatmapData = useMemo(() => {
    const serviceNames = new Set<string>()
    for (const snap of serviceHistory) {
      for (const name of Object.keys(snap.services)) {
        serviceNames.add(name)
      }
    }
    const names = Array.from(serviceNames)
    const cells: HeatmapCell[] = []

    for (let row = 0; row < names.length; row++) {
      for (let col = 0; col < 24; col++) {
        // Find snapshots for this hour
        const hourSnaps = serviceHistory.filter((s) => {
          const h = new Date(s.timestamp).getHours()
          return h === col
        })
        const latencies = hourSnaps
          .map((s) => s.services[names[row]]?.latency_ms)
          .filter((l): l is number => l !== null && l !== undefined)
        const avgLatency = latencies.length > 0
          ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length)
          : 0

        cells.push({ x: col, y: row, value: avgLatency, label: `${names[row]} @${col}:00 — ${avgLatency}ms` })
      }
    }

    return { cells, names }
  }, [serviceHistory])

  // Requests per minute chart
  const rpmData = useMemo(() => {
    if (!usageAnalytics?.data) return []
    return usageAnalytics.data.map((d) => ({
      label: new Date(d.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      value: d.request_count,
    }))
  }, [usageAnalytics])

  // Model performance table
  const sortedModels = useMemo(() => {
    if (!modelAnalytics?.models) return []
    const models = [...modelAnalytics.models]
    switch (sortKey) {
      case 'requests': return models.sort((a, b) => b.request_count - a.request_count)
      case 'latency': return models.sort((a, b) => a.avg_latency_ms - b.avg_latency_ms)
      case 'tokens': return models.sort((a, b) => b.total_tokens - a.total_tokens)
      default: return models
    }
  }, [modelAnalytics, sortKey])

  const colLabels = Array.from({ length: 24 }, (_, i) => i.toString())

  return (
    <div className="animate-tab-enter space-y-6">
      {/* Latency Heatmap */}
      <GlassPanel className="p-4">
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
          Latency Heatmap (24h)
        </h3>
        {heatmapData.cells.length > 0 ? (
          <Heatmap
            cells={heatmapData.cells}
            columns={24}
            rows={heatmapData.names.length}
            rowLabels={heatmapData.names}
            colLabels={colLabels}
          />
        ) : (
          <div className="text-xs text-center py-8" style={{ color: 'var(--text-muted)' }}>
            Collecting service data...
          </div>
        )}
      </GlassPanel>

      {/* Requests Per Minute */}
      <GlassPanel className="p-4">
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
          Request Throughput
        </h3>
        {rpmData.length > 2 ? (
          <AreaChart
            data={rpmData}
            width={700}
            height={150}
            color="var(--accent-purple)"
            showGrid
          />
        ) : (
          <div className="text-xs text-center py-8" style={{ color: 'var(--text-muted)' }}>
            No throughput data yet
          </div>
        )}
      </GlassPanel>

      {/* Model Performance Table */}
      <GlassPanel className="p-4">
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
          Model Performance
        </h3>
        {sortedModels.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <th className="text-left py-2 pr-4 font-semibold" style={{ color: 'var(--text-muted)' }}>Model</th>
                  <th
                    className="text-right py-2 px-3 font-semibold cursor-pointer hover:opacity-80"
                    style={{ color: sortKey === 'requests' ? 'var(--accent-blue)' : 'var(--text-muted)' }}
                    onClick={() => setSortKey('requests')}
                    aria-sort={sortKey === 'requests' ? 'descending' : 'none'}
                  >
                    Requests {sortKey === 'requests' && '\u2193'}
                  </th>
                  <th
                    className="text-right py-2 px-3 font-semibold cursor-pointer hover:opacity-80"
                    style={{ color: sortKey === 'latency' ? 'var(--accent-blue)' : 'var(--text-muted)' }}
                    onClick={() => setSortKey('latency')}
                    aria-sort={sortKey === 'latency' ? 'ascending' : 'none'}
                  >
                    Avg Latency {sortKey === 'latency' && '\u2191'}
                  </th>
                  <th
                    className="text-right py-2 px-3 font-semibold cursor-pointer hover:opacity-80"
                    style={{ color: sortKey === 'tokens' ? 'var(--accent-blue)' : 'var(--text-muted)' }}
                    onClick={() => setSortKey('tokens')}
                    aria-sort={sortKey === 'tokens' ? 'descending' : 'none'}
                  >
                    Total Tokens {sortKey === 'tokens' && '\u2193'}
                  </th>
                  <th className="text-right py-2 pl-3 font-semibold" style={{ color: 'var(--text-muted)' }}>Last Used</th>
                </tr>
              </thead>
              <tbody>
                {sortedModels.map((model) => (
                  <tr key={model.name} className="hover:bg-white/[0.02] transition-colors" style={{ borderBottom: '1px solid var(--border-color)' }}>
                    <td className="py-2.5 pr-4 font-mono font-medium" style={{ color: 'var(--text-primary)' }}>
                      {model.name}
                    </td>
                    <td className="text-right py-2.5 px-3 font-mono" style={{ color: 'var(--text-secondary)' }}>
                      {model.request_count.toLocaleString()}
                    </td>
                    <td className="text-right py-2.5 px-3 font-mono" style={{ color: model.avg_latency_ms > 500 ? '#f59e0b' : 'var(--text-secondary)' }}>
                      {model.avg_latency_ms.toFixed(0)}ms
                    </td>
                    <td className="text-right py-2.5 px-3 font-mono" style={{ color: 'var(--text-secondary)' }}>
                      {model.total_tokens.toLocaleString()}
                    </td>
                    <td className="text-right py-2.5 pl-3" style={{ color: 'var(--text-muted)' }}>
                      {model.last_used
                        ? new Date(model.last_used).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                        : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-xs text-center py-8" style={{ color: 'var(--text-muted)' }}>
            No model data available
          </div>
        )}
      </GlassPanel>

      {/* Memory/Resource Bars */}
      {modelAnalytics?.models && modelAnalytics.models.length > 0 && (
        <GlassPanel className="p-4">
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
            Model Usage Distribution
          </h3>
          <BarChart
            data={modelAnalytics.models.slice(0, 8).map((m) => ({
              label: m.name.split(':')[0],
              value: m.total_tokens,
              color: `linear-gradient(90deg, var(--accent-blue), var(--accent-purple))`,
            }))}
            showValues
          />
        </GlassPanel>
      )}
    </div>
  )
}
