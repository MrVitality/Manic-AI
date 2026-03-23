'use client'

import { useState, useEffect, useCallback } from 'react'
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
  const focusMode = useUiStore((s) => s.focusMode)
  const toggleFocusMode = useUiStore((s) => s.toggleFocusMode)
  const setFocusMode = useUiStore((s) => s.setFocusMode)

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

  // Alt+F toggles focus mode; Escape exits it
  const handleGlobalKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.altKey && e.key === 'f') {
        e.preventDefault()
        toggleFocusMode()
      } else if (e.key === 'Escape' && focusMode) {
        setFocusMode(false)
      }
    },
    [focusMode, toggleFocusMode, setFocusMode]
  )

  useEffect(() => {
    document.addEventListener('keydown', handleGlobalKeyDown)
    return () => document.removeEventListener('keydown', handleGlobalKeyDown)
  }, [handleGlobalKeyDown])

  const title = viewTitleMap[pathname] || 'Manic AI'
  const currentConversationId = useConversationStore((s) => s.currentConversationId)
  const isChatRoute = pathname === '/chat' || pathname.startsWith('/chat/')

  return (
    <div className="flex h-screen overflow-hidden relative">
      {/* Vignette overlay for focus mode */}
      {focusMode && (
        <div
          className="pointer-events-none fixed inset-0 z-[90]"
          style={{
            background:
              'radial-gradient(ellipse at center, transparent 55%, rgba(0,0,0,0.65) 100%)',
          }}
          aria-hidden="true"
        />
      )}

      {/* Exit Focus button */}
      {focusMode && (
        <button
          onClick={() => setFocusMode(false)}
          className="fixed bottom-6 right-6 z-[95] flex items-center gap-2 px-3 py-2 rounded-sm text-xs font-mono font-bold uppercase tracking-widest transition-all hover:opacity-80"
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-muted)',
            boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
          }}
          title="Exit focus mode (Escape)"
          aria-label="Exit focus mode"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V6a2 2 0 012-2h2M4 16v2a2 2 0 002 2h2m8-16h2a2 2 0 012 2v2m0 8v2a2 2 0 01-2 2h-2" />
          </svg>
          Exit Focus
        </button>
      )}

      {/* Sidebar — hidden in focus mode */}
      {!focusMode && (
        <Sidebar
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          onOpenSettings={() => setSettingsOpen(true)}
          onNavClick={() => setSidebarOpen(false)}
        />
      )}

      <main
        id="main-content"
        className="flex-1 flex flex-col min-w-0 transition-all duration-300"
        style={focusMode ? { maxWidth: '720px', margin: '0 auto', width: '100%' } : undefined}
      >
        {/* Mobile top bar — shown on all routes, hidden in focus mode */}
        {!focusMode && (
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
        )}

        {/* Desktop chat header strip — only on /chat with an active conversation, hidden in focus mode */}
        {!focusMode && isChatRoute && currentConversationId && (
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

      {!focusMode && sidebarOpen && (
        <div className="md:hidden fixed inset-0 bg-black/50 backdrop-blur-sm z-20" onClick={() => setSidebarOpen(false)} />
      )}
    </div>
  )
}
