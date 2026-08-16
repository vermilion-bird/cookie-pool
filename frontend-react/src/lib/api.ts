import type {
  Account, Task, Schedule, TaskTypeMeta,
  LoginStartResponse, LoginCompleteResponse, GridInstance, GridCheckResult,
  SessionV2, SessionV2Account, SessionHealth,
} from '@/types'

const API_KEY_STORAGE = 'cp_api_key'

export function getApiKey(): string {
  return localStorage.getItem(API_KEY_STORAGE) || 'dev-key'
}

export function setApiKey(key: string): void {
  if (key.trim()) localStorage.setItem(API_KEY_STORAGE, key.trim())
  else localStorage.removeItem(API_KEY_STORAGE)
}

function authError(res: Response, data: unknown): Error {
  if (res.status === 401) {
    return new Error('Invalid API key — set the correct key via the 🔑 button in the header')
  }
  return new Error((data as { detail?: string }).detail || `HTTP ${res.status}`)
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': getApiKey(),
      ...(options?.headers ?? {}),
    },
    ...options,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw authError(res, data)
  return data as T
}

async function upload<T>(url: string, file: File): Promise<T> {
  const fd = new FormData()
  fd.append('file', file)
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'X-API-Key': getApiKey() },
    body: fd,
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw authError(res, data)
  return data as T
}

export const api = {
  health: () => request<{ status: string; version: string; database: string }>('/health'),

  accounts: {
    list: () => request<{ accounts: Account[] }>('/api/accounts'),
    get: (id: number) => request<{ account: Account }>(`/api/accounts/${id}`),
    create: (payload: { name: string; platform: string; notes?: string; grid_id?: number | null; login_indicator?: string | null }) =>
      request<{ account: Account }>('/api/accounts', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    update: (id: number, payload: { name?: string; platform?: string; notes?: string; grid_id?: number | null; login_indicator?: string | null }) =>
      request<{ account: Account }>(`/api/accounts/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
    remove: (id: number) => request<{ status: string }>(`/api/accounts/${id}`, { method: 'DELETE' }),
    importCsv: (file: File) => upload<{ created: number; skipped: { name: string; reason: string }[] }>('/api/accounts/import', file),

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
    types: () => request<{ types: TaskTypeMeta[] }>('/api/tasks/meta/types'),
    create: (payload: { account_id: number; type: string; params?: string; max_retries?: number; retry_delay_seconds?: number }) =>
      request<{ task: Task }>('/api/tasks', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    run: (id: number) => request<{ task: Task; queued: boolean }>(`/api/tasks/${id}/run`, { method: 'POST' }),
    cancel: (id: number) => request<{ status: string }>(`/api/tasks/${id}/cancel`, { method: 'POST' }),
    batchRun: (taskIds: number[]) => request<{ queued: number; skipped: number[] }>('/api/tasks/batch-run', {
      method: 'POST',
      body: JSON.stringify({ task_ids: taskIds }),
    }),
    batchCancel: (taskIds: number[]) => request<{ cancelled: number }>('/api/tasks/batch-cancel', {
      method: 'POST',
      body: JSON.stringify({ task_ids: taskIds }),
    }),
    artifacts: (id: number) => request<{ task_id: number; artifacts: string[] }>(`/api/tasks/${id}/artifacts`),
    artifactUrl: (id: number, name: string) => `/api/tasks/${id}/artifacts/${encodeURIComponent(name)}`,
  },

  schedules: {
    list: () => request<{ schedules: Schedule[] }>('/api/schedules'),
    get: (id: number) => request<{ schedule: Schedule }>(`/api/schedules/${id}`),
    create: (payload: { name: string; cron: string; task_type: string; params?: string; account_id?: number | null; enabled?: boolean }) =>
      request<{ schedule: Schedule }>('/api/schedules', {
        method: 'POST',
        body: JSON.stringify(payload),
      }),
    update: (id: number, payload: Partial<Schedule>) =>
      request<{ schedule: Schedule }>(`/api/schedules/${id}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      }),
    remove: (id: number) => request<{ status: string }>(`/api/schedules/${id}`, { method: 'DELETE' }),
    trigger: (id: number) => request<{ triggered: number; schedule: Schedule }>(`/api/schedules/${id}/trigger`, { method: 'POST' }),
  },

  sessions: {
    list: () => request<{ sessions: SessionV2[] }>('/api/sessions'),
    get: (id: number) => request<{ session: SessionV2 }>(`/api/sessions/${id}`),
    create: (payload: { name: string; node_id: number }) =>
      request<{ session: SessionV2 }>('/api/sessions', { method: 'POST', body: JSON.stringify(payload) }),
    remove: (id: number) => request<{ status: string }>(`/api/sessions/${id}`, { method: 'DELETE' }),
    bindAccount: (sessionId: number, accountId: number) =>
      request<{ session_account: SessionV2Account }>(`/api/sessions/${sessionId}/accounts`, {
        method: 'POST', body: JSON.stringify({ account_id: accountId }),
      }),
    unbindAccount: (sessionId: number, accountId: number) =>
      request<{ status: string }>(`/api/sessions/${sessionId}/accounts/${accountId}`, { method: 'DELETE' }),
    startLogin: (id: number) =>
      request<{ session: SessionV2; novnc_url: string; message: string }>(`/api/sessions/${id}/login`, { method: 'POST' }),
    completeLogin: (id: number) =>
      request<{ status: string; message: string }>(`/api/sessions/${id}/login/complete`, { method: 'POST' }),
    health: (id: number) =>
      request<SessionHealth>(`/api/sessions/${id}/health`),
    restart: (id: number) =>
      request<{ session: SessionV2; novnc_url: string; message: string }>(`/api/sessions/${id}/restart`, { method: 'POST' }),
  },
}
