/**
 * Tests for the API client utilities in lib/api.ts.
 *
 * We test the unwrap helper and URL construction logic by mocking fetch.
 */

// We need to test internal functions, so we import the module and mock fetch.
// The unwrap function is not directly exported, but we can test it through
// the public API functions.

import { formatModelSize, formatFileSize, formatDate, generateMessageId } from '@/lib/api'

// Mock fetch globally
const mockFetch = jest.fn()
global.fetch = mockFetch

// Mock localStorage
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
  }
})()
Object.defineProperty(window, 'localStorage', { value: localStorageMock })

beforeEach(() => {
  mockFetch.mockClear()
  localStorageMock.clear()
})

describe('API unwrap via fetchModels', () => {
  // We test unwrap indirectly through fetchModels since unwrap is not exported

  it('should unwrap successful envelope and return data', async () => {
    const { fetchModels } = await import('@/lib/api')

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: true,
        data: { models: [{ name: 'llama3', size: 1000 }] },
        error: null,
      }),
    })

    const models = await fetchModels()
    expect(models).toEqual([{ name: 'llama3', size: 1000 }])
  })

  it('should throw on unsuccessful envelope', async () => {
    const { fetchModels } = await import('@/lib/api')

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        success: false,
        data: null,
        error: 'Model not found',
      }),
    })

    await expect(fetchModels()).rejects.toThrow('Model not found')
  })

  it('should throw on HTTP error status', async () => {
    const { fetchModels } = await import('@/lib/api')

    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: 'Internal Server Error',
    })

    await expect(fetchModels()).rejects.toThrow('API error 500')
  })
})

describe('API URL construction', () => {
  it('should use default API URL when localStorage is empty', async () => {
    const { checkHealth } = await import('@/lib/api')

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    })

    await checkHealth()

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('localhost:8081'),
      expect.anything(),
    )
  })

  it('should reject invalid API URLs from localStorage', async () => {
    localStorageMock.setItem(
      'manic-ai-storage',
      JSON.stringify({ state: { settings: { apiUrl: 'ftp://evil.com' } } })
    )

    const { checkHealth } = await import('@/lib/api')

    mockFetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ success: true }),
    })

    await checkHealth()

    // Should fall back to default, not use ftp://evil.com
    const calledUrl = mockFetch.mock.calls[0][0] as string
    expect(calledUrl).not.toContain('evil.com')
    expect(calledUrl).toContain('localhost')
  })
})

describe('Format helpers', () => {
  describe('formatModelSize', () => {
    it('should format GB sizes', () => {
      const result = formatModelSize(4 * 1024 * 1024 * 1024)
      expect(result).toBe('4.0 GB')
    })

    it('should format MB sizes', () => {
      const result = formatModelSize(500 * 1024 * 1024)
      expect(result).toBe('500 MB')
    })
  })

  describe('formatFileSize', () => {
    it('should format MB', () => {
      expect(formatFileSize(2 * 1024 * 1024)).toBe('2.0 MB')
    })

    it('should format KB', () => {
      expect(formatFileSize(1536)).toBe('1.5 KB')
    })

    it('should format bytes', () => {
      expect(formatFileSize(42)).toBe('42 B')
    })
  })

  describe('formatDate', () => {
    it('should return a formatted date string', () => {
      const result = formatDate('2025-01-15T10:30:00Z')
      expect(typeof result).toBe('string')
      expect(result.length).toBeGreaterThan(0)
    })
  })

  describe('generateMessageId', () => {
    it('should return a string starting with msg_', () => {
      const id = generateMessageId()
      expect(id).toMatch(/^msg_\d+_[a-z0-9]+$/)
    })

    it('should generate unique ids', () => {
      const id1 = generateMessageId()
      const id2 = generateMessageId()
      expect(id1).not.toBe(id2)
    })
  })
})
