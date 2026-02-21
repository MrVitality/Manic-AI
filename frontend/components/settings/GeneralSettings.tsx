'use client'

import { useChatStore } from '@/lib/store'
import GlassPanel from '@/components/ui/GlassPanel'

export default function GeneralSettings() {
  const { settings, updateSettings } = useChatStore()

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>API Configuration</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Configure your Manic AI backend connection</p>
        <GlassPanel className="p-4 space-y-4">
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>API URL</label>
            <input
              type="text"
              value={settings.apiUrl}
              onChange={(e) => updateSettings({ apiUrl: e.target.value })}
              className="input-base text-sm"
              placeholder="http://localhost:8081"
            />
          </div>
          <div>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>Default Model</label>
            <input
              type="text"
              value={settings.defaultModel}
              onChange={(e) => updateSettings({ defaultModel: e.target.value })}
              className="input-base text-sm"
              placeholder="llama3.2:3b"
            />
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>System Prompt</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Default system prompt for new conversations</p>
        <GlassPanel className="p-4">
          <textarea
            value={settings.systemPrompt}
            onChange={(e) => updateSettings({ systemPrompt: e.target.value })}
            className="input-base text-sm font-mono"
            rows={5}
            placeholder="You are a helpful AI assistant."
          />
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Streaming</h3>
        <GlassPanel className="p-4">
          <div className="flex items-center justify-between">
            <div>
              <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Stream Responses</span>
              <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>Show tokens as they arrive</p>
            </div>
            <button
              onClick={() => updateSettings({ streamResponses: !settings.streamResponses })}
              className="w-10 h-5 rounded-full transition-colors relative"
              style={{ background: settings.streamResponses ? 'var(--accent-blue)' : 'var(--bg-tertiary)' }}
            >
              <div className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all" style={{ left: settings.streamResponses ? 20 : 2 }} />
            </button>
          </div>
        </GlassPanel>
      </div>

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Dashboard</h3>
        <GlassPanel className="p-4 space-y-4">
          <div>
            <label className="flex items-center justify-between text-xs mb-1">
              <span style={{ color: 'var(--text-secondary)' }}>Health Check Interval</span>
              <span className="font-mono" style={{ color: 'var(--text-muted)' }}>{settings.healthCheckInterval / 1000}s</span>
            </label>
            <input
              type="range" min={5000} max={120000} step={5000}
              value={settings.healthCheckInterval}
              onChange={(e) => updateSettings({ healthCheckInterval: parseInt(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </div>
          <div>
            <label className="flex items-center justify-between text-xs mb-1">
              <span style={{ color: 'var(--text-secondary)' }}>Dashboard Refresh Rate</span>
              <span className="font-mono" style={{ color: 'var(--text-muted)' }}>{settings.dashboardRefreshRate / 1000}s</span>
            </label>
            <input
              type="range" min={5000} max={60000} step={5000}
              value={settings.dashboardRefreshRate}
              onChange={(e) => updateSettings({ dashboardRefreshRate: parseInt(e.target.value) })}
              className="w-full accent-blue-500"
            />
          </div>
        </GlassPanel>
      </div>
    </div>
  )
}
