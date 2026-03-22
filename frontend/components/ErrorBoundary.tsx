'use client'
import { Component, type ReactNode, type ErrorInfo } from 'react'
import GlassPanel from '@/components/ui/GlassPanel'

interface ErrorBoundaryProps {
  children: ReactNode
  fallback?: ReactNode
  sectionName?: string
  /** @deprecated use sectionName */
  label?: string
  onReset?: () => void
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    const name = this.props.sectionName || this.props.label || 'Unknown'
    console.error(`[${name}] Error:`, error, errorInfo)
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null })
    this.props.onReset?.()
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <GlassPanel className="p-6 m-4 text-center">
          <div className="text-4xl mb-3">⚠</div>
          <h3 className="text-lg font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
            {this.props.sectionName || this.props.label || 'Section'} Error
          </h3>
          <p className="text-sm mb-4" style={{ color: 'var(--text-muted)' }}>
            Something went wrong loading this section.
          </p>
          <button onClick={this.handleReset} className="btn-primary text-sm px-4 py-2">
            Try Again
          </button>
          {process.env.NODE_ENV === 'development' && this.state.error && (
            <pre
              className="mt-4 text-xs text-left p-3 rounded overflow-auto"
              style={{ background: 'var(--bg-tertiary)', color: 'var(--status-error)' }}
            >
              {this.state.error.message}
            </pre>
          )}
        </GlassPanel>
      )
    }
    return this.props.children
  }
}

export default ErrorBoundary
