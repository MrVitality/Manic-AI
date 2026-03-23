'use client'

import { useMemo, useRef, useState } from 'react'
import { useConversationStore } from '@/lib/stores/conversationStore'
import { useUiStore } from '@/lib/stores/uiStore'

// Rough token estimate: chars / 4 (standard approximation for English text)
function estimateTokens(text: string): number {
  return Math.ceil(text.length / 4)
}

// Typical context window ceiling for local models (conservative default)
const CONTEXT_WINDOW = 4096

interface Segment {
  label: string
  tokens: number
  color: string
  description: string
}

interface TooltipState {
  visible: boolean
  x: number
  segment: Segment | null
}

export default function ContextBudget() {
  const currentConversationId = useConversationStore((s) => s.currentConversationId)
  const conversation = useConversationStore((s) =>
    s.conversations.find((c) => c.id === currentConversationId) ?? null
  )
  const systemPromptSetting = useUiStore((s) => s.settings.systemPrompt)

  const [tooltip, setTooltip] = useState<TooltipState>({ visible: false, x: 0, segment: null })
  const barRef = useRef<HTMLDivElement>(null)

  const segments = useMemo<Segment[]>(() => {
    const effectiveSystemPrompt = conversation?.systemPrompt ?? systemPromptSetting ?? ''
    const systemTokens = estimateTokens(effectiveSystemPrompt)

    // Estimate RAG context: look for messages that appear to contain injected context
    // (messages with sources contribute extra context; approximate at 300 tokens per source set)
    const ragTokens = (conversation?.messages ?? []).reduce((acc, m) => {
      return acc + (m.sources && m.sources.length > 0 ? 300 + m.sources.length * 150 : 0)
    }, 0)

    // History: all non-system message content
    const historyTokens = (conversation?.messages ?? []).reduce((acc, m) => {
      return m.role !== 'system' ? acc + estimateTokens(m.content) : acc
    }, 0)

    const used = systemTokens + ragTokens + historyTokens
    const free = Math.max(0, CONTEXT_WINDOW - used)

    return [
      {
        label: 'System',
        tokens: systemTokens,
        color: 'var(--accent-purple)',
        description: `System prompt: ~${systemTokens.toLocaleString()} tokens`,
      },
      {
        label: 'RAG',
        tokens: ragTokens,
        color: 'var(--accent-cyan)',
        description: `RAG context: ~${ragTokens.toLocaleString()} tokens`,
      },
      {
        label: 'History',
        tokens: historyTokens,
        color: 'var(--accent-blue)',
        description: `Conversation history: ~${historyTokens.toLocaleString()} tokens`,
      },
      {
        label: 'Free',
        tokens: free,
        color: 'var(--border-color)',
        description: `Available: ~${free.toLocaleString()} tokens`,
      },
    ]
  }, [conversation, systemPromptSetting])

  const totalUsed = segments.slice(0, 3).reduce((a, s) => a + s.tokens, 0)
  const usagePct = Math.min(1, totalUsed / CONTEXT_WINDOW)
  const isWarning = usagePct >= 0.8

  const handleSegmentMouseEnter = (e: React.MouseEvent, segment: Segment) => {
    const rect = barRef.current?.getBoundingClientRect()
    if (!rect) return
    const relX = e.clientX - rect.left
    setTooltip({ visible: true, x: relX, segment })
  }

  const handleMouseLeave = () => {
    setTooltip((prev) => ({ ...prev, visible: false, segment: null }))
  }

  return (
    <div
      className="max-w-3xl mx-auto px-0 pb-1 pt-0"
      role="region"
      aria-label="Context window usage"
    >
      {/* Warning label when near capacity */}
      {isWarning && (
        <div
          className="flex items-center gap-1.5 mb-1 font-mono text-[10px] uppercase tracking-widest"
          style={{ color: 'var(--status-warning)' }}
        >
          <svg className="w-3 h-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
            <path
              fillRule="evenodd"
              d="M8.485 2.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 2.495zM10 5a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 5zm0 9a1 1 0 100-2 1 1 0 000 2z"
              clipRule="evenodd"
            />
          </svg>
          CTX &gt;80% FULL — {Math.round(usagePct * 100)}% used
        </div>
      )}

      {/* Segmented bar */}
      <div
        ref={barRef}
        className="relative h-1.5 w-full flex overflow-hidden"
        style={{
          background: 'var(--bg-tertiary)',
          borderRadius: '2px',
          outline: isWarning ? '0 0 0 1px var(--status-warning)' : undefined,
          boxShadow: isWarning
            ? '0 0 6px rgba(251,191,36,0.35)'
            : undefined,
        }}
        onMouseLeave={handleMouseLeave}
        role="img"
        aria-label={`Context usage: ${Math.round(usagePct * 100)}% of ${CONTEXT_WINDOW} tokens`}
      >
        {segments.map((seg, i) => {
          const pct = (seg.tokens / CONTEXT_WINDOW) * 100
          if (pct <= 0) return null
          return (
            <div
              key={seg.label}
              style={{
                width: `${Math.min(pct, 100)}%`,
                background: i === 3 ? 'transparent' : seg.color,
                opacity: i === 3 ? 0 : 0.85,
                transition: 'width 0.4s ease',
                cursor: 'default',
                flexShrink: 0,
              }}
              onMouseEnter={(e) => handleSegmentMouseEnter(e, seg)}
            />
          )
        })}
      </div>

      {/* Tooltip */}
      {tooltip.visible && tooltip.segment && (
        <div
          role="tooltip"
          style={{
            position: 'absolute',
            bottom: 'calc(100% + 6px)',
            left: `${tooltip.x}px`,
            transform: 'translateX(-50%)',
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border-color)',
            padding: '6px 10px',
            fontFamily: 'var(--font-mono, monospace)',
            fontSize: '11px',
            color: 'var(--text-secondary)',
            whiteSpace: 'nowrap',
            zIndex: 50,
            pointerEvents: 'none',
            boxShadow: '0 4px 16px rgba(0,0,0,0.4)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span
              style={{
                width: '8px',
                height: '8px',
                borderRadius: '1px',
                background: tooltip.segment.color,
                display: 'inline-block',
                flexShrink: 0,
              }}
            />
            <span>{tooltip.segment.description}</span>
          </div>
          <div style={{ marginTop: '3px', color: 'var(--text-muted)', fontSize: '10px' }}>
            {Math.round((tooltip.segment.tokens / CONTEXT_WINDOW) * 100)}% of {CONTEXT_WINDOW.toLocaleString()} ctx window
          </div>
        </div>
      )}

      {/* Legend — collapsed to a single line of dots below the bar */}
      <div
        className="flex items-center gap-3 mt-1 font-mono"
        style={{ fontSize: '9px', color: 'var(--text-muted)', letterSpacing: '0.08em' }}
        aria-hidden="true"
      >
        {segments.slice(0, 3).map((seg) => (
          <span key={seg.label} className="flex items-center gap-1">
            <span
              style={{
                width: '6px',
                height: '6px',
                borderRadius: '1px',
                background: seg.color,
                display: 'inline-block',
                opacity: 0.85,
                flexShrink: 0,
              }}
            />
            {seg.label.toUpperCase()}
          </span>
        ))}
        <span className="ml-auto">{Math.round(usagePct * 100)}% / 100%</span>
      </div>
    </div>
  )
}
