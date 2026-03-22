'use client'

import { useState } from 'react'
import { useModels } from '@/hooks/useModels'
import { pullModel, deleteModel } from '@/lib/api'
import { formatModelSize } from '@/lib/api'
import type { PullProgress } from '@/types'

export default function ModelManager() {
  const { models, isLoadingModels, refreshModels } = useModels()
  const [pullName, setPullName] = useState('')
  const [isPulling, setIsPulling] = useState(false)
  const [pullProgress, setPullProgress] = useState<PullProgress | null>(null)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handlePull = async () => {
    if (!pullName.trim()) return
    setIsPulling(true)
    setError(null)
    setPullProgress({ status: 'Starting...' })
    try {
      await pullModel(pullName.trim(), (progress) => {
        setPullProgress(progress)
      })
      setPullName('')
      setPullProgress(null)
      refreshModels()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to pull model')
    } finally {
      setIsPulling(false)
    }
  }

  const handleDelete = async (name: string) => {
    try {
      await deleteModel(name)
      setDeleteConfirm(null)
      refreshModels()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete model')
    }
  }

  const pullPercent = pullProgress?.total && pullProgress?.completed
    ? Math.round((pullProgress.completed / pullProgress.total) * 100)
    : null

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
          <div>
            <h2 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">Models</h2>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Manage your Ollama models</p>
          </div>
          <button onClick={refreshModels} disabled={isLoadingModels} className="px-3 py-2 text-sm glass-card hover:bg-white/10 transition-colors rounded-lg flex items-center gap-2 self-start sm:self-auto min-h-[44px]">
            <svg className={`w-4 h-4 ${isLoadingModels ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            Refresh
          </button>
        </div>

        {/* Pull Model */}
        <div className="glass-card p-4 rounded-xl mb-6">
          <h3 className="text-sm font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>Pull a New Model</h3>
          <div className="flex flex-col sm:flex-row gap-3">
            <input
              type="text"
              value={pullName}
              onChange={(e) => setPullName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handlePull()}
              placeholder="e.g. llama3.2:3b, mistral, codellama"
              disabled={isPulling}
              className="flex-1 px-4 py-2.5 bg-white/5 border border-white/10 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/50 focus:border-transparent placeholder-gray-500 disabled:opacity-50"
            />
            <button onClick={handlePull} disabled={isPulling || !pullName.trim()} className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 rounded-lg font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed min-h-[44px]">
              {isPulling ? 'Pulling...' : 'Pull'}
            </button>
          </div>
          {pullProgress && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs mb-1" style={{ color: 'var(--text-muted)' }}>
                <span>{pullProgress.status}</span>
                {pullPercent !== null && <span>{pullPercent}%</span>}
              </div>
              {pullPercent !== null && (
                <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden">
                  <div className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-300" style={{ width: `${pullPercent}%` }} />
                </div>
              )}
            </div>
          )}
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="hover:text-white"><svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg></button>
          </div>
        )}

        {/* Model List */}
        {isLoadingModels ? (
          <div className="text-center py-12" style={{ color: 'var(--text-muted)' }}>Loading models...</div>
        ) : models.length === 0 ? (
          <div className="text-center py-12">
            <svg className="w-16 h-16 mx-auto mb-4" style={{ color: 'var(--text-muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
            <p className="font-medium" style={{ color: 'var(--text-muted)' }}>No models installed</p>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Pull a model above to get started</p>
          </div>
        ) : (
          <div className="space-y-3">
            {models.map((model) => (
              <div key={model.name} className="glass-card p-4 rounded-xl flex items-center gap-4 group">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-emerald-500/20 to-blue-500/20 flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium">{model.name}</p>
                  <div className="flex items-center gap-3 text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                    <span>{formatModelSize(model.size)}</span>
                    {model.details?.parameter_size && <span>{model.details.parameter_size} params</span>}
                    {model.details?.family && <span>{model.details.family}</span>}
                    {model.details?.quantization_level && <span>{model.details.quantization_level}</span>}
                  </div>
                </div>
                {deleteConfirm === model.name ? (
                  <div className="flex gap-1">
                    <button onClick={() => handleDelete(model.name)} className="px-2 py-1 text-xs bg-red-600 hover:bg-red-700 rounded transition-colors">Delete</button>
                    <button onClick={() => setDeleteConfirm(null)} className="px-2 py-1 text-xs rounded transition-colors" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>Cancel</button>
                  </div>
                ) : (
                  <button onClick={() => setDeleteConfirm(model.name)} className="p-2 opacity-0 group-hover:opacity-100 hover:bg-white/10 rounded-lg transition-all">
                    <svg className="w-4 h-4" style={{ color: 'var(--text-muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
