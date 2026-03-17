/**
 * Tests for the ErrorFallback component.
 */
import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import ErrorFallback from '@/components/ErrorFallback'

describe('ErrorFallback', () => {
  const defaultError = Object.assign(new Error('Test error message'), {})
  const mockReset = jest.fn()

  beforeEach(() => {
    mockReset.mockClear()
  })

  it('should render the error message', () => {
    render(<ErrorFallback error={defaultError} reset={mockReset} />)

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('Test error message')).toBeInTheDocument()
  })

  it('should render fallback text when error has no message', () => {
    const emptyError = Object.assign(new Error(''), {})
    render(<ErrorFallback error={emptyError} reset={mockReset} />)

    expect(screen.getByText('An unexpected error occurred.')).toBeInTheDocument()
  })

  it('should display the error digest when present', () => {
    const errorWithDigest = Object.assign(new Error('fail'), { digest: 'abc-123' })
    render(<ErrorFallback error={errorWithDigest} reset={mockReset} />)

    expect(screen.getByText(/Error ID:.*abc-123/)).toBeInTheDocument()
  })

  it('should not display error digest when absent', () => {
    render(<ErrorFallback error={defaultError} reset={mockReset} />)

    expect(screen.queryByText(/Error ID:/)).not.toBeInTheDocument()
  })

  it('should render a retry button', () => {
    render(<ErrorFallback error={defaultError} reset={mockReset} />)

    const button = screen.getByRole('button', { name: /retry/i })
    expect(button).toBeInTheDocument()
  })

  it('should call reset when retry button is clicked', () => {
    render(<ErrorFallback error={defaultError} reset={mockReset} />)

    const button = screen.getByRole('button', { name: /retry/i })
    fireEvent.click(button)

    expect(mockReset).toHaveBeenCalledTimes(1)
  })
})
