'use client'

import { useState, memo } from 'react'
import type { RagSource } from '@/types'

export type ToolCallStatus = 'pending' | 'complete' | 'error'

export interface ToolCallData {
  id: string
  toolName: string
  status: ToolCallStatus
  description: string
  sources?: RagSource[]
  error?: string
  startedAt: number
  completedAt?: number
}

interface ToolCallCardProps {
  toolCall: ToolCallData
}

const ToolCallCard = memo(function ToolCallCard({ toolCall }: ToolCallCardProps) {
  const [expanded, setExpanded] = useState(false)

  const statusConfig = {
    pending: {
      icon: <SpinnerIcon className="w-4 h-4 animate-spin" />,
      label: toolCall.description || 'Processing...',
      borderColor: 'var(--accent-blue)',
      textColor: 'var(--accent-blue)',
      bgColor: 'rgba(99, 102, 241, 0.06)',
    },
    complete: {
      icon: <CheckCircleIcon className="w-4 h-4" />,
      label: toolCall.description || 'Complete',
      borderColor: 'var(--accent-cyan)',
      textColor: 'var(--accent-cyan)',
      bgColor: 'rgba(34, 211, 238, 0.06)',
    },
    error: {
      icon: <ErrorCircleIcon className="w-4 h-4" />,
      label: toolCall.error || 'Tool call failed',
      borderColor: '#ef4444',
      textColor: '#ef4444',
      bgColor: 'rgba(239, 68, 68, 0.06)',
    },
  }

  const config = statusConfig[toolCall.status]
  const hasSources = toolCall.sources && toolCall.sources.length > 0
  const isExpandable = hasSources || toolCall.status === 'error'
  const duration =
    toolCall.completedAt && toolCall.startedAt
      ? `${((toolCall.completedAt - toolCall.startedAt) / 1000).toFixed(1)}s`
      : null

  return (
    <div
      className="my-2 mx-0 font-mono text-xs transition-all duration-300 ease-in-out"
      style={{
        borderLeft: `2px solid ${config.borderColor}`,
        background: config.bgColor,
        borderTop: '1px solid var(--border-color)',
        borderRight: '1px solid var(--border-color)',
        borderBottom: '1px solid var(--border-color)',
      }}
    >
      <button
        onClick={() => isExpandable && setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-white/[0.02]"
        style={{ color: config.textColor, cursor: isExpandable ? 'pointer' : 'default' }}
        disabled={!isExpandable}
      >
        {config.icon}
        <span className="flex-1 uppercase tracking-wider truncate">
          {toolCall.toolName}
          <span className="normal-case tracking-normal ml-2" style={{ color: 'var(--text-muted)' }}>
            {config.label}
          </span>
        </span>
        {duration && (
          <span className="text-[10px] tabular-nums" style={{ color: 'var(--text-secondary)' }}>{duration}</span>
        )}
        {hasSources && (
          <span
            className="text-[10px] px-1.5 py-0.5 border"
            style={{
              borderColor: `${config.borderColor}40`,
              color: config.textColor,
              background: `${config.borderColor}15`,
            }}
          >
            {toolCall.sources!.length} SOURCES
          </span>
        )}
        {isExpandable && (
          <span style={{ color: 'var(--text-secondary)' }}>[{expanded ? '-' : '+'}]</span>
        )}
      </button>

      {expanded && (
        <div className="px-3 pb-3 animate-fade-in">
          {toolCall.status === 'error' && toolCall.error && (
            <div className="p-2 text-red-400 bg-red-500/5 border border-red-500/20 mb-2">
              ERR: {toolCall.error}
            </div>
          )}
          {hasSources && (
            <div className="space-y-1.5">
              {toolCall.sources!.map((source, idx) => (
                <div
                  key={source.id || idx}
                  className="p-2 border-l-2 border-y border-r"
                  style={{
                    borderColor: 'var(--border-color)',
                    borderLeftColor: 'var(--accent-cyan)',
                    background: 'var(--bg-elevated)',
                  }}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold" style={{ color: 'var(--accent-primary)' }}>
                      SRC_{idx.toString().padStart(2, '0')}
                      {source.document_id && (
                        <span className="font-normal" style={{ color: 'var(--text-muted)' }}>
                          {' :: '}{source.document_id.slice(0, 8)}
                        </span>
                      )}
                    </span>
                    <span
                      className="text-[10px] px-1 border"
                      style={{
                        borderColor: 'color-mix(in srgb, var(--accent-primary) 30%, transparent)',
                        color: 'var(--accent-primary)',
                        background: 'color-mix(in srgb, var(--accent-primary) 10%, transparent)',
                      }}
                    >
                      MATCH: {(source.score * 100).toFixed(0)}%
                    </span>
                  </div>
                  <p className="leading-relaxed line-clamp-2" style={{ color: 'var(--text-muted)' }}>
                    {source.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
})

export default ToolCallCard

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
      <path
        className="opacity-75"
        fill="currentColor"
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  )
}

function CheckCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}

function ErrorCircleIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  )
}
