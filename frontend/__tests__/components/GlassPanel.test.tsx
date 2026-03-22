import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import GlassPanel from '@/components/ui/GlassPanel'

describe('GlassPanel', () => {
  it('renders children', () => {
    render(<GlassPanel><span>Hello World</span></GlassPanel>)
    expect(screen.getByText('Hello World')).toBeInTheDocument()
  })

  it('applies no padding class for padding="none"', () => {
    const { container } = render(<GlassPanel padding="none">Content</GlassPanel>)
    const panel = container.firstChild as HTMLElement
    expect(panel).not.toHaveClass('p-3')
    expect(panel).not.toHaveClass('p-4')
    expect(panel).not.toHaveClass('p-6')
  })

  it('applies p-3 for padding="sm"', () => {
    const { container } = render(<GlassPanel padding="sm">Content</GlassPanel>)
    expect(container.firstChild).toHaveClass('p-3')
  })

  it('applies p-4 for padding="md" (default)', () => {
    const { container } = render(<GlassPanel>Content</GlassPanel>)
    expect(container.firstChild).toHaveClass('p-4')
  })

  it('applies p-6 for padding="lg"', () => {
    const { container } = render(<GlassPanel padding="lg">Content</GlassPanel>)
    expect(container.firstChild).toHaveClass('p-6')
  })

  it('applies transition class when hover=true', () => {
    const { container } = render(<GlassPanel hover>Content</GlassPanel>)
    expect(container.firstChild).toHaveClass('transition-all')
    expect(container.firstChild).toHaveClass('duration-200')
  })

  it('does not apply transition class when hover is false (default)', () => {
    const { container } = render(<GlassPanel>Content</GlassPanel>)
    expect(container.firstChild).not.toHaveClass('transition-all')
  })

  it('applies animate-glow class when glow=true', () => {
    const { container } = render(<GlassPanel glow>Content</GlassPanel>)
    expect(container.firstChild).toHaveClass('animate-glow')
  })

  it('does not apply animate-glow when glow is false (default)', () => {
    const { container } = render(<GlassPanel>Content</GlassPanel>)
    expect(container.firstChild).not.toHaveClass('animate-glow')
  })

  it('accepts and applies a custom className', () => {
    const { container } = render(<GlassPanel className="my-custom-class">Content</GlassPanel>)
    expect(container.firstChild).toHaveClass('my-custom-class')
  })

  it('retains base rounded-xl class regardless of props', () => {
    const { container } = render(<GlassPanel>Content</GlassPanel>)
    expect(container.firstChild).toHaveClass('rounded-xl')
  })
})
