'use client'

import { memo, useState } from 'react'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type ThoughtStepType = 'plan' | 'retrieve' | 'generate' | 'critique' | 'revise'

export interface ThoughtStep {
  id: string
  type: ThoughtStepType
  label: string
  summary: string
  detail?: string
  score?: number        // Only for 'critique' steps (0–10)
  status: 'active' | 'complete' | 'error'
  startedAt: number
  completedAt?: number
}

interface ThoughtTraceProps {
  steps: ThoughtStep[]
  isStreaming: boolean
}

// ---------------------------------------------------------------------------
// Step visual config
// ---------------------------------------------------------------------------

const STEP_CONFIG: Record<ThoughtStepType, {
  borderColor: string
  textColor: string
  bgColor: string
  prefix: string
}> = {
  plan: {
    borderColor: '#22d3ee',     // cyan
    textColor: '#22d3ee',
    bgColor: 'rgba(34, 211, 238, 0.05)',
    prefix: 'PLAN',
  },
  retrieve: {
    borderColor: '#3b82f6',     // blue
    textColor: '#3b82f6',
    bgColor: 'rgba(59, 130, 246, 0.05)',
    prefix: 'RETRIEVE',
  },
  generate: {
    borderColor: '#34d399',     // green
    textColor: '#34d399',
    bgColor: 'rgba(52, 211, 153, 0.05)',
    prefix: 'GENERATE',
  },
  critique: {
    borderColor: '#fbbf24',     // amber
    textColor: '#fbbf24',
    bgColor: 'rgba(251, 191, 36, 0.05)',
    prefix: 'CRITIQUE',
  },
  revise: {
    borderColor: '#a78bfa',     // purple
    textColor: '#a78bfa',
    bgColor: 'rgba(167, 139, 250, 0.05)',
    prefix: 'REVISE',
  },
}

// ---------------------------------------------------------------------------
// Score badge
// ---------------------------------------------------------------------------

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 8 ? '#34d399'
    : score >= 6 ? '#fbbf24'
    : '#f87171'

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        minWidth: '26px',
        padding: '1px 6px',
        fontSize: '10px',
        fontWeight: 700,
        fontFamily: 'var(--font-mono, monospace)',
        color,
        border: `1px solid ${color}40`,
        background: `${color}18`,
        letterSpacing: '0.05em',
        flexShrink: 0,
      }}
      aria-label={`Score: ${score} out of 10`}
    >
      {score}/10
    </span>
  )
}

// ---------------------------------------------------------------------------
// Status icon
// ---------------------------------------------------------------------------

function StatusIcon({ status, type }: { status: ThoughtStep['status']; type: ThoughtStepType }) {
  const color = STEP_CONFIG[type].textColor

  if (status === 'active') {
    return (
      <svg
        className="w-3.5 h-3.5 animate-spin flex-shrink-0"
        fill="none"
        viewBox="0 0 24 24"
        style={{ color }}
        aria-label="In progress"
      >
        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
        <path
          className="opacity-75"
          fill="currentColor"
          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
        />
      </svg>
    )
  }

  if (status === 'error') {
    return (
      <svg
        className="w-3.5 h-3.5 flex-shrink-0"
        fill="none"
        stroke="#f87171"
        viewBox="0 0 24 24"
        aria-label="Error"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    )
  }

  return (
    <svg
      className="w-3.5 h-3.5 flex-shrink-0"
      fill="none"
      stroke={color}
      viewBox="0 0 24 24"
      aria-label="Complete"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Single step card
// ---------------------------------------------------------------------------

const ThoughtStepCard = memo(function ThoughtStepCard({ step }: { step: ThoughtStep }) {
  const [expanded, setExpanded] = useState(false)
  const cfg = STEP_CONFIG[step.type]
  const hasDetail = Boolean(step.detail)
  const duration =
    step.completedAt && step.startedAt
      ? `${((step.completedAt - step.startedAt) / 1000).toFixed(1)}s`
      : null

  return (
    <div
      className="font-mono text-xs transition-all duration-300 ease-in-out"
      style={{
        borderLeft: `2px solid ${cfg.borderColor}`,
        background: cfg.bgColor,
        border: `1px solid var(--border-color)`,
        borderLeftColor: cfg.borderColor,
        animation: 'thoughtStepIn 0.25s ease forwards',
      }}
    >
      <button
        onClick={() => hasDetail && setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-white/[0.02]"
        style={{
          color: cfg.textColor,
          cursor: hasDetail ? 'pointer' : 'default',
        }}
        disabled={!hasDetail}
        aria-expanded={hasDetail ? expanded : undefined}
      >
        <StatusIcon status={step.status} type={step.type} />

        <span
          className="uppercase tracking-wider font-bold text-[10px] flex-shrink-0"
          style={{ minWidth: '56px' }}
        >
          {cfg.prefix}
        </span>

        <span
          className="flex-1 normal-case tracking-normal truncate text-[11px]"
          style={{ color: 'var(--text-secondary)' }}
        >
          {step.summary}
        </span>

        {step.type === 'critique' && step.score !== undefined && (
          <ScoreBadge score={step.score} />
        )}

        {duration && (
          <span
            className="text-[10px] tabular-nums flex-shrink-0"
            style={{ color: 'var(--text-muted)' }}
          >
            {duration}
          </span>
        )}

        {hasDetail && (
          <span style={{ color: 'var(--text-secondary)', fontSize: '10px' }}>
            [{expanded ? '-' : '+'}]
          </span>
        )}
      </button>

      {expanded && hasDetail && (
        <div
          className="px-3 pb-3 animate-fade-in"
          style={{ color: 'var(--text-muted)', fontSize: '11px', lineHeight: 1.6 }}
        >
          <div
            style={{
              borderTop: `1px solid var(--border-color)`,
              marginBottom: '8px',
            }}
          />
          <pre
            style={{
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              fontFamily: 'inherit',
              margin: 0,
            }}
          >
            {step.detail}
          </pre>
        </div>
      )}
    </div>
  )
})

// ---------------------------------------------------------------------------
// Container
// ---------------------------------------------------------------------------

const ThoughtTrace = memo(function ThoughtTrace({ steps, isStreaming }: ThoughtTraceProps) {
  const [collapsed, setCollapsed] = useState(false)

  if (steps.length === 0) return null

  return (
    <div className="mt-3">
      {/* Section header */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center gap-2 mb-2 font-mono text-[10px] uppercase tracking-widest transition-opacity hover:opacity-80"
        style={{ color: 'var(--text-muted)' }}
        aria-expanded={!collapsed}
        aria-controls="thought-trace-steps"
      >
        <span>[{collapsed ? '+' : '-'}]</span>
        <span>AGENT_REASONING_TRACE</span>
        <span
          style={{
            marginLeft: '4px',
            padding: '1px 6px',
            fontSize: '9px',
            border: '1px solid var(--border-color)',
            color: 'var(--text-muted)',
          }}
        >
          {steps.length} STEP{steps.length !== 1 ? 'S' : ''}
        </span>
        {isStreaming && (
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              background: 'var(--accent-cyan)',
              display: 'inline-block',
              animation: 'pulse 1.5s ease-in-out infinite',
              flexShrink: 0,
            }}
            aria-label="Streaming"
          />
        )}
      </button>

      {/* Steps */}
      {!collapsed && (
        <div
          id="thought-trace-steps"
          className="space-y-1"
          role="list"
          aria-label="Agent reasoning steps"
        >
          {steps.map((step) => (
            <div key={step.id} role="listitem">
              <ThoughtStepCard step={step} />
            </div>
          ))}
        </div>
      )}

      {/* Keyframe injection via style tag — kept scoped here to avoid global pollution */}
      <style>{`
        @keyframes thoughtStepIn {
          from { opacity: 0; transform: translateY(-4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
})

export default ThoughtTrace
