'use client'

import { useState } from 'react'
import GlassPanel from '@/components/ui/GlassPanel'
import {
  useConnectorStore,
  type ConnectorType,
  type SyncFrequency,
} from '@/lib/stores/connectorStore'

// Read n8n URL from environment variable; fall back to the standard local dev port.
// Set NEXT_PUBLIC_N8N_URL in your .env.local to point at a remote n8n instance.
const N8N_URL = process.env.NEXT_PUBLIC_N8N_URL ?? 'http://localhost:5679'

const SYNC_OPTIONS: Array<{ value: SyncFrequency; label: string }> = [
  { value: '1h', label: 'Every hour' },
  { value: '3h', label: 'Every 3 hours' },
  { value: '6h', label: 'Every 6 hours' },
  { value: '12h', label: 'Every 12 hours' },
  { value: '24h', label: 'Every 24 hours' },
]

interface ConnectorMeta {
  readonly type: ConnectorType
  readonly name: string
  readonly description: string
  readonly icon: JSX.Element
  readonly workflowFile: string
  readonly docsUrl: string
}

const CONNECTORS: readonly ConnectorMeta[] = [
  {
    type: 'notion',
    name: 'Notion',
    description: 'Sync pages and databases from Notion workspaces',
    icon: <NotionIcon />,
    workflowFile: 'notion-connector.json',
    docsUrl: 'https://www.notion.so/my-integrations',
  },
  {
    type: 'google-drive',
    name: 'Google Drive',
    description: 'Import documents, text files, and markdown from Drive folders',
    icon: <DriveIcon />,
    workflowFile: 'google-drive-connector.json',
    docsUrl: 'https://console.cloud.google.com/apis/credentials',
  },
  {
    type: 'confluence',
    name: 'Confluence',
    description: 'Sync wiki pages from Atlassian Confluence spaces',
    icon: <ConfluenceIcon />,
    workflowFile: 'confluence-connector.json',
    docsUrl: 'https://id.atlassian.com/manage-profile/security/api-tokens',
  },
] as const

export default function ConnectorSettings() {
  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-sm font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>
          Knowledge Source Connectors
        </h3>
        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)' }}>
          Connect external knowledge sources to automatically sync content into your RAG pipeline via n8n workflows.
        </p>
      </div>

      {CONNECTORS.map((connector) => (
        <ConnectorCard key={connector.type} meta={connector} />
      ))}

      <GlassPanel className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>n8n Workflow Engine</span>
            <p className="text-xs mt-0.5" style={{ color: 'var(--text-muted)' }}>
              Manage and monitor all connector workflows
            </p>
          </div>
          <a
            href={N8N_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 text-xs rounded-lg font-medium transition-colors"
            style={{
              background: 'rgba(129,140,248,0.1)',
              color: 'var(--accent-blue)',
              border: '1px solid rgba(129,140,248,0.2)',
            }}
          >
            Open n8n Dashboard
          </a>
        </div>
      </GlassPanel>
    </div>
  )
}

function ConnectorCard({ meta }: { readonly meta: ConnectorMeta }) {
  const { connectors, updateConnector } = useConnectorStore()
  const config = connectors[meta.type]
  const [showInstructions, setShowInstructions] = useState(false)

  const isConnected = config.status === 'connected'

  const handleToggle = () => {
    // NOTE: This is LOCAL-ONLY state. No API call is made to n8n or any backend.
    // The connector is not actually connected or syncing — toggling here only
    // persists a flag in the Zustand store (localStorage). Real connectivity
    // requires importing the corresponding n8n workflow and activating it.
    const nextStatus = isConnected ? 'disconnected' : 'connected'
    updateConnector(meta.type, {
      status: nextStatus,
      enabled: nextStatus === 'connected',
    })
  }

  const handleFrequencyChange = (freq: SyncFrequency) => {
    updateConnector(meta.type, { syncFrequency: freq })
  }

  const formatLastSync = (timestamp: string | null): string => {
    if (!timestamp) return 'Never'
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    const diffHours = Math.floor(diffMins / 60)
    if (diffHours < 24) return `${diffHours}h ago`
    const diffDays = Math.floor(diffHours / 24)
    return `${diffDays}d ago`
  }

  return (
    <GlassPanel className="p-4">
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{
            background: isConnected ? 'rgba(234,179,8,0.1)' : 'var(--bg-tertiary)',
            border: `1px solid ${isConnected ? 'rgba(234,179,8,0.2)' : 'var(--glass-border)'}`,
          }}
        >
          <span className="w-5 h-5" style={{ color: isConnected ? '#eab308' : 'var(--text-muted)' }}>
            {meta.icon}
          </span>
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-0.5">
            <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
              {meta.name}
            </span>
            {/* Status reflects local toggle state only — not actual n8n connectivity */}
            <span
              className="px-1.5 py-0.5 rounded text-[10px] font-medium uppercase tracking-wider"
              style={isConnected ? {
                background: 'rgba(234,179,8,0.1)',
                color: '#eab308',
                border: '1px solid rgba(234,179,8,0.2)',
              } : {
                background: 'rgba(113,113,122,0.1)',
                color: '#71717a',
                border: '1px solid rgba(113,113,122,0.2)',
              }}
            >
              {isConnected ? 'Enabled (local)' : 'Disabled'}
            </span>
          </div>
          <p className="text-xs mb-3" style={{ color: 'var(--text-muted)' }}>
            {meta.description}
          </p>

          {/* Controls */}
          <div className="flex items-center gap-4 flex-wrap">
            {/* Sync frequency */}
            <div className="flex items-center gap-1.5">
              <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>Sync:</span>
              <select
                value={config.syncFrequency}
                onChange={(e) => handleFrequencyChange(e.target.value as SyncFrequency)}
                className="text-xs rounded px-1.5 py-0.5 outline-none"
                style={{
                  background: 'var(--bg-tertiary)',
                  color: 'var(--text-secondary)',
                  border: '1px solid var(--glass-border)',
                }}
              >
                {SYNC_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Last sync */}
            <span className="text-[11px]" style={{ color: 'var(--text-muted)' }}>
              Last sync: {formatLastSync(config.lastSync)}
            </span>

            {/* Toggle */}
            <button
              role="switch"
              aria-checked={isConnected}
              aria-label={`Toggle ${meta.name} connector`}
              onClick={handleToggle}
              className="w-10 h-5 rounded-full transition-colors relative ml-auto"
              style={{ background: isConnected ? 'var(--accent-blue)' : 'var(--bg-tertiary)' }}
            >
              <div
                className="absolute top-0.5 w-4 h-4 rounded-full bg-white transition-all"
                style={{ left: isConnected ? 20 : 2 }}
              />
            </button>
          </div>

          {/* Import workflow button */}
          <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--glass-border)' }}>
            <button
              onClick={() => setShowInstructions((prev) => !prev)}
              className="text-xs font-medium transition-colors"
              style={{ color: 'var(--accent-blue)' }}
            >
              {showInstructions ? 'Hide' : 'Import Workflow'}
            </button>

            {showInstructions && (
              <div
                className="mt-2 p-3 rounded-lg text-xs space-y-2"
                style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
              >
                <p className="font-medium" style={{ color: 'var(--text-primary)' }}>
                  Import into n8n:
                </p>
                <ol className="list-decimal list-inside space-y-1" style={{ color: 'var(--text-muted)' }}>
                  <li>
                    Open{' '}
                    <a
                      href={N8N_URL}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline"
                      style={{ color: 'var(--accent-blue)' }}
                    >
                      n8n dashboard
                    </a>
                  </li>
                  <li>Click <strong>Add workflow</strong>, then <strong>... &gt; Import from File</strong></li>
                  <li>
                    Select <code className="px-1 py-0.5 rounded" style={{ background: 'var(--bg-secondary)' }}>
                      n8n-workflows/{meta.workflowFile}
                    </code>
                  </li>
                  <li>
                    Configure credentials (
                    <a
                      href={meta.docsUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="underline"
                      style={{ color: 'var(--accent-blue)' }}
                    >
                      get API key
                    </a>
                    )
                  </li>
                  <li>Activate the workflow</li>
                </ol>
              </div>
            )}
          </div>
        </div>
      </div>
    </GlassPanel>
  )
}

// --- Icons ---

function NotionIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M4.459 4.208c.746.606 1.026.56 2.428.466l13.215-.793c.28 0 .047-.28-.046-.326L18.29 2.39c-.42-.326-.98-.7-2.055-.607L3.01 2.882c-.466.047-.56.28-.374.466zm.793 3.08v13.904c0 .747.373 1.027 1.214.98l14.523-.84c.84-.046.933-.56.933-1.167V6.354c0-.606-.233-.933-.746-.886l-15.177.84c-.56.047-.747.327-.747.98zm14.337.745c.093.42 0 .84-.42.888l-.7.14v10.264c-.608.327-1.167.514-1.634.514-.747 0-.933-.234-1.494-.933l-4.577-7.186v6.952l1.447.327s0 .84-1.167.84l-3.22.187c-.093-.187 0-.653.327-.727l.84-.233V9.854L7.46 9.76c-.094-.42.14-1.026.793-1.073l3.453-.234 4.764 7.28v-6.44l-1.214-.14c-.093-.513.28-.886.746-.933zM2.69 1.59l13.874-1.02c1.681-.14 2.1.093 2.8.607l3.874 2.707c.466.327.606.747.606 1.307v16.38c0 .98-.373 1.587-1.68 1.68L6.486 24.22c-.98.047-1.448-.093-1.962-.747l-3.127-4.03c-.56-.746-.793-1.306-.793-1.96V3.084c0-.84.373-1.54 1.494-1.633z" />
    </svg>
  )
}

function DriveIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M7.71 3.5L1.15 15l3.44 5.96h6.03l-3.44-5.96L13.72 3.5zm1.76 0l6.54 11.5H22.54L16 3.5zM16 3.5l6.54 11.5-3.44 5.96-6.54-11.5zM8.15 15l3.44 5.96h6.54L14.69 15z" />
    </svg>
  )
}

function ConfluenceIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor">
      <path d="M1.393 17.465c-.28.453-.547.96-.787 1.387a.667.667 0 00.24.907l4.907 3.04a.667.667 0 00.907-.24c.213-.387.48-.853.773-1.36 2.053-3.52 4.107-3.093 7.84-1.387l4.067 1.867a.667.667 0 00.88-.333l2.187-4.96a.667.667 0 00-.334-.88c-1.24-.56-3.533-1.613-4.08-1.853-5.907-2.613-10.28-2.613-16.6 3.813zM22.607 6.535c.28-.453.547-.96.787-1.387a.667.667 0 00-.24-.907L18.247 1.2a.667.667 0 00-.907.24c-.213.387-.48.854-.773 1.36-2.053 3.52-4.107 3.094-7.84 1.387L4.66 2.32a.667.667 0 00-.88.333L1.593 7.614a.667.667 0 00.334.88c1.24.56 3.533 1.613 4.08 1.853 5.907 2.613 10.28 2.613 16.6-3.813z" />
    </svg>
  )
}
