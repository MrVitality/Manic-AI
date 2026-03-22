'use client'

import { useState, useEffect } from 'react'
import GeneralSettings from '@/components/settings/GeneralSettings'
import InferenceSettings from '@/components/settings/InferenceSettings'
import RagSettingsPanel from '@/components/settings/RagSettingsPanel'
import AppearanceSettings from '@/components/settings/AppearanceSettings'
import DataSettings from '@/components/settings/DataSettings'
import ConnectorSettings from '@/components/settings/ConnectorSettings'
import ErrorBoundary from '@/components/ErrorBoundary'
import { fetchRagStats } from '@/lib/api'
import type { SettingsSection, RagStatsData } from '@/types'

const SECTIONS: Array<{ id: SettingsSection; label: string; icon: JSX.Element }> = [
  { id: 'general', label: 'General', icon: <SettingsIcon /> },
  { id: 'inference', label: 'Inference', icon: <BrainIcon /> },
  { id: 'rag', label: 'RAG', icon: <DatabaseIcon /> },
  { id: 'appearance', label: 'Appearance', icon: <PaletteIcon /> },
  { id: 'data', label: 'Data', icon: <StorageIcon /> },
  { id: 'connectors', label: 'Connectors', icon: <ConnectorIcon /> },
  { id: 'shortcuts', label: 'Shortcuts', icon: <KeyboardIcon /> },
]

export default function AdvancedSettings() {
  const [activeSection, setActiveSection] = useState<SettingsSection>('general')
  const [ragStats, setRagStats] = useState<RagStatsData | null>(null)

  useEffect(() => {
    fetchRagStats().then(setRagStats).catch(() => {})
  }, [])

  return (
    <div className="flex-1 overflow-hidden flex flex-col md:flex-row">
      {/* Mobile section picker */}
      <div className="md:hidden p-3" style={{ borderBottom: '1px solid var(--border-color)', background: 'var(--bg-secondary)' }}>
        <h2 className="text-base font-bold gradient-text mb-2">Settings</h2>
        <select
          value={activeSection}
          onChange={(e) => setActiveSection(e.target.value as SettingsSection)}
          className="w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
          style={{ background: 'var(--glass-bg)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
        >
          {SECTIONS.map((section) => (
            <option key={section.id} value={section.id}>{section.label}</option>
          ))}
        </select>
      </div>

      {/* Desktop Settings Sidebar */}
      <nav
        className="hidden md:flex w-48 flex-shrink-0 flex-col overflow-y-auto p-3 space-y-1"
        style={{ borderRight: '1px solid var(--border-color)', background: 'var(--bg-secondary)' }}
      >
        <div className="px-3 py-2 mb-2">
          <h2 className="text-lg font-bold gradient-text">Settings</h2>
        </div>
        {SECTIONS.map((section) => (
          <button
            key={section.id}
            onClick={() => setActiveSection(section.id)}
            className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all text-left"
            style={{
              background: activeSection === section.id ? 'rgba(129,140,248,0.1)' : 'transparent',
              color: activeSection === section.id ? 'var(--accent-blue)' : 'var(--text-secondary)',
            }}
          >
            <span className="w-4 h-4 flex-shrink-0">{section.icon}</span>
            {section.label}
          </button>
        ))}
      </nav>

      {/* Settings Content */}
      <div className="flex-1 overflow-y-auto p-4 md:p-6">
        <ErrorBoundary sectionName="Settings">
          <div className="max-w-2xl mx-auto animate-tab-enter" key={activeSection}>
            {activeSection === 'general' && <GeneralSettings />}
            {activeSection === 'inference' && <InferenceSettings />}
            {activeSection === 'rag' && <RagSettingsPanel />}
            {activeSection === 'appearance' && <AppearanceSettings />}
            {activeSection === 'data' && <DataSettings ragStats={ragStats} />}
            {activeSection === 'connectors' && <ConnectorSettings />}
            {activeSection === 'shortcuts' && <ShortcutsReference />}
          </div>
        </ErrorBoundary>
      </div>
    </div>
  )
}

function ShortcutsReference() {
  const shortcuts = [
    { key: 'Ctrl+N', action: 'New chat' },
    { key: 'Ctrl+D', action: 'Documents' },
    { key: 'Ctrl+M', action: 'Models' },
    { key: 'Ctrl+H', action: 'Dashboard' },
    { key: 'Ctrl+R', action: 'RAG Center' },
    { key: 'Ctrl+,', action: 'Settings' },
    { key: 'Ctrl+K', action: 'Command Palette' },
    { key: 'Ctrl+.', action: 'Refresh view' },
    { key: 'Escape', action: 'Back to chat' },
  ]

  return (
    <div>
      <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>Keyboard Shortcuts</h3>
      <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>Quick navigation and actions</p>
      <div className="space-y-2">
        {shortcuts.map((s) => (
          <div
            key={s.key}
            className="flex items-center justify-between py-2 px-3 rounded-lg"
            style={{ background: 'var(--glass-bg)', border: '1px solid var(--glass-border)' }}
          >
            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{s.action}</span>
            <kbd className="px-2 py-0.5 rounded text-xs font-mono" style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)' }}>
              {s.key}
            </kbd>
          </div>
        ))}
      </div>
    </div>
  )
}

// Icons
function SettingsIcon() { return <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg> }
function BrainIcon() { return <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg> }
function DatabaseIcon() { return <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg> }
function PaletteIcon() { return <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 21a4 4 0 01-4-4V5a2 2 0 012-2h4a2 2 0 012 2v12a4 4 0 01-4 4zm0 0h12a2 2 0 002-2v-4a2 2 0 00-2-2h-2.343M11 7.343l1.657-1.657a2 2 0 012.828 0l2.829 2.829a2 2 0 010 2.828l-8.486 8.485M7 17h.01" /></svg> }
function StorageIcon() { return <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v4a2 2 0 01-2 2M5 12a2 2 0 00-2 2v4a2 2 0 002 2h14a2 2 0 002-2v-4a2 2 0 00-2-2m-2-4h.01M17 16h.01" /></svg> }
function ConnectorIcon() { return <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg> }
function KeyboardIcon() { return <svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" /></svg> }
