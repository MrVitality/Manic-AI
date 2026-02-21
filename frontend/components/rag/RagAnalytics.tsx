'use client'

import GlassPanel from '@/components/ui/GlassPanel'
import DonutChart from '@/components/ui/DonutChart'
import BarChart from '@/components/ui/BarChart'
import AnimatedCounter from '@/components/ui/AnimatedCounter'
import type { RagAnalyticsData, RagStatsData } from '@/types'

interface RagAnalyticsProps {
  ragAnalytics: RagAnalyticsData | null
  ragStats: RagStatsData | null
}

export default function RagAnalytics({ ragAnalytics, ragStats }: RagAnalyticsProps) {
  const docByStatus = ragAnalytics?.documents.by_status || {}

  const statusSegments = [
    { label: 'Completed', value: docByStatus['completed'] || 0, color: '#10b981' },
    { label: 'Processing', value: docByStatus['processing'] || 0, color: '#f59e0b' },
    { label: 'Failed', value: docByStatus['failed'] || 0, color: '#ef4444' },
  ].filter(s => s.value > 0)

  const docsByType = ragStats?.documents_by_type || {}
  const typeBarData = Object.entries(docsByType).map(([type, count]) => ({
    label: type.replace('text/', '').replace('application/', ''),
    value: count,
    color: 'linear-gradient(90deg, var(--accent-blue), var(--accent-purple))',
  }))

  return (
    <div className="animate-tab-enter space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 stagger-children">
        <GlassPanel className="p-4 text-center">
          <div className="text-2xl font-bold gradient-text">
            <AnimatedCounter value={ragAnalytics?.documents.total ?? 0} />
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Documents</p>
        </GlassPanel>
        <GlassPanel className="p-4 text-center">
          <div className="text-2xl font-bold gradient-text">
            <AnimatedCounter value={ragAnalytics?.chunks.total ?? 0} />
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Chunks</p>
        </GlassPanel>
        <GlassPanel className="p-4 text-center">
          <div className="text-2xl font-bold gradient-text">
            <AnimatedCounter value={ragAnalytics?.collections.total ?? 0} />
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Collections</p>
        </GlassPanel>
        <GlassPanel className="p-4 text-center">
          <div className="text-2xl font-bold gradient-text">
            <AnimatedCounter value={ragAnalytics?.searches.total ?? 0} />
          </div>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Searches</p>
        </GlassPanel>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Document Status Pie */}
        <GlassPanel className="p-4">
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-secondary)' }}>
            Document Status
          </h3>
          {statusSegments.length > 0 ? (
            <div className="flex items-center justify-center">
              <DonutChart
                segments={statusSegments}
                size={160}
                strokeWidth={20}
                centerValue={`${ragAnalytics?.documents.total ?? 0}`}
                centerLabel="total"
              />
            </div>
          ) : (
            <div className="text-xs text-center py-8" style={{ color: 'var(--text-muted)' }}>
              No document data
            </div>
          )}
          <div className="flex justify-center gap-4 mt-4">
            {statusSegments.map((seg) => (
              <div key={seg.label} className="flex items-center gap-1.5">
                <div className="w-2 h-2 rounded-full" style={{ background: seg.color }} />
                <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>{seg.label} ({seg.value})</span>
              </div>
            ))}
          </div>
        </GlassPanel>

        {/* Documents by Content Type */}
        <GlassPanel className="p-4">
          <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-secondary)' }}>
            Content Types
          </h3>
          {typeBarData.length > 0 ? (
            <BarChart data={typeBarData} showValues />
          ) : (
            <div className="text-xs text-center py-8" style={{ color: 'var(--text-muted)' }}>
              No content type data
            </div>
          )}
        </GlassPanel>
      </div>

      {/* Search Quality Metrics */}
      <GlassPanel className="p-4">
        <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-secondary)' }}>
          Search Quality Metrics
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-xl font-bold font-mono" style={{ color: 'var(--accent-cyan)' }}>
              {ragAnalytics?.searches.avg_score?.toFixed(2) ?? '--'}
            </div>
            <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Avg Score</p>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold font-mono" style={{ color: 'var(--accent-purple)' }}>
              {ragAnalytics?.searches.avg_results?.toFixed(1) ?? '--'}
            </div>
            <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Avg Results</p>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold font-mono" style={{ color: 'var(--accent-blue)' }}>
              {ragAnalytics?.searches.avg_latency_ms?.toFixed(0) ?? '--'}ms
            </div>
            <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Avg Latency</p>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
              {ragStats?.avg_chunk_tokens?.toFixed(0) ?? '--'}
            </div>
            <p className="text-[10px] mt-1" style={{ color: 'var(--text-muted)' }}>Avg Chunk Tokens</p>
          </div>
        </div>
      </GlassPanel>

      {/* Recent Ingestions */}
      {ragStats?.recent_ingestions && ragStats.recent_ingestions.length > 0 && (
        <GlassPanel className="p-4">
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
            Recent Ingestions
          </h3>
          <div className="space-y-2">
            {ragStats.recent_ingestions.map((ing, i) => (
              <div key={i} className="flex items-center justify-between py-1.5 text-xs" style={{ borderBottom: i < ragStats.recent_ingestions.length - 1 ? '1px solid var(--border-color)' : 'none' }}>
                <div className="flex items-center gap-2 min-w-0">
                  <span className="truncate" style={{ color: 'var(--text-primary)' }}>{ing.filename}</span>
                </div>
                <div className="flex items-center gap-3 flex-shrink-0">
                  <span style={{ color: 'var(--text-muted)' }}>{ing.chunks_created} chunks</span>
                  <span className={`font-medium ${ing.status === 'completed' ? 'text-emerald-400' : ing.status === 'failed' ? 'text-red-400' : 'text-yellow-400'}`}>
                    {ing.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </GlassPanel>
      )}
    </div>
  )
}
