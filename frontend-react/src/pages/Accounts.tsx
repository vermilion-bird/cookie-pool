import { useMemo, useRef, useState } from 'react'
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
import type { Account, AccountStatus } from '@/types'

type FilterValue = 'ALL' | AccountStatus

const filterOptions: { label: string; value: FilterValue }[] = [
  { label: 'All', value: 'ALL' },
  { label: 'Waiting', value: 'WAIT_LOGIN' },
  { label: 'Active', value: 'ACTIVE' },
  { label: 'In Use', value: 'IN_USE' },
  { label: 'Expired', value: 'LOGIN_EXPIRED' },
]

const platformIcons: Record<string, string> = {
  YouTube: '▶️', Google: '🔍', Facebook: '📘',
  TikTok: '🎵', Instagram: '📷', Twitter: '𝕏', LinkedIn: '💼',
}

function getIcon(platform: string): string {
  for (const [key, icon] of Object.entries(platformIcons))
    if (platform.toLowerCase().includes(key.toLowerCase())) return icon
  return '🔑'
}

const emptyForm = { name: '', platform: '', notes: '', gridId: '' as number | string, loginIndicator: '' }

export function Accounts() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<FilterValue>('ALL')
  const [form, setForm] = useState(emptyForm)
  const [showCreate, setShowCreate] = useState(false)
  const [editAccount, setEditAccount] = useState<Account | null>(null)
  const [editForm, setEditForm] = useState(emptyForm)
  const [sessionId, setSessionId] = useState<string>('')
  const [editingSessionId, setEditingSessionId] = useState<string>('')

  const { data, isLoading } = useQuery({ queryKey: ['accounts'], queryFn: api.accounts.list, refetchInterval: 15000 })
  const { data: gridData } = useQuery({ queryKey: ['grids'], queryFn: api.grids.list })
  const { data: sessionData } = useQuery({ queryKey: ['sessions'], queryFn: api.sessions.list })

  const accounts = data?.accounts ?? []
  const grids = gridData?.grids ?? []
  const sessions = sessionData?.sessions ?? []
  const filtered = useMemo(() => filter === 'ALL' ? accounts : accounts.filter(a => a.status === filter), [accounts, filter])

  const invalidate = () => {
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
        api.sessions.bindAccount(parseInt(sessionId, 10), acc.id).then(() => { toast(`Bound to session #${sessionId}`, 'success'); invalidate() }).catch(() => toast('Created but bind failed — bind manually', 'error'))
      }
      invalidate()
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
        api.sessions.bindAccount(parseInt(editingSessionId, 10), accId).then(() => { toast(`Bound to session #${editingSessionId}`, 'success'); invalidate() }).catch(() => toast('Updated but bind failed', 'error'))
      }
      invalidate()
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

  const importFileRef = useRef<HTMLInputElement>(null)
  const importMutation = useMutation({
    mutationFn: (file: File) => api.accounts.importCsv(file),
    onSuccess: (data) => { toast(`Imported ${data.created} account(s)`, 'success'); invalidate() },
    onError: (e: Error) => toast('Import failed: ' + e.message, 'error'),
  })

  function handleCreate() { if (!form.name.trim() || !form.platform.trim()) { toast('Name and platform are required', 'error'); return }; createMutation.mutate() }
  function handleSaveEdit() { if (!editForm.name.trim() || !editForm.platform.trim()) { toast('Name and platform are required', 'error'); return }; updateMutation.mutate() }
  function handleDelete(acc: Account) { if (!confirm(`Delete "${acc.name}"?`)) return; deleteMutation.mutate(acc.id) }
  function openEdit(acc: Account) {
    setEditForm({ name: acc.name, platform: acc.platform, notes: acc.notes || '', gridId: acc.grid_id ?? '', loginIndicator: acc.login_indicator || '' })
    setEditAccount(acc); setEditingSessionId('')
  }
  function gridName(acc: Account): string {
    if (!acc.grid_id) return 'Default'
    return grids.find(g => g.id === acc.grid_id)?.name ?? `Grid #${acc.grid_id}`
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><h1 className="page-title">Accounts</h1><p className="page-subtitle">{accounts.length} account(s) · {sessions.length} session(s) · {filtered.length} showing</p></div>
        <div className="flex items-center gap-2">
          <Button variant="outline" loading={importMutation.isPending} onClick={() => importFileRef.current?.click()}>⬆ Import CSV</Button>
          <input ref={importFileRef} type="file" accept=".csv,text/csv" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) importMutation.mutate(f); e.target.value = '' }} />
          <Button variant="success" onClick={() => setShowCreate(!showCreate)}>{showCreate ? 'Cancel' : '+ New Account'}</Button>
        </div>
      </div>

      {showCreate && (
        <Card>
          <CardHeader title="New Account" subtitle="Define a platform account, then bind it to a Session for login." />
          <CardSection>
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[120px] flex-1"><label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Name</label>
                <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" placeholder="tiktok_ads_01" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} onKeyDown={e => e.key === 'Enter' && handleCreate()} /></div>
              <div className="min-w-[120px] flex-1"><label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Platform</label>
                <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" placeholder="ads.tiktok.com" value={form.platform} onChange={e => setForm({ ...form, platform: e.target.value })} onKeyDown={e => e.key === 'Enter' && handleCreate()} /></div>
              <div className="min-w-[110px] flex-1"><label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Grid</label>
                <select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={form.gridId} onChange={e => setForm({ ...form, gridId: e.target.value })}><option value="">Default</option>{grids.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
              <div className="min-w-[130px] flex-1"><label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Bind to Session</label>
                <select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={sessionId} onChange={e => setSessionId(e.target.value)}><option value="">None</option>{sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
              <Button variant="success" loading={createMutation.isPending} onClick={handleCreate}>Create</Button>
            </div>
          </CardSection>
        </Card>
      )}

      <Card>
        <FilterBar options={filterOptions} value={filter} onChange={setFilter} />
        {isLoading ? <div className="space-y-2 p-5">{[1, 2, 3].map(i => <SkeletonCard key={i} />)}</div>
        : filtered.length === 0 ? <EmptyState icon="🍪" message={accounts.length === 0 ? 'No accounts yet.' : 'No accounts match this filter.'} />
        : <div className="divide-y divide-gray-100">
            {filtered.map(acc => (
              <AccountItem key={acc.id} account={acc} icon={getIcon(acc.platform)} gridName={gridName(acc)}
                sessions={sessions} onEdit={() => openEdit(acc)} onDelete={() => handleDelete(acc)}
                onBind={(sessId) => bindMutation.mutate({ accId: acc.id, sessId })} />
            ))}
          </div>}
      </Card>

      {editAccount && (
        <Modal open title={`Edit Account #${editAccount.id}`} onClose={() => setEditAccount(null)}
          footer={<><Button variant="primary" loading={updateMutation.isPending} onClick={handleSaveEdit}>Save</Button><Button variant="outline" onClick={() => setEditAccount(null)}>Cancel</Button></>}>
          <div className="space-y-4">
            <div><label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Name</label><input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={editForm.name} onChange={e => setEditForm({ ...editForm, name: e.target.value })} /></div>
            <div><label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Platform</label><input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={editForm.platform} onChange={e => setEditForm({ ...editForm, platform: e.target.value })} /></div>
            <div><label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Grid</label><select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={editForm.gridId} onChange={e => setEditForm({ ...editForm, gridId: e.target.value })}><option value="">Default</option>{grids.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
            <div><label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Bind to Session</label><select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={editingSessionId} onChange={e => setEditingSessionId(e.target.value)}><option value="">None</option>{sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function AccountItem({ account, icon, gridName, sessions, onEdit, onDelete, onBind }: {
  account: Account; icon: string; gridName: string; sessions: { id: number; name: string }[];
  onEdit: () => void; onDelete: () => void; onBind: (sessId: number) => void;
}) {
  const last = account.last_login_at || account.last_used_at

  return (
    <div className="flex flex-wrap items-center gap-4 px-5 py-4 transition-colors hover:bg-gray-50/70 sm:gap-6">
      <div className="flex items-center gap-3 min-w-0 flex-[2]">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-base">{icon}</span>
        <div className="min-w-0"><div className="text-sm font-semibold text-ink truncate">{account.name}</div><div className="text-xs text-ink-soft/50">{account.platform}</div></div>
      </div>
      <div className="flex items-center gap-3"><Badge status={account.status} /><span className="text-xs text-ink-soft/40 font-mono">{gridName}</span></div>
      <div className="hidden text-xs text-ink-soft/40 lg:block">{last ? `Last: ${timeAgo(last)}` : 'Never used'}</div>
      <div className="flex items-center gap-1.5">
        <select className="rounded-lg border border-gray-200 px-2 py-1.5 text-xs text-ink-soft/70"
          defaultValue="" onChange={e => { if (e.target.value) onBind(parseInt(e.target.value, 10)) }}>
          <option value="">+Session</option>
          {sessions.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <Button variant="ghost" size="sm" onClick={onEdit}>Edit</Button>
        <button onClick={onDelete} className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft/30 transition-colors hover:bg-red-50 hover:text-red-500" title="Delete">
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
        </button>
      </div>
    </div>
  )
}