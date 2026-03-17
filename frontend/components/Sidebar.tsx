'use client'

import { useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import { useChatStore } from '@/lib/store'
import { useModels } from '@/hooks/useModels'
import { useTheme } from '@/hooks/useTheme'
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
} from '@/components/ui/Icons'

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
  onOpenSettings: () => void
}

interface NavItem {
  path: string
  label: string
  icon: JSX.Element
  hint?: string
}

export default function Sidebar({ isOpen, onToggle, onOpenSettings }: SidebarProps) {
  const router = useRouter()
  const pathname = usePathname()
  const {
    conversations, currentConversationId,
    createConversation, selectConversation, deleteConversation,
    clearConversations,
  } = useChatStore()
  const { models, selectedModel, setSelectedModel, isLoadingModels } = useModels()
  const { theme, toggleTheme } = useTheme()
  const [showClearConfirm, setShowClearConfirm] = useState(false)

  const handleNewChat = () => {
    createConversation()
    router.push('/chat')
  }

  const handleClearAll = () => {
    clearConversations()
    setShowClearConfirm(false)
  }

  const navigateTo = (path: string) => {
    router.push(path)
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
        className={`fixed lg:relative inset-y-0 left-0 z-30 w-72 flex flex-col transform transition-transform duration-200 ease-in-out ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0 lg:w-0 lg:border-0 lg:overflow-hidden'}`}
        style={{ background: 'var(--bg-secondary)', borderRight: '1px solid var(--border-color)' }}
      >
        {/* Header */}
        <div className="p-4" style={{ borderBottom: '1px solid var(--border-color)' }}>
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-base font-semibold tracking-tight" style={{ color: 'var(--text-primary)' }}>
              Manic AI
            </h1>
            <div className="flex items-center gap-1">
              <button onClick={toggleTheme} className="p-1.5 rounded-md transition-colors hover:bg-white/5 text-zinc-400 hover:text-zinc-200" title={`Switch mode`}>
                {theme === 'dark' ? <SunIcon className="w-4 h-4" /> : <MoonIcon className="w-4 h-4" />}
              </button>
              <button onClick={onToggle} className="lg:hidden p-1.5 rounded-md text-zinc-400 hover:bg-white/5 hover:text-zinc-200">
                <CloseIcon className="w-4 h-4" />
              </button>
            </div>
          </div>
          <button onClick={handleNewChat} className="w-full btn-primary flex items-center justify-center gap-2 py-2.5">
            <PlusIcon className="w-4 h-4" /> New Chat
          </button>
        </div>

        {/* Navigation */}
        <nav className="px-2 py-2 space-y-0.5" style={{ borderBottom: '1px solid var(--border-color)' }}>
          {navItems.map((item) => (
            <button key={item.path} onClick={() => navigateTo(item.path)}
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
          <div className="flex-1 overflow-y-auto p-2">
            {conversations.length === 0 ? (
              <div className="text-center text-sm py-8" style={{ color: 'var(--text-muted)' }}>No conversations yet</div>
            ) : (
              <div className="space-y-1">
                {conversations.map((conv) => (
                  <ConversationItem key={conv.id} conversation={conv} isActive={conv.id === currentConversationId} onSelect={() => selectConversation(conv.id)} onDelete={() => deleteConversation(conv.id)} />
                ))}
              </div>
            )}
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="rounded-xl p-6 max-w-sm mx-4" style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-color)' }}>
            <h3 className="text-lg font-semibold mb-2">Clear All Conversations?</h3>
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

function ConversationItem({ conversation, isActive, onSelect, onDelete }: { conversation: { id: string; title: string; messages: Array<{ role: string }> }; isActive: boolean; onSelect: () => void; onDelete: () => void }) {
  const [showDelete, setShowDelete] = useState(false)
  return (
    <div className="group relative flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer transition-colors"
      style={{
        background: isActive ? 'rgba(129, 140, 248, 0.08)' : 'transparent',
        borderLeft: isActive ? '2px solid var(--accent-indigo)' : '2px solid transparent',
        paddingLeft: isActive ? 10 : 12,
        color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
      }}
      onClick={onSelect} onMouseEnter={() => setShowDelete(true)} onMouseLeave={() => setShowDelete(false)}>
      <ChatBubbleIcon className="w-4 h-4 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm truncate">{conversation.title}</p>
        <p className="text-xs" style={{ color: 'var(--text-muted)' }}>{conversation.messages.length} messages</p>
      </div>
      {showDelete && (
        <button onClick={(e) => { e.stopPropagation(); onDelete() }} className="p-1 rounded-md opacity-0 group-hover:opacity-100 transition-all hover:bg-red-500/20 text-red-500">
          <TrashIcon className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  )
}
