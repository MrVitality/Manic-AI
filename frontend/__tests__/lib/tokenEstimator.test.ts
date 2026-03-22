import { estimateTokens, formatTokenCount } from '@/lib/tokenEstimator'

describe('estimateTokens', () => {
  it('returns 0 for empty string', () => {
    expect(estimateTokens('')).toBe(0)
  })

  it('estimates ~4 chars per token', () => {
    expect(estimateTokens('hello world')).toBe(3) // 11/4 = 2.75 → 3
  })

  it('returns at least 1 for non-empty', () => {
    expect(estimateTokens('hi')).toBe(1)
  })
})

describe('formatTokenCount', () => {
  it('formats small numbers as-is', () => {
    expect(formatTokenCount(42)).toBe('42')
  })

  it('formats thousands with k suffix', () => {
    expect(formatTokenCount(1500)).toBe('1.5k')
  })
})
