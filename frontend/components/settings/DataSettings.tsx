'use client'

import { useState } from 'react'
import { useChatStore } from '@/lib/store'
import { clearCache } from '@/lib/api'
import GlassPanel from '@/components/ui/GlassPanel'
import type { RagStatsData } from '@/types'

interface DataSettingsProps {
  ragStats: RagStatsData | null
}

export default function DataSettings({ ragStats }: DataSettingsProps) {
  const { conversations, documents } = useChatStore()
  const [isClearingCache, setIsClearingCache] = useState(false)
  const [cacheResult, setCacheResult] = useState<string | null>(null)

  const handleClearCache = async () => {
    setIsClearingCache(true)
    setCacheResult(null)
    try {
      const result = await clearCache()
      setCacheResult(result.cleared ? `Cleared ${result.keys_removed} keys` : 'Cache clear failed')
    } catch (e) {
      setCacheResult('Failed to clear cache')
    } finally {
      setIsClearingCache(false)
    }
  }

  const handleExportConversations = () => {
    const data = JSON.stringify(conversations, null, 2)
    const blob = new Blob([data], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `manic-ai-conversations-${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const formatBytes = (bytes: number) => {
    if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${bytes} B`
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Database Statistics</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Overview of stored data</p>
        <GlassPanel className="p-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Conversations</span>
              <p className="text-lg font-bold font-mono" style={{ color: 'var(--text-primary)' }}>{conversations.length}</p>
            </div>
            <div>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Documents</span>
              <p className="text-lg font-bold font-mono" style={{ color: 'var(--text-primary)' }}>{documents.length}</p>
            </div>
            <div>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Chunks</span>
              <p className="text-lg font-bold font-mono" style={{ color: 'var(--text-primary)' }}>{ragStats?.total_chunks ?? '--'}</p>
            </div>
            <div>
              <span className="text-xs" style={{ color: 'var(--text-muted)' }}>Storage</span>
              <p className="text-lg font-bold font-mono" style={{ color: 'var(--text-primary)' }}>
                {ragStats?.storage_bytes ? formatBytes(ragStats.storage_bytes) : '--'}
              </p>
            </div>
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Export</h3>
        <GlassPanel className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Export Conversations</span>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Download as JSON file</p>
            </div>
            <button
              onClick={handleExportConversations}
              disabled={conversations.length === 0}
              className="px-3 py-1.5 text-xs btn-secondary rounded-lg"
            >
              Export JSON
            </button>
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Cache</h3>
        <GlassPanel className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Clear Redis Cache</span>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
                {cacheResult || 'Remove cached embeddings and search results'}
              </p>
            </div>
            <button
              onClick={handleClearCache}
              disabled={isClearingCache}
              className="px-3 py-1.5 text-xs rounded-lg font-medium transition-colors"
              style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}
            >
              {isClearingCache ? 'Clearing...' : 'Clear Cache'}
            </button>
          </div>
        </GlassPanel>
      </div>
    </div>
  )
}
