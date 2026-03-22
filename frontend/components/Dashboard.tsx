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
import ErrorBoundary from '@/components/ErrorBoundary'
import type { DashboardTab } from '@/types'

const TABS: Array<{ key: string; label: string }> = [
  { key: 'overview', label: 'Overview' },
  { key: 'services', label: 'Services' },
  { key: 'performance', label: 'Performance' },
]

export default function Dashboard() {
  const { dashboardTab, setDashboardTab, error, setError } = useDashboardStore()
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
    <div className="flex-1 overflow-y-auto p-4 md:p-6">
      <div className="max-w-6xl mx-auto">
        {/* Error Banner */}
        {error && (
          <div className="mb-3 px-3 py-2 rounded-lg text-sm flex items-center justify-between"
            style={{ background: 'rgba(239,68,68,0.1)', color: 'var(--status-error)', border: '1px solid rgba(239,68,68,0.2)' }}>
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-xs opacity-70 hover:opacity-100 min-w-[44px] min-h-[44px] flex items-center justify-end">Dismiss</button>
          </div>
        )}

        {/* Dashboard Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
          <div className="flex items-center gap-4">
            <div>
              <h2 className="text-xl md:text-2xl font-bold gradient-text">Command Center</h2>
              <div className="flex flex-wrap items-center gap-2 sm:gap-3 mt-1">
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
                    {lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 self-start sm:self-auto">
            {isLoadingAnalytics && (
              <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'var(--border-color)', borderTopColor: 'var(--accent-blue)' }} />
            )}
            <button
              onClick={refreshAll}
              className="px-3 py-2 text-xs glass-card hover:bg-white/[0.05] transition-all rounded-lg flex items-center gap-2 min-h-[44px]"
              style={{ color: 'var(--text-secondary)' }}
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Refresh
            </button>
          </div>
        </div>

        {/* Tab Navigation — horizontally scrollable on mobile */}
        <div className="mb-6 overflow-x-auto pb-1">
          <div className="min-w-max">
            <TabGroup
              tabs={TABS}
              activeTab={dashboardTab}
              onChange={(tab) => setDashboardTab(tab as DashboardTab)}
            />
          </div>
        </div>

        {/* Tab Content */}
        <ErrorBoundary sectionName="Dashboard">
          {dashboardTab === 'overview' && (
            <DashboardOverview
              serviceStatuses={serviceStatuses}
              serviceHistory={serviceHistory}
              usageAnalytics={usageAnalytics}
              systemUptime={uptimeSeconds}
              isLoading={isLoadingAnalytics}
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
              isLoading={isLoadingAnalytics}
            />
          )}
        </ErrorBoundary>
      </div>
    </div>
  )
}
