'use client'

import { useState, useCallback } from 'react'
import GlassPanel from '@/components/ui/GlassPanel'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ScheduledAgent {
  id: string
  query: string
  interval: string
  lastRun: string | null
  enabled: boolean
}

interface RssSource {
  id: string
  url: string
  schedule: string
  lastFetched: string | null
}

const INTERVAL_OPTIONS = [
  { value: '15m', label: 'Every 15 minutes' },
  { value: '1h', label: 'Every hour' },
  { value: '6h', label: 'Every 6 hours' },
  { value: '12h', label: 'Every 12 hours' },
  { value: '24h', label: 'Every day' },
  { value: '7d', label: 'Every week' },
]

// ---------------------------------------------------------------------------
// Initial demo data (local state only — backend is being built)
// ---------------------------------------------------------------------------

const DEMO_AGENTS: ScheduledAgent[] = [
  {
    id: 'agent-1',
    query: 'Summarize new AI papers published this week',
    interval: '24h',
    lastRun: '2026-03-21T08:00:00Z',
    enabled: true,
  },
  {
    id: 'agent-2',
    query: 'Check for security advisories and CVEs',
    interval: '6h',
    lastRun: '2026-03-22T06:00:00Z',
    enabled: false,
  },
]

const DEMO_SOURCES: RssSource[] = [
  {
    id: 'rss-1',
    url: 'https://arxiv.org/rss/cs.AI',
    schedule: '6h',
    lastFetched: '2026-03-22T06:00:00Z',
  },
  {
    id: 'rss-2',
    url: 'https://hnrss.org/frontpage',
    schedule: '1h',
    lastFetched: '2026-03-22T10:00:00Z',
  },
]

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatRelative(iso: string | null): string {
  if (!iso) return 'Never'
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diffMs / 60_000)
  if (mins < 1) return 'Just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AutomationSettings() {
  const [watchFolderConnected, setWatchFolderConnected] = useState(false)
  const [agents, setAgents] = useState<ScheduledAgent[]>(DEMO_AGENTS)
  const [sources, setSources] = useState<RssSource[]>(DEMO_SOURCES)

  // Add-source form state
  const [newUrl, setNewUrl] = useState('')
  const [newInterval, setNewInterval] = useState('6h')
  const [urlError, setUrlError] = useState<string | null>(null)

  const toggleAgent = useCallback((id: string) => {
    setAgents((prev) =>
      prev.map((a) => (a.id === id ? { ...a, enabled: !a.enabled } : a)),
    )
  }, [])

  const removeSource = useCallback((id: string) => {
    setSources((prev) => prev.filter((s) => s.id !== id))
  }, [])

  const addSource = useCallback(() => {
    const trimmed = newUrl.trim()
    if (!trimmed) {
      setUrlError('URL is required')
      return
    }
    try {
      new URL(trimmed)
    } catch {
      setUrlError('Enter a valid URL')
      return
    }
    setUrlError(null)
    setSources((prev) => [
      ...prev,
      {
        id: `rss-${Date.now()}`,
        url: trimmed,
        schedule: newInterval,
        lastFetched: null,
      },
    ])
    setNewUrl('')
    setNewInterval('6h')
  }, [newUrl, newInterval])

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
          Automation
        </h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
          Configure watch folders, scheduled agents, and RSS ingestion pipelines.
          Backend endpoints are under active development.
        </p>
      </div>

      {/* Watch Folder */}
      <GlassPanel className="p-4">
        <div className="flex items-start gap-3">
          <div
            className="mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
            style={{
              background: watchFolderConnected
                ? 'rgba(16,185,129,0.1)'
                : 'var(--bg-tertiary)',
              border: `1px solid ${
                watchFolderConnected
                  ? 'rgba(16,185,129,0.25)'
                  : 'var(--glass-border)'
              }`,
            }}
          >
            <FolderIcon
              style={{
                color: watchFolderConnected
                  ? 'var(--accent-emerald)'
                  : 'var(--text-muted)',
              }}
            />
          </div>

          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-0.5">
              <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                Watch Folder
              </span>
              <StatusBadge connected={watchFolderConnected} />
            </div>
            <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
              Automatically ingest files dropped into a monitored directory.
            </p>
            <button
              onClick={() => setWatchFolderConnected((v) => !v)}
              role="switch"
              aria-checked={watchFolderConnected}
              aria-label="Toggle watch folder"
              className="w-10 h-5 rounded-full transition-colors relative"
              style={{
                background: watchFolderConnected
                  ? 'var(--accent-emerald)'
                  : 'var(--bg-tertiary)',
              }}
            >
              <div
                className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                style={{ left: watchFolderConnected ? 20 : 2 }}
              />
            </button>
          </div>
        </div>
      </GlassPanel>

      {/* Scheduled Agents */}
      <section>
        <h4
          className="text-xs font-semibold uppercase tracking-wider mb-3"
          style={{ color: 'var(--text-muted)' }}
        >
          Scheduled Agents
        </h4>
        <div className="space-y-3">
          {agents.map((agent) => (
            <GlassPanel key={agent.id} className="p-4">
              <div className="flex items-start gap-3">
                <div
                  className="mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{
                    background: agent.enabled
                      ? 'rgba(129,140,248,0.1)'
                      : 'var(--bg-tertiary)',
                    border: `1px solid ${
                      agent.enabled
                        ? 'rgba(129,140,248,0.25)'
                        : 'var(--glass-border)'
                    }`,
                  }}
                >
                  <AgentIcon
                    style={{
                      color: agent.enabled
                        ? 'var(--accent-blue)'
                        : 'var(--text-muted)',
                    }}
                  />
                </div>

                <div className="flex-1 min-w-0">
                  <p
                    className="text-sm mb-1 leading-snug"
                    style={{ color: 'var(--text-primary)' }}
                  >
                    {agent.query}
                  </p>
                  <div className="flex items-center gap-4 flex-wrap text-xs" style={{ color: 'var(--text-muted)' }}>
                    <span>
                      Interval:{' '}
                      <span style={{ color: 'var(--text-secondary)' }}>
                        {INTERVAL_OPTIONS.find((o) => o.value === agent.interval)?.label ?? agent.interval}
                      </span>
                    </span>
                    <span>Last run: {formatRelative(agent.lastRun)}</span>
                  </div>
                </div>

                <button
                  onClick={() => toggleAgent(agent.id)}
                  role="switch"
                  aria-checked={agent.enabled}
                  aria-label={`Toggle agent: ${agent.query}`}
                  className="w-10 h-5 rounded-full transition-colors relative flex-shrink-0 mt-0.5"
                  style={{
                    background: agent.enabled
                      ? 'var(--accent-blue)'
                      : 'var(--bg-tertiary)',
                  }}
                >
                  <div
                    className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                    style={{ left: agent.enabled ? 20 : 2 }}
                  />
                </button>
              </div>
            </GlassPanel>
          ))}

          {agents.length === 0 && (
            <p className="text-xs text-center py-4" style={{ color: 'var(--text-muted)' }}>
              No scheduled agents configured.
            </p>
          )}
        </div>
      </section>

      {/* RSS Sources */}
      <section>
        <h4
          className="text-xs font-semibold uppercase tracking-wider mb-3"
          style={{ color: 'var(--text-muted)' }}
        >
          RSS Sources
        </h4>
        <div className="space-y-3">
          {sources.map((src) => (
            <GlassPanel key={src.id} className="p-4">
              <div className="flex items-start gap-3">
                <div
                  className="mt-0.5 w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: 'rgba(6,182,212,0.08)', border: '1px solid rgba(6,182,212,0.2)' }}
                >
                  <RssIcon style={{ color: 'var(--accent-cyan)' }} />
                </div>

                <div className="flex-1 min-w-0">
                  <p
                    className="text-xs font-mono truncate mb-1"
                    style={{ color: 'var(--text-primary)' }}
                    title={src.url}
                  >
                    {src.url}
                  </p>
                  <div className="flex items-center gap-4 text-xs" style={{ color: 'var(--text-muted)' }}>
                    <span>
                      Schedule:{' '}
                      <span style={{ color: 'var(--text-secondary)' }}>
                        {INTERVAL_OPTIONS.find((o) => o.value === src.schedule)?.label ?? src.schedule}
                      </span>
                    </span>
                    <span>Last fetched: {formatRelative(src.lastFetched)}</span>
                  </div>
                </div>

                <button
                  onClick={() => removeSource(src.id)}
                  className="p-1.5 rounded transition-colors flex-shrink-0 mt-0.5"
                  style={{ color: 'var(--text-muted)' }}
                  onMouseEnter={(e) => {
                    ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--status-error)'
                  }}
                  onMouseLeave={(e) => {
                    ;(e.currentTarget as HTMLButtonElement).style.color = 'var(--text-muted)'
                  }}
                  aria-label={`Remove RSS source: ${src.url}`}
                  title="Remove source"
                >
                  <TrashIcon />
                </button>
              </div>
            </GlassPanel>
          ))}

          {sources.length === 0 && (
            <p className="text-xs text-center py-4" style={{ color: 'var(--text-muted)' }}>
              No RSS sources configured.
            </p>
          )}

          {/* Add source form */}
          <GlassPanel className="p-4">
            <p className="text-xs font-medium mb-3" style={{ color: 'var(--text-secondary)' }}>
              Add RSS Source
            </p>
            <div className="flex flex-col sm:flex-row gap-2">
              <div className="flex-1">
                <input
                  type="url"
                  value={newUrl}
                  onChange={(e) => {
                    setNewUrl(e.target.value)
                    if (urlError) setUrlError(null)
                  }}
                  placeholder="https://example.com/feed.xml"
                  className="w-full px-3 py-2 rounded-lg text-xs focus:outline-none focus:ring-2"
                  style={{
                    background: 'var(--bg-tertiary)',
                    border: `1px solid ${urlError ? 'var(--status-error)' : 'var(--glass-border)'}`,
                    color: 'var(--text-primary)',
                  }}
                  aria-label="RSS feed URL"
                  aria-invalid={!!urlError}
                />
                {urlError && (
                  <p className="text-[11px] mt-1" style={{ color: 'var(--status-error)' }}>
                    {urlError}
                  </p>
                )}
              </div>

              <select
                value={newInterval}
                onChange={(e) => setNewInterval(e.target.value)}
                className="px-3 py-2 rounded-lg text-xs focus:outline-none"
                style={{
                  background: 'var(--bg-tertiary)',
                  border: '1px solid var(--glass-border)',
                  color: 'var(--text-secondary)',
                }}
                aria-label="Fetch interval"
              >
                {INTERVAL_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>

              <button
                onClick={addSource}
                className="px-4 py-2 rounded-lg text-xs font-medium transition-colors"
                style={{
                  background: 'rgba(6,182,212,0.1)',
                  color: 'var(--accent-cyan)',
                  border: '1px solid rgba(6,182,212,0.2)',
                }}
                onMouseEnter={(e) => {
                  ;(e.currentTarget as HTMLButtonElement).style.background = 'rgba(6,182,212,0.18)'
                }}
                onMouseLeave={(e) => {
                  ;(e.currentTarget as HTMLButtonElement).style.background = 'rgba(6,182,212,0.1)'
                }}
              >
                Add Source
              </button>
            </div>
          </GlassPanel>
        </div>
      </section>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatusBadge({ connected }: { connected: boolean }) {
  return (
    <span
      className="px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider"
      style={
        connected
          ? {
              background: 'rgba(16,185,129,0.1)',
              color: 'var(--accent-emerald)',
              border: '1px solid rgba(16,185,129,0.25)',
            }
          : {
              background: 'rgba(113,113,122,0.1)',
              color: '#71717a',
              border: '1px solid rgba(113,113,122,0.2)',
            }
      }
    >
      {connected ? 'Connected' : 'Disconnected'}
    </span>
  )
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

interface IconProps {
  style?: React.CSSProperties
  className?: string
}

function FolderIcon({ style, className }: IconProps) {
  return (
    <svg
      className={className ?? 'w-4 h-4'}
      style={style}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"
      />
    </svg>
  )
}

function AgentIcon({ style, className }: IconProps) {
  return (
    <svg
      className={className ?? 'w-4 h-4'}
      style={style}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
      />
    </svg>
  )
}

function RssIcon({ style, className }: IconProps) {
  return (
    <svg
      className={className ?? 'w-4 h-4'}
      style={style}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M6 5c7.18 0 13 5.82 13 13M6 11a7 7 0 017 7m-6 0a1 1 0 11-2 0 1 1 0 012 0z"
      />
    </svg>
  )
}

function TrashIcon({ style, className }: IconProps) {
  return (
    <svg
      className={className ?? 'w-3.5 h-3.5'}
      style={style}
      fill="none"
      stroke="currentColor"
      viewBox="0 0 24 24"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
      />
    </svg>
  )
}
