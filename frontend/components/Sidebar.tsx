'use client'

import { useState } from 'react'
import { useChatStore } from '@/lib/store'
import { useModels } from '@/hooks/useModels'
import { useTheme } from '@/hooks/useTheme'
import type { ActiveView } from '@/types'

interface SidebarProps {
  isOpen: boolean
  onToggle: () => void
  onOpenSettings: () => void
}

export default function Sidebar({ isOpen, onToggle, onOpenSettings }: SidebarProps) {
  const {
    conversations, currentConversationId, activeView,
    createConversation, selectConversation, deleteConversation,
    clearConversations, setActiveView,
  } = useChatStore()
  const { models, selectedModel, setSelectedModel, isLoadingModels } = useModels()
  const { theme, toggleTheme } = useTheme()
  const [showClearConfirm, setShowClearConfirm] = useState(false)

  const handleNewChat = () => { createConversation(); setActiveView('chat') }
  const handleClearAll = () => { clearConversations(); setShowClearConfirm(false) }

  const navItems: Array<{ view: ActiveView; label: string; icon: JSX.Element; hint?: string }> = [
    { view: 'chat', label: 'Chat', icon: <ChatBubbleIcon className="w-5 h-5" /> },
    { view: 'documents', label: 'Docs', icon: <DocumentIcon className="w-5 h-5" />, hint: 'Ctrl+D' },
    { view: 'models', label: 'Models', icon: <CpuIcon className="w-5 h-5" />, hint: 'Ctrl+M' },
    { view: 'dashboard', label: 'Health', icon: <DashboardIcon className="w-5 h-5" />, hint: 'Ctrl+H' },
    { view: 'rag', label: 'RAG', icon: <RagIcon className="w-5 h-5" />, hint: 'Ctrl+R' },
    { view: 'settings', label: 'Config', icon: <SettingsIcon className="w-5 h-5" />, hint: 'Ctrl+,' },
  ]

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
            <button key={item.view} onClick={() => setActiveView(item.view)}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-md text-sm transition-colors text-left"
              style={{
                background: activeView === item.view ? 'rgba(129, 140, 248, 0.1)' : 'transparent',
                color: activeView === item.view ? 'var(--accent-indigo)' : 'var(--text-secondary)',
              }}
            >
              {item.icon}
              <span>{item.label}</span>
              {item.hint && <span className="ml-auto text-xs" style={{ color: 'var(--text-muted)' }}>{item.hint}</span>}
            </button>
          ))}
        </nav>

        {/* Model Selector (chat view) */}
        {activeView === 'chat' && (
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
        {activeView === 'chat' ? (
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
          {activeView === 'chat' && conversations.length > 0 && (
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

// Icons
function BoltIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>) }
function PlusIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>) }
function CloseIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>) }
function ChatBubbleIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" /></svg>) }
function DocumentIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>) }
function CpuIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>) }
function DashboardIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 5a1 1 0 011-1h4a1 1 0 011 1v5a1 1 0 01-1 1H5a1 1 0 01-1-1V5zm10 0a1 1 0 011-1h4a1 1 0 011 1v3a1 1 0 01-1 1h-4a1 1 0 01-1-1V5zm-10 9a1 1 0 011-1h4a1 1 0 011 1v3a1 1 0 01-1 1H5a1 1 0 01-1-1v-3zm10-2a1 1 0 011-1h4a1 1 0 011 1v5a1 1 0 01-1 1h-4a1 1 0 01-1-1v-5z" /></svg>) }
function TrashIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>) }
function SettingsIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></svg>) }
function SunIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" /></svg>) }
function MoonIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" /></svg>) }
function RagIcon({ className }: { className?: string }) { return (<svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4m0 5c0 2.21-3.582 4-8 4s-8-1.79-8-4" /></svg>) }
