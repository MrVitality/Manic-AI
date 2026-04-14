'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useLeadStore } from '@/lib/stores/leadStore'
import { fetchLeads, fetchLeadDetail } from '@/lib/api'
import type { LeadSummary, LeadTier } from '@/types'

const TIERS: Array<{ value: LeadTier | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'hot', label: 'Hot' },
  { value: 'warm', label: 'Warm' },
  { value: 'cold', label: 'Cold' },
  { value: 'converted', label: 'Converted' },
  { value: 'disqualified', label: 'Disqualified' },
]

function tierColor(tier: string | null): string {
  switch (tier) {
    case 'hot': return 'var(--accent-red, #ef4444)'
    case 'warm': return 'var(--accent-amber, #f59e0b)'
    case 'cold': return 'var(--accent-blue, #3b82f6)'
    case 'converted': return 'var(--accent-green, #10b981)'
    case 'disqualified': return 'var(--text-tertiary, #6b7280)'
    default: return 'var(--text-tertiary, #6b7280)'
  }
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  const now = new Date()
  const diffHours = (now.getTime() - d.getTime()) / (1000 * 60 * 60)
  if (diffHours < 1) return 'Just now'
  if (diffHours < 24) return `${Math.round(diffHours)}h ago`
  if (diffHours < 24 * 7) return `${Math.round(diffHours / 24)}d ago`
  return d.toLocaleDateString()
}

export default function LeadsManager() {
  const {
    leads,
    total,
    isLoading,
    error,
    filter,
    setFilter,
    setLeads,
    setIsLoading,
    setError,
    selectedLead,
    setSelectedLead,
    isLoadingDetail,
    setIsLoadingDetail,
  } = useLeadStore()

  const [drawerOpen, setDrawerOpen] = useState(false)

  const loadLeads = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const { leads: data, total: count } = await fetchLeads(filter)
      setLeads(data, count)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Failed to load leads')
    } finally {
      setIsLoading(false)
    }
  }, [filter, setLeads, setIsLoading, setError])

  useEffect(() => {
    loadLeads()
  }, [loadLeads])

  const handleRowClick = useCallback(
    async (lead: LeadSummary) => {
      setDrawerOpen(true)
      setIsLoadingDetail(true)
      try {
        const detail = await fetchLeadDetail(lead.id)
        setSelectedLead(detail)
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : 'Failed to load lead detail')
      } finally {
        setIsLoadingDetail(false)
      }
    },
    [setSelectedLead, setIsLoadingDetail, setError],
  )

  const counts = useMemo(() => {
    const byTier: Record<string, number> = { hot: 0, warm: 0, cold: 0 }
    for (const l of leads) {
      if (l.tier && byTier[l.tier] !== undefined) byTier[l.tier]++
    }
    return byTier
  }, [leads])

  return (
    <div className="flex h-full w-full">
      {/* Main table */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="px-6 py-4 border-b" style={{ borderColor: 'var(--border-color)' }}>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                Leads
              </h1>
              <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                {total} total · {counts.hot ?? 0} hot · {counts.warm ?? 0} warm · {counts.cold ?? 0} cold
              </p>
            </div>
            <button
              type="button"
              className="btn-primary px-4 py-2"
              onClick={() => loadLeads()}
              disabled={isLoading}
            >
              {isLoading ? 'Refreshing…' : 'Refresh'}
            </button>
          </div>

          <div className="flex gap-2 mt-4">
            {TIERS.map((t) => {
              const isActive = (filter.tier ?? 'all') === t.value
              return (
                <button
                  key={t.value}
                  type="button"
                  onClick={() =>
                    setFilter({ tier: t.value === 'all' ? null : (t.value as LeadTier), offset: 0 })
                  }
                  className="px-3 py-1.5 rounded-md text-sm"
                  style={{
                    background: isActive ? 'var(--bg-elevated)' : 'transparent',
                    border: `1px solid ${isActive ? 'var(--accent-blue)' : 'var(--border-color)'}`,
                    color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                  }}
                >
                  {t.label}
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
                <th className="text-left px-6 py-3 font-medium">Name</th>
                <th className="text-left px-6 py-3 font-medium">Tier</th>
                <th className="text-left px-6 py-3 font-medium">Score</th>
                <th className="text-left px-6 py-3 font-medium">Source</th>
                <th className="text-left px-6 py-3 font-medium">Interest</th>
                <th className="text-left px-6 py-3 font-medium">Timeline</th>
                <th className="text-left px-6 py-3 font-medium">Last contacted</th>
                <th className="text-left px-6 py-3 font-medium">Created</th>
              </tr>
            </thead>
            <tbody>
              {!isLoading && leads.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-6 py-10 text-center"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    No leads yet. Drop a test payload via{' '}
                    <code>POST /v1/re/leads/intake</code> or wire the Seller Blueprint webhook.
                  </td>
                </tr>
              )}
              {leads.map((lead) => (
                <tr
                  key={lead.id}
                  onClick={() => handleRowClick(lead)}
                  className="cursor-pointer hover:bg-[var(--bg-hover,rgba(255,255,255,0.03))]"
                  style={{ borderBottom: '1px solid var(--border-color)' }}
                >
                  <td className="px-6 py-3" style={{ color: 'var(--text-primary)' }}>
                    <div className="font-medium">{lead.name}</div>
                    {lead.email && (
                      <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                        {lead.email}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className="px-2 py-0.5 rounded text-xs font-semibold uppercase"
                      style={{
                        background: `${tierColor(lead.tier)}20`,
                        color: tierColor(lead.tier),
                      }}
                    >
                      {lead.tier ?? '—'}
                    </span>
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-primary)' }}>
                    {lead.score ?? '—'}
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {lead.source ?? '—'}
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {lead.property_interest ?? '—'}
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {lead.timeline ?? '—'}
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {formatDate(lead.last_contacted)}
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {formatDate(lead.created_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail drawer */}
      {drawerOpen && (
        <aside
          className="w-96 flex flex-col border-l overflow-hidden"
          style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
        >
          <header
            className="px-5 py-4 flex items-center justify-between border-b"
            style={{ borderColor: 'var(--border-color)' }}
          >
            <h2 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
              Lead Detail
            </h2>
            <button
              type="button"
              className="text-sm"
              style={{ color: 'var(--text-secondary)' }}
              onClick={() => {
                setDrawerOpen(false)
                setSelectedLead(null)
              }}
            >
              ✕
            </button>
          </header>
          <div className="flex-1 overflow-auto p-5 space-y-4 text-sm">
            {isLoadingDetail && <div style={{ color: 'var(--text-secondary)' }}>Loading…</div>}
            {!isLoadingDetail && selectedLead && (
              <>
                <section>
                  <div className="font-semibold text-lg" style={{ color: 'var(--text-primary)' }}>
                    {selectedLead.name}
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>{selectedLead.email}</div>
                  <div style={{ color: 'var(--text-secondary)' }}>{selectedLead.phone}</div>
                </section>

                <section>
                  <div className="flex gap-2 items-center">
                    <span
                      className="px-2 py-0.5 rounded text-xs font-semibold uppercase"
                      style={{
                        background: `${tierColor(selectedLead.tier)}20`,
                        color: tierColor(selectedLead.tier),
                      }}
                    >
                      {selectedLead.tier ?? '—'}
                    </span>
                    <span style={{ color: 'var(--text-primary)' }}>
                      Score {selectedLead.score ?? '—'}
                    </span>
                  </div>
                  {selectedLead.score_reasoning && (
                    <p className="mt-2 italic" style={{ color: 'var(--text-secondary)' }}>
                      {selectedLead.score_reasoning}
                    </p>
                  )}
                </section>

                <section>
                  <div className="uppercase text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>
                    Interest
                  </div>
                  <div style={{ color: 'var(--text-primary)' }}>
                    {selectedLead.property_interest ?? '—'}
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    {selectedLead.buyer_seller} · {selectedLead.timeline}
                  </div>
                </section>

                {selectedLead.message && (
                  <section>
                    <div className="uppercase text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>
                      Message
                    </div>
                    <div
                      className="p-3 rounded"
                      style={{
                        background: 'var(--bg-elevated)',
                        color: 'var(--text-primary)',
                      }}
                    >
                      {selectedLead.message}
                    </div>
                  </section>
                )}

                {selectedLead.tags.length > 0 && (
                  <section>
                    <div className="uppercase text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>
                      Tags
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {selectedLead.tags.map((t) => (
                        <span
                          key={t}
                          className="px-2 py-0.5 rounded text-xs"
                          style={{
                            background: 'var(--bg-elevated)',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  </section>
                )}

                <section>
                  <div className="uppercase text-xs mb-2" style={{ color: 'var(--text-tertiary)' }}>
                    Activity ({selectedLead.interactions.length})
                  </div>
                  <ul className="space-y-2">
                    {selectedLead.interactions.map((i) => (
                      <li
                        key={i.id}
                        className="p-2 rounded"
                        style={{
                          background: 'var(--bg-elevated)',
                          color: 'var(--text-primary)',
                        }}
                      >
                        <div className="flex items-center justify-between text-xs" style={{ color: 'var(--text-secondary)' }}>
                          <span>{i.type}</span>
                          <span>{formatDate(i.created_at)}</span>
                        </div>
                        {i.subject && <div className="font-medium mt-1">{i.subject}</div>}
                        {i.body && <div className="mt-1 text-xs">{i.body}</div>}
                      </li>
                    ))}
                    {selectedLead.interactions.length === 0 && (
                      <li style={{ color: 'var(--text-secondary)' }}>No activity yet.</li>
                    )}
                  </ul>
                </section>
              </>
            )}
          </div>
        </aside>
      )}
    </div>
  )
}
