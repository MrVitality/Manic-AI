'use client'

import { useState, useEffect } from 'react'
import GlassPanel from '@/components/ui/GlassPanel'
import FlowDiagram from '@/components/ui/FlowDiagram'
import Badge from '@/components/ui/Badge'
import { fetchDocuments, fetchDocumentChunks } from '@/lib/api'
import type { DocumentInfo, ChunkInfo, RagStatsData } from '@/types'

interface RagPipelineProps {
  ragStats: RagStatsData | null
}

export default function RagPipeline({ ragStats }: RagPipelineProps) {
  const [documents, setDocuments] = useState<DocumentInfo[]>([])
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null)
  const [chunks, setChunks] = useState<ChunkInfo[]>([])
  const [totalChunks, setTotalChunks] = useState(0)
  const [isLoadingChunks, setIsLoadingChunks] = useState(false)

  useEffect(() => {
    fetchDocuments().then(setDocuments).catch(() => {})
  }, [])

  const handleSelectDoc = async (docId: string) => {
    setSelectedDoc(docId)
    setIsLoadingChunks(true)
    try {
      const data = await fetchDocumentChunks(docId)
      setChunks(data.chunks)
      setTotalChunks(data.total)
    } catch {
      setChunks([])
    } finally {
      setIsLoadingChunks(false)
    }
  }

  const flowNodes = [
    { id: 'upload', label: 'Upload', subtitle: `${ragStats?.total_documents ?? 0} docs`, status: 'active' as const, x: 20, y: 72 },
    { id: 'chunk', label: 'Chunking', subtitle: `${ragStats?.total_chunks ?? 0} chunks`, status: 'active' as const, x: 185, y: 72 },
    { id: 'embed', label: 'Embedding', subtitle: ragStats?.embedding_model ?? 'nomic', status: 'active' as const, x: 350, y: 72 },
    { id: 'store', label: 'Vector Store', subtitle: `${ragStats?.vector_dimension ?? 768}d`, status: 'active' as const, x: 515, y: 72 },
  ]

  const flowEdges = [
    { from: 'upload', to: 'chunk' },
    { from: 'chunk', to: 'embed' },
    { from: 'embed', to: 'store' },
  ]

  const processingDocs = documents.filter((d) => d.status === 'processing')

  return (
    <div className="animate-tab-enter space-y-6">
      {/* Pipeline Flow Diagram */}
      <GlassPanel className="p-4">
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
          RAG Pipeline
        </h3>
        <FlowDiagram nodes={flowNodes} edges={flowEdges} width={680} height={200} />
      </GlassPanel>

      {/* Ingestion Queue */}
      {processingDocs.length > 0 && (
        <GlassPanel className="p-4">
          <h3 className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
            <div className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
            Ingestion Queue
          </h3>
          <div className="space-y-2">
            {processingDocs.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between py-2" style={{ borderBottom: '1px solid var(--border-color)' }}>
                <div className="flex items-center gap-3">
                  <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="var(--accent-blue)" strokeWidth="2">
                    <path d="M12 2a10 10 0 0 1 10 10" strokeLinecap="round" />
                  </svg>
                  <span className="text-sm" style={{ color: 'var(--text-primary)' }}>{doc.filename}</span>
                </div>
                <Badge variant="processing">processing</Badge>
              </div>
            ))}
          </div>
        </GlassPanel>
      )}

      {/* Chunk Inspector */}
      <GlassPanel className="p-4">
        <h3 className="text-sm font-semibold mb-3" style={{ color: 'var(--text-secondary)' }}>
          Chunk Inspector
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Document list */}
          <div className="md:col-span-1 max-h-80 overflow-y-auto space-y-1">
            {documents.length === 0 ? (
              <p className="text-xs py-4 text-center" style={{ color: 'var(--text-muted)' }}>No documents</p>
            ) : (
              documents.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => handleSelectDoc(doc.id)}
                  className="w-full text-left p-2 rounded-lg text-xs transition-colors"
                  style={{
                    background: selectedDoc === doc.id ? 'rgba(129,140,248,0.1)' : 'transparent',
                    color: selectedDoc === doc.id ? 'var(--accent-blue)' : 'var(--text-secondary)',
                    border: selectedDoc === doc.id ? '1px solid rgba(129,140,248,0.2)' : '1px solid transparent',
                  }}
                >
                  <div className="font-medium truncate">{doc.filename}</div>
                  <div className="flex items-center gap-2 mt-0.5" style={{ color: 'var(--text-muted)' }}>
                    <span>{doc.chunk_count} chunks</span>
                    <Badge variant={doc.status === 'completed' ? 'completed' : doc.status === 'failed' ? 'failed' : 'processing'} size="sm">
                      {doc.status}
                    </Badge>
                  </div>
                </button>
              ))
            )}
          </div>

          {/* Chunk content */}
          <div className="md:col-span-2 max-h-80 overflow-y-auto">
            {!selectedDoc ? (
              <div className="flex items-center justify-center h-full py-8">
                <p className="text-xs" style={{ color: 'var(--text-muted)' }}>Select a document to inspect chunks</p>
              </div>
            ) : isLoadingChunks ? (
              <div className="flex items-center justify-center h-full py-8">
                <div className="w-5 h-5 border-2 rounded-full animate-spin" style={{ borderColor: 'var(--border-color)', borderTopColor: 'var(--accent-blue)' }} />
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-[10px] mb-2" style={{ color: 'var(--text-muted)' }}>
                  {totalChunks} chunks total
                </p>
                {chunks.map((chunk) => (
                  <div
                    key={chunk.id}
                    className="p-3 rounded-lg text-xs"
                    style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-color)' }}
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="font-mono font-semibold" style={{ color: 'var(--accent-cyan)' }}>
                        Chunk #{chunk.chunk_index}
                      </span>
                      <span style={{ color: 'var(--text-muted)' }}>{chunk.content_tokens} tokens</span>
                    </div>
                    <p className="leading-relaxed line-clamp-4" style={{ color: 'var(--text-secondary)' }}>
                      {chunk.content}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </GlassPanel>
    </div>
  )
}
