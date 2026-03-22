'use client'

import { useMemo } from 'react'
import DonutChart from '@/components/ui/DonutChart'
import Sparkline from '@/components/ui/Sparkline'
import AnimatedCounter from '@/components/ui/AnimatedCounter'
import PulseIndicator from '@/components/ui/PulseIndicator'
import GlassPanel from '@/components/ui/GlassPanel'
import type { ServiceStatus, UsageAnalyticsData, ServiceHealthSnapshot } from '@/types'

interface DashboardOverviewProps {
  serviceStatuses: Record<string, ServiceStatus>
  serviceHistory: ServiceHealthSnapshot[]
  usageAnalytics: UsageAnalyticsData | null
  systemUptime: number | null
}

export default function DashboardOverview({
  serviceStatuses,
  serviceHistory,
  usageAnalytics,
  systemUptime,
}: DashboardOverviewProps) {
  const services = Object.entries(serviceStatuses)
  const healthyCount = services.filter(([, s]) => s.status === 'healthy').length
  const totalCount = services.length || 1

  const donutSegments = useMemo(() => [
    { label: 'Healthy', value: healthyCount, color: '#10b981' },
    { label: 'Degraded', value: services.filter(([, s]) => s.status === 'degraded').length, color: '#f59e0b' },
    { label: 'Offline', value: services.filter(([, s]) => s.status === 'offline').length, color: '#ef4444' },
    { label: 'Unknown', value: services.filter(([, s]) => s.status === 'unknown').length, color: '#6b7280' },
  ].filter(s => s.value > 0), [serviceStatuses])

  // Build sparkline data per service from history
  const serviceSparklines = useMemo(() => {
    const map: Record<string, number[]> = {}
    const sorted = [...serviceHistory].sort((a, b) => a.timestamp.localeCompare(b.timestamp)).slice(-20)
    for (const snap of sorted) {
      for (const [name, data] of Object.entries(snap.services)) {
        if (!map[name]) map[name] = []
        map[name].push(data.latency_ms ?? 0)
      }
    }
    return map
  }, [serviceHistory])

  const totalTokens24h = usageAnalytics?.totals?.total_tokens ?? 0
  const totalRequests24h = usageAnalytics?.totals?.total_requests ?? 0

  return (
    <div className="animate-tab-enter space-y-6">
      {/* Top Row: Health Ring + Counters */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* System Health Ring */}
        <GlassPanel className="flex flex-col items-center justify-center py-6">
          <DonutChart
            segments={donutSegments}
            size={120}
            strokeWidth={12}
            centerValue={`${healthyCount}/${totalCount}`}
            centerLabel="Services"
          />
          <p className="mt-3 text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
            System Health
          </p>
        </GlassPanel>

        {/* Token Usage Counter */}
        <GlassPanel className="flex flex-col items-center justify-center py-6">
          <div className="text-3xl font-bold gradient-text">
            <AnimatedCounter value={totalTokens24h} duration={1200} />
          </div>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-muted)' }}>Tokens (24h)</p>
          <div className="mt-3 text-lg font-semibold" style={{ color: 'var(--text-secondary)' }}>
            <AnimatedCounter value={totalRequests24h} duration={800} /> requests
          </div>
        </GlassPanel>

        {/* Uptime Counter */}
        <GlassPanel className="flex flex-col items-center justify-center py-6">
          <div className="flex items-center gap-2 mb-2">
            <svg className="w-5 h-5 animate-heartbeat" viewBox="0 0 24 24" fill="none" stroke="var(--accent-cyan)" strokeWidth="2">
              <path d="M22 12h-4l-3 9L9 3l-3 9H2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="text-sm font-medium" style={{ color: 'var(--accent-cyan)' }}>Live</span>
          </div>
          <div className="text-2xl font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
            {systemUptime ? formatUptime(systemUptime) : '--:--:--'}
          </div>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-muted)' }}>Uptime</p>
        </GlassPanel>
      </div>

      {/* Service Grid */}
      <div>
        <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2" />
          </svg>
          Services
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 stagger-children">
          {services.map(([key, svc]) => (
            <GlassPanel key={key} hover className="p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <PulseIndicator status={svc.status} />
                  <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{svc.name}</span>
                </div>
                <span className="text-xs font-mono" style={{ color: svc.latency_ms && svc.latency_ms > 500 ? 'var(--status-warning)' : svc.latency_ms && svc.latency_ms > 1000 ? 'var(--status-error)' : 'var(--text-muted)' }}>
                  {svc.latency_ms ? `${svc.latency_ms.toFixed(0)}ms` : '--'}
                </span>
              </div>
              <div className="text-[10px] truncate mb-2" style={{ color: 'var(--text-muted)' }}>{svc.url}</div>
              <Sparkline
                values={serviceSparklines[key] || [0]}
                color={svc.status === 'healthy' ? '#10b981' : svc.status === 'degraded' ? '#f59e0b' : '#ef4444'}
                width={200}
                height={32}
              />
            </GlassPanel>
          ))}
        </div>
      </div>

      {/* Recent Activity Feed */}
      {usageAnalytics?.data && usageAnalytics.data.length > 0 && (
        <GlassPanel className="p-4">
          <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>Recent Activity</h3>
          <div className="space-y-2">
            {usageAnalytics.data.slice(-8).reverse().map((point, i) => (
              <div key={i} className="flex items-center justify-between py-1.5" style={{ borderBottom: i < 7 ? '1px solid var(--border-color)' : 'none' }}>
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                    {new Date(point.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                  <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                    {point.request_count} requests
                  </span>
                </div>
                <div className="flex items-center gap-4">
                  <span className="text-xs font-mono" style={{ color: 'var(--accent-cyan)' }}>
                    {point.total_tokens.toLocaleString()} tok
                  </span>
                  <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                    {point.avg_latency_ms}ms
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

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  return `${h.toString().padStart(2, '0')}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}
