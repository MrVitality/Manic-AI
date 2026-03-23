'use client'

import { useEffect, useRef, useMemo, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useCommandPaletteStore } from '@/lib/stores/commandPaletteStore'
import { useChatStore } from '@/lib/store'
import { useConversationStore } from '@/lib/stores/conversationStore'
import { useModelStore } from '@/lib/stores/modelStore'
import type { Command } from '@/types'
import { SearchIcon } from '@/components/ui/Icons'

export default function CommandPalette() {
  const { isOpen, query, selectedIndex, close, setQuery, setSelectedIndex } = useCommandPaletteStore()
  const {
    conversations, documents, models,
    createConversation, updateSettings, settings,
    useRag, setUseRag,
  } = useChatStore()
  const { clearConversations } = useConversationStore()
  const router = useRouter()

  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  const navigateTo = useCallback((path: string) => {
    router.push(path)
  }, [router])

  // Build command list
  const commands = useMemo((): Command[] => {
    const cmds: Command[] = [
      // Navigation
      { id: 'nav-chat', label: 'Go to Chat', description: 'Open the chat view', category: 'navigation', shortcut: 'Escape', action: () => navigateTo('/chat') },
      { id: 'nav-docs', label: 'Go to Documents', description: 'Browse uploaded documents', category: 'navigation', shortcut: 'Ctrl+D', action: () => navigateTo('/documents') },
      { id: 'nav-models', label: 'Go to Models', description: 'Manage AI models', category: 'navigation', shortcut: 'Ctrl+M', action: () => navigateTo('/models') },
      { id: 'nav-dashboard', label: 'Go to Dashboard', description: 'System command center', category: 'navigation', shortcut: 'Ctrl+H', action: () => navigateTo('/dashboard') },
      { id: 'nav-rag', label: 'Go to RAG Center', description: 'Knowledge base management', category: 'navigation', shortcut: 'Ctrl+R', action: () => navigateTo('/rag') },
      { id: 'nav-settings', label: 'Go to Settings', description: 'Advanced configuration', category: 'navigation', shortcut: 'Ctrl+,', action: () => navigateTo('/settings') },
      // Actions
      { id: 'action-new-chat', label: 'New Chat', description: 'Start a new conversation', category: 'action', shortcut: 'Ctrl+N', action: () => { createConversation(); navigateTo('/chat') } },
      { id: 'action-toggle-theme', label: 'Toggle Theme', description: `Switch to ${settings.theme === 'dark' ? 'light' : 'dark'} mode`, category: 'action', action: () => updateSettings({ theme: settings.theme === 'dark' ? 'light' : 'dark' }) },
      { id: 'action-toggle-rag', label: 'Toggle RAG', description: `${useRag ? 'Disable' : 'Enable'} RAG for chat`, category: 'action', action: () => setUseRag(!useRag) },
      { id: 'action-refresh', label: 'Refresh View', description: 'Reload current view data', category: 'action', shortcut: 'Ctrl+.', action: () => window.dispatchEvent(new CustomEvent('manic-refresh')) },
      { id: 'clear-conversations', label: 'Clear All Conversations', description: 'Permanently delete all chat history', category: 'action', action: () => { if (window.confirm('Delete all conversations? This cannot be undone.')) { clearConversations() } } },
    ]

    // Dynamic: conversations
    conversations.slice(0, 10).forEach((conv) => {
      cmds.push({
        id: `conv-${conv.id}`,
        label: conv.title,
        description: `${conv.messages.length} messages`,
        category: 'conversation',
        action: () => {
          useConversationStore.getState().selectConversation(conv.id)
          navigateTo('/chat')
        },
      })
    })

    // Dynamic: documents
    documents.slice(0, 10).forEach((doc) => {
      cmds.push({
        id: `doc-${doc.id}`,
        label: doc.filename,
        description: `${doc.content_type} · ${doc.chunk_count} chunks`,
        category: 'document',
        action: () => navigateTo('/documents'),
      })
    })

    // Dynamic: models
    models.slice(0, 10).forEach((model) => {
      cmds.push({
        id: `model-${model.name}`,
        label: model.name,
        description: model.details ? `${model.details.parameter_size} · ${model.details.quantization_level}` : 'AI Model',
        category: 'model',
        action: () => {
          useModelStore.getState().setSelectedModel(model.name)
          navigateTo('/chat')
        },
      })
    })

    return cmds
  }, [conversations, documents, models, settings.theme, useRag, createConversation, navigateTo, updateSettings, setUseRag, clearConversations])

  // Fuzzy filter
  const filtered = useMemo(() => {
    if (!query.trim()) return commands
    const lower = query.toLowerCase()
    const tokens = lower.split(/\s+/)
    return commands
      .map((cmd) => {
        const text = `${cmd.label} ${cmd.description || ''} ${cmd.category}`.toLowerCase()
        let score = 0
        for (const token of tokens) {
          if (text.includes(token)) score += 1
          if (cmd.label.toLowerCase().startsWith(token)) score += 2
          if (cmd.label.toLowerCase() === token) score += 3
        }
        return { cmd, score }
      })
      .filter(({ score }) => score > 0)
      .sort((a, b) => b.score - a.score)
      .map(({ cmd }) => cmd)
  }, [commands, query])

  // Focus input on open
  useEffect(() => {
    if (isOpen) {
      requestAnimationFrame(() => inputRef.current?.focus())
    }
  }, [isOpen])

  // Scroll selected item into view
  useEffect(() => {
    if (!listRef.current) return
    const items = listRef.current.querySelectorAll('[data-command-item]')
    items[selectedIndex]?.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  const executeCommand = useCallback((cmd: Command) => {
    close()
    requestAnimationFrame(() => cmd.action())
  }, [close])

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSelectedIndex(Math.min(selectedIndex + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSelectedIndex(Math.max(selectedIndex - 1, 0))
    } else if (e.key === 'Enter' && filtered[selectedIndex]) {
      e.preventDefault()
      executeCommand(filtered[selectedIndex])
    } else if (e.key === 'Escape') {
      e.preventDefault()
      close()
    }
  }, [selectedIndex, filtered, close, setSelectedIndex, executeCommand])

  // Focus trap: keep Tab navigation inside the palette
  const handleOverlayKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key !== 'Tab') return
    const palette = e.currentTarget.querySelector('[role="dialog"]') as HTMLElement | null
    if (!palette) return
    const focusable = palette.querySelectorAll<HTMLElement>(
      'input, button, [tabindex]:not([tabindex="-1"])'
    )
    if (focusable.length === 0) return
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (e.shiftKey) {
      if (document.activeElement === first) {
        e.preventDefault()
        last.focus()
      }
    } else {
      if (document.activeElement === last) {
        e.preventDefault()
        first.focus()
      }
    }
  }, [])

  if (!isOpen) return null

  const categoryLabels: Record<string, string> = {
    navigation: 'Navigation',
    action: 'Actions',
    conversation: 'Conversations',
    document: 'Documents',
    model: 'Models',
    search: 'Search',
  }

  // Group commands by category
  const grouped: Array<{ category: string; commands: Command[] }> = []
  let currentCategory = ''
  let globalIndex = 0
  const indexMap = new Map<string, number>()

  for (const cmd of filtered) {
    if (cmd.category !== currentCategory) {
      currentCategory = cmd.category
      grouped.push({ category: currentCategory, commands: [] })
    }
    grouped[grouped.length - 1].commands.push(cmd)
    indexMap.set(cmd.id, globalIndex)
    globalIndex++
  }

  return (
    <div
      className="fixed inset-0 z-[100] flex items-start justify-center pt-[15vh]"
      onClick={close}
      onKeyDown={handleOverlayKeyDown}
    >
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-palette-enter" />

      {/* Palette */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Command palette"
        className="relative w-full max-w-lg mx-4 rounded-xl overflow-hidden shadow-2xl animate-palette-enter"
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-color)',
          boxShadow: '0 25px 50px -12px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search Input */}
        <div className="flex items-center gap-3 px-4 py-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <SearchIcon className="w-4 h-4 flex-shrink-0" style={{ color: 'var(--text-muted)' }} aria-hidden="true" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command or search..."
            className="flex-1 bg-transparent text-sm outline-none"
            style={{ color: 'var(--text-primary)' }}
            autoComplete="off"
            spellCheck={false}
            role="combobox"
            aria-expanded={true}
            aria-controls="command-palette-listbox"
            aria-activedescendant={filtered[selectedIndex] ? `command-${filtered[selectedIndex].id}` : undefined}
            aria-autocomplete="list"
            aria-label="Search commands"
          />
          <kbd
            className="px-1.5 py-0.5 rounded text-[10px] font-mono"
            style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)', border: '1px solid var(--border-color)' }}
          >
            ESC
          </kbd>
        </div>

        {/* Results */}
        <div
          ref={listRef}
          id="command-palette-listbox"
          role="listbox"
          aria-label="Commands"
          className="max-h-80 overflow-y-auto scrollbar-hide py-2"
        >
          {filtered.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <p className="text-sm" style={{ color: 'var(--text-muted)' }}>No results found</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-muted)', opacity: 0.6 }}>
                Try a different search term
              </p>
            </div>
          ) : (
            grouped.map((group) => (
              <div key={group.category}>
                <div className="px-4 py-1.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
                    {categoryLabels[group.category] || group.category}
                  </span>
                </div>
                {group.commands.map((cmd) => {
                  const idx = indexMap.get(cmd.id) ?? 0
                  const isSelected = idx === selectedIndex
                  return (
                    <button
                      key={cmd.id}
                      id={`command-${cmd.id}`}
                      data-command-item
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => executeCommand(cmd)}
                      onMouseEnter={() => setSelectedIndex(idx)}
                      className="w-full flex items-center gap-3 px-4 py-2 text-left transition-colors"
                      style={{
                        background: isSelected ? 'rgba(129,140,248,0.1)' : 'transparent',
                      }}
                    >
                      <span className="w-5 h-5 flex-shrink-0 flex items-center justify-center">
                        <CategoryIcon category={cmd.category} />
                      </span>
                      <div className="flex-1 min-w-0">
                        <span className="text-sm block truncate" style={{ color: isSelected ? 'var(--accent-blue)' : 'var(--text-primary)' }}>
                          {cmd.label}
                        </span>
                        {cmd.description && (
                          <span className="text-xs block truncate" style={{ color: 'var(--text-muted)' }}>
                            {cmd.description}
                          </span>
                        )}
                      </div>
                      {cmd.shortcut && (
                        <kbd
                          className="px-1.5 py-0.5 rounded text-[10px] font-mono flex-shrink-0"
                          style={{ background: 'var(--bg-tertiary)', color: 'var(--text-muted)', border: '1px solid var(--border-color)' }}
                        >
                          {cmd.shortcut}
                        </kbd>
                      )}
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div
          className="flex items-center justify-between px-4 py-2 text-[10px]"
          style={{ borderTop: '1px solid var(--border-color)', color: 'var(--text-muted)' }}
        >
          <div className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <kbd className="px-1 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}>↑↓</kbd>
              navigate
            </span>
            <span className="flex items-center gap-1">
              <kbd className="px-1 py-0.5 rounded" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}>↵</kbd>
              select
            </span>
          </div>
          <span>{filtered.length} result{filtered.length !== 1 ? 's' : ''}</span>
        </div>
      </div>
    </div>
  )
}

// Icons
function CategoryIcon({ category }: { category: string }) {
  const style = { color: 'var(--text-muted)' }
  switch (category) {
    case 'navigation':
      return <svg style={style} className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
    case 'action':
      return <svg style={style} className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
    case 'conversation':
      return <svg style={style} className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>
    case 'document':
      return <svg style={style} className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
    case 'model':
      return <svg style={style} className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" /></svg>
    default:
      return <svg style={style} className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
  }
}
