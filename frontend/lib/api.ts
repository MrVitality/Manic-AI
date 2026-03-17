// =============================================================================
// Manic AI - API Client (Unified API)
// =============================================================================

import type {
  Model, ModelsResponse, DocumentInfo, PullProgress, ServicesStatusResponse,
  UsageAnalyticsData, ModelAnalyticsData, RagAnalyticsData, ServiceHealthSnapshot,
  ChunkInfo, SearchExplainResult, SearchExplainResponse, RagStatsData, SystemInfo,
  CollectionInfo,
} from '@/types'

const DEFAULT_API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8081'

// Configurable allowlist of permitted API hostnames.
// Extend this array to allow additional trusted hosts.
const ALLOWED_HOSTNAMES: string[] = [
  'localhost',
  '127.0.0.1',
  '0.0.0.0',
  '::1',
]

function isValidApiUrl(url: string): boolean {
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return false
    }
    if (ALLOWED_HOSTNAMES.includes(parsed.hostname)) {
      return true
    }
    return false
  } catch {
    return false
  }
}

const getApiUrl = (): string => {
  // Check localStorage for user-configured API URL (from settings)
  if (typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem('manic-ai-storage')
      if (stored) {
        const parsed = JSON.parse(stored)
        const candidate = parsed?.state?.settings?.apiUrl
        if (candidate) {
          if (isValidApiUrl(candidate)) {
            return candidate
          }
          console.warn(
            `[Manic AI] Invalid API URL found in localStorage: "${candidate}". ` +
            'Falling back to default. Only http/https URLs on localhost or allowed hosts are permitted.'
          )
        }
      }
    } catch {
      // Ignore parse errors
    }
  }
  // Fallback to env var or default
  return DEFAULT_API_URL
}

// =============================================================================
// Models
// =============================================================================

export async function fetchModels(): Promise<Model[]> {
  const response = await fetch(`${getApiUrl()}/models`)
  if (!response.ok) {
    throw new Error(`Failed to fetch models: ${response.statusText}`)
  }
  const data: ModelsResponse = await response.json()
  return data.models || []
}

export async function pullModel(
  modelName: string,
  onProgress?: (progress: PullProgress) => void
): Promise<void> {
  const response = await fetch(`${getApiUrl()}/models/pull`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name: modelName }),
  })

  if (!response.body) throw new Error('No response body')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (trimmed.startsWith('data: ')) {
          try {
            const data: PullProgress = JSON.parse(trimmed.slice(6))
            onProgress?.(data)
          } catch { /* skip */ }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function deleteModel(modelName: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/models/${encodeURIComponent(modelName)}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete model: ${response.statusText}`)
  }
}

// =============================================================================
// Chat - Streaming via Unified API SSE
// =============================================================================

export interface ChatOptions {
  model: string
  messages: Array<{ role: string; content: string }>
  temperature?: number
  maxTokens?: number
  systemPrompt?: string
  stream?: boolean
  useRag?: boolean
}

export interface StreamEvent {
  type: 'content' | 'sources' | 'done' | 'error'
  content?: string
  sources?: any[]
  error?: string
}

export async function* streamChat(
  options: ChatOptions,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent, void, unknown> {
  const { model, messages, temperature = 0.7, systemPrompt, useRag = false } = options

  const allMessages = systemPrompt
    ? [{ role: 'system', content: systemPrompt }, ...messages]
    : messages

  const response = await fetch(`${getApiUrl()}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model,
      messages: allMessages,
      temperature,
      use_rag: useRag,
    }),
    signal,
  })

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.statusText}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (trimmed.startsWith('data: ')) {
          try {
            const event: StreamEvent = JSON.parse(trimmed.slice(6))
            yield event
            if (event.type === 'done' || event.type === 'error') return
          } catch { /* skip */ }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}

export async function chat(options: ChatOptions): Promise<{ content: string; sources: any[] }> {
  const { model, messages, temperature = 0.7, systemPrompt, useRag = false } = options

  const allMessages = systemPrompt
    ? [{ role: 'system', content: systemPrompt }, ...messages]
    : messages

  const response = await fetch(`${getApiUrl()}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model,
      messages: allMessages,
      temperature,
      use_rag: useRag,
      stream: false,
    }),
  })

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.statusText}`)
  }

  const data = await response.json()
  return {
    content: data.message?.content || '',
    sources: data.sources || [],
  }
}

// =============================================================================
// Documents
// =============================================================================

export async function fetchDocuments(): Promise<DocumentInfo[]> {
  const response = await fetch(`${getApiUrl()}/documents`)
  if (!response.ok) throw new Error(`Failed to fetch documents: ${response.statusText}`)
  return response.json()
}

export async function ingestDocument(
  content: string,
  filename: string,
  contentType: string = 'text/plain'
): Promise<{ document_id: string; chunks_created: number }> {
  const response = await fetch(`${getApiUrl()}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, filename, content_type: contentType }),
  })
  if (!response.ok) throw new Error(`Failed to ingest document: ${response.statusText}`)
  return response.json()
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`${getApiUrl()}/documents/${documentId}`, {
    method: 'DELETE',
  })
  if (!response.ok) throw new Error(`Failed to delete document: ${response.statusText}`)
}

// =============================================================================
// Services Health
// =============================================================================

export async function fetchServicesStatus(): Promise<ServicesStatusResponse> {
  const response = await fetch(`${getApiUrl()}/services/status`)
  if (!response.ok) throw new Error(`Failed to fetch service status: ${response.statusText}`)
  return response.json()
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${getApiUrl()}/health`, {
      signal: AbortSignal.timeout(5000),
    })
    return response.ok
  } catch {
    return false
  }
}

// =============================================================================
// Embeddings
// =============================================================================

export async function generateEmbedding(text: string, model?: string): Promise<number[]> {
  const response = await fetch(`${getApiUrl()}/embed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, model }),
  })
  if (!response.ok) throw new Error(`Failed to generate embedding: ${response.statusText}`)
  const data = await response.json()
  return data.embedding
}

// =============================================================================
// Format Helpers
// =============================================================================

export function formatModelSize(bytes: number): string {
  const gb = bytes / (1024 * 1024 * 1024)
  if (gb >= 1) return `${gb.toFixed(1)} GB`
  const mb = bytes / (1024 * 1024)
  return `${mb.toFixed(0)} MB`
}

export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${bytes} B`
}

export function formatDate(date: Date | string): string {
  const d = new Date(date)
  return d.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
}

// =============================================================================
// Analytics
// =============================================================================

export async function fetchUsageAnalytics(
  period: string = 'day',
  startDate?: string,
  endDate?: string,
  model?: string
): Promise<UsageAnalyticsData> {
  const params = new URLSearchParams({ period })
  if (startDate) params.set('start_date', startDate)
  if (endDate) params.set('end_date', endDate)
  if (model) params.set('model', model)
  const response = await fetch(`${getApiUrl()}/analytics/usage?${params}`)
  if (!response.ok) throw new Error(`Failed to fetch usage analytics: ${response.statusText}`)
  return response.json()
}

export async function fetchModelAnalytics(): Promise<ModelAnalyticsData> {
  const response = await fetch(`${getApiUrl()}/analytics/models`)
  if (!response.ok) throw new Error(`Failed to fetch model analytics: ${response.statusText}`)
  return response.json()
}

export async function fetchRagAnalytics(): Promise<RagAnalyticsData> {
  const response = await fetch(`${getApiUrl()}/analytics/rag`)
  if (!response.ok) throw new Error(`Failed to fetch RAG analytics: ${response.statusText}`)
  return response.json()
}

export async function fetchServiceHistory(
  service?: string,
  hours: number = 24
): Promise<{ history: ServiceHealthSnapshot[] }> {
  const params = new URLSearchParams({ hours: hours.toString() })
  if (service) params.set('service', service)
  const response = await fetch(`${getApiUrl()}/analytics/services/history?${params}`)
  if (!response.ok) throw new Error(`Failed to fetch service history: ${response.statusText}`)
  return response.json()
}

// =============================================================================
// RAG Management
// =============================================================================

export async function fetchDocumentChunks(
  documentId: string,
  limit: number = 50,
  offset: number = 0
): Promise<{ chunks: ChunkInfo[]; total: number }> {
  const params = new URLSearchParams({ limit: limit.toString(), offset: offset.toString() })
  const response = await fetch(`${getApiUrl()}/documents/${documentId}/chunks?${params}`)
  if (!response.ok) throw new Error(`Failed to fetch chunks: ${response.statusText}`)
  return response.json()
}

export async function searchExplain(request: {
  query: string
  top_k?: number
  threshold?: number
  use_hybrid?: boolean
  collection_id?: string | null
  include_vectors?: boolean
  backend?: string
}): Promise<SearchExplainResponse> {
  const response = await fetch(`${getApiUrl()}/search/explain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) throw new Error(`Search explain failed: ${response.statusText}`)
  return response.json()
}

export async function fetchRagStats(): Promise<RagStatsData> {
  const response = await fetch(`${getApiUrl()}/rag/stats`)
  if (!response.ok) throw new Error(`Failed to fetch RAG stats: ${response.statusText}`)
  return response.json()
}

export async function fetchCollections(): Promise<CollectionInfo[]> {
  const response = await fetch(`${getApiUrl()}/collections`)
  if (!response.ok) throw new Error(`Failed to fetch collections: ${response.statusText}`)
  return response.json()
}

// =============================================================================
// System
// =============================================================================

export async function fetchSystemInfo(): Promise<SystemInfo> {
  const response = await fetch(`${getApiUrl()}/system/info`)
  if (!response.ok) throw new Error(`Failed to fetch system info: ${response.statusText}`)
  return response.json()
}

export async function clearCache(): Promise<{ cleared: boolean; keys_removed: number }> {
  const response = await fetch(`${getApiUrl()}/system/cache/clear`, { method: 'POST' })
  if (!response.ok) throw new Error(`Failed to clear cache: ${response.statusText}`)
  return response.json()
}

export function streamServiceStatus(): EventSource {
  return new EventSource(`${getApiUrl()}/services/status/stream`)
}
