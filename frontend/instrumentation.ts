/**
 * Next.js instrumentation hook — runs once in the Node.js server process
 * before any application code is loaded.
 *
 * Purpose: the preview/test runner injects a broken `localStorage` stub into
 * the Node process (via --localstorage-file without a valid path).  Any code
 * that calls `localStorage.getItem` during SSR (Supabase SDK, etc.) throws
 * "localStorage.getItem is not a function" because the stub is malformed.
 *
 * We replace it with a safe no-op that always returns null on the server,
 * satisfying both real-SSR environments (where localStorage is undefined)
 * and preview environments (where it exists but is broken).
 */
export async function register() {
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const g = globalThis as Record<string, unknown>
    const ls = g['localStorage'] as Storage | undefined
    if (!ls || typeof ls.getItem !== 'function') {
      g['localStorage'] = {
        getItem: (_key: string) => null,
        setItem: (_key: string, _value: string) => {},
        removeItem: (_key: string) => {},
        clear: () => {},
        key: (_index: number) => null,
        length: 0,
      } satisfies Storage
    }
  }
}
