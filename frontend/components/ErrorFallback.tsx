'use client'

interface ErrorFallbackProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function ErrorFallback({ error, reset }: ErrorFallbackProps) {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center font-mono">
      <div
        className="text-4xl mb-6"
        style={{ color: 'var(--accent-red, #ef4444)' }}
      >
        [!]
      </div>
      <h2
        className="text-xl font-bold mb-2 uppercase tracking-widest"
        style={{ color: 'var(--text-primary)' }}
      >
        Something went wrong
      </h2>
      <p
        className="max-w-md mb-4 text-sm"
        style={{ color: 'var(--text-muted)' }}
      >
        {error.message || 'An unexpected error occurred.'}
      </p>
      {error.digest && (
        <p
          className="text-xs mb-6"
          style={{ color: 'var(--text-muted)', opacity: 0.6 }}
        >
          Error ID: {error.digest}
        </p>
      )}
      <button
        onClick={reset}
        className="px-6 py-2 rounded-sm transition-all border text-sm font-mono font-bold uppercase"
        style={{
          background: 'var(--accent-blue)',
          color: 'white',
          border: '1px solid var(--accent-blue)',
        }}
      >
        [RETRY]
      </button>
    </div>
  )
}
