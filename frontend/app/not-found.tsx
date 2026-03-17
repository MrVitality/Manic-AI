'use client'

import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="flex-1 flex flex-col items-center justify-center p-8 text-center font-mono min-h-screen" style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)' }}>
      <div className="text-6xl mb-6 font-bold tracking-tighter" style={{ color: 'var(--accent-blue)' }}>
        404
      </div>
      <h2 className="text-2xl font-bold mb-2 uppercase tracking-widest" style={{ color: 'var(--text-primary)' }}>
        Route Not Found
      </h2>
      <p className="max-w-md mb-8 text-sm" style={{ color: 'var(--text-muted)' }}>
        // The requested path does not exist in the system.
      </p>
      <Link
        href="/chat"
        className="px-6 py-2 rounded-sm transition-all border text-sm font-mono font-bold uppercase"
        style={{
          background: 'var(--accent-blue)',
          color: 'white',
          border: '1px solid var(--accent-blue)',
        }}
      >
        [RETURN_HOME]
      </Link>
    </div>
  )
}
