'use client'

import { useState, useCallback } from 'react'
import { usePinnedStore } from '@/lib/stores/pinnedStore'

interface PinnedDrawerProps {
  /** Called with a message ID to scroll to that message in the list */
  onScrollToMessage: (id: string) => void
}

export default function PinnedDrawer({ onScrollToMessage }: PinnedDrawerProps) {
  const { pinnedMessages, unpinMessage } = usePinnedStore()
  const [collapsed, setCollapsed] = useState(false)

  if (pinnedMessages.length === 0) return null

  return (
    <div
      className="border-b font-mono"
      style={{
        background: 'color-mix(in srgb, var(--accent-cyan) 5%, var(--bg-secondary))',
        borderColor: 'color-mix(in srgb, var(--accent-cyan) 30%, var(--border-color))',
      }}
    >
      {/* Header row */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        className="w-full flex items-center gap-2 px-4 py-2 text-left transition-opacity hover:opacity-80"
        aria-expanded={!collapsed}
        aria-label="Toggle pinned messages"
      >
        <PinIcon className="w-3 h-3 flex-shrink-0" style={{ color: 'var(--accent-cyan)' }} />
        <span className="text-[10px] uppercase tracking-widest font-bold" style={{ color: 'var(--accent-cyan)' }}>
          Pinned
        </span>
        <span
          className="text-[10px] px-1.5 py-0.5 border ml-1"
          style={{
            borderColor: 'color-mix(in srgb, var(--accent-cyan) 30%, transparent)',
            background: 'color-mix(in srgb, var(--accent-cyan) 10%, transparent)',
            color: 'var(--accent-cyan)',
          }}
        >
          {pinnedMessages.length}
        </span>
        <span className="ml-auto text-[10px]" style={{ color: 'var(--text-muted)' }}>
          {collapsed ? '[+]' : '[-]'}
        </span>
      </button>

      {/* Pinned items */}
      {!collapsed && (
        <div className="flex flex-col gap-0.5 px-4 pb-2">
          {pinnedMessages.map((pinned) => (
            <PinnedItem
              key={pinned.id}
              id={pinned.id}
              role={pinned.role}
              content={pinned.content}
              model={pinned.model}
              onScrollTo={onScrollToMessage}
              onUnpin={unpinMessage}
            />
          ))}
        </div>
      )}
    </div>
  )
}

interface PinnedItemProps {
  id: string
  role: string
  content: string
  model?: string
  onScrollTo: (id: string) => void
  onUnpin: (id: string) => void
}

function PinnedItem({ id, role, content, model, onScrollTo, onUnpin }: PinnedItemProps) {
  const handleClick = useCallback(() => onScrollTo(id), [id, onScrollTo])
  const handleUnpin = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation()
      onUnpin(id)
    },
    [id, onUnpin]
  )

  const preview = content.length > 120 ? content.slice(0, 120).trimEnd() + '...' : content

  return (
    <div
      className="group flex items-start gap-2 px-3 py-2 rounded-sm cursor-pointer transition-colors"
      style={{
        background: 'color-mix(in srgb, var(--accent-cyan) 4%, transparent)',
        border: '1px solid color-mix(in srgb, var(--accent-cyan) 15%, transparent)',
      }}
      onClick={handleClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && handleClick()}
      aria-label={`Jump to pinned message: ${preview}`}
    >
      {/* Role badge */}
      <span
        className="text-[9px] px-1 py-0.5 border font-bold flex-shrink-0 mt-0.5"
        style={{
          color: role === 'user' ? 'var(--text-secondary)' : 'var(--accent-cyan)',
          borderColor: role === 'user' ? 'var(--border-color)' : 'var(--accent-cyan)',
          background: 'var(--bg-tertiary)',
        }}
      >
        {role === 'user' ? 'USR' : 'SYS'}
      </span>

      {/* Preview text */}
      <p className="flex-1 text-xs leading-relaxed truncate" style={{ color: 'var(--text-secondary)' }}>
        {preview}
      </p>

      {/* Model tag */}
      {model && (
        <span
          className="text-[9px] px-1 border flex-shrink-0 mt-0.5 hidden group-hover:inline"
          style={{ color: 'var(--text-muted)', borderColor: 'var(--border-color)', background: 'var(--bg-tertiary)' }}
        >
          {model}
        </span>
      )}

      {/* Unpin button */}
      <button
        onClick={handleUnpin}
        className="flex-shrink-0 p-0.5 rounded transition-opacity opacity-0 group-hover:opacity-100 hover:opacity-60"
        style={{ color: 'var(--text-muted)' }}
        title="Unpin message"
        aria-label="Unpin this message"
      >
        <XIcon className="w-3 h-3" />
      </button>
    </div>
  )
}

function PinIcon({ className, style }: { className?: string; style?: React.CSSProperties }) {
  return (
    <svg className={className} style={style} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"
      />
    </svg>
  )
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
    </svg>
  )
}
