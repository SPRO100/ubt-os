import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info)
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          margin: '40px auto', maxWidth: 560, background: 'var(--surface)',
          border: '1px solid #ef444444', borderLeft: '4px solid var(--red)',
          borderRadius: 10, padding: '24px 28px',
        }}>
          <div style={{ fontWeight: 700, color: 'var(--red)', marginBottom: 8, fontSize: 15 }}>
            ⚠️ Ошибка компонента
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: "'IBM Plex Mono',monospace",
            whiteSpace: 'pre-wrap', marginBottom: 16 }}>
            {this.state.error.message}
          </div>
          <button onClick={() => this.setState({ error: null })}
            style={{ fontSize: 12, padding: '6px 16px', borderRadius: 6,
              background: 'var(--surface2)', border: '1px solid var(--border)',
              color: 'var(--text)', cursor: 'pointer' }}>
            Попробовать снова
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
