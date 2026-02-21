'use client'

import { useRagStore } from '@/lib/stores/ragStore'
import { useRagCenter } from '@/hooks/useRagCenter'
import { useDashboardData } from '@/hooks/useDashboardData'
import TabGroup from '@/components/ui/TabGroup'
import RagPipeline from '@/components/rag/RagPipeline'
import RagCollections from '@/components/rag/RagCollections'
import RagSearchLab from '@/components/rag/RagSearchLab'
import RagAnalytics from '@/components/rag/RagAnalytics'
import type { RagCenterTab } from '@/types'

const TABS: Array<{ key: string; label: string }> = [
  { key: 'pipeline', label: 'Pipeline' },
  { key: 'collections', label: 'Collections' },
  { key: 'search-lab', label: 'Search Lab' },
  { key: 'analytics', label: 'Analytics' },
]

export default function RagCenter() {
  const { ragTab, setRagTab, searchConfig, setSearchConfig } = useRagStore()
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
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl font-bold gradient-text">RAG Center</h2>
            <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
              Manage your knowledge base and search pipeline
            </p>
          </div>
          <div className="flex items-center gap-3 text-xs" style={{ color: 'var(--text-muted)' }}>
            {ragStats && (
              <>
                <span>{ragStats.total_documents} docs</span>
                <span className="opacity-30">|</span>
                <span>{ragStats.total_chunks} chunks</span>
                <span className="opacity-30">|</span>
                <span>{ragStats.embedding_model}</span>
              </>
            )}
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="mb-6">
          <TabGroup
            tabs={TABS}
            activeTab={ragTab}
            onChange={(tab) => setRagTab(tab as RagCenterTab)}
          />
        </div>

        {/* Tab Content */}
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
            onSearch={performSearch}
            onConfigChange={(updates) => setSearchConfig({ ...searchConfig, ...updates })}
          />
        )}

        {ragTab === 'analytics' && (
          <RagAnalytics ragAnalytics={ragAnalytics} ragStats={ragStats} />
        )}
      </div>
    </div>
  )
}
