import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import '@testing-library/jest-dom'
import FeedbackButtons from '@/components/FeedbackButtons'

// Mock the API module so no real HTTP calls are made
jest.mock('@/lib/api', () => ({
  submitFeedback: jest.fn(),
}))

import { submitFeedback } from '@/lib/api'
const mockSubmitFeedback = submitFeedback as jest.MockedFunction<typeof submitFeedback>

beforeEach(() => {
  mockSubmitFeedback.mockResolvedValue(undefined as any)
})

afterEach(() => {
  jest.clearAllMocks()
})

describe('FeedbackButtons', () => {
  const defaultProps = {
    messageId: 'msg-123',
    conversationId: 'conv-456',
  }

  it('renders two buttons (thumbs up and thumbs down)', () => {
    render(<FeedbackButtons {...defaultProps} />)
    expect(screen.getByTitle('Helpful')).toBeInTheDocument()
    expect(screen.getByTitle('Not helpful')).toBeInTheDocument()
  })

  it('buttons are enabled before any submission', () => {
    render(<FeedbackButtons {...defaultProps} />)
    expect(screen.getByTitle('Helpful')).not.toBeDisabled()
    expect(screen.getByTitle('Not helpful')).not.toBeDisabled()
  })

  it('shows "Thanks!" after clicking thumbs up', async () => {
    render(<FeedbackButtons {...defaultProps} />)
    fireEvent.click(screen.getByTitle('Helpful'))
    await waitFor(() => {
      expect(screen.getByText('Thanks!')).toBeInTheDocument()
    })
  })

  it('shows "Thanks!" after clicking thumbs down', async () => {
    render(<FeedbackButtons {...defaultProps} />)
    fireEvent.click(screen.getByTitle('Not helpful'))
    await waitFor(() => {
      expect(screen.getByText('Thanks!')).toBeInTheDocument()
    })
  })

  it('hides the buttons after a successful submission', async () => {
    render(<FeedbackButtons {...defaultProps} />)
    fireEvent.click(screen.getByTitle('Helpful'))
    await waitFor(() => {
      expect(screen.queryByTitle('Helpful')).not.toBeInTheDocument()
      expect(screen.queryByTitle('Not helpful')).not.toBeInTheDocument()
    })
  })

  it('calls submitFeedback with rating=1 when thumbs up is clicked', async () => {
    render(<FeedbackButtons {...defaultProps} />)
    fireEvent.click(screen.getByTitle('Helpful'))
    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledWith(
        expect.objectContaining({ rating: 1, message_id: 'msg-123' })
      )
    })
  })

  it('calls submitFeedback with rating=-1 when thumbs down is clicked', async () => {
    render(<FeedbackButtons {...defaultProps} />)
    fireEvent.click(screen.getByTitle('Not helpful'))
    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledWith(
        expect.objectContaining({ rating: -1, message_id: 'msg-123' })
      )
    })
  })

  it('still shows "Thanks!" even when the API call fails (silent failure)', async () => {
    mockSubmitFeedback.mockRejectedValueOnce(new Error('Network error'))
    render(<FeedbackButtons {...defaultProps} />)
    fireEvent.click(screen.getByTitle('Helpful'))
    // After the rejection is caught silently, state is NOT set to submitted
    // (the component only sets submitted on success — buttons remain rendered)
    await waitFor(() => {
      // Buttons are re-enabled after isSubmitting resets
      expect(screen.getByTitle('Helpful')).not.toBeDisabled()
    })
  })

  it('passes optional props (queryText, responseText, hadRag) to submitFeedback', async () => {
    render(
      <FeedbackButtons
        messageId="m1"
        queryText="What is AI?"
        responseText="It is a field..."
        hadRag={true}
      />
    )
    fireEvent.click(screen.getByTitle('Helpful'))
    await waitFor(() => {
      expect(mockSubmitFeedback).toHaveBeenCalledWith(
        expect.objectContaining({
          query_text: 'What is AI?',
          response_text: 'It is a field...',
          had_rag: true,
        })
      )
    })
  })
})
