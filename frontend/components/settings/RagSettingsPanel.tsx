'use client'

import { useChatStore } from '@/lib/store'
import GlassPanel from '@/components/ui/GlassPanel'

export default function RagSettingsPanel() {
  const { settings, updateSettings } = useChatStore()

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Search Configuration</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Default RAG search parameters</p>
        <GlassPanel className="p-4 space-y-4">
          <div>
            <label className="flex items-center justify-between text-xs mb-2">
              <span style={{ color: 'var(--text-secondary)' }}>Top K Results</span>
              <span className="font-mono font-bold" style={{ color: 'var(--accent-blue)' }}>{settings.ragTopK}</span>
            </label>
            <input
              type="range" min={1} max={20}
              value={settings.ragTopK}
              onChange={(e) => updateSettings({ ragTopK: parseInt(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </div>
          <div>
            <label className="flex items-center justify-between text-xs mb-2">
              <span style={{ color: 'var(--text-secondary)' }}>Similarity Threshold</span>
              <span className="font-mono font-bold" style={{ color: 'var(--accent-blue)' }}>{settings.ragThreshold.toFixed(2)}</span>
            </label>
            <input
              type="range" min={0} max={100}
              value={settings.ragThreshold * 100}
              onChange={(e) => updateSettings({ ragThreshold: parseInt(e.target.value) / 100 })}
              className="w-full accent-blue-500"
            />
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Backend</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Vector search backend configuration</p>
        <GlassPanel className="p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium mb-2" style={{ color: 'var(--text-secondary)' }}>Vector Backend</label>
            <div className="grid grid-cols-3 gap-2">
              {(['supabase', 'qdrant', 'both'] as const).map((backend) => (
                <button
                  key={backend}
                  onClick={() => updateSettings({ ragBackend: backend })}
                  className="py-2 rounded-lg text-xs font-medium transition-all text-center capitalize"
                  style={{
                    background: settings.ragBackend === backend ? 'rgba(129,140,248,0.1)' : 'var(--glass-bg)',
                    border: `1px solid ${settings.ragBackend === backend ? 'rgba(129,140,248,0.3)' : 'var(--glass-border)'}`,
                    color: settings.ragBackend === backend ? 'var(--accent-blue)' : 'var(--text-secondary)',
                  }}
                >
                  {backend === 'supabase' ? 'pgvector' : backend}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Hybrid Search</span>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Combine vector + keyword search</p>
            </div>
            <button
              onClick={() => updateSettings({ ragUseHybrid: !settings.ragUseHybrid })}
              className="w-10 h-5 rounded-full transition-colors relative"
              style={{ background: settings.ragUseHybrid ? 'var(--accent-blue)' : 'var(--bg-tertiary)' }}
            >
              <div className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all" style={{ left: settings.ragUseHybrid ? 20 : 2 }} />
            </button>
          </div>
        </GlassPanel>
      </div>
    </div>
  )
}
