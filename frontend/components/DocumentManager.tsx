'use client'

import { useState, useRef, DragEvent } from 'react'
import { useDocuments } from '@/hooks/useDocuments'
import { formatFileSize, formatDate } from '@/lib/api'

export default function DocumentManager() {
  const { documents, isLoadingDocuments, uploadDocument, deleteDocument, loadDocuments } = useDocuments()
  const [isDragging, setIsDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDrop = async (e: DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      setUploading(true)
      try {
        for (const file of files) {
          await uploadDocument(file)
        }
      } finally {
        setUploading(false)
      }
    }
  }

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    if (files.length > 0) {
      setUploading(true)
      try {
        for (const file of files) {
          await uploadDocument(file)
        }
      } finally {
        setUploading(false)
      }
    }
  }

  const handleDelete = async (id: string) => {
    await deleteDocument(id)
    setDeleteConfirm(null)
  }

  const statusColors: Record<string, string> = {
    processing: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    completed: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    failed: 'bg-red-500/20 text-red-400 border-red-500/30',
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6">
      <div className="max-w-4xl mx-auto">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
          <div>
            <h2 className="text-xl md:text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">Documents</h2>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Upload and manage documents for RAG-enhanced conversations</p>
          </div>
          <button onClick={loadDocuments} className="px-3 py-2 text-sm glass-card hover:bg-white/10 transition-colors rounded-lg flex items-center gap-2 self-start sm:self-auto min-h-[44px]">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" /></svg>
            Refresh
          </button>
        </div>

        {/* Upload Zone */}
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={`
            mb-6 p-8 border-2 border-dashed rounded-xl text-center cursor-pointer transition-all
            ${isDragging ? 'border-blue-400 bg-blue-500/10' : 'border-white/20 hover:border-white/40 hover:bg-white/5'}
            ${uploading ? 'opacity-50 pointer-events-none' : ''}
          `}
        >
          <input ref={fileInputRef} type="file" multiple onChange={handleFileSelect} className="hidden" accept=".txt,.md,.csv,.json,.html,.xml,.pdf" />
          <svg className="w-12 h-12 mx-auto mb-3" style={{ color: 'var(--text-muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
          <p className="font-medium">{uploading ? 'Uploading...' : isDragging ? 'Drop files here' : 'Drag & drop files or click to browse'}</p>
          <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Supports .txt, .md, .csv, .json, .html, .xml</p>
        </div>

        {/* Document List */}
        {isLoadingDocuments ? (
          <div className="text-center py-12" style={{ color: 'var(--text-muted)' }}>Loading documents...</div>
        ) : documents.length === 0 ? (
          <div className="text-center py-12">
            <svg className="w-16 h-16 mx-auto mb-4" style={{ color: 'var(--text-muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
            <p className="font-medium" style={{ color: 'var(--text-muted)' }}>No documents yet</p>
            <p className="text-sm mt-1" style={{ color: 'var(--text-muted)' }}>Upload documents to enhance your AI conversations with context</p>
          </div>
        ) : (
          <div className="space-y-3">
            {documents.map((doc) => (
              <div key={doc.id} className="glass-card p-4 rounded-xl flex items-center gap-4 group">
                <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center flex-shrink-0">
                  <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{doc.filename}</p>
                  <div className="flex items-center gap-3 text-xs mt-1" style={{ color: 'var(--text-muted)' }}>
                    <span>{formatFileSize(doc.file_size)}</span>
                    <span>{doc.chunk_count} chunks</span>
                    {doc.created_at && <span>{formatDate(doc.created_at)}</span>}
                  </div>
                </div>
                <span className={`px-2.5 py-1 text-xs font-medium rounded-full border ${statusColors[doc.status] || ''}`}>
                  {doc.status}
                </span>
                {deleteConfirm === doc.id ? (
                  <div className="flex gap-1">
                    <button onClick={() => handleDelete(doc.id)} className="px-2 py-1 text-xs bg-red-600 hover:bg-red-700 rounded transition-colors">Yes</button>
                    <button onClick={() => setDeleteConfirm(null)} className="px-2 py-1 text-xs rounded transition-colors" style={{ background: 'var(--bg-elevated)', color: 'var(--text-secondary)' }}>No</button>
                  </div>
                ) : (
                  <button onClick={() => setDeleteConfirm(doc.id)} className="p-2 opacity-0 group-hover:opacity-100 hover:bg-white/10 rounded-lg transition-all">
                    <svg className="w-4 h-4" style={{ color: 'var(--text-muted)' }} fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
