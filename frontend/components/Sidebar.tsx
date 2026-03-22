'use client'

import { useState, useMemo, useRef } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useChatStore } from '@/lib/store'
import { useConversationStore } from '@/lib/stores/conversationStore'
import { useModels } from '@/hooks/useModels'
import { useTheme } from '@/hooks/useTheme'
import type { Conversation } from '@/types'
import {
  PlusIcon,
  CloseIcon,
  ChatBubbleIcon,
  DocumentIcon,
  CpuIcon,
  DashboardIcon,
  TrashIcon,
  SettingsIcon,
  SunIcon,
  MoonIcon,
  RagIcon,
  DownloadIcon,
  UploadIcon,
} from '@/components/ui/Icons'

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
  onOpenSettings: () => void
  onNavClick?: () => void
}

interface NavItem {
  path: string
  label: string
  icon: JSX.Element
  hint?: string
}

// Groups conversations into time-based buckets for display in the sidebar.
function groupConversationsByDate(convos: Conversation[]): Record<string, Conversation[]> {
  const now = new Date()
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const startOfYesterday = new Date(startOfToday.getTime() - 86_400_000)
  const startOfWeek = new Date(startOfToday.getTime() - 7 * 86_400_000)

  const groups: Record<string, Conversation[]> = {
    Today: [],
    Yesterday: [],
    'This Week': [],
    Older: [],
  }

  for (const c of convos) {
    const t = new Date(c.updatedAt).getTime()
    if (t >= startOfToday.getTime()) {
      groups['Today'].push(c)
    } else if (t >= startOfYesterday.getTime()) {
      groups['Yesterday'].push(c)
    } else if (t >= startOfWeek.getTime()) {
      groups['This Week'].push(c)
    } else {
      groups['Older'].push(c)
    }
  }

  return groups
}

export default function Sidebar({ isOpen, onToggle, onOpenSettings, onNavClick }: SidebarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const {
    conversations, currentConversationId,
    createConversation, selectConversation, deleteConversation,
    clearConversations,
  } = useChatStore()
  const { importConversation } = useConversationStore()
  const { models, selectedModel, setSelectedModel, isLoadingModels } = useModels()
  const { theme, toggleTheme } = useTheme()
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [importError, setImportError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const filteredConversations = useMemo(
    () =>
      conversations.filter(
        (c) => !searchQuery || c.title.toLowerCase().includes(searchQuery.toLowerCase()),
      ),
    [conversations, searchQuery],
  )

  const groupedConversations = useMemo(
    () => groupConversationsByDate(filteredConversations),
    [filteredConversations],
  )

  const GROUP_LABELS = ['Today', 'Yesterday', 'This Week', 'Older'] as const

  const handleNewChat = () => {
    createConversation()
    router.push('/chat')
  }

  const handleClearAll = () => {
    clearConversations()
    setShowClearConfirm(false)
  }

  const handleExport = (conversation: Conversation) => {
    const data = {
      id: conversation.id,
      title: conversation.title,
      messages: conversation.messages,
      model: conversation.model,
      createdAt: conversation.createdAt,
      exportedAt: new Date().toISOString(),
    }
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${conversation.title.replace(/[^a-z0-9]/gi, '-').toLowerCase()}-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleImportClick = () => {
    setImportError(null)
    fileInputRef.current?.click()
  }

  const handleImportFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    if (!file.name.endsWith('.json')) {
      setImportError('Only .json files are supported')
      e.target.value = ''
      return
    }

    const reader = new FileReader()
    reader.onload = (ev) => {
      try {
        const raw = ev.target?.result
        if (typeof raw !== 'string') throw new Error('Could not read file')
        const data = JSON.parse(raw) as Record<string, unknown>
        if (typeof data !== 'object' || data === null || Array.isArray(data)) {
          throw new Error('Invalid conversation format')
        }
        importConversation(data)
        router.push('/chat')
      } catch (err) {
        setImportError(err instanceof Error ? err.message : 'Failed to import conversation')
      }
    }
    reader.onerror = () => setImportError('Failed to read file')
    reader.readAsText(file)
    e.target.value = '' // reset so the same file can be re-imported
  }

  const navigateTo = (path: string) => {
    router.push(path)
    onNavClick?.()
  }

  const navItems: NavItem[] = [
    { path: '/chat', label: 'Chat', icon: <ChatBubbleIcon className="w-5 h-5" /> },
    { path: '/documents', label: 'Docs', icon: <DocumentIcon className="w-5 h-5" />, hint: 'Ctrl+D' },
    { path: '/models', label: 'Models', icon: <CpuIcon className="w-5 h-5" />, hint: 'Ctrl+M' },
    { path: '/dashboard', label: 'Health', icon: <DashboardIcon className="w-5 h-5" />, hint: 'Ctrl+H' },
    { path: '/rag', label: 'RAG', icon: <RagIcon className="w-5 h-5" />, hint: 'Ctrl+R' },
    { path: '/settings', label: 'Config', icon: <SettingsIcon className="w-5 h-5" />, hint: 'Ctrl+,' },
  ]

  const isActive = (path: string) => pathname === path || pathname.startsWith(path + '/')

  const isChatView = isActive('/chat')

  return (
    <>
      <aside
        role="navigation"
        aria-label="Main navigation"
        className={`fixed md:relative inset-y-0 left-0 z-30 w-72 flex flex-col transform transition-transform duration-200 ease-in-out ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0 md:w-0 md:border-0 md:overflow-hidden'}`}
        style={{ background: 'var(--bg-secondary)', borderRight: '1px solid var(--border-color)' }}
      >
        {/* Header */}
        <div className="p-4" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-base font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Manic AI
            </h1>
            <div className="flex items-center gap-1">
              <button onClick={toggleTheme} className="p-1.5 rounded-md transition-colors hover:bg-white/5 text-zinc-400 hover:text-zinc-200" title={`Switch mode`} aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
                {theme === 'dark' ? <SunIcon className="w-4 h-4" /> : <MoonIcon className="w-4 h-4" />}
              </button>
              <button onClick={onToggle} className="md:hidden p-1.5 rounded-md text-zinc-400 hover:bg-white/5 hover:text-zinc-200 min-w-[44px] min-h-[44px] flex items-center justify-center" aria-label="Close sidebar">
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
          <div className="flex gap-2">
            <button onClick={handleNewChat} className="flex-1 btn-primary flex items-center justify-center gap-2 py-2.5">
              <PlusIcon className="w-4 h-4" /> New Chat
            </button>
            <button
              onClick={handleImportClick}
              className="btn-secondary flex items-center justify-center px-3 py-2.5"
              title="Import conversation from JSON"
              aria-label="Import conversation"
            >
              <UploadIcon className="w-4 h-4" />
            </button>
          </div>
          {importError && (
            <p className="mt-2 text-xs text-red-400" role="alert">{importError}</p>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept=".json,application/json"
            className="hidden"
            aria-hidden="true"
            onChange={handleImportFile}
          />
        </div>

        {/* Navigation */}
        <nav aria-label="Page navigation" className="px-2 py-2 space-y-0.5" style={{ borderBottom: '1px solid var(--border-color)' }}>
          {navItems.map((item) => (
            <button key={item.path} onClick={() => navigateTo(item.path)}
              aria-current={isActive(item.path) ? 'page' : undefined}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors text-left"
              style={{
                background: isActive(item.path) ? 'rgba(129, 140, 248, 0.1)' : 'transparent',
                color: isActive(item.path) ? 'var(--accent-indigo)' : 'var(--text-secondary)',
              }}
            >
              {item.icon}
              <span>{item.label}</span>
              {item.hint && <span className="ml-auto text-xs" style={{ color: 'var(--text-muted)' }}>{item.hint}</span>}
            </button>
          ))}
        </nav>

        {/* Model Selector (chat view) */}
        {isChatView && (
          <div className="p-3" style={{ borderBottom: '1px solid var(--border-color)' }}>
            <label className="block text-xs font-medium mb-1.5" style={{ color: 'var(--text-muted)' }}>Model</label>
            <select value={selectedModel} onChange={(e) => setSelectedModel(e.target.value)} disabled={isLoadingModels}
              className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/50"
              style={{ background: 'var(--glass-bg)', border: '1px solid var(--border-color)', color: 'var(--text-primary)' }}
            >
              {isLoadingModels ? <option>Loading...</option>
                : models.length === 0 ? <option>No models</option>
                  : models.map((m) => <option key={m.name} value={m.name}>{m.name}</option>)}
            </select>
          </div>
        )}

        {/* Conversations List (chat view) */}
        {isChatView ? (
          <div className="flex flex-col flex-1 min-h-0">
            {/* Search input */}
            <div className="px-2 pt-2 pb-1">
              <div className="relative flex items-center">
                <svg
                  className="absolute left-2.5 w-3.5 h-3.5 pointer-events-none"
                  style={{ color: 'var(--text-muted)' }}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z" />
                </svg>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search conversations..."
                  className="w-full pl-8 pr-7 py-1.5 text-xs rounded-md focus:outline-none focus:ring-1 focus:ring-[var(--accent-indigo)]"
                  style={{
                    background: 'var(--bg-tertiary)',
                    border: '1px solid var(--border-color)',
                    color: 'var(--text-primary)',
                  }}
                />
                {searchQuery && (
                  <button
                    onClick={() => setSearchQuery('')}
                    className="absolute right-2 p-0.5 rounded hover:opacity-70"
                    aria-label="Clear search"
                    style={{ color: 'var(--text-muted)' }}
                  >
                    <CloseIcon className="w-3 h-3" />
                  </button>
                )}
              </div>
            </div>

            {/* Grouped conversation list */}
            <div className="flex-1 overflow-y-auto p-2">
              {conversations.length === 0 ? (
                <div className="text-center text-sm py-8" style={{ color: 'var(--text-muted)' }}>No conversations yet</div>
              ) : filteredConversations.length === 0 ? (
                <div className="text-center text-sm py-8" style={{ color: 'var(--text-muted)' }}>No results for "{searchQuery}"</div>
              ) : (
                <div className="space-y-3">
                  {GROUP_LABELS.map((label) => {
                    const group = groupedConversations[label]
                    if (!group || group.length === 0) return null
                    return (
                      <div key={label}>
                        <p
                          className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider"
                          style={{ color: 'var(--text-muted)' }}
                        >
                          {label}
                        </p>
                        <div className="space-y-0.5">
                          {group.map((conv) => (
                            <ConversationItem
                              key={conv.id}
                              conversation={conv}
                              isActive={conv.id === currentConversationId}
                              onSelect={() => selectConversation(conv.id)}
                              onDelete={() => deleteConversation(conv.id)}
                              onExport={() => handleExport(conv)}
                            />
                          ))}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        ) : <div className="flex-1" />}

        {/* Footer */}
        <div className="p-3 space-y-1.5" style={{ borderTop: '1px solid var(--border-color)' }}>
          {isChatView && conversations.length > 0 && (
            <button onClick={() => setShowClearConfirm(true)} className="w-full btn-ghost text-xs flex items-center justify-center gap-2" style={{ color: 'var(--text-muted)' }}>
              <TrashIcon className="w-4 h-4" /> Clear All
            </button>
          )}
          <button onClick={onOpenSettings} className="w-full btn-ghost text-xs flex items-center justify-center gap-2" style={{ color: 'var(--text-muted)' }}>
            <SettingsIcon className="w-4 h-4" /> Quick Settings
          </button>
        </div>
      </aside>

      {showClearConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="clear-confirm-title">
          <div className="rounded-xl p-6 max-w-sm mx-4" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-color)' }}>
            <h3 id="clear-confirm-title" className="text-lg font-semibold mb-2">Clear All Conversations?</h3>
            <p className="text-sm mb-4" style={{ color: 'var(--text-secondary)' }}>This will permanently delete all chat history.</p>
            <div className="flex gap-3">
              <button onClick={() => setShowClearConfirm(false)} className="flex-1 btn-secondary">Cancel</button>
              <button onClick={handleClearAll} className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-medium transition-colors">Delete All</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function ConversationItem({ conversation, isActive, onSelect, onDelete, onExport }: { conversation: { id: string; title: string; messages: Array<{ role: string }> }; isActive: boolean; onSelect: () => void; onDelete: () => void; onExport: () => void }) {
  return (
    <div className="group relative flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors focus-within:opacity-100"
      style={{
        background: isActive ? 'rgba(129, 140, 248, 0.08)' : 'transparent',
        borderLeft: isActive ? '2px solid var(--accent-indigo)' : '2px solid transparent',
        paddingLeft: isActive ? 10 : 12,
        color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
      }}
      onClick={onSelect}>
      <ChatBubbleIcon className="w-4 h-4 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm truncate">{conversation.title}</p>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{conversation.messages.length} messages</p>
      </div>
      <button
        tabIndex={0}
        onClick={(e) => { e.stopPropagation(); onExport() }}
        aria-label={`Export conversation: ${conversation.title}`}
        className="p-1 rounded-md opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all hover:bg-blue-500/20 focus:bg-blue-500/20 text-blue-400"
      >
        <DownloadIcon className="w-3.5 h-3.5" />
      </button>
      <button
        tabIndex={0}
        onClick={(e) => { e.stopPropagation(); onDelete() }}
        aria-label={`Delete conversation: ${conversation.title}`}
        className="p-1 rounded-md opacity-0 group-hover:opacity-100 focus:opacity-100 transition-all hover:bg-red-500/20 focus:bg-red-500/20 text-red-500"
      >
        <TrashIcon className="w-3.5 h-3.5" />
      </button>
    </div>
  )
}
