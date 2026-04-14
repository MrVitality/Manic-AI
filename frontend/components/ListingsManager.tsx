'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useListingStore } from '@/lib/stores/listingStore'
import {
  fetchListings,
  fetchListingDetail,
  createListing,
  generateContentForListing,
} from '@/lib/api'
import type {
  ListingSummary,
  ListingStatus,
  ListingCreatePayload,
  GenerateContentResult,
} from '@/types'

const STATUSES: Array<{ value: ListingStatus | 'all'; label: string }> = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'pending', label: 'Pending' },
  { value: 'sold', label: 'Sold' },
  { value: 'draft', label: 'Draft' },
]

function statusColor(status: string | null): string {
  switch (status) {
    case 'active':
      return 'var(--accent-green, #10b981)'
    case 'pending':
      return 'var(--accent-amber, #f59e0b)'
    case 'sold':
      return 'var(--accent-blue, #3b82f6)'
    case 'expired':
    case 'withdrawn':
      return 'var(--accent-red, #ef4444)'
    case 'draft':
      return 'var(--text-tertiary, #6b7280)'
    default:
      return 'var(--text-tertiary, #6b7280)'
  }
}

function formatPrice(n: number | null): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`
  if (n >= 1_000) return `$${Math.round(n / 1_000)}k`
  return `$${n}`
}

function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString()
}

export default function ListingsManager() {
  const router = useRouter()
  const {
    listings,
    total,
    isLoading,
    error,
    filter,
    setFilter,
    setListings,
    setIsLoading,
    setError,
    selectedListing,
    setSelectedListing,
    isLoadingDetail,
    setIsLoadingDetail,
    addListing,
  } = useListingStore()

  const [drawerOpen, setDrawerOpen] = useState(false)
  const [createOpen, setCreateOpen] = useState(false)

  // Generate-content workflow state
  const [isGenerating, setIsGenerating] = useState(false)
  const [genResult, setGenResult] = useState<GenerateContentResult | null>(null)
  const [genError, setGenError] = useState<string | null>(null)

  const loadListings = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const { listings: data, total: count } = await fetchListings(filter)
      setListings(data, count)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Failed to load listings')
    } finally {
      setIsLoading(false)
    }
  }, [filter, setListings, setIsLoading, setError])

  useEffect(() => {
    loadListings()
  }, [loadListings])

  const handleRowClick = useCallback(
    async (listing: ListingSummary) => {
      setDrawerOpen(true)
      setIsLoadingDetail(true)
      setGenResult(null)
      setGenError(null)
      try {
        const detail = await fetchListingDetail(listing.id)
        setSelectedListing(detail)
      } catch (exc) {
        setError(exc instanceof Error ? exc.message : 'Failed to load listing detail')
      } finally {
        setIsLoadingDetail(false)
      }
    },
    [setSelectedListing, setIsLoadingDetail, setError],
  )

  const handleGenerate = useCallback(async () => {
    if (!selectedListing) return
    setIsGenerating(true)
    setGenError(null)
    setGenResult(null)
    try {
      const result = await generateContentForListing(selectedListing.id)
      setGenResult(result)
      // Refresh detail to reflect content_generated:true
      const refreshed = await fetchListingDetail(selectedListing.id)
      setSelectedListing(refreshed)
      // Refresh table list
      loadListings()
    } catch (exc) {
      setGenError(exc instanceof Error ? exc.message : 'Content generation failed')
    } finally {
      setIsGenerating(false)
    }
  }, [selectedListing, setSelectedListing, loadListings])

  const counts = useMemo(() => {
    const byStatus: Record<string, number> = { active: 0, pending: 0, sold: 0, draft: 0 }
    for (const l of listings) {
      if (byStatus[l.status] !== undefined) byStatus[l.status]++
    }
    return byStatus
  }, [listings])

  return (
    <div className="flex h-full w-full">
      {/* Main table */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="px-6 py-4 border-b" style={{ borderColor: 'var(--border-color)' }}>
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold" style={{ color: 'var(--text-primary)' }}>
                Listings
              </h1>
              <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                {total} total · {counts.active ?? 0} active · {counts.pending ?? 0} pending ·{' '}
                {counts.sold ?? 0} sold
              </p>
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn-secondary px-4 py-2"
                onClick={() => loadListings()}
                disabled={isLoading}
              >
                {isLoading ? 'Refreshing…' : 'Refresh'}
              </button>
              <button
                type="button"
                className="btn-primary px-4 py-2"
                onClick={() => setCreateOpen(true)}
              >
                + New Listing
              </button>
            </div>
          </div>

          <div className="flex gap-2 mt-4">
            {STATUSES.map((t) => {
              const isActive = (filter.status ?? 'all') === t.value
              return (
                <button
                  key={t.value}
                  type="button"
                  onClick={() =>
                    setFilter({
                      status: t.value === 'all' ? null : (t.value as ListingStatus),
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
                <th className="text-left px-6 py-3 font-medium">Address</th>
                <th className="text-left px-6 py-3 font-medium">City</th>
                <th className="text-left px-6 py-3 font-medium">Price</th>
                <th className="text-left px-6 py-3 font-medium">Bd/Ba</th>
                <th className="text-left px-6 py-3 font-medium">DOM</th>
                <th className="text-left px-6 py-3 font-medium">Status</th>
                <th className="text-left px-6 py-3 font-medium">Content</th>
                <th className="text-left px-6 py-3 font-medium">Listed</th>
              </tr>
            </thead>
            <tbody>
              {!isLoading && listings.length === 0 && (
                <tr>
                  <td
                    colSpan={8}
                    className="px-6 py-10 text-center"
                    style={{ color: 'var(--text-secondary)' }}
                  >
                    No listings yet. Click <strong>+ New Listing</strong> to add one, or import
                    via <code>POST /v1/re/listings</code>.
                  </td>
                </tr>
              )}
              {listings.map((l) => (
                <tr
                  key={l.id}
                  onClick={() => handleRowClick(l)}
                  className="cursor-pointer hover:bg-[var(--bg-hover,rgba(255,255,255,0.03))]"
                  style={{ borderBottom: '1px solid var(--border-color)' }}
                >
                  <td className="px-6 py-3" style={{ color: 'var(--text-primary)' }}>
                    <div className="font-medium">{l.address}</div>
                    {l.mls_number && (
                      <div className="text-xs" style={{ color: 'var(--text-secondary)' }}>
                        MLS #{l.mls_number}
                      </div>
                    )}
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {l.city ?? '—'}
                    {l.state ? `, ${l.state}` : ''}
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-primary)' }}>
                    {formatPrice(l.list_price)}
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {l.beds ?? '—'}/{l.baths ?? '—'}
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {l.days_on_market ?? '—'}
                  </td>
                  <td className="px-6 py-3">
                    <span
                      className="px-2 py-0.5 rounded text-xs font-semibold uppercase"
                      style={{
                        background: `${statusColor(l.status)}20`,
                        color: statusColor(l.status),
                      }}
                    >
                      {l.status}
                    </span>
                  </td>
                  <td className="px-6 py-3">
                    {l.content_generated ? (
                      <span
                        className="px-2 py-0.5 rounded text-xs"
                        style={{
                          background: 'rgba(16, 185, 129, 0.15)',
                          color: 'var(--accent-green, #10b981)',
                        }}
                      >
                        Generated
                      </span>
                    ) : (
                      <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                        —
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-3" style={{ color: 'var(--text-secondary)' }}>
                    {formatDate(l.list_date)}
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
          className="w-[28rem] flex flex-col border-l overflow-hidden"
          style={{ borderColor: 'var(--border-color)', background: 'var(--bg-secondary)' }}
        >
          <header
            className="px-5 py-4 flex items-center justify-between border-b"
            style={{ borderColor: 'var(--border-color)' }}
          >
            <h2 className="font-semibold" style={{ color: 'var(--text-primary)' }}>
              Listing Detail
            </h2>
            <button
              type="button"
              className="text-sm"
              style={{ color: 'var(--text-secondary)' }}
              onClick={() => {
                setDrawerOpen(false)
                setSelectedListing(null)
                setGenResult(null)
                setGenError(null)
              }}
            >
              ✕
            </button>
          </header>
          <div className="flex-1 overflow-auto p-5 space-y-4 text-sm">
            {isLoadingDetail && <div style={{ color: 'var(--text-secondary)' }}>Loading…</div>}
            {!isLoadingDetail && selectedListing && (
              <>
                <section>
                  <div className="font-semibold text-lg" style={{ color: 'var(--text-primary)' }}>
                    {selectedListing.address}
                  </div>
                  <div style={{ color: 'var(--text-secondary)' }}>
                    {selectedListing.city}
                    {selectedListing.state ? `, ${selectedListing.state}` : ''}{' '}
                    {selectedListing.zip ?? ''}
                  </div>
                </section>

                <section className="grid grid-cols-2 gap-3">
                  <Stat label="Price" value={formatPrice(selectedListing.list_price)} />
                  <Stat label="Status" value={selectedListing.status} />
                  <Stat label="Beds" value={String(selectedListing.beds ?? '—')} />
                  <Stat label="Baths" value={String(selectedListing.baths ?? '—')} />
                  <Stat
                    label="Sqft"
                    value={selectedListing.sqft?.toLocaleString() ?? '—'}
                  />
                  <Stat label="DOM" value={String(selectedListing.days_on_market ?? '—')} />
                </section>

                {selectedListing.description && (
                  <section>
                    <SectionLabel>Description</SectionLabel>
                    <div
                      className="p-3 rounded"
                      style={{ background: 'var(--bg-elevated)', color: 'var(--text-primary)' }}
                    >
                      {selectedListing.description}
                    </div>
                  </section>
                )}

                {selectedListing.key_features.length > 0 && (
                  <section>
                    <SectionLabel>Key Features</SectionLabel>
                    <div className="flex flex-wrap gap-1">
                      {selectedListing.key_features.map((f) => (
                        <span
                          key={f}
                          className="px-2 py-0.5 rounded text-xs"
                          style={{
                            background: 'var(--bg-elevated)',
                            color: 'var(--text-secondary)',
                          }}
                        >
                          {f}
                        </span>
                      ))}
                    </div>
                  </section>
                )}

                {selectedListing.agent_notes && (
                  <section>
                    <SectionLabel>Agent Notes</SectionLabel>
                    <div
                      className="p-3 rounded italic"
                      style={{
                        background: 'var(--bg-elevated)',
                        color: 'var(--text-secondary)',
                      }}
                    >
                      {selectedListing.agent_notes}
                    </div>
                  </section>
                )}

                {/* Generate Content action */}
                <section
                  className="p-4 rounded border"
                  style={{
                    background: 'var(--bg-elevated)',
                    borderColor: 'var(--border-color)',
                  }}
                >
                  <SectionLabel>Content Generation</SectionLabel>
                  <p className="text-xs mb-3" style={{ color: 'var(--text-secondary)' }}>
                    Generate a multi-platform content calendar for this listing. This may take 60
                    seconds or more.
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="btn-primary px-3 py-1.5 text-sm"
                      disabled={isGenerating}
                      onClick={handleGenerate}
                    >
                      {isGenerating
                        ? 'Generating… (this may take 60s+)'
                        : selectedListing.content_generated
                          ? 'Regenerate Content'
                          : 'Generate Content'}
                    </button>
                    <button
                      type="button"
                      className="btn-secondary px-3 py-1.5 text-sm"
                      onClick={() => router.push(`/content?listing_id=${selectedListing.id}`)}
                    >
                      View Content →
                    </button>
                  </div>
                  {genError && (
                    <div
                      className="mt-3 p-2 rounded text-xs"
                      style={{
                        background: 'rgba(239, 68, 68, 0.15)',
                        color: 'var(--accent-red, #ef4444)',
                      }}
                    >
                      {genError}
                    </div>
                  )}
                  {genResult && (
                    <div
                      className="mt-3 p-2 rounded text-xs"
                      style={{
                        background: 'rgba(16, 185, 129, 0.10)',
                        color: 'var(--text-primary)',
                      }}
                    >
                      Generated <strong>{genResult.total}</strong> entries —{' '}
                      <span style={{ color: 'var(--accent-green, #10b981)' }}>
                        {genResult.draft} draft
                      </span>
                      ,{' '}
                      <span style={{ color: 'var(--accent-amber, #f59e0b)' }}>
                        {genResult.flagged} flagged
                      </span>
                      ,{' '}
                      <span style={{ color: 'var(--accent-red, #ef4444)' }}>
                        {genResult.blocked} blocked
                      </span>
                      .
                    </div>
                  )}
                </section>

                <section className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  Source: {selectedListing.source} · Created{' '}
                  {formatDate(selectedListing.created_at)}
                </section>
              </>
            )}
          </div>
        </aside>
      )}

      {/* Create form modal */}
      {createOpen && (
        <CreateListingModal
          onClose={() => setCreateOpen(false)}
          onCreated={(listing) => {
            addListing(listing)
            setCreateOpen(false)
            loadListings()
          }}
        />
      )}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div
      className="p-2 rounded"
      style={{ background: 'var(--bg-elevated)', color: 'var(--text-primary)' }}
    >
      <div className="text-[10px] uppercase" style={{ color: 'var(--text-tertiary)' }}>
        {label}
      </div>
      <div className="font-medium">{value}</div>
    </div>
  )
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div className="uppercase text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>
      {children}
    </div>
  )
}

function CreateListingModal({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: (listing: ListingSummary) => void
}) {
  const [form, setForm] = useState<ListingCreatePayload>({
    address: '',
    city: '',
    state: '',
    zip: '',
    status: 'draft',
    source: 'manual',
  })
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.address.trim()) {
      setError('Address is required')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      const created = await createListing(form)
      onCreated(created)
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : 'Failed to create listing')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
    >
      <form
        onSubmit={handleSubmit}
        className="rounded-xl p-6 w-full max-w-md mx-4 space-y-3"
        style={{
          background: 'var(--bg-elevated)',
          border: '1px solid var(--border-color)',
          color: 'var(--text-primary)',
        }}
      >
        <h3 className="text-lg font-semibold">New Listing</h3>

        <Field label="Address *">
          <input
            className="input-base"
            value={form.address}
            onChange={(e) => setForm({ ...form, address: e.target.value })}
            required
          />
        </Field>

        <div className="grid grid-cols-3 gap-2">
          <Field label="City">
            <input
              className="input-base"
              value={form.city ?? ''}
              onChange={(e) => setForm({ ...form, city: e.target.value })}
            />
          </Field>
          <Field label="State">
            <input
              className="input-base"
              value={form.state ?? ''}
              onChange={(e) => setForm({ ...form, state: e.target.value })}
            />
          </Field>
          <Field label="Zip">
            <input
              className="input-base"
              value={form.zip ?? ''}
              onChange={(e) => setForm({ ...form, zip: e.target.value })}
            />
          </Field>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <Field label="Beds">
            <input
              type="number"
              className="input-base"
              value={form.beds ?? ''}
              onChange={(e) =>
                setForm({ ...form, beds: e.target.value ? Number(e.target.value) : undefined })
              }
            />
          </Field>
          <Field label="Baths">
            <input
              type="number"
              className="input-base"
              value={form.baths ?? ''}
              onChange={(e) =>
                setForm({ ...form, baths: e.target.value ? Number(e.target.value) : undefined })
              }
            />
          </Field>
          <Field label="Price">
            <input
              type="number"
              className="input-base"
              value={form.list_price ?? ''}
              onChange={(e) =>
                setForm({
                  ...form,
                  list_price: e.target.value ? Number(e.target.value) : undefined,
                })
              }
            />
          </Field>
        </div>

        <Field label="Status">
          <select
            className="input-base"
            value={form.status}
            onChange={(e) => setForm({ ...form, status: e.target.value as ListingStatus })}
          >
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="pending">Pending</option>
            <option value="sold">Sold</option>
          </select>
        </Field>

        {error && (
          <div
            className="text-xs p-2 rounded"
            style={{
              background: 'rgba(239, 68, 68, 0.15)',
              color: 'var(--accent-red, #ef4444)',
            }}
          >
            {error}
          </div>
        )}

        <div className="flex gap-2 justify-end pt-2">
          <button type="button" className="btn-secondary px-4 py-2" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn-primary px-4 py-2" disabled={submitting}>
            {submitting ? 'Creating…' : 'Create'}
          </button>
        </div>
      </form>

      {/* Inline base input style — uses CSS vars */}
      <style jsx>{`
        :global(.input-base) {
          width: 100%;
          padding: 0.5rem 0.75rem;
          background: var(--bg-secondary);
          border: 1px solid var(--border-color);
          border-radius: 0.375rem;
          color: var(--text-primary);
          font-size: 0.875rem;
        }
        :global(.input-base:focus) {
          outline: none;
          border-color: var(--accent-blue);
        }
      `}</style>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <div
        className="text-xs uppercase mb-1"
        style={{ color: 'var(--text-tertiary)' }}
      >
        {label}
      </div>
      {children}
    </label>
  )
}
