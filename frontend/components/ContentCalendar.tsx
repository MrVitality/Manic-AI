'use client'

import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useContentStore } from '@/lib/stores/contentStore'
import {
  fetchContentCalendar,
  fetchContent,
  updateContent,
  approveContent,
  rejectContent,
  recheckContent,
} from '@/lib/api'
import type {
  ContentEntry,
  ContentStatus,
  ContentPlatform,
  FairHousingVerdict,
} from '@/types'

const STATUSES: Array<{ value: ContentStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'draft', label: 'Draft' },
  { value: 'flagged', label: 'Flagged' },
  { value: 'blocked', label: 'Blocked' },
  { value: 'approved', label: 'Approved' },
  { value: 'scheduled', label: 'Scheduled' },
  { value: 'posted', label: 'Posted' },
  { value: 'archived', label: 'Archived' },
]

const PLATFORMS: ContentPlatform[] = [
  'instagram',
  'facebook',
  'linkedin',
  'email',
  'tiktok',
  'youtube',
  'mls',
  'reels',
  'all',
]

export function verdictColor(v: FairHousingVerdict): {
  bg: string
  fg: string
  label: string
} {
  switch (v) {
    case 'pass':
      return { bg: 'var(--accent-green, #10b981)', fg: '#fff', label: 'Compliant' }
    case 'warn':
      return { bg: 'var(--accent-amber, #f59e0b)', fg: '#000', label: 'Review' }
    case 'block':
      return { bg: 'var(--accent-red, #ef4444)', fg: '#fff', label: 'Blocked' }
    default:
      return { bg: 'var(--text-tertiary, #6b7280)', fg: '#fff', label: 'Unchecked' }
  }
}

function statusColor(status: string): string {
  switch (status) {
    case 'draft':
      return 'var(--text-tertiary, #6b7280)'
    case 'flagged':
      return 'var(--accent-amber, #f59e0b)'
    case 'blocked':
      return 'var(--accent-red, #ef4444)'
    case 'approved':
      return 'var(--accent-green, #10b981)'
    case 'scheduled':
      return 'var(--accent-blue, #3b82f6)'
    case 'posted':
      return 'var(--accent-indigo, #818cf8)'
    case 'archived':
      return 'var(--text-tertiary, #6b7280)'
    default:
      return 'var(--text-tertiary, #6b7280)'
  }
}

function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleString()
}

function shortBody(s: string, len = 80): string {
  if (!s) return ''
  return s.length > len ? s.slice(0, len) + '…' : s
}

export default function ContentCalendar() {
  const searchParams = useSearchParams()
  const listingIdParam = searchParams.get('listing_id')

  const {
    entries,
    total,
    isLoading,
    error,
    filter,
    setFilter,
    setEntries,
    setIsLoading,
    setError,
    selectedEntry,
    setSelectedEntry,
    isLoadingDetail,
    setIsLoadingDetail,
    upsertEntry,
  } = useContentStore()

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [toast, setToast] = useState<{
    msg: string
    kind: 'error' | 'success'
  } | null>(null)

  // Editable buffer for the detail drawer
  const [editBody, setEditBody] = useState('')
  const [editTitle, setEditTitle] = useState('')
  const [savingEdits, setSavingEdits] = useState(false)
  const [actioning, setActioning] = useState(false)

  // Apply listing_id from query string once
  useEffect(() => {
    if (listingIdParam && filter.listing_id !== listingIdParam) {
      setFilter({ listing_id: listingIdParam, offset: 0 })
    }
  }, [listingIdParam, filter.listing_id, setFilter])

  const loadEntries = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const { entries: data, total: count } = await fetchContentCalendar(filter)
      setEntries(data, count)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Failed to load content')
    } finally {
      setIsLoading(false)
    }
  }, [filter, setEntries, setIsLoading, setError])

  useEffect(() => {
    loadEntries()
  }, [loadEntries])

  const showToast = useCallback((msg: string, kind: 'error' | 'success' = 'success') => {
    setToast({ msg, kind })
    setTimeout(() => setToast(null), 4000)
  }, [])

  const handleRowClick = useCallback(
    async (entry: ContentEntry) => {
      setDrawerOpen(true)
      setIsLoadingDetail(true)
      try {
        const detail = await fetchContent(entry.id)
        setSelectedEntry(detail)
        setEditBody(detail.content ?? '')
        setEditTitle(detail.title ?? '')
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : 'Failed to load entry detail')
      } finally {
        setIsLoadingDetail(false)
      }
    },
    [setSelectedEntry, setIsLoadingDetail, setError],
  )

  const handleSaveEdits = useCallback(async () => {
    if (!selectedEntry) return
    setSavingEdits(true)
    try {
      const updated = await updateContent(selectedEntry.id, {
        title: editTitle,
        content: editBody,
      })
      setSelectedEntry(updated)
      upsertEntry(updated)
      showToast('Saved')
    } catch (exc) {
      showToast(exc instanceof Error ? exc.message : 'Save failed', 'error')
    } finally {
      setSavingEdits(false)
    }
  }, [selectedEntry, editTitle, editBody, setSelectedEntry, upsertEntry, showToast])

  const handleApprove = useCallback(async () => {
    if (!selectedEntry) return
    if (selectedEntry.fair_housing_verdict === 'warn') {
      const ok = window.confirm(
        'This content has a Fair Housing warning. Approving it anyway. Continue?',
      )
      if (!ok) return
    }
    setActioning(true)
    try {
      const updated = await approveContent(selectedEntry.id)
      setSelectedEntry(updated)
      upsertEntry(updated)
      showToast('Approved')
    } catch (exc) {
      const err = exc as Error & { code?: string }
      if (err.code === 'blocked_by_compliance') {
        showToast('BLOCKED — Fair Housing violation. Cannot approve.', 'error')
      } else {
        showToast(err.message ?? 'Approve failed', 'error')
      }
    } finally {
      setActioning(false)
    }
  }, [selectedEntry, setSelectedEntry, upsertEntry, showToast])

  const handleReject = useCallback(async () => {
    if (!selectedEntry) return
    setActioning(true)
    try {
      const updated = await rejectContent(selectedEntry.id)
      setSelectedEntry(updated)
      upsertEntry(updated)
      showToast('Rejected')
    } catch (exc) {
      showToast(exc instanceof Error ? exc.message : 'Reject failed', 'error')
    } finally {
      setActioning(false)
    }
  }, [selectedEntry, setSelectedEntry, upsertEntry, showToast])

  const handleRecheck = useCallback(async () => {
    if (!selectedEntry) return
    setActioning(true)
    try {
      const updated = await recheckContent(selectedEntry.id)
      setSelectedEntry(updated)
      upsertEntry(updated)
      showToast(`Rechecked: ${updated.fair_housing_verdict ?? 'unchecked'}`)
    } catch (exc) {
      showToast(exc instanceof Error ? exc.message : 'Recheck failed', 'error')
    } finally {
      setActioning(false)
    }
  }, [selectedEntry, setSelectedEntry, upsertEntry, showToast])

  return (
    <div className="flex h-full w-full">
      {/* Main table */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="px-6 py-4 border-b" style={{ borderColor: 'var(--border-color)' }}>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                Content Calendar
              </h1>
              <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                {total} entries
                {filter.listing_id && (
                  <>
                    {' '}
                    · filtered by listing{' '}
                    <button
                      type="button"
                      onClick={() => setFilter({ listing_id: null, offset: 0 })}
                      className="underline"
                      style={{ color: 'var(--accent-blue)' }}
                    >
                      clear
                    </button>
                  </>
                )}
              </p>
            </div>
            <div className="flex gap-2 items-center">
              <select
                value={filter.platform ?? ''}
                onChange={(e) =>
                  setFilter({
                    platform: e.target.value ? (e.target.value as ContentPlatform) : null,
                    offset: 0,
                  })
                }
                className="px-3 py-2 rounded-md text-sm"
                style={{
                  background: 'var(--bg-elevated)',
                  border: '1px solid var(--border-color)',
                  color: 'var(--text-primary)',
                }}
              >
                <option value="">All platforms</option>
                {PLATFORMS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className="btn-secondary px-4 py-2"
                onClick={() => loadEntries()}
                disabled={isLoading}
              >
                {isLoading ? 'Refreshing…' : 'Refresh'}
              </button>
            </div>
          </div>

          <div className="flex gap-2 mt-4 flex-wrap">
            {STATUSES.map((s) => {
              const isActive = (filter.status ?? 'all') === s.value
              return (
                <button
                  key={s.value}
                  type="button"
                  onClick={() =>
                    setFilter({
                      status: s.value === 'all' ? null : (s.value as ContentStatus),
                      offset: 0,
                    })
                  }
                  className="px-3 py-1.5 rounded-md text-sm"
                  style={{
                    background: isActive ? 'var(--bg-elevated)' : 'transparent',
                    border: `1px solid ${isActive ? 'var(--accent-blue)' : 'var(--border-color)'}`,
                    color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  }}
                >
                  {s.label}
                </button>
              )
            })}
          </div>
        </header>

        {error && (
          <div
            className="px-6 py-3 text-sm"
            style={{ background: 'var(--bg-error, #fef2f2)', color: 'var(--text-error, #991b1b)' }}
          >
            {error}
          </div>
        )}

        <div className="flex-1 overflow-auto">
          <table className="w-full text-sm">
            <thead
              className="sticky top-0"
              style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}
            >
              <tr>
                <th className="text-left px-6 py-3 font-medium">Platform</th>
                <th className="text-left px-6 py-3 font-medium">Title / Body</th>
                <th className="text-left px-6 py-3 font-medium">Compliance</th>
                <th className="text-left px-6 py-3 font-medium">Status</th>
                <th className="text-left px-6 py-3 font-medium">Scheduled</th>
                <th className="text-left px-6 py-3 font-medium">Listing</th>
              </tr>
            </thead>
            <tbody>
              {!isLoading && entries.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-6 py-10 text-center"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    No content yet. Generate content from a listing to populate the calendar.
                  </td>
                </tr>
              )}
              {entries.map((e) => {
                const v = verdictColor(e.fair_housing_verdict)
                return (
                  <tr
                    key={e.id}
                    onClick={() => handleRowClick(e)}
                    className="cursor-pointer hover:bg-[var(--bg-hover,rgba(255,255,255,0.03))]"
                    style={{ borderBottom: '1px solid var(--border-color)' }}
                  >
                    <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                      <div className="text-xs uppercase font-semibold">{e.platform}</div>
                      <div className="text-[10px]" style={{ color: 'var(--text-tertiary)' }}>
                        {e.content_type}
                      </div>
                    </td>
                    <td className="px-6 py-3" style={{ color: 'var(--text-primary)' }}>
                      <div className="font-medium">{e.title ?? shortBody(e.content)}</div>
                      {e.title && (
                        <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                          {shortBody(e.content)}
                        </div>
                      )}
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className="px-2 py-0.5 rounded text-xs font-semibold uppercase"
                        style={{ background: v.bg, color: v.fg }}
                      >
                        {v.label}
                      </span>
                    </td>
                    <td className="px-6 py-3">
                      <span
                        className="px-2 py-0.5 rounded text-xs font-semibold uppercase"
                        style={{
                          background: `${statusColor(e.status)}20`,
                          color: statusColor(e.status),
                        }}
                      >
                        {e.status}
                      </span>
                    </td>
                    <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                      {formatDateTime(e.scheduled_date)}
                    </td>
                    <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                      {e.source_listing ?? (e.listing_id ? '(linked)' : '—')}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail drawer */}
      {drawerOpen && (
        <aside
          className="w-[32rem] flex flex-col border-l overflow-hidden"
          style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
        >
          <header
            className="px-5 py-4 flex items-center justify-between border-b"
            style={{ borderColor: 'var(--border-color)' }}
          >
            <h2 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
              Content Detail
            </h2>
            <button
              type="button"
              className="text-sm"
              style={{ color: 'var(--text-secondary)' }}
              onClick={() => {
                setDrawerOpen(false)
                setSelectedEntry(null)
              }}
            >
              ✕
            </button>
          </header>

          <div className="flex-1 overflow-auto p-5 space-y-4 text-sm">
            {isLoadingDetail && <div style={{ color: 'var(--text-secondary)' }}>Loading…</div>}
            {!isLoadingDetail && selectedEntry && (
              <>
                {/* BLOCKED banner */}
                {selectedEntry.fair_housing_verdict === 'block' && (
                  <div
                    className="p-3 rounded text-sm font-medium"
                    style={{
                      background: 'rgba(239, 68, 68, 0.15)',
                      border: '1px solid var(--accent-red, #ef4444)',
                      color: 'var(--accent-red, #ef4444)',
                    }}
                  >
                    BLOCKED — Fair Housing violation detected. Edit the content and click
                    Recheck to update the verdict.
                  </div>
                )}

                <section>
                  <div
                    className="text-xs uppercase mb-1"
                    style={{ color: 'var(--text-tertiary)' }}
                  >
                    Platform · Type
                  </div>
                  <div className="font-medium" style={{ color: 'var(--text-primary)' }}>
                    {selectedEntry.platform} · {selectedEntry.content_type}
                  </div>
                </section>

                <section>
                  <div
                    className="text-xs uppercase mb-1"
                    style={{ color: 'var(--text-tertiary)' }}
                  >
                    Title
                  </div>
                  <input
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    className="w-full px-3 py-2 rounded text-sm"
                    style={{
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-primary)',
                    }}
                  />
                </section>

                <section>
                  <div
                    className="text-xs uppercase mb-1"
                    style={{ color: 'var(--text-tertiary)' }}
                  >
                    Body
                  </div>
                  <textarea
                    value={editBody}
                    onChange={(e) => setEditBody(e.target.value)}
                    rows={10}
                    className="w-full px-3 py-2 rounded text-sm font-mono"
                    style={{
                      background: 'var(--bg-elevated)',
                      border: '1px solid var(--border-color)',
                      color: 'var(--text-primary)',
                      resize: 'vertical',
                    }}
                  />
                </section>

                {/* Fair Housing audit */}
                <section
                  className="p-3 rounded border"
                  style={{
                    background: 'var(--bg-elevated)',
                    borderColor: 'var(--border-color)',
                  }}
                >
                  <div
                    className="text-xs uppercase mb-2"
                    style={{ color: 'var(--text-tertiary)' }}
                  >
                    Fair Housing Audit
                  </div>
                  <div className="flex items-center gap-2 mb-2">
                    {(() => {
                      const v = verdictColor(selectedEntry.fair_housing_verdict)
                      return (
                        <span
                          className="px-2 py-0.5 rounded text-xs font-semibold uppercase"
                          style={{ background: v.bg, color: v.fg }}
                        >
                          {v.label}
                        </span>
                      )
                    })()}
                    <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                      Checked {formatDateTime(selectedEntry.compliance_checked_at)}
                    </span>
                  </div>
                  {selectedEntry.fair_housing_notes && (
                    <div
                      className="text-xs p-2 rounded"
                      style={{
                        background: 'var(--bg-secondary)',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      {selectedEntry.fair_housing_notes}
                    </div>
                  )}
                </section>

                {/* Action buttons */}
                <section className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    className="btn-primary px-3 py-1.5 text-sm"
                    onClick={handleApprove}
                    disabled={actioning || selectedEntry.fair_housing_verdict === 'block'}
                    title={
                      selectedEntry.fair_housing_verdict === 'block'
                        ? 'Cannot approve content that is blocked by Fair Housing compliance.'
                        : undefined
                    }
                  >
                    Approve
                  </button>
                  <button
                    type="button"
                    className="btn-secondary px-3 py-1.5 text-sm"
                    onClick={handleReject}
                    disabled={actioning}
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    className="btn-secondary px-3 py-1.5 text-sm"
                    onClick={handleRecheck}
                    disabled={actioning}
                  >
                    Recheck
                  </button>
                  <button
                    type="button"
                    className="btn-secondary px-3 py-1.5 text-sm"
                    onClick={handleSaveEdits}
                    disabled={savingEdits}
                  >
                    {savingEdits ? 'Saving…' : 'Save Edits'}
                  </button>
                </section>

                <section className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  Status: {selectedEntry.status} · Scheduled{' '}
                  {formatDateTime(selectedEntry.scheduled_date)} · Created{' '}
                  {formatDateTime(selectedEntry.created_at)}
                </section>
              </>
            )}
          </div>
        </aside>
      )}

      {/* Toast */}
      {toast && (
        <div
          className="fixed bottom-6 right-6 px-4 py-2 rounded shadow-lg text-sm z-50"
          style={{
            background:
              toast.kind === 'error'
                ? 'var(--accent-red, #ef4444)'
                : 'var(--accent-green, #10b981)',
            color: '#fff',
          }}
        >
          {toast.msg}
        </div>
      )}
    </div>
  )
}
