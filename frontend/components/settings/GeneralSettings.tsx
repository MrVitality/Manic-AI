'use client'

import { useRef, useState } from 'react'
import { useChatStore } from '@/lib/store'
import { useUiStore } from '@/lib/stores/uiStore'
import { checkHealth } from '@/lib/api'
import GlassPanel from '@/components/ui/GlassPanel'

export default function GeneralSettings() {
  const { settings, updateSettings } = useChatStore()
  const [showApiKey, setShowApiKey] = useState(false)
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'ok' | 'fail'>('idle')
  const [importError, setImportError] = useState<string | null>(null)
  const importInputRef = useRef<HTMLInputElement>(null)

  const handleExport = () => {
    const currentSettings = useUiStore.getState().settings
    const blob = new Blob([JSON.stringify(currentSettings, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'manic-ai-settings.json'
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setImportError(null)
    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const imported = JSON.parse(ev.target?.result as string)
        useUiStore.getState().updateSettings(imported)
      } catch {
        setImportError('Invalid settings file — could not parse JSON.')
      }
    }
    reader.readAsText(file)
    // Reset input so the same file can be re-imported if needed
    e.target.value = ''
  }

  const handleTestConnection = async () => {
    setTestStatus('testing')
    const ok = await checkHealth()
    setTestStatus(ok ? 'ok' : 'fail')
    // Reset status after 3 seconds
    setTimeout(() => setTestStatus('idle'), 3000)
  }

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
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-secondary)' }}>API Key</label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <input
                  type={showApiKey ? 'text' : 'password'}
                  value={settings.apiKey}
                  onChange={(e) => updateSettings({ apiKey: e.target.value })}
                  className="input-base text-sm w-full pr-9"
                  placeholder="Leave blank if not required"
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  aria-label={showApiKey ? 'Hide API key' : 'Show API key'}
                  onClick={() => setShowApiKey((v) => !v)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-xs transition-colors"
                  style={{ color: 'var(--text-muted)' }}
                >
                  {showApiKey ? (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
                      <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
                      <line x1="1" y1="1" x2="23" y2="23" />
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                      <circle cx="12" cy="12" r="3" />
                    </svg>
                  )}
                </button>
              </div>
              <button
                type="button"
                onClick={handleTestConnection}
                disabled={testStatus === 'testing'}
                className="px-3 py-1.5 text-xs rounded-lg font-medium transition-colors flex-shrink-0"
                style={{
                  background: testStatus === 'ok'
                    ? 'rgba(34,197,94,0.1)'
                    : testStatus === 'fail'
                      ? 'rgba(239,68,68,0.1)'
                      : 'rgba(129,140,248,0.1)',
                  color: testStatus === 'ok'
                    ? '#22c55e'
                    : testStatus === 'fail'
                      ? '#ef4444'
                      : 'var(--accent-blue)',
                  border: `1px solid ${testStatus === 'ok' ? 'rgba(34,197,94,0.2)' : testStatus === 'fail' ? 'rgba(239,68,68,0.2)' : 'rgba(129,140,248,0.2)'}`,
                  opacity: testStatus === 'testing' ? 0.6 : 1,
                }}
              >
                {testStatus === 'testing' ? 'Testing...' : testStatus === 'ok' ? 'Connected' : testStatus === 'fail' ? 'Failed' : 'Test'}
              </button>
            </div>
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
              role="switch"
              aria-checked={settings.streamResponses}
              aria-label="Stream Responses"
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

      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Settings Data</h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Export your settings as a JSON file or import a previously saved configuration</p>
        <GlassPanel className="p-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={handleExport}
              className="px-3 py-1.5 text-xs rounded-lg font-medium transition-colors flex-shrink-0"
              style={{
                background: 'rgba(129,140,248,0.1)',
                color: 'var(--accent-blue)',
                border: '1px solid rgba(129,140,248,0.2)',
              }}
            >
              Export Settings
            </button>
            <button
              type="button"
              onClick={() => importInputRef.current?.click()}
              className="px-3 py-1.5 text-xs rounded-lg font-medium transition-colors flex-shrink-0"
              style={{
                background: 'rgba(129,140,248,0.1)',
                color: 'var(--accent-blue)',
                border: '1px solid rgba(129,140,248,0.2)',
              }}
            >
              Import Settings
            </button>
            <input
              ref={importInputRef}
              type="file"
              accept="application/json,.json"
              onChange={handleImport}
              className="hidden"
              aria-label="Import settings JSON file"
            />
            {importError && (
              <span className="text-xs" style={{ color: '#ef4444' }}>{importError}</span>
            )}
          </div>
        </GlassPanel>
      </div>
    </div>
  )
}
