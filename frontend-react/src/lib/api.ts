import type { Account, Task, LoginStartResponse, LoginCompleteResponse, GridInstance, GridCheckResult } from '@/types'

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers ?? {}) },
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data.detail || `HTTP ${res.status}`)
  }
  return data as T
}

export const api = {
  health: () => request<{ status: string }>('/health'),

  accounts: {
    list: () => request<{ accounts: Account[] }>('/api/accounts'),
    get: (id: number) => request<{ account: Account }>(`/api/accounts/${id}`),
    create: (payload: { name: string; platform: string; notes?: string; grid_id?: number | null }) =>
      request<{ account: Account }>('/api/accounts', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    update: (id: number, payload: { name?: string; notes?: string; grid_id?: number | null }) =>
      request<{ account: Account }>(`/api/accounts/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
    remove: (id: number) => request<{ status: string }>(`/api/accounts/${id}`, { method: 'DELETE' }),

    startLogin: (id: number) =>
      request<LoginStartResponse>(`/api/accounts/${id}/login`, { method: 'POST' }),
    completeLogin: (id: number) =>
      request<LoginCompleteResponse>(`/api/accounts/${id}/login/complete`, { method: 'POST' }),
    cancelLogin: (id: number) =>
      request<{ status: string }>(`/api/accounts/${id}/login/cancel`, { method: 'POST' }),
  },

  grids: {
    list: () => request<{ grids: GridInstance[] }>('/api/grids'),
    get: (id: number) => request<{ grid: GridInstance }>(`/api/grids/${id}`),
    create: (payload: { name: string; hub_url: string; novnc_base_url?: string; max_sessions?: number; notes?: string }) =>
      request<{ grid: GridInstance }>('/api/grids', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    update: (id: number, payload: Partial<GridInstance>) =>
      request<{ grid: GridInstance }>(`/api/grids/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
    remove: (id: number) => request<{ status: string }>(`/api/grids/${id}`, { method: 'DELETE' }),
    check: (id: number) => request<GridCheckResult>(`/api/grids/${id}/check`, { method: 'POST' }),
  },

  tasks: {
    list: () => request<{ tasks: Task[] }>('/api/tasks'),
    get: (id: number) => request<{ task: Task }>(`/api/tasks/${id}`),
    create: (payload: { account_id: number; type: string; params?: string }) =>
      request<{ task: Task }>('/api/tasks', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    run: (id: number) => request<{ task: Task }>(`/api/tasks/${id}/run`, { method: 'POST' }),
    cancel: (id: number) => request<{ status: string }>(`/api/tasks/${id}/cancel`, { method: 'POST' }),
  },
}