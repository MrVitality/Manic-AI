'use client'

import { useState, useEffect } from 'react'
import { useChatStore } from '@/lib/store'
import { useModels } from '@/hooks/useModels'
import { formatModelSize, checkHealth } from '@/lib/api'
import type { Settings } from '@/types'

interface SettingsModalProps {
  isOpen: boolean
  onClose: () => void
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { settings, updateSettings } = useChatStore()
  const { models, refreshModels, isLoadingModels } = useModels()
  const [localSettings, setLocalSettings] = useState<Settings>(settings)
  const [activeTab, setActiveTab] = useState<'general' | 'rag' | 'models' | 'shortcuts'>('general')
  const [connectionStatus, setConnectionStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking')

  useEffect(() => {
    if (isOpen) {
      setLocalSettings(settings)
      checkConnection()
    }
  }, [isOpen, settings])

  const checkConnection = async () => {
    setConnectionStatus('checking')
    const isHealthy = await checkHealth()
    setConnectionStatus(isHealthy ? 'connected' : 'disconnected')
  }

  const handleSave = () => {
    updateSettings(localSettings)
    onClose()
  }

  const handleReset = () => {
    setLocalSettings(settings)
  }

  if (!isOpen) return null

  const tabs = [
    { key: 'general' as const, label: 'General' },
    { key: 'rag' as const, label: 'RAG' },
    { key: 'models' as const, label: 'Models' },
    { key: 'shortcuts' as const, label: 'Shortcuts' },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div
        className="rounded-xl w-full max-w-2xl max-h-[90vh] overflow-hidden mx-4 flex flex-col animate-fade-in"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-color)' }}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <h2 className="text-lg font-semibold gradient-text">Settings</h2>
          <button onClick={onClose} className="p-1 rounded hover:opacity-80" style={{ color: 'var(--text-muted)' }}>
            <CloseIcon className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex" style={{ borderBottom: '1px solid var(--border-color)' }}>
          {tabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className="px-4 py-3 text-sm font-medium transition-colors"
              style={{
                color: activeTab === tab.key ? 'var(--accent-blue)' : 'var(--text-muted)',
                borderBottom: activeTab === tab.key ? '2px solid var(--accent-blue)' : '2px solid transparent',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-4">
          {activeTab === 'general' && (
            <GeneralSettings
              settings={localSettings}
              onChange={setLocalSettings}
              connectionStatus={connectionStatus}
              onCheckConnection={checkConnection}
            />
          )}
          {activeTab === 'rag' && (
            <RagSettings settings={localSettings} onChange={setLocalSettings} />
          )}
          {activeTab === 'models' && (
            <ModelsSettings
              models={models}
              isLoading={isLoadingModels}
              onRefresh={refreshModels}
            />
          )}
          {activeTab === 'shortcuts' && (
            <ShortcutsReference />
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-4" style={{ borderTop: '1px solid var(--border-color)' }}>
          <button onClick={handleReset} className="btn-secondary text-sm">Reset</button>
          <button onClick={onClose} className="btn-secondary text-sm">Cancel</button>
          <button onClick={handleSave} className="btn-primary text-sm">Save Changes</button>
        </div>
      </div>
    </div>
  )
}

// General Settings Tab
interface GeneralSettingsProps {
  settings: Settings
  onChange: (settings: Settings) => void
  connectionStatus: 'checking' | 'connected' | 'disconnected'
  onCheckConnection: () => void
}

function GeneralSettings({ settings, onChange, connectionStatus, onCheckConnection }: GeneralSettingsProps) {
  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <div className="p-4 rounded-xl" style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)' }}>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>Connection Status</h3>
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Manic AI unified API</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium"
              style={{
                background: connectionStatus === 'connected' ? 'rgba(16,185,129,0.1)' : connectionStatus === 'disconnected' ? 'rgba(239,68,68,0.1)' : 'rgba(245,158,11,0.1)',
                color: connectionStatus === 'connected' ? '#10b981' : connectionStatus === 'disconnected' ? '#ef4444' : '#f59e0b',
              }}
            >
              <div className="w-2 h-2 rounded-full" style={{
                background: connectionStatus === 'connected' ? '#10b981' : connectionStatus === 'disconnected' ? '#ef4444' : '#f59e0b',
              }} />
              {connectionStatus === 'checking' ? 'Checking...' : connectionStatus === 'connected' ? 'Connected' : 'Disconnected'}
            </div>
            <button onClick={onCheckConnection} className="btn-ghost text-xs py-1 px-2">Refresh</button>
          </div>
        </div>
      </div>

      {/* API URL */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>API URL</label>
        <input
          type="text"
          value={settings.apiUrl}
          onChange={(e) => onChange({ ...settings, apiUrl: e.target.value })}
          className="input-base"
          placeholder="http://localhost:8081"
        />
        <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>The URL of your Manic AI API endpoint</p>
      </div>

      {/* Theme */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>Theme</h3>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Choose dark or light mode</p>
        </div>
        <div className="flex items-center gap-1 p-1 rounded-lg" style={{ background: 'var(--glass-bg)', border: '1px solid var(--border-color)' }}>
          <button
            onClick={() => onChange({ ...settings, theme: 'dark' })}
            className="px-3 py-1.5 rounded text-xs font-medium transition-all"
            style={{
              background: settings.theme === 'dark' ? 'var(--accent-blue)' : 'transparent',
              color: settings.theme === 'dark' ? 'white' : 'var(--text-muted)',
            }}
          >
            Dark
          </button>
          <button
            onClick={() => onChange({ ...settings, theme: 'light' })}
            className="px-3 py-1.5 rounded text-xs font-medium transition-all"
            style={{
              background: settings.theme === 'light' ? 'var(--accent-blue)' : 'transparent',
              color: settings.theme === 'light' ? 'white' : 'var(--text-muted)',
            }}
          >
            Light
          </button>
        </div>
      </div>

      {/* Temperature */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
          Temperature: {settings.temperature}
        </label>
        <input
          type="range" min="0" max="2" step="0.1"
          value={settings.temperature}
          onChange={(e) => onChange({ ...settings, temperature: parseFloat(e.target.value) })}
          className="w-full accent-blue-500"
        />
        <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
          <span>Precise (0)</span><span>Balanced (0.7)</span><span>Creative (2)</span>
        </div>
      </div>

      {/* Stream Responses */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>Stream Responses</h3>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Show responses as they generate</p>
        </div>
        <ToggleSwitch
          enabled={settings.streamResponses}
          onChange={(enabled) => onChange({ ...settings, streamResponses: enabled })}
        />
      </div>

      {/* System Prompt */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>System Prompt</label>
        <textarea
          value={settings.systemPrompt}
          onChange={(e) => onChange({ ...settings, systemPrompt: e.target.value })}
          className="input-base h-24 resize-none"
          placeholder="You are a helpful AI assistant..."
        />
      </div>

      {/* Max Tokens */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
          Max Response Length: {settings.maxTokens} tokens
        </label>
        <input
          type="range" min="256" max="4096" step="256"
          value={settings.maxTokens}
          onChange={(e) => onChange({ ...settings, maxTokens: parseInt(e.target.value) })}
          className="w-full accent-blue-500"
        />
        <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
          <span>Short (256)</span><span>Medium (2048)</span><span>Long (4096)</span>
        </div>
      </div>

      {/* Default Model */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>Default Model</label>
        <input
          type="text"
          value={settings.defaultModel}
          onChange={(e) => onChange({ ...settings, defaultModel: e.target.value })}
          className="input-base"
          placeholder="llama3.2:3b"
        />
        <p className="text-xs mt-1" style={{ color: 'var(--text-muted)' }}>The model to use for new conversations</p>
      </div>
    </div>
  )
}

// RAG Settings Tab
interface RagSettingsProps {
  settings: Settings
  onChange: (settings: Settings) => void
}

function RagSettings({ settings, onChange }: RagSettingsProps) {
  return (
    <div className="space-y-6">
      <div className="p-4 rounded-xl" style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)' }}>
        <h3 className="font-medium text-sm mb-1" style={{ color: 'var(--text-primary)' }}>Retrieval-Augmented Generation</h3>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          RAG enhances AI responses by searching your uploaded documents for relevant context. Toggle RAG on/off in the chat area.
        </p>
      </div>

      {/* Top K */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
          Top K Results: {settings.ragTopK}
        </label>
        <input
          type="range" min="1" max="20" step="1"
          value={settings.ragTopK}
          onChange={(e) => onChange({ ...settings, ragTopK: parseInt(e.target.value) })}
          className="w-full accent-purple-500"
        />
        <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
          <span>Focused (1)</span><span>Balanced (5)</span><span>Broad (20)</span>
        </div>
        <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
          Number of document chunks to retrieve per query. More results provide broader context but may dilute relevance.
        </p>
      </div>

      {/* Threshold */}
      <div>
        <label className="block text-sm font-medium mb-2" style={{ color: 'var(--text-primary)' }}>
          Similarity Threshold: {settings.ragThreshold}
        </label>
        <input
          type="range" min="0" max="1" step="0.05"
          value={settings.ragThreshold}
          onChange={(e) => onChange({ ...settings, ragThreshold: parseFloat(e.target.value) })}
          className="w-full accent-purple-500"
        />
        <div className="flex justify-between text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
          <span>Lenient (0)</span><span>Moderate (0.7)</span><span>Strict (1.0)</span>
        </div>
        <p className="text-xs mt-2" style={{ color: 'var(--text-muted)' }}>
          Minimum similarity score for document chunks. Higher values return only highly relevant results.
        </p>
      </div>
    </div>
  )
}

// Models Settings Tab
interface ModelsSettingsProps {
  models: Array<{ name: string; size: number; modified_at: string; details?: { parameter_size: string } }>
  isLoading: boolean
  onRefresh: () => void
}

function ModelsSettings({ models, isLoading, onRefresh }: ModelsSettingsProps) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>Installed Models</h3>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="btn-secondary text-xs flex items-center gap-2 py-1.5 px-3"
        >
          <RefreshIcon className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {isLoading ? (
        <div className="text-center py-8" style={{ color: 'var(--text-muted)' }}>Loading models...</div>
      ) : models.length === 0 ? (
        <div className="text-center py-8">
          <p style={{ color: 'var(--text-muted)' }} className="mb-2">No models installed</p>
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            Pull models using the Models tab or: <code className="px-2 py-1 rounded" style={{ background: 'var(--glass-bg)' }}>ollama pull llama3.2</code>
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {models.map((model) => (
            <div key={model.name} className="p-3 rounded-lg flex items-center justify-between" style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)' }}>
              <div>
                <h4 className="font-medium text-sm" style={{ color: 'var(--text-primary)' }}>{model.name}</h4>
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                  {formatModelSize(model.size)}
                  {model.details?.parameter_size && ` \u00b7 ${model.details.parameter_size}`}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// Keyboard Shortcuts Reference
function ShortcutsReference() {
  const shortcuts = [
    { keys: ['Ctrl', 'N'], action: 'New Chat' },
    { keys: ['Ctrl', 'D'], action: 'Open Documents' },
    { keys: ['Ctrl', 'M'], action: 'Open Models' },
    { keys: ['Ctrl', 'H'], action: 'Open Health Dashboard' },
    { keys: ['Escape'], action: 'Back to Chat' },
    { keys: ['Enter'], action: 'Send Message' },
    { keys: ['Shift', 'Enter'], action: 'New Line in Input' },
  ]

  return (
    <div className="space-y-4">
      <div className="p-4 rounded-xl" style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)' }}>
        <h3 className="font-medium text-sm mb-1" style={{ color: 'var(--text-primary)' }}>Keyboard Shortcuts</h3>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
          Use these shortcuts to navigate Manic AI quickly. On macOS, use Cmd instead of Ctrl.
        </p>
      </div>

      <div className="space-y-1">
        {shortcuts.map((shortcut) => (
          <div
            key={shortcut.action}
            className="flex items-center justify-between py-2.5 px-3 rounded-lg"
            style={{ background: 'var(--glass-bg)' }}
          >
            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{shortcut.action}</span>
            <div className="flex items-center gap-1">
              {shortcut.keys.map((key, i) => (
                <span key={i}>
                  <kbd
                    className="px-2 py-1 rounded text-xs font-mono"
                    style={{
                      background: 'var(--bg-tertiary)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-primary)',
                    }}
                  >
                    {key}
                  </kbd>
                  {i < shortcut.keys.length - 1 && (
                    <span className="mx-0.5 text-xs" style={{ color: 'var(--text-muted)' }}>+</span>
                  )}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// Toggle Switch Component
interface ToggleSwitchProps {
  enabled: boolean
  onChange: (enabled: boolean) => void
}

function ToggleSwitch({ enabled, onChange }: ToggleSwitchProps) {
  return (
    <button
      onClick={() => onChange(!enabled)}
      className="relative inline-flex h-6 w-11 items-center rounded-full transition-colors"
      style={{
        background: enabled
          ? 'linear-gradient(135deg, var(--accent-blue), var(--accent-purple))'
          : 'var(--bg-tertiary)',
      }}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
          enabled ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  )
}

// Icons
function CloseIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}

function RefreshIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
    </svg>
  )
}
