import { describe, it, expect, vi, beforeEach } from 'vitest'
import { api, getApiKey, setApiKey } from './api'

describe('api client', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.unstubAllGlobals()
  })

  it('defaults to dev-key when unset', () => {
    expect(getApiKey()).toBe('dev-key')
  })

  it('sends X-API-Key header on requests', async () => {
    setApiKey('k-123')
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok' }) })
    vi.stubGlobal('fetch', fetchMock)
    await api.health()
    const [url, opts] = fetchMock.mock.calls[0]
    expect(url).toBe('/health')
    expect(opts.headers['X-API-Key']).toBe('k-123')
  })

  it('throws with server detail on error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: async () => ({ detail: 'boom' }),
    }))
    await expect(api.accounts.list()).rejects.toThrow('boom')
  })

  it('throws clear message on 401', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: 'Invalid or missing API key' }),
    }))
    await expect(api.accounts.list()).rejects.toThrow(/Invalid API key/)
  })
})
