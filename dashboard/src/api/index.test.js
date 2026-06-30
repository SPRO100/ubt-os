import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { agentsHeaders, getAgentsToken, notifyApiError } from './index'

describe('agentsHeaders', () => {
  beforeEach(() => localStorage.clear())

  it('returns no Authorization when token is not set', () => {
    const h = agentsHeaders({ 'Content-Type': 'application/json' })
    expect(h['Content-Type']).toBe('application/json')
    expect(h.Authorization).toBeUndefined()
  })

  it('adds Bearer Authorization when token is set', () => {
    localStorage.setItem('agents_api_token', 'secret123')
    expect(getAgentsToken()).toBe('secret123')
    const h = agentsHeaders()
    expect(h.Authorization).toBe('Bearer secret123')
  })

  it('preserves extra headers alongside the token', () => {
    localStorage.setItem('agents_api_token', 't')
    const h = agentsHeaders({ 'X-Test': '1' })
    expect(h['X-Test']).toBe('1')
    expect(h.Authorization).toBe('Bearer t')
  })
})

describe('notifyApiError', () => {
  afterEach(() => vi.restoreAllMocks())

  it('dispatches a ubt:api-error event with source and message', () => {
    const handler = vi.fn()
    window.addEventListener('ubt:api-error', handler)
    notifyApiError('fetch:accounts', new Error('boom'))
    expect(handler).toHaveBeenCalledTimes(1)
    expect(handler.mock.calls[0][0].detail).toEqual({ source: 'fetch:accounts', message: 'boom' })
    window.removeEventListener('ubt:api-error', handler)
  })

  it('maps AbortError to a timeout message', () => {
    const handler = vi.fn()
    window.addEventListener('ubt:api-error', handler)
    const err = new Error('aborted'); err.name = 'AbortError'
    notifyApiError('count:videos', err)
    expect(handler.mock.calls[0][0].detail.message).toBe('таймаут запроса')
    window.removeEventListener('ubt:api-error', handler)
  })
})
