'use client'

import { useState } from 'react'
import Sidebar from '@/components/Sidebar'
import ChatArea from '@/components/ChatArea'
import DocumentManager from '@/components/DocumentManager'
import ModelManager from '@/components/ModelManager'
import Dashboard from '@/components/Dashboard'
import RagCenter from '@/components/RagCenter'
import AdvancedSettings from '@/components/AdvancedSettings'
import CommandPalette from '@/components/CommandPalette'
import SettingsModal from '@/components/SettingsModal'
import { useChatStore } from '@/lib/store'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

export default function Home() {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const { activeView, currentConversation } = useChatStore()

  useKeyboardShortcuts()

  const renderActiveView = () => {
    switch (activeView) {
      case 'documents': return <DocumentManager />
      case 'models': return <ModelManager />
      case 'dashboard': return <Dashboard />
      case 'rag': return <RagCenter />
      case 'settings': return <AdvancedSettings />
      default: return <ChatArea />
    }
  }

  const viewTitles: Record<string, string> = {
    chat: currentConversation?.title || 'New Chat',
    documents: 'Documents',
    models: 'Models',
    dashboard: 'Dashboard',
    rag: 'RAG Center',
    settings: 'Settings',
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onOpenSettings={() => setSettingsOpen(true)}
      />

      <main className="flex-1 flex flex-col min-w-0">
        <div className="lg:hidden flex items-center gap-3 p-4" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <button onClick={() => setSidebarOpen(!sidebarOpen)} className="p-2 rounded-lg" style={{ background: 'var(--glass-bg)' }}>
            <MenuIcon />
          </button>
          <h1 className="font-semibold truncate">{viewTitles[activeView]}</h1>
        </div>
        {renderActiveView()}
      </main>

      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <CommandPalette />

      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-20" onClick={() => setSidebarOpen(false)} />
      )}
    </div>
  )
}

function MenuIcon() {
  return (<svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" /></svg>)
}
