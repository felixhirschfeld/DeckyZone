import { Field } from '@decky/ui'
import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

type Props = {
  title?: string
  children: ReactNode
}

type State = {
  hasError: boolean
}

class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error) {
    console.log(error)
    return { hasError: true }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.log(error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <Field disabled label="Error">
          {this.props.title
            ? `Error while trying to render ${this.props.title}`
            : 'Error while trying to render this panel'}
        </Field>
      )
    }

    return this.props.children
  }
}

export default ErrorBoundary
