import { render, screen, fireEvent } from '@testing-library/react'
import '@testing-library/jest-dom'
import EmptyState from '@/components/ui/EmptyState'

describe('EmptyState', () => {
  it('renders the title', () => {
    render(<EmptyState title="Nothing here yet" />)
    expect(screen.getByText('Nothing here yet')).toBeInTheDocument()
  })

  it('renders the description when provided', () => {
    render(<EmptyState title="Empty" description="Add something to get started." />)
    expect(screen.getByText('Add something to get started.')).toBeInTheDocument()
  })

  it('does not render description element when omitted', () => {
    render(<EmptyState title="Empty" />)
    expect(screen.queryByRole('paragraph')).not.toBeInTheDocument()
  })

  it('renders an action button when action prop is provided', () => {
    const handleClick = jest.fn()
    render(<EmptyState title="Empty" action={{ label: 'Create Item', onClick: handleClick }} />)
    expect(screen.getByRole('button', { name: 'Create Item' })).toBeInTheDocument()
  })

  it('does not render a button when action prop is omitted', () => {
    render(<EmptyState title="Empty" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('calls action.onClick when the button is clicked', () => {
    const handleClick = jest.fn()
    render(<EmptyState title="Empty" action={{ label: 'Go', onClick: handleClick }} />)
    fireEvent.click(screen.getByRole('button', { name: 'Go' }))
    expect(handleClick).toHaveBeenCalledTimes(1)
  })

  it('renders an icon when provided', () => {
    render(
      <EmptyState
        title="No results"
        icon={<svg data-testid="my-icon" />}
      />
    )
    expect(screen.getByTestId('my-icon')).toBeInTheDocument()
  })

  it('does not render the icon wrapper when icon is omitted', () => {
    const { container } = render(<EmptyState title="No icon" />)
    // The icon wrapper div has mb-4 and is the first child only when icon exists
    const iconWrapper = container.querySelector('.mb-4')
    expect(iconWrapper).not.toBeInTheDocument()
  })

  it('renders title as an h3 element', () => {
    render(<EmptyState title="My Title" />)
    expect(screen.getByRole('heading', { level: 3, name: 'My Title' })).toBeInTheDocument()
  })
})
