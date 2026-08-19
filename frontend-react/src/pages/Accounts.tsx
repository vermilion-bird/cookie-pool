import { useMemo, useRef, useState, useEffect } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardSection, CardHeader } from '@/components/Card'
import { Button } from '@/components/Button'
import { Badge } from '@/components/Badge'
import { FilterBar } from '@/components/FilterBar'
import { Modal } from '@/components/Modal'
import { EmptyState, SkeletonCard } from '@/components/EmptyState'
import { useToast } from '@/hooks/useToast'
import { timeAgo } from '@/lib/format'
import type { Account, AccountStatus, SessionV2 } from '@/types'

type FilterValue = 'ALL' | AccountStatus

const filterOptions: { label: string; value: FilterValue }[] = [
  { label: 'All', value: 'ALL' },
  { label: 'Waiting', value: 'WAIT_LOGIN' },
  { label: 'Active', value: 'ACTIVE' },
  { label: 'In Use', value: 'IN_USE' },
  { label: 'Expired', value: 'LOGIN_EXPIRED' },
]

// ── Predefined platforms ──
const PREDEFINED_PLATFORMS = [
  { label: 'YouTube',        value: 'youtube.com' },
  { label: 'TikTok',         value: 'tiktok.com' },
  { label: 'Instagram',      value: 'instagram.com' },
  { label: 'Facebook',       value: 'facebook.com' },
  { label: 'Twitter / X',    value: 'twitter.com' },
  { label: 'LinkedIn',       value: 'linkedin.com' },
  { label: 'Reddit',         value: 'reddit.com' },
  { label: '微信',            value: 'weixin.qq.com' },
  { label: '抖音',            value: 'douyin.com' },
  { label: '小红书',          value: 'xiaohongshu.com' },
  { label: 'Bilibili',       value: 'bilibili.com' },
  { label: '微博',            value: 'weibo.com' },
  { label: '快手',            value: 'kuaishou.com' },
  { label: '知乎',            value: 'zhihu.com' },
]

const platformIcons: Record<string, string> = {
  YouTube: '▶️', Google: '🔍', Facebook: '📘',
  TikTok: '🎵', Instagram: '📷', Twitter: '𝕏', LinkedIn: '💼',
  Reddit: '🤖', Bilibili: '📺', WeChat: '💬', Weibo: '📢', Zhihu: '❓',
}

function getIcon(platform: string): string {
  for (const [key, icon] of Object.entries(platformIcons))
    if (platform.toLowerCase().includes(key.toLowerCase())) return icon
  return '🔑'
}

// ── Session status dot styles (compact) ──
const sessionStatusDot: Record<string, string> = {
  ACTIVE: 'bg-emerald-500', LOGIN: 'bg-indigo-500', IDLE: 'bg-gray-400',
  CREATING: 'bg-amber-500', READY: 'bg-blue-500',
  CLOSED: 'bg-gray-300', FAILED: 'bg-red-500',
}

// ── PlatformSelect: searchable dropdown with custom fallback ──
function PlatformSelect({ value, onChange, id }: { value: string; onChange: (v: string) => void; id?: string }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState(value)
  const containerRef = useRef<HTMLDivElement>(null)

  // sync external value changes (e.g. edit form load)
  useEffect(() => { setQuery(value) }, [value])

  // close on outside click
  useEffect(() => {
    if (!open) return
    function handler(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const filtered = PREDEFINED_PLATFORMS.filter(p =>
    p.label.toLowerCase().includes(query.toLowerCase()) ||
    p.value.toLowerCase().includes(query.toLowerCase())
  )
  const exactMatch = PREDEFINED_PLATFORMS.some(p => p.value === query || p.label === query)
  const showCustom = query.trim().length > 0 && !exactMatch

  function select(platformValue: string) {
    setQuery(platformValue)
    onChange(platformValue)
    setOpen(false)
  }

  return (
    <div ref={containerRef} className="relative">
      <input
        id={id}
        className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
        placeholder="Search or type custom..."
        value={query}
        onFocus={() => setOpen(true)}
        onChange={e => { setQuery(e.target.value); onChange(e.target.value); setOpen(true) }}
        onKeyDown={e => {
          if (e.key === 'Escape') setOpen(false)
          if (e.key === 'Enter') {
            if (filtered.length === 1 && !showCustom) select(filtered[0].value)
            else if (showCustom) { onChange(query.trim()); setOpen(false) }
          }
        }}
      />
      {open && (filtered.length > 0 || showCustom) && (
        <div className="absolute z-30 mt-1 w-full rounded-lg border border-gray-200 bg-white shadow-lg max-h-56 overflow-y-auto">
          {filtered.map(p => (
            <button
              key={p.value}
              type="button"
              className={`flex w-full items-center gap-2 px-3 py-2 text-sm text-left transition-colors hover:bg-gray-100 ${p.value === query || p.label === query ? 'bg-blue-50 text-blue-700' : 'text-ink-soft'}`}
              onClick={() => select(p.value)}
            >
              <span className="text-xs opacity-60 w-6 text-center">{(platformIcons[p.label] ?? '')}</span>
              <span className="font-medium">{p.label}</span>
              <span className="text-xs opacity-40 ml-auto">{p.value}</span>
            </button>
          ))}
          {showCustom && (
            <button
              type="button"
              className="flex w-full items-center gap-2 px-3 py-2 text-sm text-left text-blue-600 transition-colors hover:bg-blue-50 border-t border-gray-100"
              onClick={() => { onChange(query.trim()); setQuery(query.trim()); setOpen(false) }}
            >
              <span className="text-xs">✏️</span>
              <span>Use custom: <strong>{query.trim()}</strong></span>
            </button>
          )}
        </div>
      )}
    </div>
  )
}

const emptyForm = { name: '', platform: '', notes: '', gridId: '' as number | string, loginIndicator: '' }

export function Accounts() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<FilterValue>('ALL')
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [form, setForm] = useState(emptyForm)
  const [showCreate, setShowCreate] = useState(false)
  const [editAccount, setEditAccount] = useState<Account | null>(null)
  const [editForm, setEditForm] = useState(emptyForm)
  const [sessionId, setSessionId] = useState<string>('')
  const [editingSessionId, setEditingSessionId] = useState<string>('')

  const { data, isLoading } = useQuery({ queryKey: ['accounts', { page, page_size: pageSize, status: filter === 'ALL' ? undefined : filter }], queryFn: () => api.accounts.list({ page, page_size: pageSize, status: filter === 'ALL' ? undefined : filter }), refetchInterval: 15000 })
  const { data: gridData } = useQuery({ queryKey: ['grids'], queryFn: api.grids.list })
  const { data: sessionData } = useQuery({ queryKey: ['sessions'], queryFn: api.sessions.list })

  const accounts = data?.accounts ?? []
  const total = data?.total ?? 0
  const totalPages = data?.total_pages ?? 1
  const grids = gridData?.grids ?? []
  const sessions: SessionV2[] = sessionData?.sessions ?? []

  // ── Build account → session binding lookup ──
  const accountSessionMap = useMemo(() => {
    const map = new Map<number, SessionV2>()
    for (const s of sessions) {
      for (const sa of s.accounts ?? []) {
        map.set(sa.account_id, s)
      }
    }
    return map
  }, [sessions])

  const invalidate = () => {
    setPage(1)
    queryClient.invalidateQueries({ queryKey: ['accounts'] })
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
  }

  const createMutation = useMutation({
    mutationFn: () =>
      api.accounts.create({
        name: form.name.trim(), platform: form.platform.trim(), notes: form.notes.trim(),
        grid_id: form.gridId ? parseInt(form.gridId as string, 10) : null,
        login_indicator: form.loginIndicator.trim() || null,
      }),
    onSuccess: (data) => {
      const acc = data.account
      toast(`Created "${acc.name}"`, 'success')
      setForm(emptyForm); setShowCreate(false)
      if (sessionId) {
        bindMutation.mutate({ accId: acc.id, sessId: parseInt(sessionId, 10) })
      } else {
        invalidate()
      }
    },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const updateMutation = useMutation({
    mutationFn: () =>
      api.accounts.update(editAccount!.id, {
        name: editForm.name.trim(), platform: editForm.platform.trim(), notes: editForm.notes.trim(),
        grid_id: editForm.gridId ? parseInt(editForm.gridId as string, 10) : null,
        login_indicator: editForm.loginIndicator.trim() || null,
      }),
    onSuccess: () => {
      const accId = editAccount!.id
      toast('Account updated', 'success'); setEditAccount(null)
      if (editingSessionId) {
        bindMutation.mutate({ accId, sessId: parseInt(editingSessionId, 10) })
      } else {
        invalidate()
      }
    },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.accounts.remove(id),
    onSuccess: (_, id) => { toast(`Deleted "${accounts.find(a => a.id === id)?.name ?? id}"`, 'success'); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const bindMutation = useMutation({
    mutationFn: ({ accId, sessId }: { accId: number; sessId: number }) => api.sessions.bindAccount(sessId, accId),
    onSuccess: () => { toast('Bound to session', 'success'); invalidate() },
    onError: (e: Error) => toast('Bind failed: ' + e.message, 'error'),
  })

  const unbindMutation = useMutation({
    mutationFn: ({ accId, sessId }: { accId: number; sessId: number }) => api.sessions.unbindAccount(sessId, accId),
    onSuccess: () => { toast('Unbound from session', 'success'); invalidate() },
    onError: (e: Error) => toast('Unbind failed: ' + e.message, 'error'),
  })

  const statusChangeMutation = useMutation({
    mutationFn: ({ accId, status }: { accId: number; status: string }) => api.accounts.update(accId, { status }),
    onSuccess: (_, vars) => { toast('Status → ' + vars.status, 'success'); invalidate() },
    onError: (e: Error) => toast('Status change failed: ' + e.message, 'error'),
  })

  const importFileRef = useRef<HTMLInputElement>(null)
  const importMutation = useMutation({
    mutationFn: (file: File) => api.accounts.importCsv(file),
    onSuccess: (data) => { toast(`Imported ${data.created} account(s)`, 'success'); invalidate() },
    onError: (e: Error) => toast('Import failed: ' + e.message, 'error'),
  })

  function sessionLabel(s: SessionV2): string {
    const count = (s.accounts ?? []).length
    return s.name + ' (' + s.status + (count > 0 ? ' · ' + count + ' acct' : '') + ')'
  }

  function handleCreate() { if (!form.name.trim() || !form.platform.trim()) { toast('Name and platform are required', 'error'); return }; createMutation.mutate() }
  function handleSaveEdit() { if (!editForm.name.trim() || !editForm.platform.trim()) { toast('Name and platform are required', 'error'); return }; updateMutation.mutate() }
  function handleDelete(acc: Account) { if (!confirm(`Delete "${acc.name}"?`)) return; deleteMutation.mutate(acc.id) }
  function openEdit(acc: Account) {
    const bound = accountSessionMap.get(acc.id)
    setEditForm({ name: acc.name, platform: acc.platform, notes: acc.notes || '', gridId: acc.grid_id ?? '', loginIndicator: acc.login_indicator || '' })
    setEditAccount(acc); setEditingSessionId(bound ? String(bound.id) : '')
  }
  function gridName(acc: Account): string {
    if (!acc.grid_id) return 'Default'
    return grids.find(g => g.id === acc.grid_id)?.name ?? `Grid #${acc.grid_id}`
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2 sm:gap-3">
        <div><h1 className="page-title text-xl sm:text-2xl">Accounts</h1><p className="page-subtitle text-xs sm:text-sm">{accounts.length} accounts · {sessions.filter(s => s.status === 'ACTIVE').length} active sessions</p></div>
        <div className="flex items-center gap-1.5 sm:gap-2">
          <Button variant="outline" loading={importMutation.isPending} onClick={() => importFileRef.current?.click()}><span className="hidden sm:inline">⬆ Import CSV</span><span className="sm:hidden">⬆</span></Button>
          <input ref={importFileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) importMutation.mutate(f); e.target.value = '' }} />
          <Button variant="success" onClick={() => setShowCreate(!showCreate)}>{showCreate ? 'Cancel' : <><span className="hidden sm:inline">+ New Account</span><span className="sm:hidden">+ New</span></>}</Button>
        </div>
      </div>

      {showCreate && (
        <Card>
          <CardHeader title="New Account" subtitle="Define a platform account, optionally bind to an existing Session." />
          <CardSection>
            <div className="grid grid-cols-1 sm:flex sm:flex-wrap items-end gap-3">
              <div className="sm:min-w-[120px] sm:flex-1"><label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Name</label>
                <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" placeholder="tiktok_ads_01" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} onKeyDown={e => e.key === 'Enter' && handleCreate()} /></div>
              <div className="sm:min-w-[120px] sm:flex-1"><label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Platform</label>
                <PlatformSelect value={form.platform} onChange={v => setForm({ ...form, platform: v })} /></div>
              <div className="sm:min-w-[110px] sm:flex-1"><label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Grid</label>
                <select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={form.gridId} onChange={e => setForm({ ...form, gridId: e.target.value })}><option value="">Default</option>{grids.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
              <div className="sm:min-w-[140px] sm:flex-1"><label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Bind to Session</label>
                <select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={sessionId} onChange={e => setSessionId(e.target.value)}><option value="">None (bind later)</option>{sessions.map(s => <option key={s.id} value={s.id}>{sessionLabel(s)}</option>)}</select></div>
              <Button variant="success" loading={createMutation.isPending} onClick={handleCreate} className="w-full sm:w-auto">Create</Button>
            </div>
          </CardSection>
        </Card>
      )}

      <Card>
        <FilterBar options={filterOptions} value={filter} onChange={setFilter} />
        {isLoading ? <div className="space-y-2 p-5">{[1, 2, 3].map(i => <SkeletonCard key={i} />)}</div>
        : accounts.length === 0 ? <EmptyState icon="🍪" message={accounts.length === 0 ? 'No accounts yet.' : 'No accounts match this filter.'} />
        : <div className="divide-y divide-gray-100">
            {accounts.map(acc => (
              <AccountItem key={acc.id} account={acc} icon={getIcon(acc.platform)} gridName={gridName(acc)}
                boundSession={accountSessionMap.get(acc.id) ?? null}
                sessions={sessions}
                onEdit={() => openEdit(acc)} onDelete={() => handleDelete(acc)}
                onBind={(sessId) => bindMutation.mutate({ accId: acc.id, sessId })}
                onUnbind={(sessId) => unbindMutation.mutate({ accId: acc.id, sessId })}
                onStatusChange={(status) => statusChangeMutation.mutate({ accId: acc.id, status })}
                bindPending={bindMutation.isPending}
                unbindPending={unbindMutation.isPending}
                statusPending={statusChangeMutation.isPending}
              />
            ))}
          </div>}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between py-3 px-1">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {total} accounts &middot; Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1 text-sm rounded-lg border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >Prev</button>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1 text-sm rounded-lg border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >Next</button>
          </div>
        </div>
      )}
      </Card>

      {editAccount && (
        <Modal open title={`Edit Account #${editAccount.id}`} onClose={() => setEditAccount(null)}
          footer={<><Button variant="primary" loading={updateMutation.isPending} onClick={handleSaveEdit}>Save</Button><Button variant="outline" onClick={() => setEditAccount(null)}>Cancel</Button></>}>
          <div className="space-y-4">
            <div><label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Name</label><input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /></div>
            <div><label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Platform</label><PlatformSelect value={editForm.platform} onChange={v => setEditForm({ ...editForm, platform: v })} /></div>
            <div><label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Grid</label><select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={editForm.gridId} onChange={e => setEditForm({ ...editForm, gridId: e.target.value })}><option value="">Default</option>{grids.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Session Binding</label>
              <select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={editingSessionId} onChange={e => setEditingSessionId(e.target.value)}>
                <option value="">None (unbind)</option>
                {sessions.map(s => <option key={s.id} value={s.id}>{sessionLabel(s)}</option>)}
              </select>
              {editingSessionId && (() => {
                const targetSession = sessions.find(s => s.id === parseInt(editingSessionId, 10))
                const conflict = targetSession?.accounts?.find(
                  sa => sa.platform === editForm.platform && sa.account_id !== editAccount!.id
                )
                if (conflict) {
                  return <p className="mt-1.5 text-xs text-amber-600">⚠ Session already has an account ({conflict.account?.name ?? '#' + conflict.account_id}) for platform "{editForm.platform}"</p>
                }
                return null
              })()}
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

// ── Valid status transitions per current status ──
const STATUS_TRANSITIONS: Record<string, { label: string; value: string }[]> = {
  WAIT_LOGIN:    [{ label: 'Disable', value: 'DISABLED' }],
  ACTIVE:        [{ label: 'Disable', value: 'DISABLED' }],
  IN_USE:        [{ label: 'Release', value: 'ACTIVE' }, { label: 'Disable', value: 'DISABLED' }],
  LOGIN_EXPIRED: [{ label: 'Retry Login', value: 'WAIT_LOGIN' }, { label: 'Disable', value: 'DISABLED' }],
  DISABLED:      [{ label: 'Enable', value: 'WAIT_LOGIN' }],
  ERROR:         [{ label: 'Reset', value: 'WAIT_LOGIN' }, { label: 'Disable', value: 'DISABLED' }],
}

// ── Status change label colors ──
const statusActionStyle: Record<string, string> = {
  DISABLED: 'text-gray-500 hover:bg-gray-100',
  ACTIVE: 'text-emerald-600 hover:bg-emerald-50',
  WAIT_LOGIN: 'text-amber-600 hover:bg-amber-50',
}

function AccountItem({ account, icon, gridName, boundSession, sessions, onEdit, onDelete, onBind, onUnbind, onStatusChange, bindPending, unbindPending, statusPending }: {
  account: Account; icon: string; gridName: string;
  boundSession: SessionV2 | null;
  sessions: SessionV2[];
  onEdit: () => void; onDelete: () => void;
  onBind: (sessId: number) => void; onUnbind: (sessId: number) => void;
  onStatusChange: (status: string) => void;
  bindPending: boolean; unbindPending: boolean; statusPending: boolean;
}) {
  const last = account.last_login_at || account.last_used_at
  const [showBind, setShowBind] = useState(false)
  const [showStatus, setShowStatus] = useState(false)

  const transitions = STATUS_TRANSITIONS[account.status] ?? []

  // Sessions eligible for binding
  const availableSessions = useMemo(() => {
    return sessions.filter(s =>
      ['ACTIVE', 'LOGIN', 'IDLE', 'READY'].includes(s.status)
    )
  }, [sessions])

  // Check for platform conflict in bound session
  const platformConflict = useMemo(() => {
    if (!boundSession) return null
    return boundSession.accounts?.find(
      sa => sa.platform === account.platform && sa.account_id !== account.id
    ) ?? null
  }, [boundSession, account.platform, account.id])

  return (
    <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 px-4 sm:px-5 py-3 sm:py-4 transition-colors hover:bg-gray-50/70">
      {/* ── Top row: icon + name + badge ── */}
      <div className="flex items-center gap-3 min-w-0 flex-1">
        <span className="flex h-8 w-8 sm:h-9 sm:w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-sm sm:text-base">{icon}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-ink truncate">{account.name}</span>
            <Badge status={account.status} />
          </div>
          <div className="flex items-center gap-2 mt-0.5">
            <span className="text-xs text-ink-soft/50">{account.platform}</span>
            <span className="hidden sm:inline text-xs text-ink-soft/30">·</span>
            <span className="text-xs text-ink-soft/40 sm:hidden">{gridName}</span>
            <span className="hidden sm:inline text-xs text-ink-soft/30 font-mono">{gridName}</span>
            {last && <><span className="text-xs text-ink-soft/20">·</span><span className="text-xs text-ink-soft/40">{timeAgo(last)}</span></>}
          </div>
        </div>
      </div>

      {/* ── Middle: bound session (desktop only) ── */}
      <div className="hidden sm:flex items-center gap-2 min-w-0" style={{ maxWidth: '180px' }}>
        {boundSession ? (
          <div className="flex items-center gap-1.5 min-w-0">
            <span className={'inline-block h-1.5 w-1.5 shrink-0 rounded-full ' + (sessionStatusDot[boundSession.status] ?? 'bg-gray-400')} />
            <span className="text-xs font-medium text-ink-soft truncate">{boundSession.name}</span>
            <span className="text-[0.6rem] font-semibold uppercase tracking-wider text-ink-soft/40 shrink-0">{boundSession.status}</span>
            <button onClick={() => onUnbind(boundSession.id)} disabled={unbindPending}
              className="ml-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded text-ink-soft/25 transition-colors hover:bg-red-50 hover:text-red-400" title="Unbind">
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
            {platformConflict && <span className="shrink-0 text-xs text-amber-500">⚠</span>}
          </div>
        ) : <span className="text-xs text-ink-soft/25 italic">not bound</span>}
      </div>

      {/* ── Mobile: bound session bar ── */}
      {boundSession && (
        <div className="sm:hidden flex items-center gap-1.5 text-xs bg-gray-50 rounded-lg px-2 py-1 w-fit">
          <span className={'inline-block h-1.5 w-1.5 rounded-full ' + (sessionStatusDot[boundSession.status] ?? 'bg-gray-400')} />
          <span className="text-ink-soft/70">{boundSession.name}</span>
          <span className="text-ink-soft/40">({boundSession.status})</span>
          <button onClick={() => onUnbind(boundSession.id)} disabled={unbindPending}
            className="ml-1 flex h-4 w-4 items-center justify-center rounded text-ink-soft/30 hover:bg-red-50 hover:text-red-400" title="Unbind">
            <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" /></svg>
          </button>
        </div>
      )}

      {/* ── Actions ── */}
      <div className="flex items-center gap-1 sm:ml-auto">
        {/* Status */}
        {transitions.length > 0 && (
          !showStatus ? (
            <button onClick={() => setShowStatus(true)} disabled={statusPending}
              className="flex h-7 sm:h-8 items-center gap-1 rounded-lg px-1.5 sm:px-2 text-xs text-ink-soft/50 transition-colors hover:bg-amber-50 hover:text-amber-600" title="Change status">
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
              <span className="hidden sm:inline">Status</span>
            </button>
          ) : (
            <select className="rounded-lg border border-gray-200 px-2 py-1 sm:py-1.5 text-xs max-w-[120px]" defaultValue="" autoFocus onBlur={() => setShowStatus(false)}
              onChange={e => { if (e.target.value) onStatusChange(e.target.value); setShowStatus(false) }}>
              <option value="" disabled>— {account.status} —</option>
              {transitions.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          )
        )}

        {/* Bind */}
        {!showBind ? (
          <button onClick={() => setShowBind(true)}
            className="flex h-7 sm:h-8 items-center gap-1 rounded-lg px-1.5 sm:px-2 text-xs text-ink-soft/50 transition-colors hover:bg-indigo-50 hover:text-indigo-600"
            title={boundSession ? 'Switch' : 'Bind'}>
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></svg>
            <span className="hidden sm:inline">{boundSession ? 'Switch' : 'Bind'}</span>
          </button>
        ) : (
          <select className="rounded-lg border border-gray-200 px-2 py-1 sm:py-1.5 text-xs max-w-[130px]" autoFocus onBlur={() => setShowBind(false)}
            defaultValue={boundSession ? String(boundSession.id) : ''}
            onChange={e => { if (e.target.value) onBind(parseInt(e.target.value, 10)); else if (boundSession) onUnbind(boundSession.id); setShowBind(false) }}>
            <option value="">— unbind —</option>
            {availableSessions.map(s => <option key={s.id} value={s.id}>{s.name} ({s.status})</option>)}
          </select>
        )}

        <Button variant="ghost" size="sm" onClick={onEdit}>Edit</Button>
        <button onClick={onDelete} className="flex h-7 w-7 sm:h-8 sm:w-8 items-center justify-center rounded-lg text-ink-soft/30 transition-colors hover:bg-red-50 hover:text-red-500" title="Delete">
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
        </button>
      </div>
    </div>
  )
}