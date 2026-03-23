'use client'

import { useState, useEffect } from 'react'
import { usePathname } from 'next/navigation'
import Sidebar from '@/components/Sidebar'
import CommandPalette from '@/components/CommandPalette'
import SettingsModal from '@/components/SettingsModal'
import SystemPromptEditor from '@/components/SystemPromptEditor'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { MenuIcon } from '@/components/ui/Icons'
import { useUiStore } from '@/lib/stores/uiStore'
import { useModelStore } from '@/lib/stores/modelStore'
import { useConversationStore } from '@/lib/stores/conversationStore'
import { useConnectorStore } from '@/lib/stores/connectorStore'

const ACCENT_COLORS: Record<string, string> = {
  blue: '#3b82f6',
  indigo: '#818cf8',
  violet: '#a78bfa',
  purple: '#8b5cf6',
  emerald: '#10b981',
}

const FONT_SIZES: Record<string, string> = {
  sm: '14px',
  base: '16px',
  lg: '18px',
}

const viewTitleMap: Record<string, string> = {
  '/chat': 'Chat',
  '/documents': 'Documents',
  '/models': 'Models',
  '/dashboard': 'Dashboard',
  '/rag': 'RAG Center',
  '/settings': 'Settings',
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  // Start open on desktop, closed on mobile. SSR defaults to true (desktop-first).
  // A useEffect immediately corrects to false on mobile before first paint is committed.
  const [sidebarOpen, setSidebarOpen] = useState(true)

  useEffect(() => {
    if (window.innerWidth < 768) {
      setSidebarOpen(false)
    }
  }, [])
  const [settingsOpen, setSettingsOpen] = useState(false)
  const pathname = usePathname()
  const settings = useUiStore((s) => s.settings)

  useKeyboardShortcuts()

  // Rehydrate persisted stores on client mount (skipHydration: true keeps SSR safe)
  useEffect(() => {
    useUiStore.persist.rehydrate()
    useModelStore.persist.rehydrate()
    useConversationStore.persist.rehydrate()
    useConnectorStore.persist.rehydrate()
  }, [])

  // Apply accent color at runtime when settings change
  useEffect(() => {
    const color = ACCENT_COLORS[settings.accentColor]
    if (color) {
      document.documentElement.style.setProperty('--accent-blue', color)
      document.documentElement.style.setProperty('--accent-cyan', color)
      document.documentElement.style.setProperty('--accent-primary', color)
    }
  }, [settings.accentColor])

  // Apply font size at runtime when settings change
  useEffect(() => {
    const size = FONT_SIZES[settings.fontSize]
    if (size) {
      document.documentElement.style.fontSize = size
    }
  }, [settings.fontSize])

  const title = viewTitleMap[pathname] || 'Manic AI'
  const currentConversationId = useConversationStore((s) => s.currentConversationId)
  const isChatRoute = pathname === '/chat' || pathname.startsWith('/chat/')

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onOpenSettings={() => setSettingsOpen(true)}
        onNavClick={() => setSidebarOpen(false)}
      />

      <main className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar — shown on all routes */}
        <div className="md:hidden flex items-center gap-3 p-4" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 rounded-lg min-w-[44px] min-h-[44px] flex items-center justify-center"
            style={{ background: 'var(--glass-bg)' }}
            aria-label="Open navigation menu"
          >
            <MenuIcon className="w-6 h-6" />
          </button>
          <h1 className="font-semibold truncate flex-1">{title}</h1>
          {isChatRoute && currentConversationId && (
            <SystemPromptEditor conversationId={currentConversationId} />
          )}
        </div>

        {/* Desktop chat header strip — only on /chat with an active conversation */}
        {isChatRoute && currentConversationId && (
          <div
            className="hidden md:flex items-center justify-end px-4 py-1.5"
            style={{ borderBottom: '1px solid var(--border-color)', background: 'var(--bg-secondary)' }}
          >
            <SystemPromptEditor conversationId={currentConversationId} />
          </div>
        )}

        {children}
      </main>

      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
      <CommandPalette />

      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-20" onClick={() => setSidebarOpen(false)} />
      )}
    </div>
  )
}
