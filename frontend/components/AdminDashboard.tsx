'use client'

import { useState, useEffect, useCallback } from 'react'
import { PlusIcon, CloseIcon, TrashIcon } from '@/components/ui/Icons'
import { getApiUrl } from '@/lib/api'

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface AdminUser {
  id: string
  email: string
  username: string | null
  is_active: boolean
  is_admin: boolean
  api_key_masked: string
  rate_limit_override: number | null
  created_at: string
  updated_at: string
}

interface SystemStats {
  total_users: number
  active_users: number
  admin_users: number
  total_chats: number
  total_searches: number
  total_feedback: number
}

interface PaginatedUsers {
  users: AdminUser[]
  total: number
  limit: number
  offset: number
}

interface CreateUserForm {
  email: string
  password: string
  username: string
  is_admin: boolean
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

function getApiKey(): string {
  if (typeof window === 'undefined') return ''
  // Try sessionStorage first (admin-specific key), then fall back to main app key
  const adminKey = sessionStorage.getItem('manic-admin-api-key')
  if (adminKey) return adminKey
  try {
    const stored = localStorage.getItem('manic-ai-ui')
    if (stored) {
      const parsed = JSON.parse(stored)
      return parsed?.state?.settings?.apiKey ?? ''
    }
  } catch { /* ignore */ }
  return ''
}

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${getApiUrl()}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': getApiKey(),
      ...options.headers,
    },
  })
  const body = await res.json()
  if (!res.ok || !body.success) {
    throw new Error(body?.error?.message ?? `HTTP ${res.status}`)
  }
  return body.data as T
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({ label, value, accent }: { label: string; value: number; accent?: string }) {
  return (
    <div
      className="rounded-xl p-4 flex flex-col gap-1"
      style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-color)' }}
    >
      <span className="text-xs font-medium uppercase tracking-wider" style={{ color: 'var(--text-muted)' }}>
        {label}
      </span>
      <span
        className="text-2xl font-bold tabular-nums"
        style={{ color: accent ?? 'var(--text-primary)' }}
      >
        {value.toLocaleString()}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Create-user modal
// ---------------------------------------------------------------------------

const EMPTY_FORM: CreateUserForm = { email: '', password: '', username: '', is_admin: false }

function CreateUserModal({
  onClose,
  onCreated,
}: {
  onClose: () => void
  onCreated: () => void
}) {
  const [form, setForm] = useState<CreateUserForm>(EMPTY_FORM)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      await apiFetch('/v1/admin/users', {
        method: 'POST',
        body: JSON.stringify({
          email: form.email,
          password: form.password,
          username: form.username || undefined,
          is_admin: form.is_admin,
        }),
      })
      onCreated()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user')
    } finally {
      setLoading(false)
    }
  }

  const field = (label: string, key: keyof CreateUserForm, type = 'text') => (
    <div>
      <label className="block text-xs font-medium mb-1" style={{ color: 'var(--text-muted)' }}>
        {label}
      </label>
      <input
        type={type}
        value={form[key] as string}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
        className="w-full px-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/50"
        style={{
          background: 'var(--bg-tertiary)',
          border: '1px solid var(--border-color)',
          color: 'var(--text-primary)',
        }}
      />
    </div>
  )

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-user-title"
    >
      <div
        className="rounded-xl p-6 w-full max-w-md mx-4"
        style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border-color)' }}
      >
        <div className="flex items-center justify-between mb-5">
          <h2 id="create-user-title" className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>
            Create User
          </h2>
          <button onClick={onClose} aria-label="Close" className="p-1.5 rounded-md hover:bg-white/5 text-zinc-400 hover:text-zinc-200">
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {field('Email *', 'email', 'email')}
          {field('Password * (min 8 chars)', 'password', 'password')}
          {field('Username (optional)', 'username')}

          <div className="flex items-center gap-2">
            <input
              id="is_admin"
              type="checkbox"
              checked={form.is_admin}
              onChange={(e) => setForm((f) => ({ ...f, is_admin: e.target.checked }))}
              className="rounded"
            />
            <label htmlFor="is_admin" className="text-sm" style={{ color: 'var(--text-secondary)' }}>
              Grant admin privileges
            </label>
          </div>

          {error && (
            <p className="text-sm text-red-400" role="alert">{error}</p>
          )}

          <div className="flex gap-3 pt-2">
            <button type="button" onClick={onClose} className="flex-1 btn-secondary">
              Cancel
            </button>
            <button type="submit" disabled={loading} className="flex-1 btn-primary">
              {loading ? 'Creating…' : 'Create User'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// User row
// ---------------------------------------------------------------------------

function UserRow({
  user,
  onToggleActive,
  onToggleAdmin,
  onDeactivate,
}: {
  user: AdminUser
  onToggleActive: (id: string, value: boolean) => Promise<void>
  onToggleAdmin: (id: string, value: boolean) => Promise<void>
  onDeactivate: (id: string) => Promise<void>
}) {
  const [busy, setBusy] = useState(false)

  const act = async (fn: () => Promise<void>) => {
    setBusy(true)
    try { await fn() } finally { setBusy(false) }
  }

  const createdDate = new Date(user.created_at).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })

  return (
    <tr
      className="border-b transition-colors hover:bg-white/[0.02]"
      style={{ borderColor: 'var(--border-color)', opacity: user.is_active ? 1 : 0.5 }}
    >
      {/* Email / username */}
      <td className="px-4 py-3">
        <p className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>{user.email}</p>
        {user.username && (
          <p className="text-xs" style={{ color: 'var(--text-muted)' }}>@{user.username}</p>
        )}
      </td>

      {/* Status badge */}
      <td className="px-4 py-3">
        <span
          className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
          style={{
            background: user.is_active ? 'rgba(16,185,129,0.12)' : 'rgba(239,68,68,0.12)',
            color: user.is_active ? '#10b981' : '#ef4444',
          }}
        >
          {user.is_active ? 'Active' : 'Inactive'}
        </span>
      </td>

      {/* Admin badge */}
      <td className="px-4 py-3">
        {user.is_admin && (
          <span
            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
            style={{ background: 'rgba(129,140,248,0.12)', color: 'var(--accent-indigo)' }}
          >
            Admin
          </span>
        )}
      </td>

      {/* API key (masked) */}
      <td className="px-4 py-3">
        <code className="text-xs font-mono" style={{ color: 'var(--text-muted)' }}>
          {user.api_key_masked}
        </code>
      </td>

      {/* Created */}
      <td className="px-4 py-3 text-xs" style={{ color: 'var(--text-muted)' }}>
        {createdDate}
      </td>

      {/* Actions */}
      <td className="px-4 py-3">
        <div className="flex items-center gap-2">
          <button
            disabled={busy}
            onClick={() => act(() => onToggleActive(user.id, !user.is_active))}
            className="text-xs px-2 py-1 rounded-md transition-colors"
            style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-color)',
              color: 'var(--text-secondary)',
            }}
            title={user.is_active ? 'Deactivate' : 'Activate'}
          >
            {user.is_active ? 'Disable' : 'Enable'}
          </button>

          <button
            disabled={busy}
            onClick={() => act(() => onToggleAdmin(user.id, !user.is_admin))}
            className="text-xs px-2 py-1 rounded-md transition-colors"
            style={{
              background: 'var(--bg-tertiary)',
              border: '1px solid var(--border-color)',
              color: user.is_admin ? 'var(--accent-indigo)' : 'var(--text-secondary)',
            }}
            title={user.is_admin ? 'Revoke admin' : 'Grant admin'}
          >
            {user.is_admin ? 'Revoke' : 'Make Admin'}
          </button>

          <button
            disabled={busy || !user.is_active}
            onClick={() => act(() => onDeactivate(user.id))}
            className="p-1.5 rounded-md text-red-500 hover:bg-red-500/10 transition-colors disabled:opacity-30"
            title="Soft-delete (deactivate)"
            aria-label={`Deactivate ${user.email}`}
          >
            <TrashIcon className="w-3.5 h-3.5" />
          </button>
        </div>
      </td>
    </tr>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AdminDashboard() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<SystemStats | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [page, setPage] = useState(0)
  const PAGE_SIZE = 50

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const usersData = await apiFetch<PaginatedUsers>(`/v1/admin/users?limit=${PAGE_SIZE}&offset=${page * PAGE_SIZE}`)
      setUsers(usersData.users)
      setTotal(usersData.total)
      // Stats are optional — don't block the page if they fail
      try {
        const statsData = await apiFetch<SystemStats>('/v1/admin/stats')
        setStats(statsData)
      } catch {
        // Stats endpoint may not be fully set up yet — ignore
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load admin data')
    } finally {
      setLoading(false)
    }
  }, [page])

  useEffect(() => { fetchData() }, [fetchData])

  const handleToggleActive = useCallback(async (id: string, value: boolean) => {
    try {
      await apiFetch(`/v1/admin/users/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_active: value }),
      })
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update user')
    }
  }, [fetchData])

  const handleToggleAdmin = useCallback(async (id: string, value: boolean) => {
    try {
      await apiFetch(`/v1/admin/users/${id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_admin: value }),
      })
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update user')
    }
  }, [fetchData])

  const handleDeactivate = useCallback(async (id: string) => {
    try {
      await apiFetch(`/v1/admin/users/${id}`, { method: 'DELETE' })
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete user')
    }
  }, [fetchData])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-xl md:text-2xl font-bold gradient-text">Admin Dashboard</h2>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>
              User management and system overview
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn-primary flex items-center gap-2 self-start sm:self-auto"
          >
            <PlusIcon className="w-4 h-4" />
            New User
          </button>
        </div>

        {/* Error banner */}
        {error && (
          <div
            className="px-4 py-3 rounded-lg text-sm flex items-center justify-between"
            style={{ background: 'rgba(239,68,68,0.1)', color: '#ef4444', border: '1px solid rgba(239,68,68,0.2)' }}
            role="alert"
          >
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-xs opacity-70 hover:opacity-100">Dismiss</button>
          </div>
        )}

        {/* Stats row */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatCard label="Total Users" value={stats.total_users} />
            <StatCard label="Active Users" value={stats.active_users} accent="#10b981" />
            <StatCard label="Admins" value={stats.admin_users} accent="var(--accent-indigo)" />
            <StatCard label="Chats" value={stats.total_chats} />
            <StatCard label="Searches" value={stats.total_searches} />
            <StatCard label="Feedback" value={stats.total_feedback} />
          </div>
        )}

        {/* Users table */}
        <div
          className="rounded-xl overflow-hidden"
          style={{ border: '1px solid var(--border-color)', background: 'var(--bg-elevated)' }}
        >
          {/* Table header bar */}
          <div
            className="px-4 py-3 flex items-center justify-between"
            style={{ borderBottom: '1px solid var(--border-color)' }}
          >
            <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>
              Users
              {!loading && (
                <span className="ml-2 text-xs font-normal" style={{ color: 'var(--text-muted)' }}>
                  ({total} total)
                </span>
              )}
            </h3>
            <button
              onClick={fetchData}
              disabled={loading}
              className="text-xs btn-ghost px-2 py-1"
              style={{ color: 'var(--text-muted)' }}
            >
              {loading ? 'Loading…' : 'Refresh'}
            </button>
          </div>

          {loading ? (
            <div className="py-16 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              Loading users…
            </div>
          ) : users.length === 0 ? (
            <div className="py-16 text-center text-sm" style={{ color: 'var(--text-muted)' }}>
              No users found.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                    {['User', 'Status', 'Role', 'API Key', 'Created', 'Actions'].map((h) => (
                      <th
                        key={h}
                        className="px-4 py-2 text-left text-xs font-semibold uppercase tracking-wider"
                        style={{ color: 'var(--text-muted)' }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <UserRow
                      key={u.id}
                      user={u}
                      onToggleActive={handleToggleActive}
                      onToggleAdmin={handleToggleAdmin}
                      onDeactivate={handleDeactivate}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {totalPages > 1 && (
            <div
              className="px-4 py-3 flex items-center justify-between text-sm"
              style={{ borderTop: '1px solid var(--border-color)' }}
            >
              <span style={{ color: 'var(--text-muted)' }}>
                Page {page + 1} of {totalPages}
              </span>
              <div className="flex gap-2">
                <button
                  disabled={page === 0}
                  onClick={() => setPage((p) => p - 1)}
                  className="btn-secondary text-xs px-3 py-1 disabled:opacity-40"
                >
                  Previous
                </button>
                <button
                  disabled={page >= totalPages - 1}
                  onClick={() => setPage((p) => p + 1)}
                  className="btn-secondary text-xs px-3 py-1 disabled:opacity-40"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Create user modal */}
      {showCreateModal && (
        <CreateUserModal
          onClose={() => setShowCreateModal(false)}
          onCreated={fetchData}
        />
      )}
    </div>
  )
}
