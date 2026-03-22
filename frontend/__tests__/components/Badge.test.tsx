import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import Badge from '@/components/ui/Badge'

describe('Badge', () => {
  it('renders with text content', () => {
    render(<Badge variant="healthy">Online</Badge>)
    expect(screen.getByText('Online')).toBeInTheDocument()
  })

  it.each([
    ['healthy', '#10b981'],
    ['degraded', '#f59e0b'],
    ['offline', '#ef4444'],
    ['unknown', '#6b7280'],
    ['processing', '#3b82f6'],
    ['completed', '#10b981'],
    ['failed', '#ef4444'],
    ['info', '#3b82f6'],
  ] as const)('applies correct color style for variant "%s"', (variant, expectedColor) => {
    render(<Badge variant={variant}>{variant}</Badge>)
    const badge = screen.getByText(variant).closest('span')
    expect(badge).toHaveStyle({ color: expectedColor })
  })

  it('renders the dot indicator inside the badge', () => {
    const { container } = render(<Badge variant="healthy">Active</Badge>)
    // The dot is a sibling <span> inside the outer <span>
    const outerSpan = screen.getByText('Active').closest('span')
    const dotSpan = outerSpan?.querySelector('span')
    expect(dotSpan).toBeInTheDocument()
    expect(dotSpan).toHaveStyle({ background: '#10b981' })
  })

  it('applies text-xs class for size="sm" (default)', () => {
    render(<Badge variant="healthy">Small</Badge>)
    const badge = screen.getByText('Small').closest('span')
    expect(badge).toHaveClass('text-xs')
  })

  it('applies text-sm class for size="md"', () => {
    render(<Badge variant="healthy" size="md">Medium</Badge>)
    const badge = screen.getByText('Medium').closest('span')
    expect(badge).toHaveClass('text-sm')
  })

  it('applies animate-pulse class to dot when pulse=true', () => {
    const { container } = render(<Badge variant="healthy" pulse>Pulsing</Badge>)
    const outerSpan = screen.getByText('Pulsing').closest('span')
    const dotSpan = outerSpan?.querySelector('span')
    expect(dotSpan).toHaveClass('animate-pulse')
  })

  it('does not apply animate-pulse when pulse is false (default)', () => {
    const { container } = render(<Badge variant="healthy">Stable</Badge>)
    const outerSpan = screen.getByText('Stable').closest('span')
    const dotSpan = outerSpan?.querySelector('span')
    expect(dotSpan).not.toHaveClass('animate-pulse')
  })
})
