'use client'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html lang="en" data-theme="dark">
      <body
        style={{
          background: '#0a0a0f',
          color: '#e4e4e7',
          fontFamily: 'monospace',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          margin: 0,
        }}
      >
        <div style={{ textAlign: 'center', padding: '2rem' }}>
          <div style={{ fontSize: '3rem', color: '#ef4444', marginBottom: '1.5rem' }}>[!]</div>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 'bold', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '0.5rem' }}>
            Critical Error
          </h2>
          <p style={{ color: '#71717a', fontSize: '0.875rem', marginBottom: '1.5rem', maxWidth: '400px' }}>
            {error.message || 'An unexpected error occurred at the root level.'}
          </p>
          {error.digest && (
            <p style={{ color: '#52525b', fontSize: '0.75rem', marginBottom: '1.5rem' }}>
              Error ID: {error.digest}
            </p>
          )}
          <button
            onClick={reset}
            style={{
              padding: '0.5rem 1.5rem',
              background: '#3b82f6',
              color: 'white',
              border: '1px solid #3b82f6',
              borderRadius: '2px',
              fontSize: '0.875rem',
              fontFamily: 'monospace',
              fontWeight: 'bold',
              textTransform: 'uppercase',
              cursor: 'pointer',
            }}
          >
            [RETRY]
          </button>
        </div>
      </body>
    </html>
  )
}
