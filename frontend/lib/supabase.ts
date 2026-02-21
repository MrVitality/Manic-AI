// Supabase client for authentication
const getSupabaseUrl = (): string => {
  if (typeof window !== 'undefined') {
    try {
      const stored = localStorage.getItem('manic-ai-storage')
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

class SupabaseAuth {
  private baseUrl: string
  private anonKey: string

  constructor() {
    this.baseUrl = getSupabaseUrl()
    this.anonKey = getAnonKey()
  }

  private getHeaders(accessToken?: string): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      'apikey': this.anonKey,
    }
    if (accessToken) {
      headers['Authorization'] = `Bearer ${accessToken}`
    }
    return headers
  }

  async signUp(email: string, password: string): Promise<{ user: User | null; session: Session | null; error: AuthError | null }> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/v1/signup`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()

      if (!response.ok) {
        return { user: null, session: null, error: { message: data.message || data.msg || 'Signup failed', status: response.status } }
      }

      if (data.access_token) {
        const session: Session = {
          access_token: data.access_token,
          refresh_token: data.refresh_token,
          expires_in: data.expires_in,
          expires_at: Date.now() + (data.expires_in * 1000),
          user: data.user,
        }
        return { user: data.user, session, error: null }
      }

      return { user: data.user || data, session: null, error: null }
    } catch (err) {
      return { user: null, session: null, error: { message: 'Network error' } }
    }
  }

  async signIn(email: string, password: string): Promise<{ user: User | null; session: Session | null; error: AuthError | null }> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/v1/token?grant_type=password`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({ email, password }),
      })

      const data = await response.json()

      if (!response.ok) {
        return { user: null, session: null, error: { message: data.message || data.msg || data.error_description || 'Login failed', status: response.status } }
      }

      const session: Session = {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        expires_in: data.expires_in,
        expires_at: Date.now() + (data.expires_in * 1000),
        user: data.user,
      }

      return { user: data.user, session, error: null }
    } catch (err) {
      return { user: null, session: null, error: { message: 'Network error' } }
    }
  }

  async signOut(accessToken: string): Promise<{ error: AuthError | null }> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/v1/logout`, {
        method: 'POST',
        headers: this.getHeaders(accessToken),
      })

      if (!response.ok) {
        const data = await response.json()
        return { error: { message: data.message || 'Logout failed', status: response.status } }
      }

      return { error: null }
    } catch (err) {
      return { error: { message: 'Network error' } }
    }
  }

  async getUser(accessToken: string): Promise<{ user: User | null; error: AuthError | null }> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/v1/user`, {
        method: 'GET',
        headers: this.getHeaders(accessToken),
      })

      const data = await response.json()

      if (!response.ok) {
        return { user: null, error: { message: data.message || 'Failed to get user', status: response.status } }
      }

      return { user: data, error: null }
    } catch (err) {
      return { user: null, error: { message: 'Network error' } }
    }
  }

  async refreshToken(refreshToken: string): Promise<{ session: Session | null; error: AuthError | null }> {
    try {
      const response = await fetch(`${this.baseUrl}/auth/v1/token?grant_type=refresh_token`, {
        method: 'POST',
        headers: this.getHeaders(),
        body: JSON.stringify({ refresh_token: refreshToken }),
      })

      const data = await response.json()

      if (!response.ok) {
        return { session: null, error: { message: data.message || 'Token refresh failed', status: response.status } }
      }

      const session: Session = {
        access_token: data.access_token,
        refresh_token: data.refresh_token,
        expires_in: data.expires_in,
        expires_at: Date.now() + (data.expires_in * 1000),
        user: data.user,
      }

      return { session, error: null }
    } catch (err) {
      return { session: null, error: { message: 'Network error' } }
    }
  }
}

export const supabaseAuth = new SupabaseAuth()
