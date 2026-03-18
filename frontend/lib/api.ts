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

/** Return the versioned API base, e.g. ``http://localhost:8081/v1``. */
const getApiV1 = (): string => `${getApiUrl()}/v1`

/**
 * Unwrap the standard API envelope ``{ success, data, error, meta }``.
 * Throws when ``success`` is false or when the envelope is missing.
 */
async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${response.statusText}`)
  }
  const envelope = await response.json()
  if (envelope && typeof envelope.success === 'boolean') {
    if (!envelope.success) {
      throw new Error(envelope.error || 'Unknown API error')
    }
    return envelope.data as T
  }
  // Fallback: response is not wrapped (e.g. streaming endpoints or legacy)
  return envelope as T
}

// =============================================================================
// Models
// =============================================================================

export async function fetchModels(): Promise<Model[]> {
  const response = await fetch(`${getApiV1()}/models`)
  const data = await unwrap<ModelsResponse>(response)
  return data.models || []
}

export async function pullModel(
  modelName: string,
  onProgress?: (progress: PullProgress) => void
): Promise<void> {
  const response = await fetch(`${getApiV1()}/models/pull`, {
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
  const response = await fetch(`${getApiV1()}/models/${encodeURIComponent(modelName)}`, {
    method: 'DELETE',
  })
  await unwrap<unknown>(response)
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
  type: 'content' | 'sources' | 'done' | 'error' | 'tool_start' | 'tool_end'
  content?: string
  sources?: any[]
  error?: string
  tool_name?: string
  tool_call_id?: string
  tool_description?: string
}

export async function* streamChat(
  options: ChatOptions,
  signal?: AbortSignal,
): AsyncGenerator<StreamEvent, void, unknown> {
  const { model, messages, temperature = 0.7, systemPrompt, useRag = false } = options

  const allMessages = systemPrompt
    ? [{ role: 'system', content: systemPrompt }, ...messages]
    : messages

  const response = await fetch(`${getApiV1()}/chat/stream`, {
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

  const response = await fetch(`${getApiV1()}/chat`, {
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

  const data = await unwrap<any>(response)
  return {
    content: data.message?.content || '',
    sources: data.sources || [],
  }
}

// =============================================================================
// Documents
// =============================================================================

export async function fetchDocuments(): Promise<DocumentInfo[]> {
  const response = await fetch(`${getApiV1()}/documents`)
  return unwrap<DocumentInfo[]>(response)
}

export async function ingestDocument(
  content: string,
  filename: string,
  contentType: string = 'text/plain'
): Promise<{ document_id: string; chunks_created: number }> {
  const response = await fetch(`${getApiV1()}/ingest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content, filename, content_type: contentType }),
  })
  return unwrap<{ document_id: string; chunks_created: number }>(response)
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`${getApiV1()}/documents/${documentId}`, {
    method: 'DELETE',
  })
  await unwrap<unknown>(response)
}

// =============================================================================
// Services Health
// =============================================================================

export async function fetchServicesStatus(): Promise<ServicesStatusResponse> {
  const response = await fetch(`${getApiUrl()}/services/status`)
  return unwrap<ServicesStatusResponse>(response)
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${getApiUrl()}/health`, {
      signal: AbortSignal.timeout(5000),
    })
    if (!response.ok) return false
    const envelope = await response.json()
    return envelope?.success === true
  } catch {
    return false
  }
}

// =============================================================================
// Embeddings
// =============================================================================

export async function generateEmbedding(text: string, model?: string): Promise<number[]> {
  const response = await fetch(`${getApiV1()}/embed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, model }),
  })
  const data = await unwrap<{ embedding: number[]; model: string; dimensions: number }>(response)
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
  const response = await fetch(`${getApiV1()}/analytics/usage?${params}`)
  return unwrap<UsageAnalyticsData>(response)
}

export async function fetchModelAnalytics(): Promise<ModelAnalyticsData> {
  const response = await fetch(`${getApiV1()}/analytics/models`)
  return unwrap<ModelAnalyticsData>(response)
}

export async function fetchRagAnalytics(): Promise<RagAnalyticsData> {
  const response = await fetch(`${getApiV1()}/analytics/rag`)
  return unwrap<RagAnalyticsData>(response)
}

export async function fetchServiceHistory(
  service?: string,
  hours: number = 24
): Promise<{ history: ServiceHealthSnapshot[] }> {
  const params = new URLSearchParams({ hours: hours.toString() })
  if (service) params.set('service', service)
  const response = await fetch(`${getApiV1()}/analytics/services/history?${params}`)
  return unwrap<{ history: ServiceHealthSnapshot[] }>(response)
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
  const response = await fetch(`${getApiV1()}/documents/${documentId}/chunks?${params}`)
  return unwrap<{ chunks: ChunkInfo[]; total: number }>(response)
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
  const response = await fetch(`${getApiV1()}/search/explain`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  return unwrap<SearchExplainResponse>(response)
}

export async function fetchRagStats(): Promise<RagStatsData> {
  const response = await fetch(`${getApiV1()}/rag/stats`)
  return unwrap<RagStatsData>(response)
}

export async function fetchCollections(): Promise<CollectionInfo[]> {
  const response = await fetch(`${getApiV1()}/collections`)
  return unwrap<CollectionInfo[]>(response)
}

// =============================================================================
// System
// =============================================================================

export async function fetchSystemInfo(): Promise<SystemInfo> {
  const response = await fetch(`${getApiV1()}/system/info`)
  return unwrap<SystemInfo>(response)
}

export async function clearCache(): Promise<{ cleared: boolean; keys_removed: number }> {
  const response = await fetch(`${getApiV1()}/system/cache/clear`, { method: 'POST' })
  return unwrap<{ cleared: boolean; keys_removed: number }>(response)
}

export function streamServiceStatus(): EventSource {
  return new EventSource(`${getApiUrl()}/services/status/stream`)
}
