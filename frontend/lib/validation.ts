/**
 * File upload validation utilities.
 * Enforces a mime type allowlist and size limit before files are attached.
 */

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024 // 10 MB

const ALLOWED_MIME_TYPES = new Set([
  'application/pdf',
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
  'application/msword',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
])

const ALLOWED_EXTENSIONS = new Set([
  '.pdf', '.txt', '.md', '.csv', '.json', '.doc', '.docx',
])

export interface FileValidationResult {
  valid: boolean
  error?: string
}

export function validateUploadedFile(file: File): FileValidationResult {
  if (file.size > MAX_FILE_SIZE_BYTES) {
    return { valid: false, error: `File too large (max ${MAX_FILE_SIZE_BYTES / 1024 / 1024} MB)` }
  }

  const ext = '.' + file.name.split('.').pop()?.toLowerCase()
  if (!ALLOWED_EXTENSIONS.has(ext)) {
    return { valid: false, error: `File type not allowed. Accepted: ${[...ALLOWED_EXTENSIONS].join(', ')}` }
  }

  if (file.type && !ALLOWED_MIME_TYPES.has(file.type)) {
    return { valid: false, error: `File type not allowed. Accepted: PDF, text, markdown, CSV, JSON, Word` }
  }

  return { valid: true }
}
