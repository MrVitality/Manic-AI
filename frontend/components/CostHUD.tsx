'use client'

import { useEffect, useRef, useState } from 'react'

interface CostHUDProps {
  /** Number of completion tokens generated so far */
  completionTokens: number
  /** Number of prompt tokens sent */
  promptTokens: number
  /** Whether the stream is currently active */
  isStreaming: boolean
}

// GPT-4o pricing: $5/M prompt, $15/M completion (per OpenAI published rates)
const GPT4O_PROMPT_COST_PER_TOKEN = 5 / 1_000_000
const GPT4O_COMPLETION_COST_PER_TOKEN = 15 / 1_000_000

function calcGpt4oCost(promptTokens: number, completionTokens: number): number {
  return (
    promptTokens * GPT4O_PROMPT_COST_PER_TOKEN +
    completionTokens * GPT4O_COMPLETION_COST_PER_TOKEN
  )
}

type HUDPhase = 'hidden' | 'streaming' | 'complete'

export default function CostHUD({ completionTokens, promptTokens, isStreaming }: CostHUDProps) {
  const streamStartRef = useRef<number | null>(null)
  const [tokensPerSec, setTokensPerSec] = useState<number>(0)
  const [phase, setPhase] = useState<HUDPhase>('hidden')
  const hideTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const rafRef = useRef<number | null>(null)

  // Track stream start time
  useEffect(() => {
    if (isStreaming) {
      if (streamStartRef.current === null) {
        streamStartRef.current = Date.now()
      }
      setPhase('streaming')
      if (hideTimerRef.current !== null) {
        clearTimeout(hideTimerRef.current)
        hideTimerRef.current = null
      }
    } else if (!isStreaming && streamStartRef.current !== null) {
      // Stream just completed
      setPhase('complete')
      hideTimerRef.current = setTimeout(() => {
        setPhase('hidden')
        streamStartRef.current = null
        setTokensPerSec(0)
      }, 5000)
    }

    return () => {
      if (hideTimerRef.current !== null) clearTimeout(hideTimerRef.current)
    }
  }, [isStreaming])

  // Compute tokens/sec via rAF during streaming
  useEffect(() => {
    if (!isStreaming || streamStartRef.current === null) {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      return
    }

    const tick = () => {
      if (streamStartRef.current !== null) {
        const elapsedSec = (Date.now() - streamStartRef.current) / 1000
        if (elapsedSec > 0.1) {
          setTokensPerSec(completionTokens / elapsedSec)
        }
      }
      rafRef.current = requestAnimationFrame(tick)
    }

    rafRef.current = requestAnimationFrame(tick)

    return () => {
      if (rafRef.current !== null) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [isStreaming, completionTokens])

  // Final tokens/sec snapshot when stream ends
  useEffect(() => {
    if (!isStreaming && streamStartRef.current !== null && completionTokens > 0) {
      const elapsedSec = (Date.now() - streamStartRef.current) / 1000
      if (elapsedSec > 0.1) {
        setTokensPerSec(completionTokens / elapsedSec)
      }
    }
  }, [isStreaming, completionTokens])

  if (phase === 'hidden' || (completionTokens === 0 && promptTokens === 0)) {
    return null
  }

  const gpt4oCost = calcGpt4oCost(promptTokens, completionTokens)
  // Ollama local inference is free — savings equals the full GPT-4o cost
  const saved = gpt4oCost

  const isVisible = phase === 'streaming' || phase === 'complete'

  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Inference cost savings"
      style={{
        position: 'absolute',
        bottom: '80px',
        right: '16px',
        zIndex: 40,
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0)' : 'translateY(8px)',
        transition: 'opacity 0.3s ease, transform 0.3s ease',
        pointerEvents: isVisible ? 'auto' : 'none',
        background: 'var(--bg-elevated)',
        border: '1px solid var(--border-color)',
        borderLeft: '2px solid var(--accent-cyan)',
        padding: '8px 12px',
        fontFamily: 'var(--font-mono, monospace)',
        fontSize: '11px',
        color: 'var(--text-secondary)',
        minWidth: '180px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.4)',
      }}
    >
      {/* Header */}
      <div
        style={{
          fontSize: '9px',
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: 'var(--accent-cyan)',
          marginBottom: '6px',
          display: 'flex',
          alignItems: 'center',
          gap: '6px',
        }}
      >
        <span
          style={{
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: phase === 'streaming' ? 'var(--accent-cyan)' : 'var(--accent-emerald)',
            display: 'inline-block',
            animation: phase === 'streaming' ? 'pulse 1.5s ease-in-out infinite' : 'none',
          }}
        />
        {phase === 'streaming' ? 'INFERENCE_ACTIVE' : 'INFERENCE_COMPLETE'}
      </div>

      {/* Metrics rows */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
        <MetricRow
          label="TPS"
          value={tokensPerSec > 0 ? `${tokensPerSec.toFixed(1)} tok/s` : '—'}
          color="var(--text-secondary)"
        />
        <MetricRow
          label="TOKENS"
          value={`${completionTokens.toLocaleString()} out / ${promptTokens.toLocaleString()} in`}
          color="var(--text-secondary)"
        />
        <MetricRow
          label="GPT-4o~"
          value={`$${gpt4oCost.toFixed(4)}`}
          color="var(--text-muted)"
        />

        {/* Savings line */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: '4px',
            paddingTop: '4px',
            borderTop: '1px solid var(--border-color)',
          }}
        >
          <span style={{ color: 'var(--text-muted)', fontSize: '9px', letterSpacing: '0.1em' }}>
            YOU_SAVED
          </span>
          <span
            style={{
              color: '#34d399',
              fontWeight: 700,
              fontSize: '13px',
              letterSpacing: '0.02em',
            }}
          >
            ${saved.toFixed(4)}
          </span>
        </div>
      </div>
    </div>
  )
}

function MetricRow({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px' }}>
      <span style={{ fontSize: '9px', letterSpacing: '0.1em', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
        {label}
      </span>
      <span style={{ color, fontSize: '11px', fontVariantNumeric: 'tabular-nums' }}>
        {value}
      </span>
    </div>
  )
}
