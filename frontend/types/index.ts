// =============================================================================
// Manic AI - Type Definitions
// =============================================================================

// Tool call types
export type ToolCallStatus = 'pending' | 'complete' | 'error'

export interface ToolCallInfo {
  id: string
  toolName: string
  status: ToolCallStatus
  description: string
  sources?: RagSource[]
  error?: string
  startedAt: number
  completedAt?: number
}

// Message types
export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: Date
  model?: string
  isStreaming?: boolean
  error?: string
  sources?: RagSource[]
  toolCalls?: ToolCallInfo[]
}

// Conversation types
export interface Conversation {
  id: string
  title: string
  messages: Message[]
  model: string
  createdAt: Date
  updatedAt: Date
}

// Model types
export interface Model {
  name: string
  modified_at: string
  size: number
  digest: string
  details?: {
    family: string
    parameter_size: string
    quantization_level: string
  }
}

// API Response types
export interface ChatResponse {
  id: string
  model: string
  message: {
    role: string
    content: string
  }
  sources: RagSource[]
  usage: Record<string, number>
}

export interface ModelsResponse {
  models: Model[]
}

// Settings types
export interface Settings {
  defaultModel: string
  temperature: number
  maxTokens: number
  systemPrompt: string
  streamResponses: boolean
  apiUrl: string
  theme: 'dark' | 'light'
  ragTopK: number
  ragThreshold: number
  accentColor: 'blue' | 'purple' | 'cyan' | 'emerald' | 'rose'
  fontSize: 'sm' | 'base' | 'lg'
  enableAnimations: boolean
  healthCheckInterval: number
  dashboardRefreshRate: number
  ragBackend: 'supabase' | 'qdrant' | 'both'
  ragUseHybrid: boolean
}

// RAG types
export interface RagSource {
  id: string
  document_id: string
  content: string
  score: number
  metadata: Record<string, any>
  vector_score?: number
  keyword_score?: number
}

export interface DocumentInfo {
  id: string
  filename: string
  content_type: string
  file_size: number
  status: 'processing' | 'completed' | 'failed'
  chunk_count: number
  metadata: Record<string, any>
  created_at: string | null
  updated_at: string | null
}

// Model pull progress
export interface PullProgress {
  status: string
  digest?: string
  total?: number
  completed?: number
}

// Service health
export interface ServiceStatus {
  name: string
  url: string
  status: 'healthy' | 'degraded' | 'offline' | 'unknown'
  latency_ms: number | null
}

export interface ServicesStatusResponse {
  timestamp: string
  services: Record<string, ServiceStatus>
}

// Active view
export type ActiveView = 'chat' | 'documents' | 'models' | 'dashboard' | 'rag' | 'settings'

// Dashboard types
export type DashboardTab = 'overview' | 'services' | 'performance'
export type RagCenterTab = 'pipeline' | 'collections' | 'search-lab' | 'analytics' | 'eval'
export type SettingsSection = 'general' | 'models' | 'rag' | 'inference' | 'appearance' | 'data' | 'connectors' | 'shortcuts'

// Service health snapshot
export interface ServiceHealthSnapshot {
  timestamp: string
  services: Record<string, {
    status: 'healthy' | 'degraded' | 'offline' | 'unknown'
    latency_ms: number | null
  }>
}

// Analytics types
export interface UsageDataPoint {
  timestamp: string
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  request_count: number
  avg_latency_ms: number
  model?: string
}

export interface UsageAnalyticsData {
  data: UsageDataPoint[]
  totals: {
    total_tokens: number
    total_requests: number
    avg_latency_ms: number
  }
}

export interface ModelAnalyticsEntry {
  name: string
  request_count: number
  total_tokens: number
  avg_latency_ms: number
  avg_tokens_per_request: number
  last_used: string
  size_bytes?: number
}

export interface ModelAnalyticsData {
  models: ModelAnalyticsEntry[]
}

export interface RagAnalyticsData {
  documents: {
    total: number
    by_status: Record<string, number>
  }
  chunks: {
    total: number
    avg_per_document: number
    total_tokens: number
  }
  searches: {
    total: number
    avg_results: number
    avg_score: number
    avg_latency_ms: number
  }
  collections: {
    total: number
    avg_documents_per_collection: number
  }
}

// RAG Center types
export interface CollectionInfo {
  id: string
  name: string
  description: string | null
  is_public: boolean
  embedding_model: string
  metadata: Record<string, any>
  document_count: number
  created_at: string | null
}

export interface ChunkInfo {
  id: string
  chunk_index: number
  content: string
  content_tokens: number
  metadata: Record<string, any>
  created_at?: string
}

export interface SearchConfig {
  topK: number
  threshold: number
  useHybrid: boolean
  backend: 'supabase' | 'qdrant' | 'both'
  collectionId: string | null
  includeVectors: boolean
}

export interface SearchExplainResult {
  id: string
  document_id: string
  content: string
  vector_score: number
  keyword_score: number
  combined_score: number
  document_filename: string
  metadata: Record<string, any>
}

export interface SearchExplainResponse {
  results: SearchExplainResult[]
  query_embedding_preview: number[]
  search_latency_ms: number
}

export interface RagStatsData {
  total_documents: number
  total_chunks: number
  total_collections: number
  storage_bytes: number
  avg_chunk_tokens: number
  embedding_model: string
  vector_dimension: number
  index_type: string
  documents_by_type: Record<string, number>
  recent_ingestions: Array<{
    document_id: string
    filename: string
    chunks_created: number
    status: string
    created_at: string
  }>
}

// System types
export interface SystemInfo {
  version: string
  uptime_seconds: number
  start_time: string
  config: {
    chat_model: string
    embedding_model: string
    vector_dimension: number
    rag_top_k: number
    rag_threshold: number
  }
  database: {
    pool_size: number
    pool_free: number
  }
}

// Command Palette types
export interface Command {
  id: string
  label: string
  description?: string
  category: 'navigation' | 'action' | 'search' | 'conversation' | 'document' | 'model'
  shortcut?: string
  action: () => void
}

// Chart data types
export interface SparklineData {
  values: number[]
  color?: string
}

export interface DonutSegment {
  label: string
  value: number
  color: string
}

export interface HeatmapCell {
  x: number
  y: number
  value: number
  label?: string
}

// API Error
export interface ApiError {
  error: string
  message: string
  statusCode: number
}
