'use client'

import { useState, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import CommandPalette from '@/components/CommandPalette'
import SettingsModal from '@/components/SettingsModal'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { MenuIcon } from '@/components/ui/Icons'
import { useUiStore } from '@/lib/stores/uiStore'
import { useModelStore } from '@/lib/stores/modelStore'
import { useConversationStore } from '@/lib/stores/conversationStore'
import { useConnectorStore } from '@/lib/stores/connectorStore'

const viewTitleMap: Record<string, string> = {
  '/chat': 'Chat',
  '/documents': 'Documents',
  '/models': 'Models',
  '/dashboard': 'Dashboard',
  '/rag': 'RAG Center',
  '/settings': 'Settings',
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const pathname = usePathname()

  useKeyboardShortcuts()

  // Rehydrate persisted stores on client mount (skipHydration: true keeps SSR safe)
  useEffect(() => {
    useUiStore.persist.rehydrate()
    useModelStore.persist.rehydrate()
    useConversationStore.persist.rehydrate()
    useConnectorStore.persist.rehydrate()
  }, [])

  const title = viewTitleMap[pathname] || 'Manic AI'

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
            <MenuIcon className="w-6 h-6" />
          </button>
          <h1 className="font-semibold truncate">{title}</h1>
        </div>
        {children}
      </main>

      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <CommandPalette />

      {sidebarOpen && (
        <div className="lg:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-20" onClick={() => setSidebarOpen(false)} />
      )}
    </div>
  )
}
