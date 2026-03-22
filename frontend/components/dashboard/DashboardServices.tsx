'use client'

import { useState, useMemo } from 'react'
import GlassPanel from '@/components/ui/GlassPanel'
import AreaChart from '@/components/ui/AreaChart'
import PulseIndicator from '@/components/ui/PulseIndicator'
import Badge from '@/components/ui/Badge'
import type { ServiceStatus, ServiceHealthSnapshot } from '@/types'

interface DashboardServicesProps {
  serviceStatuses: Record<string, ServiceStatus>
  serviceHistory: ServiceHealthSnapshot[]
}

const SERVICE_GROUPS: Record<string, string[]> = {
  'AI Core': ['ollama', 'langfuse'],
  'Data Layer': ['database', 'qdrant'],
  'Search & Web': ['searxng'],
}

export default function DashboardServices({ serviceStatuses, serviceHistory }: DashboardServicesProps) {
  const [expandedService, setExpandedService] = useState<string | null>(null)
  const services = Object.entries(serviceStatuses)

  // Build per-service latency chart data from history
  const serviceChartData = useMemo(() => {
    const map: Record<string, Array<{ label: string; value: number }>> = {}
    const sorted = [...serviceHistory].sort((a, b) => a.timestamp.localeCompare(b.timestamp)).slice(-50)
    for (const snap of sorted) {
      const label = new Date(snap.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      for (const [name, data] of Object.entries(snap.services)) {
        if (!map[name]) map[name] = []
        map[name].push({ label, value: data.latency_ms ?? 0 })
      }
    }
    return map
  }, [serviceHistory])

  return (
    <div className="animate-tab-enter space-y-6">
      {/* Service Accordion */}
      <div className="space-y-3">
        {services.map(([key, svc]) => {
          const isExpanded = expandedService === key
          const chartData = serviceChartData[key] || []

          return (
            <GlassPanel key={key} className="overflow-hidden">
              <button
                onClick={() => setExpandedService(isExpanded ? null : key)}
                aria-expanded={isExpanded}
                className="w-full flex items-center justify-between p-4 text-left transition-colors hover:bg-white/[0.02]"
              >
                <div className="flex items-center gap-3">
                  <PulseIndicator status={svc.status} size="md" />
                  <div>
                    <span className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{svc.name}</span>
                    <span className="text-xs ml-2" style={{ color: 'var(--text-muted)' }}>{svc.url}</span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Badge variant={svc.status === 'healthy' ? 'healthy' : svc.status === 'degraded' ? 'degraded' : 'offline'}>
                    {svc.status}
                  </Badge>
                  <span className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
                    {svc.latency_ms ? `${svc.latency_ms.toFixed(1)}ms` : '--'}
                  </span>
                  <svg
                    className={`w-4 h-4 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
                    fill="none" stroke="var(--text-muted)" viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </button>

              <div
                className={`overflow-hidden transition-all duration-200 ${isExpanded ? 'max-h-96' : 'max-h-0'}`}
                style={isExpanded ? { borderTop: '1px solid var(--border-color)' } : undefined}
              >
                <div className="px-4 pb-4">
                  <div className="pt-4">
                    <h4 className="text-xs font-semibold mb-3" style={{ color: 'var(--text-muted)' }}>
                      Latency History
                    </h4>
                    {chartData.length > 2 ? (
                      <AreaChart
                        data={chartData}
                        width={600}
                        height={120}
                        color="var(--accent-blue)"
                        showGrid
                      />
                    ) : (
                      <div className="text-xs text-center py-6" style={{ color: 'var(--text-muted)' }}>
                        Collecting latency data...
                      </div>
                    )}
                  </div>

                  {/* Uptime Bar */}
                  <div className="mt-4">
                    <h4 className="text-xs font-semibold mb-2" style={{ color: 'var(--text-muted)' }}>
                      Status Timeline (last {serviceHistory.length} checks)
                    </h4>
                    <div className="flex gap-[2px] h-3 rounded-full overflow-hidden">
                      {serviceHistory.slice(-60).map((snap, i) => {
                        const s = snap.services[key]
                        const color = !s ? '#374151' : s.status === 'healthy' ? '#10b981' : s.status === 'degraded' ? '#f59e0b' : '#ef4444'
                        return (
                          <div
                            key={snap.timestamp}
                            className="flex-1 transition-colors"
                            style={{ background: color, minWidth: 2 }}
                            title={`${new Date(snap.timestamp).toLocaleTimeString()} — ${s?.status || 'no data'}`}
                          />
                        )
                      })}
                    </div>
                  </div>
                </div>
              </div>
            </GlassPanel>
          )
        })}
      </div>

      {/* Docker Network Map */}
      <GlassPanel className="p-4">
        <h3 className="text-sm font-semibold mb-4" style={{ color: 'var(--text-secondary)' }}>
          Network Topology
        </h3>
        <svg viewBox="0 0 700 300" className="w-full" style={{ height: 300 }}>
          {/* Group boxes */}
          {Object.entries(SERVICE_GROUPS).map(([group, members], gi) => {
            const gx = 30 + gi * 230
            const gy = 20
            const gw = 200
            const gh = 260
            return (
              <g key={group}>
                <rect x={gx} y={gy} width={gw} height={gh} rx="12" fill="var(--glass-bg)" stroke="var(--glass-border)" strokeWidth="1" />
                <text x={gx + gw / 2} y={gy + 20} textAnchor="middle" fill="var(--text-muted)" fontSize="10" fontWeight="600">
                  {group}
                </text>
                {members.map((name, mi) => {
                  const svc = serviceStatuses[name]
                  if (!svc) return null
                  const nx = gx + 20
                  const ny = gy + 40 + mi * 55
                  const statusColor = svc.status === 'healthy' ? '#10b981' : svc.status === 'degraded' ? '#f59e0b' : '#ef4444'
                  return (
                    <g key={name}>
                      <rect x={nx} y={ny} width={160} height={44} rx="8" fill="var(--bg-elevated)" stroke={statusColor} strokeWidth="1.5" opacity="0.9" />
                      <circle cx={nx + 14} cy={ny + 22} r="5" fill={statusColor}>
                        {svc.status === 'healthy' && (
                          <animate attributeName="opacity" values="1;0.5;1" dur="2s" repeatCount="indefinite" />
                        )}
                      </circle>
                      <text x={nx + 28} y={ny + 18} fill="var(--text-primary)" fontSize="11" fontWeight="600">
                        {svc.name}
                      </text>
                      <text x={nx + 28} y={ny + 32} fill="var(--text-muted)" fontSize="9">
                        {svc.latency_ms ? `${svc.latency_ms.toFixed(0)}ms` : 'N/A'}
                      </text>
                    </g>
                  )
                })}
              </g>
            )
          })}

          {/* Connection lines between groups */}
          <line x1="230" y1="150" x2="260" y2="150" stroke="var(--accent-blue)" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.4" />
          <line x1="460" y1="150" x2="490" y2="150" stroke="var(--accent-blue)" strokeWidth="1.5" strokeDasharray="4 3" opacity="0.4" />
        </svg>
      </GlassPanel>
    </div>
  )
}
