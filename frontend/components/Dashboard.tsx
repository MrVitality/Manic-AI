'use client'

import { useState, useEffect } from 'react'
import { useDashboardStore } from '@/lib/stores/dashboardStore'
import { useDashboardData } from '@/hooks/useDashboardData'
import { useUiStore } from '@/lib/stores/uiStore'
import TabGroup from '@/components/ui/TabGroup'
import DashboardOverview from '@/components/dashboard/DashboardOverview'
import DashboardServices from '@/components/dashboard/DashboardServices'
import DashboardPerformance from '@/components/dashboard/DashboardPerformance'
import PulseIndicator from '@/components/ui/PulseIndicator'
import type { DashboardTab } from '@/types'

const TABS: Array<{ key: string; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'services', label: 'Services' },
  { key: 'performance', label: 'Performance' },
]

export default function Dashboard() {
  const { dashboardTab, setDashboardTab } = useDashboardStore()
  const {
    serviceHistory,
    usageAnalytics,
    modelAnalytics,
    ragAnalytics,
    systemInfo,
    isStreaming,
    isLoadingAnalytics,
    lastRefresh,
    refreshAll,
  } = useDashboardData()
  const serviceStatuses = useUiStore((s) => s.serviceStatuses)

  const services = Object.entries(serviceStatuses)
  const healthyCount = services.filter(([, s]) => s.status === 'healthy').length
  const totalCount = services.length

  // Uptime counter
  const [uptimeSeconds, setUptimeSeconds] = useState<number | null>(null)
  useEffect(() => {
    if (!systemInfo?.uptime_seconds) return
    setUptimeSeconds(systemInfo.uptime_seconds)
    const interval = setInterval(() => {
      setUptimeSeconds((prev) => (prev !== null ? prev + 1 : null))
    }, 1000)
    return () => clearInterval(interval)
  }, [systemInfo?.uptime_seconds])

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto">
        {/* Dashboard Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-2xl font-bold gradient-text">Command Center</h2>
              <div className="flex items-center gap-3 mt-1">
                <div className="flex items-center gap-1.5">
                  <PulseIndicator
                    status={healthyCount === totalCount && totalCount > 0 ? 'healthy' : totalCount === 0 ? 'unknown' : 'degraded'}
                    size="sm"
                  />
                  <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    {totalCount === 0 ? 'Checking...' : `${healthyCount}/${totalCount} online`}
                  </span>
                </div>
                {isStreaming && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded" style={{ background: 'rgba(16,185,129,0.1)', color: '#10b981' }}>
                    LIVE
                  </span>
                )}
                {lastRefresh && (
                  <span className="text-[10px]" style={{ color: 'var(--text-muted)' }}>
                    Updated {lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {isLoadingAnalytics && (
              <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'var(--border-color)', borderTopColor: 'var(--accent-blue)' }} />
            )}
            <button
              onClick={refreshAll}
              className="px-3 py-1.5 text-xs glass-card hover:bg-white/[0.05] transition-all rounded-lg flex items-center gap-2"
              style={{ color: 'var(--text-secondary)' }}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="mb-6">
          <TabGroup
            tabs={TABS}
            activeTab={dashboardTab}
            onChange={(tab) => setDashboardTab(tab as DashboardTab)}
          />
        </div>

        {/* Tab Content */}
        {dashboardTab === 'overview' && (
          <DashboardOverview
            serviceStatuses={serviceStatuses}
            serviceHistory={serviceHistory}
            usageAnalytics={usageAnalytics}
            systemUptime={uptimeSeconds}
          />
        )}

        {dashboardTab === 'services' && (
          <DashboardServices
            serviceStatuses={serviceStatuses}
            serviceHistory={serviceHistory}
          />
        )}

        {dashboardTab === 'performance' && (
          <DashboardPerformance
            usageAnalytics={usageAnalytics}
            modelAnalytics={modelAnalytics}
            serviceHistory={serviceHistory}
          />
        )}
      </div>
    </div>
  )
}
