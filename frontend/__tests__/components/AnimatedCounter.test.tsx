import { render, screen } from '@testing-library/react'
import '@testing-library/jest-dom'
import AnimatedCounter from '@/components/ui/AnimatedCounter'

// Mock requestAnimationFrame so the animation runs synchronously to the final value
beforeAll(() => {
  jest.spyOn(window, 'requestAnimationFrame').mockImplementation((cb) => {
    // Call the callback with a timestamp far in the future so progress === 1
    cb(performance.now() + 999999)
    return 0
  })
  jest.spyOn(window, 'cancelAnimationFrame').mockImplementation(() => {})
})

afterAll(() => {
  jest.restoreAllMocks()
})

describe('AnimatedCounter', () => {
  it('renders the target value after animation completes', () => {
    render(<AnimatedCounter value={42} />)
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders zero correctly', () => {
    render(<AnimatedCounter value={0} />)
    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('renders with a prefix', () => {
    render(<AnimatedCounter value={100} prefix="$" />)
    expect(screen.getByText(/\$100/)).toBeInTheDocument()
  })

  it('renders with a suffix', () => {
    render(<AnimatedCounter value={75} suffix="%" />)
    expect(screen.getByText(/75%/)).toBeInTheDocument()
  })

  it('renders with both prefix and suffix', () => {
    render(<AnimatedCounter value={9} prefix="~" suffix="x" />)
    expect(screen.getByText(/~9x/)).toBeInTheDocument()
  })

  it('renders with decimal places when decimals prop is set', () => {
    render(<AnimatedCounter value={3.14} decimals={2} />)
    expect(screen.getByText(/3\.14/)).toBeInTheDocument()
  })

  it('applies custom className to the span', () => {
    const { container } = render(<AnimatedCounter value={1} className="text-2xl" />)
    expect(container.firstChild).toHaveClass('text-2xl')
  })

  it('always has tabular-nums class', () => {
    const { container } = render(<AnimatedCounter value={1} />)
    expect(container.firstChild).toHaveClass('tabular-nums')
  })
})
