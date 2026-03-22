'use client'
import { useState } from 'react'
import { submitFeedback } from '@/lib/api'

interface FeedbackButtonsProps {
  messageId: string
  conversationId?: string
  queryText?: string
  responseText?: string
  hadRag?: boolean
}

export default function FeedbackButtons({
  messageId,
  conversationId,
  queryText,
  responseText,
  hadRag,
}: FeedbackButtonsProps) {
  const [submitted, setSubmitted] = useState<number | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleFeedback = async (rating: number) => {
    if (submitted !== null || isSubmitting) return
    setIsSubmitting(true)
    try {
      await submitFeedback({
        rating,
        message_id: messageId,
        conversation_id: conversationId,
        query_text: queryText,
        response_text: responseText,
        had_rag: hadRag,
      })
      setSubmitted(rating)
    } catch {
      // Silently fail — feedback is non-critical
    } finally {
      setIsSubmitting(false)
    }
  }

  if (submitted !== null) {
    return (
      <span className="text-xs" style={{ color: 'var(--text-muted)' }}>
        Thanks!
      </span>
    )
  }

  return (
    <div className="flex items-center gap-1">
      <button
        onClick={() => handleFeedback(1)}
        disabled={isSubmitting}
        title="Helpful"
        className="p-1 rounded transition-colors hover:opacity-80 disabled:opacity-40"
        style={{ color: 'var(--text-muted)' }}
      >
        <ThumbsUpIcon className="w-4 h-4" />
      </button>
      <button
        onClick={() => handleFeedback(-1)}
        disabled={isSubmitting}
        title="Not helpful"
        className="p-1 rounded transition-colors hover:opacity-80 disabled:opacity-40"
        style={{ color: 'var(--text-muted)' }}
      >
        <ThumbsDownIcon className="w-4 h-4" />
      </button>
    </div>
  )
}

function ThumbsUpIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M14 9V5a3 3 0 00-3-3l-4 9v11h11.28a2 2 0 002-1.7l1.38-9a2 2 0 00-2-2.3H14zM7 22H4a2 2 0 01-2-2v-7a2 2 0 012-2h3"
      />
    </svg>
  )
}

function ThumbsDownIcon({ className }: { className?: string }) {
  return (
    <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M10 15v4a3 3 0 003 3l4-9V2H5.72a2 2 0 00-2 1.7l-1.38 9a2 2 0 002 2.3H10zM17 2h2.67A2.31 2.31 0 0122 4v7a2.31 2.31 0 01-2.33 2H17"
      />
    </svg>
  )
}
