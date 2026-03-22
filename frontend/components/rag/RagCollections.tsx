'use client'

import { useState } from 'react'
import GlassPanel from '@/components/ui/GlassPanel'
import Badge from '@/components/ui/Badge'
import type { CollectionInfo } from '@/types'

interface RagCollectionsProps {
  collections: CollectionInfo[]
  onRefresh: () => void
}

export default function RagCollections({ collections, onRefresh }: RagCollectionsProps) {
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [isCreating, setIsCreating] = useState(false)

  const [createError, setCreateError] = useState<string | null>(null)

  const handleCreate = async () => {
    if (!newName.trim()) return
    setIsCreating(true)
    setCreateError(null)
    try {
      const { createCollection } = await import('@/lib/api')
      await createCollection(newName.trim(), newDesc.trim() || undefined)
      setNewName('')
      setNewDesc('')
      setShowCreateModal(false)
      onRefresh()
    } catch {
      setCreateError('Failed to create collection — check API connection')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <div className="animate-tab-enter space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-secondary)' }}>
          {collections.length} Collection{collections.length !== 1 ? 's' : ''}
        </h3>
        <button
          onClick={() => setShowCreateModal(true)}
          className="px-3 py-1.5 text-xs btn-primary rounded-lg flex items-center gap-1.5"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Collection
        </button>
      </div>

      {/* Collection Grid */}
      {collections.length === 0 ? (
        <GlassPanel className="p-8 text-center">
          <svg className="w-10 h-10 mx-auto mb-3" fill="none" stroke="var(--text-muted)" viewBox="0 0 24 24" strokeWidth="1.5">
            <path strokeLinecap="round" strokeLinejoin="round" d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
          </svg>
          <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No collections yet</p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>Create one to organize your documents</p>
        </GlassPanel>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 stagger-children">
          {collections.map((coll) => (
            <GlassPanel key={coll.id} hover className="p-4">
              <div className="flex items-start justify-between mb-2">
                <h4 className="text-sm font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                  {coll.name}
                </h4>
                <Badge variant={coll.is_public ? 'healthy' : 'unknown'} size="sm">
                  {coll.is_public ? 'public' : 'private'}
                </Badge>
              </div>
              {coll.description && (
                <p className="text-xs mb-3 line-clamp-2" style={{ color: 'var(--text-muted)' }}>
                  {coll.description}
                </p>
              )}
              <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
                <span className="flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  {coll.document_count} docs
                </span>
                <span>{coll.embedding_model}</span>
              </div>
              {coll.created_at && (
                <p className="text-[10px] mt-2" style={{ color: 'var(--text-muted)' }}>
                  Created {new Date(coll.created_at).toLocaleDateString()}
                </p>
              )}
            </GlassPanel>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div role="dialog" aria-modal="true" aria-labelledby="create-collection-title" className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="rounded-xl p-6 max-w-md w-full mx-4 animate-palette-enter" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-color)' }}>
            <h3 id="create-collection-title" className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>New Collection</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Name</label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  className="input-base text-sm"
                  placeholder="e.g., Research Papers"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>Description (optional)</label>
                <textarea
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="input-base text-sm"
                  rows={3}
                  placeholder="What this collection is about..."
                />
              </div>
            </div>
            {createError && (
              <p className="text-xs mt-2 px-2 py-1 rounded" style={{ color: 'var(--status-error)', background: 'rgba(239,68,68,0.1)' }}>
                {createError}
              </p>
            )}
            <div className="flex gap-3 mt-5">
              <button onClick={() => { setShowCreateModal(false); setCreateError(null) }} className="flex-1 btn-secondary">Cancel</button>
              <button onClick={handleCreate} disabled={!newName.trim() || isCreating} className="flex-1 btn-primary">
                {isCreating ? 'Creating...' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
