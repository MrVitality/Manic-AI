'use client'
import { useMemo } from 'react'
import { estimateTokens, formatTokenCount } from '@/lib/tokenEstimator'

interface TokenCounterProps {
  inputText: string
  isStreaming: boolean
  streamedText: string
  model?: string
}

export default function TokenCounter({ inputText, isStreaming, streamedText, model }: TokenCounterProps) {
  const inputTokens = useMemo(() => estimateTokens(inputText), [inputText])
  const outputTokens = useMemo(() => estimateTokens(streamedText), [streamedText])

  return (
    <div className="flex items-center gap-3 text-[11px] px-1" style={{ color: 'var(--text-muted)' }}>
      <span title="Estimated input tokens">
        ↑ {formatTokenCount(inputTokens)} tokens
      </span>
      {isStreaming && (
        <span title="Estimated output tokens (streaming)" className="animate-pulse">
          ↓ {formatTokenCount(outputTokens)} tokens
        </span>
      )}
      {!isStreaming && outputTokens > 0 && (
        <span title="Output tokens">
          ↓ {formatTokenCount(outputTokens)} tokens
        </span>
      )}
      {model && (
        <span className="ml-auto opacity-60" title="Active model">
          {model}
        </span>
      )}
    </div>
  )
}
