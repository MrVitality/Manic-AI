'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { useModels } from '@/hooks/useModels'
import { streamChat } from '@/lib/api'
import type { StreamEvent } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface VoteRecord {
  id: string
  modelA: string
  modelB: string
  winner: 'left' | 'right' | 'tie'
  prompt: string
  timestamp: string
}

interface LeaderboardEntry {
  model: string
  wins: number
  losses: number
  ties: number
  total: number
  winRate: number
}

interface PanelState {
  content: string
  status: 'idle' | 'streaming' | 'done' | 'error'
  error: string | null
  latencyMs: number | null
  tokenCount: number
}

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

const VOTES_KEY = 'manic-arena-votes'

function loadVotes(): VoteRecord[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(VOTES_KEY)
    return raw ? (JSON.parse(raw) as VoteRecord[]) : []
  } catch {
    return []
  }
}

function saveVotes(votes: VoteRecord[]): void {
  try {
    localStorage.setItem(VOTES_KEY, JSON.stringify(votes))
  } catch { /* ignore */ }
}

function computeLeaderboard(votes: VoteRecord[]): LeaderboardEntry[] {
  const map = new Map<string, { wins: number; losses: number; ties: number }>()

  const ensure = (model: string) => {
    if (!map.has(model)) map.set(model, { wins: 0, losses: 0, ties: 0 })
    return map.get(model)!
  }

  for (const v of votes) {
    const a = ensure(v.modelA)
    const b = ensure(v.modelB)
    if (v.winner === 'left') { a.wins++; b.losses++ }
    else if (v.winner === 'right') { b.wins++; a.losses++ }
    else { a.ties++; b.ties++ }
  }

  return Array.from(map.entries())
    .map(([model, s]) => {
      const total = s.wins + s.losses + s.ties
      return { model, ...s, total, winRate: total > 0 ? s.wins / total : 0 }
    })
    .sort((a, b) => b.winRate - a.winRate || b.total - a.total)
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

const IDLE_PANEL: PanelState = {
  content: '',
  status: 'idle',
  error: null,
  latencyMs: null,
  tokenCount: 0,
}

export default function ArenaPage() {
  const { models, isLoadingModels } = useModels()

  const [modelA, setModelA] = useState('')
  const [modelB, setModelB] = useState('')
  const [prompt, setPrompt] = useState('')
  const [panelA, setPanelA] = useState<PanelState>(IDLE_PANEL)
  const [panelB, setPanelB] = useState<PanelState>(IDLE_PANEL)
  const [isRunning, setIsRunning] = useState(false)
  const [hasResult, setHasResult] = useState(false)
  const [votes, setVotes] = useState<VoteRecord[]>([])
  const [showLeaderboard, setShowLeaderboard] = useState(false)

  const abortA = useRef<AbortController | null>(null)
  const abortB = useRef<AbortController | null>(null)

  useEffect(() => {
    setVotes(loadVotes())
  }, [])

  // Auto-select first two models once loaded
  useEffect(() => {
    if (models.length >= 1 && !modelA) setModelA(models[0].name)
    if (models.length >= 2 && !modelB) setModelB(models[1].name)
  }, [models, modelA, modelB])

  const streamOne = async (
    model: string,
    ctrl: AbortController,
    setter: React.Dispatch<React.SetStateAction<PanelState>>,
  ) => {
    const startMs = Date.now()
    let accumulated = ''
    let tokens = 0

    setter({ content: '', status: 'streaming', error: null, latencyMs: null, tokenCount: 0 })

    try {
      const gen = streamChat(
        { model, messages: [{ role: 'user', content: prompt }] },
        ctrl.signal,
      )

      for await (const event of gen) {
        const ev = event as StreamEvent
        if (ev.type === 'content' && ev.content) {
          accumulated += ev.content
          tokens += ev.content.split(/\s+/).filter(Boolean).length
          setter((prev) => ({ ...prev, content: accumulated, tokenCount: tokens }))
        }
        if (ev.type === 'done' || ev.type === 'error') break
      }

      setter({
        content: accumulated,
        status: 'done',
        error: null,
        latencyMs: Date.now() - startMs,
        tokenCount: tokens,
      })
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      setter((prev) => ({
        ...prev,
        status: 'error',
        error: err instanceof Error ? err.message : 'Unknown error',
      }))
    }
  }

  const handleSend = useCallback(async () => {
    if (!prompt.trim() || !modelA || !modelB || isRunning) return

    abortA.current?.abort()
    abortB.current?.abort()
    abortA.current = new AbortController()
    abortB.current = new AbortController()

    setHasResult(false)
    setIsRunning(true)

    await Promise.allSettled([
      streamOne(modelA, abortA.current, setPanelA),
      streamOne(modelB, abortB.current, setPanelB),
    ])

    setHasResult(true)
    setIsRunning(false)
  }, [prompt, modelA, modelB, isRunning])

  const handleStop = () => {
    abortA.current?.abort()
    abortB.current?.abort()
    setIsRunning(false)
  }

  const handleVote = (winner: 'left' | 'right' | 'tie') => {
    if (!modelA || !modelB) return
    const record: VoteRecord = {
      id: `vote_${Date.now()}`,
      modelA,
      modelB,
      winner,
      prompt,
      timestamp: new Date().toISOString(),
    }
    const updated = [record, ...votes].slice(0, 500)
    setVotes(updated)
    saveVotes(updated)
    setHasResult(false)
    setPanelA(IDLE_PANEL)
    setPanelB(IDLE_PANEL)
    setPrompt('')
  }

  const leaderboard = computeLeaderboard(votes)

  const canSend = prompt.trim().length > 0 && !!modelA && !!modelB && modelA !== modelB && !isRunning

  return (
    <div className="flex flex-col h-full min-h-0 font-mono" style={{ background: 'var(--bg-primary)' }}>
      {/* Top header */}
      <div
        className="flex items-center justify-between px-6 py-3 border-b shrink-0"
        style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--accent-primary)' }}>
            [MODEL_ARENA]
          </span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            // A/B comparison &amp; voting
          </span>
        </div>
        <button
          onClick={() => setShowLeaderboard((v) => !v)}
          className="px-3 py-1.5 text-xs rounded-sm border transition-all uppercase tracking-wide"
          style={{
            borderColor: showLeaderboard ? 'var(--accent-primary)' : 'var(--border-color)',
            color: showLeaderboard ? 'var(--accent-primary)' : 'var(--text-muted)',
            background: showLeaderboard
              ? 'color-mix(in srgb, var(--accent-primary) 10%, transparent)'
              : 'transparent',
          }}
        >
          [LEADERBOARD: {votes.length} VOTES]
        </button>
      </div>

      {/* Leaderboard panel */}
      {showLeaderboard && (
        <div
          className="border-b px-6 py-4 shrink-0"
          style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
        >
          <p className="text-xs uppercase tracking-widest mb-3" style={{ color: 'var(--accent-cyan)' }}>
            [WIN_RATES]
          </p>
          {leaderboard.length === 0 ? (
            <p className="text-xs" style={{ color: 'var(--text-muted)' }}>// No votes recorded yet</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs" style={{ borderCollapse: 'separate', borderSpacing: 0 }}>
                <thead>
                  <tr style={{ color: 'var(--text-muted)' }}>
                    {['RANK', 'MODEL', 'WIN%', 'W', 'L', 'T', 'TOTAL'].map((h) => (
                      <th key={h} className="text-left px-3 py-1.5 font-normal">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {leaderboard.map((entry, idx) => (
                    <tr
                      key={entry.model}
                      className="border-t"
                      style={{ borderColor: 'var(--border-color)' }}
                    >
                      <td className="px-3 py-1.5" style={{ color: 'var(--text-muted)' }}>
                        #{idx + 1}
                      </td>
                      <td className="px-3 py-1.5 font-bold" style={{ color: 'var(--accent-primary)' }}>
                        {entry.model}
                      </td>
                      <td className="px-3 py-1.5" style={{ color: 'var(--accent-cyan)' }}>
                        {(entry.winRate * 100).toFixed(1)}%
                      </td>
                      <td className="px-3 py-1.5" style={{ color: '#4ade80' }}>{entry.wins}</td>
                      <td className="px-3 py-1.5" style={{ color: '#ef4444' }}>{entry.losses}</td>
                      <td className="px-3 py-1.5" style={{ color: 'var(--text-muted)' }}>{entry.ties}</td>
                      <td className="px-3 py-1.5" style={{ color: 'var(--text-secondary)' }}>{entry.total}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Model selectors row */}
      <div
        className="flex items-center gap-4 px-6 py-3 border-b shrink-0"
        style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
      >
        <div className="flex-1">
          <label className="block text-[10px] uppercase tracking-widest mb-1" style={{ color: 'var(--text-muted)' }}>
            [MODEL_A]
          </label>
          <select
            value={modelA}
            onChange={(e) => setModelA(e.target.value)}
            disabled={isLoadingModels || isRunning}
            className="w-full px-3 py-1.5 text-xs rounded-sm focus:outline-none"
            style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              fontFamily: 'monospace',
            }}
          >
            {isLoadingModels ? (
              <option>Loading...</option>
            ) : (
              models.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                </option>
              ))
            )}
          </select>
        </div>

        <div
          className="shrink-0 text-xs px-3 py-1 rounded-sm border"
          style={{
            borderColor: 'var(--border-color)',
            color: 'var(--text-muted)',
          }}
        >
          VS
        </div>

        <div className="flex-1">
          <label className="block text-[10px] uppercase tracking-widest mb-1" style={{ color: 'var(--text-muted)' }}>
            [MODEL_B]
          </label>
          <select
            value={modelB}
            onChange={(e) => setModelB(e.target.value)}
            disabled={isLoadingModels || isRunning}
            className="w-full px-3 py-1.5 text-xs rounded-sm focus:outline-none"
            style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-primary)',
              fontFamily: 'monospace',
            }}
          >
            {isLoadingModels ? (
              <option>Loading...</option>
            ) : (
              models.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                </option>
              ))
            )}
          </select>
        </div>
      </div>

      {/* Response panels */}
      <div className="flex flex-1 min-h-0 overflow-hidden">
        <ArenaPanel label="MODEL_A" model={modelA} state={panelA} accentVar="var(--accent-primary)" />
        <div className="w-px shrink-0" style={{ background: 'var(--border-color)' }} />
        <ArenaPanel label="MODEL_B" model={modelB} state={panelB} accentVar="var(--accent-cyan)" />
      </div>

      {/* Vote buttons */}
      {hasResult && (
        <div
          className="flex items-center justify-center gap-4 px-6 py-4 border-t shrink-0"
          style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
        >
          <span className="text-xs mr-2" style={{ color: 'var(--text-muted)' }}>
            // Which response was better?
          </span>
          <button
            onClick={() => handleVote('left')}
            className="px-5 py-2 text-xs rounded-sm border transition-all uppercase tracking-wide"
            style={{ borderColor: 'var(--accent-primary)', color: 'var(--accent-primary)' }}
          >
            [VOTE LEFT: {modelA}]
          </button>
          <button
            onClick={() => handleVote('tie')}
            className="px-5 py-2 text-xs rounded-sm border transition-all uppercase tracking-wide"
            style={{ borderColor: 'var(--text-muted)', color: 'var(--text-muted)' }}
          >
            [TIE]
          </button>
          <button
            onClick={() => handleVote('right')}
            className="px-5 py-2 text-xs rounded-sm border transition-all uppercase tracking-wide"
            style={{ borderColor: 'var(--accent-cyan)', color: 'var(--accent-cyan)' }}
          >
            [VOTE RIGHT: {modelB}]
          </button>
        </div>
      )}

      {/* Prompt input bar */}
      <div
        className="flex items-end gap-3 px-6 py-4 border-t shrink-0"
        style={{ borderColor: 'var(--border-color)', background: 'var(--bg-primary)' }}
      >
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="// Enter your prompt — both models will respond simultaneously..."
          rows={2}
          className="flex-1 px-3 py-2 text-xs rounded-sm resize-none focus:outline-none"
          style={{
            background: 'var(--bg-tertiary)',
            border: '1px solid var(--border-color)',
            color: 'var(--text-primary)',
            fontFamily: 'monospace',
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              handleSend()
            }
          }}
          onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent-primary)')}
          onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-color)')}
        />
        {isRunning ? (
          <button
            onClick={handleStop}
            className="px-4 py-2 text-xs rounded-sm border transition-all uppercase tracking-wide shrink-0"
            style={{ borderColor: '#ef4444', color: '#ef4444' }}
          >
            [STOP]
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!canSend}
            className="px-4 py-2 text-xs rounded-sm border transition-all uppercase tracking-wide shrink-0 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              borderColor: 'var(--accent-primary)',
              color: 'var(--accent-primary)',
              background: 'color-mix(in srgb, var(--accent-primary) 10%, transparent)',
            }}
          >
            [SEND]
          </button>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Arena panel — one side of the comparison
// ---------------------------------------------------------------------------

function ArenaPanel({
  label,
  model,
  state,
  accentVar,
}: {
  label: string
  model: string
  state: PanelState
  accentVar: string
}) {
  return (
    <div className="flex-1 flex flex-col min-h-0 min-w-0">
      {/* Panel header */}
      <div
        className="flex items-center justify-between px-4 py-2.5 border-b shrink-0 text-xs"
        style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
      >
        <span className="font-bold truncate" style={{ color: accentVar }}>
          [{label}] {model || '—'}
        </span>
        {state.latencyMs !== null && (
          <span style={{ color: 'var(--text-muted)', fontSize: '10px' }}>
            {state.latencyMs}ms · {state.tokenCount} tokens
          </span>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {state.status === 'idle' && (
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
            // Awaiting prompt...
          </p>
        )}
        {state.status === 'error' && (
          <p className="text-xs" style={{ color: '#ef4444' }}>
            ERR: {state.error}
          </p>
        )}
        {(state.status === 'streaming' || state.status === 'done') && (
          <pre
            className="whitespace-pre-wrap break-words leading-relaxed text-xs"
            style={{ color: 'var(--text-primary)', fontFamily: 'monospace' }}
          >
            {state.content}
            {state.status === 'streaming' && (
              <span
                className="inline-block w-1.5 h-3 ml-0.5 animate-pulse"
                style={{ background: accentVar, verticalAlign: 'text-bottom' }}
              />
            )}
          </pre>
        )}
      </div>
    </div>
  )
}
