// Supabase client for authentication — uses the official @supabase/supabase-js SDK
// which handles token storage, rotation, and refresh automatically.
import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const getSupabaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem('manic-ai-ui')
      if (stored) {
        const parsed = JSON.parse(stored)
        if (parsed?.state?.settings?.supabaseUrl) {
          return parsed.state.settings.supabaseUrl
        }
      }
    } catch { }
  }
  return process.env.NEXT_PUBLIC_SUPABASE_URL || 'http://localhost:8001'
}

const getAnonKey = (): string => {
  return process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || ''
}

// ---------------------------------------------------------------------------
// Public types — kept identical to the previous hand-rolled versions so that
// every call-site continues to work without changes.
// ---------------------------------------------------------------------------

export interface User {
  id: string
  email: string
  created_at: string
}

export interface Session {
  access_token: string
  refresh_token: string
  expires_in: number
  expires_at?: number
  user: User
}

export interface AuthError {
  message: string
  status?: number
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Map a Supabase SDK user object to our public User type. */
const toUser = (u: { id: string; email?: string; created_at: string }): User => ({
  id: u.id,
  email: u.email ?? '',
  created_at: u.created_at,
})

/** Map a Supabase SDK session to our public Session type. */
const toSession = (s: {
  access_token: string
  refresh_token: string
  expires_in: number
  expires_at?: number
  user: { id: string; email?: string; created_at: string }
}): Session => ({
  access_token: s.access_token,
  refresh_token: s.refresh_token,
  expires_in: s.expires_in,
  expires_at: s.expires_at,
  user: toUser(s.user),
})

// ---------------------------------------------------------------------------
// SupabaseAuth — thin wrapper that delegates to the official SDK client
// ---------------------------------------------------------------------------

class SupabaseAuth {
  private client: SupabaseClient

  constructor() {
    const isServer = typeof window === 'undefined'
    this.client = createClient(getSupabaseUrl(), getAnonKey(), {
      auth: {
        persistSession: true,
        autoRefreshToken: !isServer,
        detectSessionInUrl: !isServer,
        storage: isServer
          ? { getItem: () => null, setItem: () => {}, removeItem: () => {} }
          : undefined,
      },
    })
  }

  async signUp(
    email: string,
    password: string,
  ): Promise<{ user: User | null; session: Session | null; error: AuthError | null }> {
    const { data, error } = await this.client.auth.signUp({ email, password })

    if (error) {
      return { user: null, session: null, error: { message: error.message, status: error.status } }
    }

    const user = data.user ? toUser(data.user as { id: string; email?: string; created_at: string }) : null
    const session = data.session
      ? toSession(data.session as unknown as Parameters<typeof toSession>[0])
      : null

    return { user, session, error: null }
  }

  async signIn(
    email: string,
    password: string,
  ): Promise<{ user: User | null; session: Session | null; error: AuthError | null }> {
    const { data, error } = await this.client.auth.signInWithPassword({ email, password })

    if (error) {
      return { user: null, session: null, error: { message: error.message, status: error.status } }
    }

    const user = data.user ? toUser(data.user as { id: string; email?: string; created_at: string }) : null
    const session = data.session
      ? toSession(data.session as unknown as Parameters<typeof toSession>[0])
      : null

    return { user, session, error: null }
  }

  async signOut(_accessToken?: string): Promise<{ error: AuthError | null }> {
    const { error } = await this.client.auth.signOut()

    if (error) {
      return { error: { message: error.message, status: error.status } }
    }

    return { error: null }
  }

  async getUser(_accessToken?: string): Promise<{ user: User | null; error: AuthError | null }> {
    const { data, error } = await this.client.auth.getUser()

    if (error) {
      return { user: null, error: { message: error.message, status: error.status } }
    }

    const user = data.user
      ? toUser(data.user as { id: string; email?: string; created_at: string })
      : null

    return { user, error: null }
  }

  async refreshToken(_refreshToken?: string): Promise<{ session: Session | null; error: AuthError | null }> {
    const { data, error } = await this.client.auth.refreshSession()

    if (error) {
      return { session: null, error: { message: error.message, status: error.status } }
    }

    const session = data.session
      ? toSession(data.session as unknown as Parameters<typeof toSession>[0])
      : null

    return { session, error: null }
  }
}

export const supabaseAuth = new SupabaseAuth()
