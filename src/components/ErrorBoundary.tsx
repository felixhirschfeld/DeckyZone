import { PanelSection, PanelSectionRow } from '@decky/ui'
import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

type Props = {
  title: string
  children: ReactNode
}

type State = {
  hasError: boolean
}

class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error(`Failed to render panel "${this.props.title}"`, error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <PanelSection title={this.props.title}>
          <PanelSectionRow>
            <div>Failed to render this panel.</div>
          </PanelSectionRow>
        </PanelSection>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
