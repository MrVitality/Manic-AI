// =============================================================================
// Manic AI - API Client (Unified API)
// =============================================================================

import type {
  Model, ModelsResponse, DocumentInfo, PullProgress, ServicesStatusResponse,
  UsageAnalyticsData, ModelAnalyticsData, RagAnalyticsData, ServiceHealthSnapshot,
  ChunkInfo, SearchExplainResult, SearchExplainResponse, RagStatsData, SystemInfo,
  CollectionInfo, RagSource,
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

// Allow private/LAN IPs for non-localhost deployments (Tailscale, LAN, etc.)
const PRIVATE_IP_PATTERNS = [
  /^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$/,           // 10.0.0.0/8
  /^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}$/,  // 172.16.0.0/12
  /^192\.168\.\d{1,3}\.\d{1,3}$/,               // 192.168.0.0/16
  /^100\.(6[4-9]|[7-9]\d|1[0-2]\d|127)\.\d{1,3}\.\d{1,3}$/,  // Tailscale CGNAT 100.64.0.0/10
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
    // Allow private/LAN IPs for self-hosted deployments
    if (PRIVATE_IP_PATTERNS.some((re) => re.test(parsed.hostname))) {
      return true
    }
    return false
  } catch {
    return false
  }
}

let _cachedApiUrl: string | null = null

/** Invalidate the cached API URL (call when settings change). */
export function invalidateApiUrlCache(): void {
  _cachedApiUrl = null
}

export const getApiUrl = (): string => {
  if (_cachedApiUrl !== null) return _cachedApiUrl

  // Check localStorage for user-configured API URL (from settings)
  if (typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem('manic-ai-ui')
      if (stored) {
        const parsed = JSON.parse(stored)
        const candidate = parsed?.state?.settings?.apiUrl
        if (candidate) {
          if (isValidApiUrl(candidate)) {
            _cachedApiUrl = candidate
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
  _cachedApiUrl = DEFAULT_API_URL
  return _cachedApiUrl
}

/** Read the API key from settings persisted in localStorage. */
export function getApiKey(): string {
  if (typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem('manic-ai-ui')
      if (stored) {
        const parsed = JSON.parse(stored)
        const key = parsed?.state?.settings?.apiKey
        if (typeof key === 'string') return key
      }
    } catch {
      // Ignore parse errors
    }
  }
  return ''
}

/**
 * Build a headers object that always includes Content-Type and, when an API
 * key is configured, the X-API-Key header.
 */
function buildHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...extra }
  const apiKey = getApiKey()
  if (apiKey) {
    headers['X-API-Key'] = apiKey
  }
  return headers
}

/** Default timeout (ms) for regular (non-streaming) fetch calls. */
const DEFAULT_TIMEOUT_MS = 30_000

/** Timeout (ms) for streaming fetch calls. */
const STREAM_TIMEOUT_MS = 120_000

/** Return the versioned API base, e.g. ``http://localhost:8081/v1``. */
const getApiV1 = (): string => `${getApiUrl()}/v1`

/**
 * Unwrap the standard API envelope ``{ success, data, error, meta }``.
 * Throws when ``success`` is false or when the envelope is missing.
 */
async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    // Try to parse the envelope error from the response body
    try {
      const envelope = await response.json()
      if (envelope?.error) {
        const err = envelope.error
        // Structured error: { code, message, details? }
        const message = typeof err === 'string' ? err : err.message || 'Unknown API error'
        const apiError = new Error(message) as Error & { code?: string; details?: unknown[] }
        if (typeof err === 'object') {
          apiError.code = err.code
          apiError.details = err.details
        }
        throw apiError
      }
    } catch (e) {
      if (e instanceof Error && e.message !== 'Unknown API error') throw e
    }
    throw new Error(`API error ${response.status}: ${response.statusText}`)
  }
  const envelope = await response.json()
  if (envelope && typeof envelope.success === 'boolean') {
    if (!envelope.success) {
      const err = envelope.error
      const message = typeof err === 'string' ? err : err?.message || 'Unknown API error'
      const apiError = new Error(message) as Error & { code?: string; details?: unknown[] }
      if (typeof err === 'object' && err !== null) {
        apiError.code = err.code
        apiError.details = err.details
      }
      throw apiError
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
  const response = await fetch(`${getApiV1()}/models`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  const data = await unwrap<ModelsResponse>(response)
  return data.models || []
}

export async function pullModel(
  modelName: string,
  onProgress?: (progress: PullProgress) => void
): Promise<void> {
  const response = await fetch(`${getApiV1()}/models/pull`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ name: modelName }),
    signal: AbortSignal.timeout(STREAM_TIMEOUT_MS),
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
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
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
  sources?: RagSource[]
  error?: string
  tool_name?: string
  tool_call_id?: string
  tool_description?: string
}

export async function* streamChat(
  options: ChatOptions,
  signal?: AbortSignal,
  endpoint: 'chat' | 'agent' = 'chat',
): AsyncGenerator<StreamEvent, void, unknown> {
  const { model, messages, temperature = 0.7, systemPrompt, useRag = false } = options

  const allMessages = systemPrompt
    ? [{ role: 'system', content: systemPrompt }, ...messages]
    : messages

  const streamPath = endpoint === 'agent' ? '/agent/stream' : '/chat/stream'
  const combinedSignal = signal
    ? (AbortSignal as unknown as { any: (signals: AbortSignal[]) => AbortSignal }).any([signal, AbortSignal.timeout(STREAM_TIMEOUT_MS)])
    : AbortSignal.timeout(STREAM_TIMEOUT_MS)
  const response = await fetch(`${getApiV1()}${streamPath}`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({
      model,
      messages: allMessages,
      temperature,
      use_rag: useRag,
    }),
    signal: combinedSignal,
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

export async function chat(options: ChatOptions): Promise<{ content: string; sources: RagSource[] }> {
  const { model, messages, temperature = 0.7, systemPrompt, useRag = false } = options

  const allMessages = systemPrompt
    ? [{ role: 'system', content: systemPrompt }, ...messages]
    : messages

  const response = await fetch(`${getApiV1()}/chat`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({
      model,
      messages: allMessages,
      temperature,
      use_rag: useRag,
      stream: false,
    }),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })

  const data = await unwrap<{ message?: { content?: string }; sources?: RagSource[] }>(response)
  return {
    content: data.message?.content || '',
    sources: data.sources || [],
  }
}

// =============================================================================
// Documents
// =============================================================================

export async function fetchDocuments(): Promise<DocumentInfo[]> {
  const response = await fetch(`${getApiV1()}/documents`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<DocumentInfo[]>(response)
}

export async function ingestDocument(
  content: string,
  filename: string,
  contentType: string = 'text/plain'
): Promise<{ document_id: string; chunks_created: number }> {
  const response = await fetch(`${getApiV1()}/ingest`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ content, filename, content_type: contentType }),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<{ document_id: string; chunks_created: number }>(response)
}

export async function deleteDocument(documentId: string): Promise<void> {
  const response = await fetch(`${getApiV1()}/documents/${documentId}`, {
    method: 'DELETE',
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  await unwrap<unknown>(response)
}

// =============================================================================
// Services Health
// =============================================================================

export async function fetchServicesStatus(): Promise<ServicesStatusResponse> {
  const response = await fetch(`${getApiUrl()}/services/status`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<ServicesStatusResponse>(response)
}

export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${getApiUrl()}/health`, {
      headers: buildHeaders(),
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
    headers: buildHeaders(),
    body: JSON.stringify({ text, model }),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
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
  const response = await fetch(`${getApiV1()}/analytics/usage?${params}`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<UsageAnalyticsData>(response)
}

export async function fetchModelAnalytics(): Promise<ModelAnalyticsData> {
  const response = await fetch(`${getApiV1()}/analytics/models`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<ModelAnalyticsData>(response)
}

export async function fetchRagAnalytics(): Promise<RagAnalyticsData> {
  const response = await fetch(`${getApiV1()}/analytics/rag`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<RagAnalyticsData>(response)
}

export async function fetchServiceHistory(
  service?: string,
  hours: number = 24
): Promise<{ history: ServiceHealthSnapshot[] }> {
  const params = new URLSearchParams({ hours: hours.toString() })
  if (service) params.set('service', service)
  const response = await fetch(`${getApiV1()}/analytics/services/history?${params}`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
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
  const response = await fetch(`${getApiV1()}/documents/${documentId}/chunks?${params}`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
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
  rerank?: boolean
  keyword_weight?: number
}): Promise<SearchExplainResponse> {
  const response = await fetch(`${getApiV1()}/search/explain`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<SearchExplainResponse>(response)
}

export async function fetchRagStats(): Promise<RagStatsData> {
  const response = await fetch(`${getApiV1()}/rag/stats`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<RagStatsData>(response)
}

export async function fetchCollections(): Promise<CollectionInfo[]> {
  const response = await fetch(`${getApiV1()}/collections`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<CollectionInfo[]>(response)
}

export async function createCollection(
  name: string,
  description?: string,
): Promise<unknown> {
  const response = await fetch(`${getApiV1()}/collections`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ name, description: description || undefined }),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<unknown>(response)
}

export async function deleteCollection(name: string): Promise<void> {
  const response = await fetch(`${getApiV1()}/collections/${encodeURIComponent(name)}`, {
    method: 'DELETE',
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  if (!response.ok) {
    throw new Error(`Failed to delete collection: ${response.statusText}`)
  }
}

// =============================================================================
// RAG Evaluation
// =============================================================================

export interface SearchLogEntry {
  id: string
  query: string
  backend: string
  use_hybrid: boolean
  top_k: number
  reranked: boolean
  result_count: number
  avg_score: number
  max_score: number
  latency_ms: number
  created_at: string | null
}

export async function fetchSearchHistory(limit = 50, offset = 0): Promise<SearchLogEntry[]> {
  const params = new URLSearchParams({ limit: limit.toString(), offset: offset.toString() })
  const response = await fetch(`${getApiV1()}/eval/search-history?${params}`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<SearchLogEntry[]>(response)
}

export interface EvalRequest {
  query: string
  expected_doc_ids: string[]
  top_k: number
}

export interface EvalMetrics {
  precision: number
  recall: number
  ndcg: number
  mrr: number
  query?: string
  top_k?: number
}

export interface BatchEvalRequest {
  test_cases: EvalRequest[]
}

export interface BatchEvalResult {
  results: EvalMetrics[]
  aggregate: EvalMetrics
}

export async function runEval(request: EvalRequest): Promise<EvalMetrics> {
  const response = await fetch(`${getApiV1()}/eval/run`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<EvalMetrics>(response)
}

export async function runBatchEval(request: BatchEvalRequest): Promise<BatchEvalResult> {
  const response = await fetch(`${getApiV1()}/eval/batch`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(request),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<BatchEvalResult>(response)
}

// =============================================================================
// Feedback
// =============================================================================

export async function submitFeedback(feedback: {
  rating: number
  comment?: string
  conversation_id?: string
  message_id?: string
  query_text?: string
  response_text?: string
  had_rag?: boolean
}): Promise<{ id: string; rating: number }> {
  const response = await fetch(`${getApiV1()}/feedback`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(feedback),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<{ id: string; rating: number }>(response)
}

// =============================================================================
// System
// =============================================================================

export async function fetchSystemInfo(): Promise<SystemInfo> {
  const response = await fetch(`${getApiV1()}/system/info`, {
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<SystemInfo>(response)
}

export async function clearCache(): Promise<{ cleared: boolean; keys_removed: number }> {
  const response = await fetch(`${getApiV1()}/system/cache/clear`, {
    method: 'POST',
    headers: buildHeaders(),
    signal: AbortSignal.timeout(DEFAULT_TIMEOUT_MS),
  })
  return unwrap<{ cleared: boolean; keys_removed: number }>(response)
}

export function streamServiceStatus(): EventSource {
  return new EventSource(`${getApiUrl()}/services/status/stream`)
}

export function connectStatusWebSocket(
  onMessage: (data: ServicesStatusResponse) => void,
  onError?: (error: Event) => void,
): WebSocket {
  const wsUrl = getApiUrl().replace(/^http/, 'ws') + '/ws/status'
  const ws = new WebSocket(wsUrl)

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data)
      if (data.type !== 'pong') {
        onMessage(data)
      }
    } catch { /* skip malformed frames */ }
  }

  ws.onerror = (event) => onError?.(event)

  // Ping every 30s to keep the connection alive
  const pingInterval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send('ping')
    }
  }, 30000)

  ws.onclose = () => clearInterval(pingInterval)

  return ws
}
