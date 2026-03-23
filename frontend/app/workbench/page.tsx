'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { useModels } from '@/hooks/useModels'
import { streamChat } from '@/lib/api'
import type { StreamEvent } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PromptVersion {
  id: string
  name: string
  systemPrompt: string
  userMessage: string
  savedAt: string
}

interface ModelResult {
  model: string
  content: string
  latencyMs: number | null
  tokenCount: number
  status: 'idle' | 'streaming' | 'done' | 'error'
  error: string | null
}

// ---------------------------------------------------------------------------
// localStorage helpers
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'manic-workbench-prompts'

function loadVersions(): PromptVersion[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as PromptVersion[]) : []
  } catch {
    return []
  }
}

function saveVersions(versions: PromptVersion[]): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(versions))
  } catch { /* ignore quota errors */ }
}

// ---------------------------------------------------------------------------
// Page component
// ---------------------------------------------------------------------------

export default function WorkbenchPage() {
  const { models, isLoadingModels } = useModels()

  const [systemPrompt, setSystemPrompt] = useState('')
  const [userMessage, setUserMessage] = useState('')
  const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set())
  const [results, setResults] = useState<ModelResult[]>([])
  const [isRunning, setIsRunning] = useState(false)

  // Prompt versioning state
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [saveName, setSaveName] = useState('')
  const [showVersionPanel, setShowVersionPanel] = useState(false)

  const abortRefs = useRef<Map<string, AbortController>>(new Map())

  // Load versions from localStorage once
  useEffect(() => {
    setVersions(loadVersions())
  }, [])

  const toggleModel = (modelName: string) => {
    setSelectedModels((prev) => {
      const next = new Set(prev)
      if (next.has(modelName)) {
        next.delete(modelName)
      } else {
        next.add(modelName)
      }
      return next
    })
  }

  const handleRunAll = useCallback(async () => {
    if (!userMessage.trim() || selectedModels.size === 0 || isRunning) return

    // Abort any in-flight requests
    abortRefs.current.forEach((ctrl) => ctrl.abort())
    abortRefs.current.clear()

    const modelList = Array.from(selectedModels)

    // Initialise result cards
    const initial: ModelResult[] = modelList.map((m) => ({
      model: m,
      content: '',
      latencyMs: null,
      tokenCount: 0,
      status: 'streaming',
      error: null,
    }))
    setResults(initial)
    setIsRunning(true)

    const streamOne = async (model: string, idx: number) => {
      const ctrl = new AbortController()
      abortRefs.current.set(model, ctrl)

      const startMs = Date.now()
      let accumulated = ''
      let tokens = 0

      try {
        const gen = streamChat(
          {
            model,
            messages: [{ role: 'user', content: userMessage }],
            systemPrompt: systemPrompt || undefined,
          },
          ctrl.signal,
        )

        for await (const event of gen) {
          const ev = event as StreamEvent
          if (ev.type === 'content' && ev.content) {
            accumulated += ev.content
            tokens += ev.content.split(/\s+/).filter(Boolean).length
            setResults((prev) =>
              prev.map((r, i) =>
                i === idx
                  ? { ...r, content: accumulated, tokenCount: tokens, status: 'streaming' }
                  : r,
              ),
            )
          }
          if (ev.type === 'done' || ev.type === 'error') break
        }

        const latencyMs = Date.now() - startMs
        setResults((prev) =>
          prev.map((r, i) =>
            i === idx
              ? { ...r, content: accumulated, latencyMs, tokenCount: tokens, status: 'done' }
              : r,
          ),
        )
      } catch (err) {
        if ((err as Error).name === 'AbortError') return
        setResults((prev) =>
          prev.map((r, i) =>
            i === idx
              ? {
                  ...r,
                  status: 'error',
                  error: err instanceof Error ? err.message : 'Unknown error',
                }
              : r,
          ),
        )
      } finally {
        abortRefs.current.delete(model)
      }
    }

    await Promise.allSettled(modelList.map((m, i) => streamOne(m, i)))
    setIsRunning(false)
  }, [userMessage, systemPrompt, selectedModels, isRunning])

  const handleStop = () => {
    abortRefs.current.forEach((ctrl) => ctrl.abort())
    abortRefs.current.clear()
    setIsRunning(false)
    setResults((prev) =>
      prev.map((r) => (r.status === 'streaming' ? { ...r, status: 'done' } : r)),
    )
  }

  const handleSavePrompt = () => {
    if (!saveName.trim()) return
    const newVersion: PromptVersion = {
      id: `v_${Date.now()}`,
      name: saveName.trim(),
      systemPrompt,
      userMessage,
      savedAt: new Date().toISOString(),
    }
    const updated = [newVersion, ...versions].slice(0, 30)
    setVersions(updated)
    saveVersions(updated)
    setSaveName('')
  }

  const handleLoadVersion = (v: PromptVersion) => {
    setSystemPrompt(v.systemPrompt)
    setUserMessage(v.userMessage)
    setShowVersionPanel(false)
  }

  const handleDeleteVersion = (id: string) => {
    const updated = versions.filter((v) => v.id !== id)
    setVersions(updated)
    saveVersions(updated)
  }

  const allSelected = models.length > 0 && models.every((m) => selectedModels.has(m.name))

  const handleSelectAll = () => {
    if (allSelected) {
      setSelectedModels(new Set())
    } else {
      setSelectedModels(new Set(models.map((m) => m.name)))
    }
  }

  return (
    <div className="flex flex-col h-full min-h-0 font-mono" style={{ background: 'var(--bg-primary)' }}>
      {/* Header bar */}
      <div
        className="flex items-center justify-between px-6 py-3 border-b shrink-0"
        style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
      >
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold uppercase tracking-widest" style={{ color: 'var(--accent-cyan)' }}>
            [WORKBENCH]
          </span>
          <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
            // Prompt Engineering Lab
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowVersionPanel((v) => !v)}
            className="px-3 py-1.5 text-xs rounded-sm border transition-all uppercase tracking-wide"
            style={{
              borderColor: showVersionPanel ? 'var(--accent-cyan)' : 'var(--border-color)',
              color: showVersionPanel ? 'var(--accent-cyan)' : 'var(--text-muted)',
              background: showVersionPanel
                ? 'color-mix(in srgb, var(--accent-cyan) 10%, transparent)'
                : 'transparent',
            }}
          >
            [VERSIONS: {versions.length}]
          </button>
          {isRunning ? (
            <button
              onClick={handleStop}
              className="px-4 py-1.5 text-xs rounded-sm border transition-all uppercase tracking-wide"
              style={{
                borderColor: '#ef4444',
                color: '#ef4444',
                background: 'color-mix(in srgb, #ef4444 10%, transparent)',
              }}
            >
              [STOP]
            </button>
          ) : (
            <button
              onClick={handleRunAll}
              disabled={selectedModels.size === 0 || !userMessage.trim()}
              className="px-4 py-1.5 text-xs rounded-sm border transition-all uppercase tracking-wide disabled:opacity-40 disabled:cursor-not-allowed"
              style={{
                borderColor: 'var(--accent-primary)',
                color: 'var(--accent-primary)',
                background: 'color-mix(in srgb, var(--accent-primary) 10%, transparent)',
              }}
            >
              [RUN ALL: {selectedModels.size}]
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Left panel: inputs ~60% */}
        <div
          className="flex flex-col min-h-0 border-r"
          style={{ width: '60%', borderColor: 'var(--border-color)' }}
        >
          {/* System prompt */}
          <div className="flex flex-col flex-1 min-h-0 p-4 gap-2">
            <label className="text-xs uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
              [SYSTEM_PROMPT]
            </label>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              placeholder="// Define system behavior, persona, constraints..."
              className="flex-1 min-h-0 w-full p-3 text-xs rounded-sm resize-none focus:outline-none focus:ring-1 placeholder-shown:text-sm"
              style={{
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                fontFamily: 'monospace',
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent-cyan)')}
              onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-color)')}
            />
          </div>

          {/* User message */}
          <div
            className="flex flex-col gap-2 p-4 border-t shrink-0"
            style={{ borderColor: 'var(--border-color)' }}
          >
            <label className="text-xs uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
              [USER_MESSAGE]
            </label>
            <textarea
              value={userMessage}
              onChange={(e) => setUserMessage(e.target.value)}
              placeholder="// Enter the prompt to test across models..."
              rows={4}
              className="w-full p-3 text-xs rounded-sm resize-none focus:outline-none"
              style={{
                background: 'var(--bg-tertiary)',
                border: '1px solid var(--border-color)',
                color: 'var(--text-primary)',
                fontFamily: 'monospace',
              }}
              onFocus={(e) => (e.currentTarget.style.borderColor = 'var(--accent-primary)')}
              onBlur={(e) => (e.currentTarget.style.borderColor = 'var(--border-color)')}
            />

            {/* Save version row */}
            <div className="flex gap-2 items-center mt-1">
              <input
                type="text"
                value={saveName}
                onChange={(e) => setSaveName(e.target.value)}
                placeholder="Version name..."
                className="flex-1 px-3 py-1.5 text-xs rounded-sm focus:outline-none"
                style={{
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)',
                  fontFamily: 'monospace',
                }}
                onKeyDown={(e) => { if (e.key === 'Enter') handleSavePrompt() }}
              />
              <button
                onClick={handleSavePrompt}
                disabled={!saveName.trim()}
                className="px-3 py-1.5 text-xs rounded-sm border uppercase tracking-wide transition-all disabled:opacity-40 disabled:cursor-not-allowed"
                style={{
                  borderColor: 'var(--border-color)',
                  color: 'var(--text-muted)',
                }}
              >
                [SAVE]
              </button>
            </div>
          </div>

          {/* Model selector */}
          <div
            className="p-4 border-t shrink-0"
            style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
          >
            <div className="flex items-center justify-between mb-2">
              <label className="text-xs uppercase tracking-widest" style={{ color: 'var(--text-muted)' }}>
                [MODELS]
              </label>
              <button
                onClick={handleSelectAll}
                className="text-xs px-2 py-0.5 rounded-sm border transition-all"
                style={{ borderColor: 'var(--border-color)', color: 'var(--text-muted)' }}
              >
                {allSelected ? 'Deselect All' : 'Select All'}
              </button>
            </div>
            {isLoadingModels ? (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>// Loading models...</p>
            ) : models.length === 0 ? (
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>// No models available</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {models.map((m) => {
                  const checked = selectedModels.has(m.name)
                  return (
                    <button
                      key={m.name}
                      onClick={() => toggleModel(m.name)}
                      className="flex items-center gap-1.5 px-2 py-1 text-xs rounded-sm border transition-all"
                      style={{
                        borderColor: checked ? 'var(--accent-primary)' : 'var(--border-color)',
                        color: checked ? 'var(--accent-primary)' : 'var(--text-muted)',
                        background: checked
                          ? 'color-mix(in srgb, var(--accent-primary) 10%, transparent)'
                          : 'transparent',
                      }}
                    >
                      <span
                        className="w-3 h-3 border rounded-sm flex items-center justify-center shrink-0"
                        style={{
                          borderColor: checked ? 'var(--accent-primary)' : 'var(--border-color)',
                          background: checked ? 'var(--accent-primary)' : 'transparent',
                        }}
                      >
                        {checked && (
                          <svg className="w-2 h-2" fill="currentColor" viewBox="0 0 12 12" style={{ color: 'var(--bg-primary)' }}>
                            <path d="M10 3L5 8.5 2 5.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" fill="none" />
                          </svg>
                        )}
                      </span>
                      {m.name}
                    </button>
                  )
                })}
              </div>
            )}
          </div>
        </div>

        {/* Right panel: results grid or version panel */}
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          {showVersionPanel ? (
            <div className="flex flex-col h-full overflow-hidden">
              <div
                className="px-4 py-3 border-b shrink-0 text-xs uppercase tracking-widest"
                style={{ borderColor: 'var(--border-color)', color: 'var(--accent-cyan)' }}
              >
                [SAVED_VERSIONS]
              </div>
              <div className="flex-1 overflow-y-auto p-3 space-y-2">
                {versions.length === 0 ? (
                  <p className="text-xs text-center py-8" style={{ color: 'var(--text-muted)' }}>
                    // No saved prompts yet
                  </p>
                ) : (
                  versions.map((v) => (
                    <div
                      key={v.id}
                      className="p-3 rounded-sm border text-xs"
                      style={{ borderColor: 'var(--border-color)', background: 'var(--glass-bg)' }}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-bold" style={{ color: 'var(--accent-primary)' }}>
                          {v.name}
                        </span>
                        <span style={{ color: 'var(--text-muted)' }}>
                          {new Date(v.savedAt).toLocaleDateString()}
                        </span>
                      </div>
                      {v.systemPrompt && (
                        <p className="truncate mb-1" style={{ color: 'var(--text-muted)' }}>
                          SYS: {v.systemPrompt}
                        </p>
                      )}
                      <p className="truncate mb-3" style={{ color: 'var(--text-secondary)' }}>
                        USR: {v.userMessage}
                      </p>
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleLoadVersion(v)}
                          className="px-3 py-1 rounded-sm border text-xs transition-all"
                          style={{
                            borderColor: 'var(--accent-primary)',
                            color: 'var(--accent-primary)',
                          }}
                        >
                          [LOAD]
                        </button>
                        <button
                          onClick={() => handleDeleteVersion(v.id)}
                          className="px-3 py-1 rounded-sm border text-xs transition-all"
                          style={{ borderColor: '#ef444488', color: '#ef4444' }}
                        >
                          [DEL]
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : (
            <div className="flex flex-col h-full overflow-hidden">
              <div
                className="px-4 py-3 border-b shrink-0 text-xs uppercase tracking-widest"
                style={{ borderColor: 'var(--border-color)', color: 'var(--text-muted)' }}
              >
                [RESULTS: {results.length}]
              </div>
              {results.length === 0 ? (
                <div className="flex-1 flex items-center justify-center">
                  <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                    // Select models and run to see side-by-side results
                  </p>
                </div>
              ) : (
                <div className="flex-1 overflow-y-auto p-3 grid gap-3" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))' }}>
                  {results.map((r) => (
                    <ResultCard key={r.model} result={r} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Result card
// ---------------------------------------------------------------------------

function ResultCard({ result }: { result: ModelResult }) {
  const statusColor =
    result.status === 'error'
      ? '#ef4444'
      : result.status === 'done'
      ? 'var(--accent-cyan)'
      : 'var(--accent-primary)'

  const statusLabel =
    result.status === 'streaming'
      ? 'STREAMING'
      : result.status === 'done'
      ? 'DONE'
      : result.status === 'error'
      ? 'ERROR'
      : 'IDLE'

  return (
    <div
      className="flex flex-col rounded-sm border text-xs"
      style={{ borderColor: 'var(--border-color)', background: 'var(--glass-bg)' }}
    >
      {/* Card header */}
      <div
        className="flex items-center justify-between px-3 py-2 border-b"
        style={{ borderColor: 'var(--border-color)' }}
      >
        <span className="font-bold truncate" style={{ color: 'var(--accent-primary)' }}>
          {result.model}
        </span>
        <span
          className="ml-2 shrink-0 px-1.5 py-0.5 rounded-sm border font-mono"
          style={{ borderColor: statusColor, color: statusColor, fontSize: '10px' }}
        >
          {statusLabel}
        </span>
      </div>

      {/* Stats row */}
      <div
        className="flex gap-4 px-3 py-1.5 border-b text-[10px]"
        style={{ borderColor: 'var(--border-color)', color: 'var(--text-muted)' }}
      >
        <span>
          LATENCY:{' '}
          <span style={{ color: 'var(--text-primary)' }}>
            {result.latencyMs !== null ? `${result.latencyMs}ms` : '…'}
          </span>
        </span>
        <span>
          TOKENS:{' '}
          <span style={{ color: 'var(--text-primary)' }}>{result.tokenCount}</span>
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 p-3 overflow-y-auto" style={{ maxHeight: '320px', minHeight: '120px' }}>
        {result.status === 'error' ? (
          <p style={{ color: '#ef4444' }}>ERR: {result.error}</p>
        ) : result.content ? (
          <pre
            className="whitespace-pre-wrap break-words leading-relaxed"
            style={{ color: 'var(--text-primary)', fontFamily: 'monospace', fontSize: '11px' }}
          >
            {result.content}
            {result.status === 'streaming' && (
              <span
                className="inline-block w-1.5 h-3 ml-0.5 animate-pulse"
                style={{ background: 'var(--accent-primary)', verticalAlign: 'text-bottom' }}
              />
            )}
          </pre>
        ) : (
          <p style={{ color: 'var(--text-muted)' }}>// Awaiting response...</p>
        )}
      </div>
    </div>
  )
}
