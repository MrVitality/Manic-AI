'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import GlassPanel from '@/components/ui/GlassPanel'
import ScoreBar from '@/components/ui/ScoreBar'
import Badge from '@/components/ui/Badge'
import EmptyState from '@/components/ui/EmptyState'
import type { SearchConfig, SearchExplainResult } from '@/types'

interface RagSearchLabProps {
  searchQuery: string
  searchResults: SearchExplainResult[]
  searchLatency: number | null
  isSearching: boolean
  searchConfig: SearchConfig
  onSearch: (query: string, config: SearchConfig) => void
  onConfigChange: (config: Partial<SearchConfig>) => void
}

export default function RagSearchLab({
  searchQuery,
  searchResults,
  searchLatency,
  isSearching,
  searchConfig,
  onSearch,
  onConfigChange,
}: RagSearchLabProps) {
  const [query, setQuery] = useState(searchQuery)
  const debounceRef = useRef<NodeJS.Timeout>()

  const handleQueryChange = useCallback((value: string) => {
    setQuery(value)
    clearTimeout(debounceRef.current)
    if (value.trim()) {
      debounceRef.current = setTimeout(() => {
        onSearch(value, searchConfig)
      }, 300)
    }
  }, [searchConfig, onSearch])

  // Clean up debounce timer on unmount
  useEffect(() => {
    return () => clearTimeout(debounceRef.current)
  }, [])

  const handleConfigChange = useCallback((updates: Partial<SearchConfig>) => {
    onConfigChange(updates)
    if (query.trim()) {
      clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        onSearch(query, { ...searchConfig, ...updates })
      }, 500)
    }
  }, [query, searchConfig, onSearch, onConfigChange])

  return (
    <div className="animate-tab-enter space-y-6">
      {/* Search Input */}
      <GlassPanel className="p-4">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" fill="none" stroke="var(--text-muted)" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={query}
              onChange={(e) => handleQueryChange(e.target.value)}
              className="input-base pl-10 text-sm"
              placeholder="Enter a search query to test RAG retrieval..."
              autoFocus
            />
          </div>
          {isSearching && (
            <div className="w-5 h-5 border-2 rounded-full animate-spin flex-shrink-0" style={{ borderColor: 'var(--border-color)', borderTopColor: 'var(--accent-blue)' }} />
          )}
          {searchLatency !== null && !isSearching && (
            <span className="text-xs font-mono flex-shrink-0 px-2 py-1 rounded" style={{ background: 'var(--glass-bg)', color: 'var(--accent-cyan)' }}>
              {searchLatency.toFixed(0)}ms
            </span>
          )}
        </div>
      </GlassPanel>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Config Panel */}
        <GlassPanel className="p-4 lg:col-span-1">
          <h4 className="text-xs font-semibold mb-3" style={{ color: 'var(--text-muted)' }}>Search Config</h4>
          <div className="space-y-4">
            <div>
              <label className="flex items-center justify-between text-xs mb-1">
                <span style={{ color: 'var(--text-secondary)' }}>Top K</span>
                <span className="font-mono" style={{ color: 'var(--text-muted)' }}>{searchConfig.topK}</span>
              </label>
              <input
                type="range" min={1} max={20} value={searchConfig.topK}
                onChange={(e) => handleConfigChange({ topK: parseInt(e.target.value) })}
                className="w-full accent-blue-500"
              />
            </div>
            <div>
              <label className="flex items-center justify-between text-xs mb-1">
                <span style={{ color: 'var(--text-secondary)' }}>Threshold</span>
                <span className="font-mono" style={{ color: 'var(--text-muted)' }}>{searchConfig.threshold.toFixed(2)}</span>
              </label>
              <input
                type="range" min={0} max={100} value={searchConfig.threshold * 100}
                onChange={(e) => handleConfigChange({ threshold: parseInt(e.target.value) / 100 })}
                className="w-full accent-blue-500"
              />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs" style={{ color: 'var(--text-secondary)' }}>Hybrid Search</span>
              <button
                onClick={() => handleConfigChange({ useHybrid: !searchConfig.useHybrid })}
                className="w-9 h-5 rounded-full transition-colors relative"
                style={{ background: searchConfig.useHybrid ? 'var(--accent-blue)' : 'var(--bg-tertiary)' }}
              >
                <div className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all" style={{ left: searchConfig.useHybrid ? 18 : 2 }} />
              </button>
            </div>
            <div>
              <label className="block text-xs mb-1" style={{ color: 'var(--text-secondary)' }}>Backend</label>
              <select
                value={searchConfig.backend}
                onChange={(e) => handleConfigChange({ backend: e.target.value as any })}
                className="w-full px-2 py-1.5 rounded text-xs"
                style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
              >
                <option value="supabase">Supabase (pgvector)</option>
                <option value="qdrant">Qdrant</option>
                <option value="both">Both</option>
              </select>
            </div>
          </div>
        </GlassPanel>

        {/* Results */}
        <div className="lg:col-span-3 space-y-3">
          {searchResults.length === 0 && !isSearching && query.trim() && (
            <GlassPanel className="p-2">
              <EmptyState
                title="No results found"
                description="Try adjusting your query or lowering the relevance threshold."
              />
            </GlassPanel>
          )}

          {searchResults.length === 0 && !query.trim() && (
            <GlassPanel className="p-8 text-center">
              <svg className="w-8 h-8 mx-auto mb-2" fill="none" stroke="var(--text-muted)" viewBox="0 0 24 24" strokeWidth="1.5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m5.231 13.481L15 17.25m-4.5-15H5.625c-.621 0-1.125.504-1.125 1.125v16.5c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9zm3.75 11.625a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" />
              </svg>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Type a query to search your document collection</p>
            </GlassPanel>
          )}

          {searchResults.map((result, i) => (
            <GlassPanel key={result.id} className="p-4">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold font-mono" style={{ color: 'var(--accent-blue)' }}>#{i + 1}</span>
                  <span className="text-xs truncate" style={{ color: 'var(--text-muted)' }}>
                    {result.document_filename}
                  </span>
                </div>
                <Badge variant="healthy" size="sm">
                  {result.combined_score.toFixed(3)}
                </Badge>
              </div>
              <p className="text-xs leading-relaxed mb-3 line-clamp-3" style={{ color: 'var(--text-secondary)' }}>
                {result.content}
              </p>
              <div className="space-y-1.5">
                <ScoreBar label="Vector" score={result.vector_score} color="#8b5cf6" />
                <ScoreBar label="Keyword" score={result.keyword_score} color="#3b82f6" />
                <ScoreBar label="Combined" score={result.combined_score} color="#10b981" />
              </div>
            </GlassPanel>
          ))}
        </div>
      </div>
    </div>
  )
}
