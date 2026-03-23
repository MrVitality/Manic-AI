'use client'

import { useRagStore } from '@/lib/stores/ragStore'
import { useRagCenter } from '@/hooks/useRagCenter'
import { useDashboardData } from '@/hooks/useDashboardData'
import TabGroup from '@/components/ui/TabGroup'
import RagPipeline from '@/components/rag/RagPipeline'
import RagCollections from '@/components/rag/RagCollections'
import RagSearchLab from '@/components/rag/RagSearchLab'
import RagAnalytics from '@/components/rag/RagAnalytics'
import RagEval from '@/components/rag/RagEval'
import ErrorBoundary from '@/components/ErrorBoundary'
import type { RagCenterTab } from '@/types'

const SKELETON_BAR_STYLE = {
  display: 'inline-block',
  height: '12px',
  borderRadius: '4px',
  background: 'var(--bg-elevated)',
  animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
} as const

const TABS: Array<{ key: string; label: string }> = [
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'collections', label: 'Collections' },
  { key: 'search-lab', label: 'Search Lab' },
  { key: 'analytics', label: 'Analytics' },
  { key: 'eval', label: 'Evaluation' },
]

export default function RagCenter() {
  const { ragTab, setRagTab, searchConfig, setSearchConfig, error, setError, isLoadingStats } = useRagStore()
  const {
    ragStats,
    collections,
    searchQuery,
    searchResults,
    searchLatency,
    isSearching,
    refreshCollections,
    performSearch,
  } = useRagCenter()
  const { ragAnalytics } = useDashboardData()

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

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-6">
          <div>
            <h2 className="text-xl md:text-2xl font-bold gradient-text">RAG Center</h2>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              Manage your knowledge base and search pipeline
            </p>
          </div>
          <div className="flex items-center gap-2 text-xs flex-wrap" style={{ color: 'var(--text-muted)' }}>
            {isLoadingStats && !ragStats ? (
              <>
                <span style={{ ...SKELETON_BAR_STYLE, width: '48px' }} />
                <span className="opacity-30">|</span>
                <span style={{ ...SKELETON_BAR_STYLE, width: '56px' }} />
                <span className="opacity-30">|</span>
                <span style={{ ...SKELETON_BAR_STYLE, width: '80px' }} />
              </>
            ) : ragStats ? (
              <>
                <span>{ragStats.total_documents} docs</span>
                <span className="opacity-30">|</span>
                <span>{ragStats.total_chunks} chunks</span>
                <span className="opacity-30 hidden sm:inline">|</span>
                <span className="hidden sm:inline">{ragStats.embedding_model}</span>
              </>
            ) : null}
          </div>
        </div>

        {/* Tab Navigation — horizontally scrollable on mobile */}
        <div className="mb-6 overflow-x-auto pb-1">
          <div className="min-w-max">
            <TabGroup
              tabs={TABS}
              activeTab={ragTab}
              onChange={(tab) => setRagTab(tab as RagCenterTab)}
            />
          </div>
        </div>

        {/* Tab Content */}
        <ErrorBoundary sectionName="RAG Center">
          {ragTab === 'pipeline' && (
            <RagPipeline ragStats={ragStats} />
          )}

          {ragTab === 'collections' && (
            <RagCollections collections={collections} onRefresh={refreshCollections} />
          )}

          {ragTab === 'search-lab' && (
            <RagSearchLab
              searchQuery={searchQuery}
              searchResults={searchResults}
              searchLatency={searchLatency}
              isSearching={isSearching}
              searchConfig={searchConfig}
              collections={collections}
              onSearch={performSearch}
              onConfigChange={(updates) => setSearchConfig({ ...searchConfig, ...updates })}
            />
          )}

          {ragTab === 'analytics' && (
            <RagAnalytics ragAnalytics={ragAnalytics} ragStats={ragStats} />
          )}

          {ragTab === 'eval' && (
            <RagEval />
          )}
        </ErrorBoundary>
      </div>
    </div>
  )
}
