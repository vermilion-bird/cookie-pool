import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardSection, CardHeader } from '@/components/Card'
import { Button } from '@/components/Button'
import { Badge } from '@/components/Badge'
import { Modal } from '@/components/Modal'
import { EmptyState, SkeletonCard } from '@/components/EmptyState'
import { useToast } from '@/hooks/useToast'
import { fmtDate } from '@/lib/format'
import type { Schedule, Account, TaskTypeMeta } from '@/types'

const emptyForm = { name: '', cron: '0 9 * * *', taskType: 'visit_url', params: '{}', accountId: '' as number | string, enabled: true }

export function Schedules() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [editSchedule, setEditSchedule] = useState<Schedule | null>(null)
  const [form, setForm] = useState(emptyForm)
  const [page, setPage] = useState(1)
  const pageSize = 20

  const { data, isLoading } = useQuery({ queryKey: ['schedules', { page, page_size: pageSize }], queryFn: () => api.schedules.list({ page, page_size: pageSize }), refetchInterval: 30000 })
  const { data: acctData } = useQuery({ queryKey: ['accounts'], queryFn: () => api.accounts.list() })
  const { data: typeData } = useQuery({ queryKey: ['task-types'], queryFn: () => api.tasks.types() })

  const schedules = data?.schedules ?? []
  const total = data?.total ?? 0
  const totalPages = data?.total_pages ?? 1
  const accounts = acctData?.accounts ?? []
  const types = typeData?.types ?? []

  const invalidate = () => {
    setPage(1)
    queryClient.invalidateQueries({ queryKey: ['schedules'] })
    queryClient.invalidateQueries({ queryKey: ['tasks'] })
  }

  function resetForm() { setForm(emptyForm) }
  function populateEdit(s: Schedule) {
    setForm({
      name: s.name, cron: s.cron, taskType: s.task_type,
      params: s.params, accountId: s.account_id ?? '', enabled: s.enabled,
    })
  }

  function accountLabel(id: number | null): string {
    if (id === null) return 'All ACTIVE accounts'
    const a = accounts.find(x => x.id === id)
    return a ? a.name : `Account #${id}`
  }

  const createMutation = useMutation({
    mutationFn: () => api.schedules.create({
      name: form.name.trim(), cron: form.cron.trim(), task_type: form.taskType.trim(),
      params: form.params, account_id: form.accountId ? parseInt(form.accountId as string, 10) : null,
      enabled: form.enabled,
    }),
    onSuccess: () => { toast('Schedule created', 'success'); setShowCreate(false); resetForm(); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const updateMutation = useMutation({
    mutationFn: () => api.schedules.update(editSchedule!.id, {
      name: form.name.trim(), cron: form.cron.trim(), task_type: form.taskType.trim(),
      params: form.params, account_id: form.accountId ? parseInt(form.accountId as string, 10) : null,
      enabled: form.enabled,
    }),
    onSuccess: () => { toast('Schedule updated', 'success'); setEditSchedule(null); resetForm(); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.schedules.remove(id),
    onSuccess: () => { toast('Schedule deleted', 'success'); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const triggerMutation = useMutation({
    mutationFn: (id: number) => api.schedules.trigger(id),
    onSuccess: (data) => { toast(`Triggered ${data.triggered} task(s)`, 'success'); invalidate() },
    onError: (e: Error) => toast('Trigger failed: ' + e.message, 'error'),
  })

  function handleSave() {
    if (!form.name.trim() || !form.cron.trim() || !form.taskType.trim()) {
      toast('Name, cron and task type are required', 'error'); return
    }
    try { JSON.parse(form.params || '{}') } catch { toast('Params must be valid JSON', 'error'); return }
    if (editSchedule) updateMutation.mutate()
    else createMutation.mutate()
  }

  const modalOpen = showCreate || editSchedule !== null
  const modalTitle = editSchedule ? `Edit Schedule #${editSchedule.id}` : 'New Schedule'

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Schedules</h1>
          <p className="page-subtitle">{schedules.length} scheduled · {schedules.filter(s => s.enabled).length} enabled</p>
        </div>
        <Button variant="success" onClick={() => setShowCreate(true)}>+ New Schedule</Button>
      </div>

      <Card>
        {isLoading ? (
          <div className="space-y-2 p-5">{[1, 2].map(i => <SkeletonCard key={i} />)}</div>
        ) : schedules.length === 0 ? (
          <EmptyState icon="⏰" message="No schedules yet. Add a cron schedule to automate tasks." />
        ) : (
          <div className="divide-y divide-gray-100">
            {schedules.map(s => (
              <div key={s.id} className="flex flex-wrap items-center gap-4 px-5 py-4 transition-colors hover:bg-gray-50/70 sm:gap-6">
                <div className="min-w-0 flex-[2]">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ink truncate">{s.name}</span>
                    <Badge status={s.enabled ? 'ACTIVE' : 'DISABLED'} />
                  </div>
                  <p className="mt-0.5 font-mono text-xs text-ink-soft/50">{s.cron} · {s.task_type}</p>
                </div>
                <div className="hidden text-xs text-ink-soft/50 md:block">
                  <div>{accountLabel(s.account_id)}</div>
                  {s.next_run_at && <div className="mt-0.5 text-ink-soft/40">Next: {fmtDate(s.next_run_at)}</div>}
                </div>
                <div className="flex items-center gap-1.5">
                  <Button variant="outline" size="sm" loading={triggerMutation.isPending} onClick={() => {
                    if (confirm(`Trigger "${s.name}" now?`)) triggerMutation.mutate(s.id)
                  }}>Trigger</Button>
                  <Button variant="ghost" size="sm" onClick={() => { setEditSchedule(s); populateEdit(s) }}>Edit</Button>
                  <button
                    onClick={() => { if (confirm(`Delete schedule "${s.name}"?`)) deleteMutation.mutate(s.id) }}
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft/30 transition-colors hover:bg-red-50 hover:text-red-500"
                    title="Delete schedule"
                  >
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between py-3 px-1">
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {total} schedules &middot; Page {page} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page <= 1}
              className="px-3 py-1 text-sm rounded-lg border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">Prev</button>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages}
              className="px-3 py-1 text-sm rounded-lg border border-gray-300 dark:border-gray-600 disabled:opacity-40 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors">Next</button>
          </div>
        </div>
      )}

      {modalOpen && (
        <Modal
          open
          title={modalTitle}
          onClose={() => { setShowCreate(false); setEditSchedule(null); resetForm() }}
          footer={
            <>
              <Button variant="primary" loading={createMutation.isPending || updateMutation.isPending} onClick={handleSave}>Save</Button>
              <Button variant="outline" onClick={() => { setShowCreate(false); setEditSchedule(null); resetForm() }}>Cancel</Button>
            </>
          }
        >
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Name</label>
                <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" placeholder="daily check" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} />
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Cron <span className="text-ink-soft/30">(分 时 日 月 周1-7)</span></label>
                <input className="w-full rounded-lg border border-gray-200 px-3 py-2 font-mono text-sm" value={form.cron} onChange={e => setForm({ ...form, cron: e.target.value })} />
              </div>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Task Type</label>
                <select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={form.taskType}
                  onChange={e => {
                    const t = types.find(x => x.type === e.target.value)
                    setForm({ ...form, taskType: e.target.value, params: t ? JSON.stringify(t.params_template, null, 2) : form.params })
                  }}>
                  {types.map(t => <option key={t.type} value={t.type}>{t.type} — {t.description}</option>)}
                </select>
              </div>
              <div>
                <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Target Account</label>
                <select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={form.accountId}
                  onChange={e => setForm({ ...form, accountId: e.target.value })}>
                  <option value="">All ACTIVE accounts</option>
                  {accounts.map(a => <option key={a.id} value={a.id}>#{a.id} — {a.name}</option>)}
                </select>
              </div>
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Params (JSON)</label>
              <textarea className="w-full rounded-lg border border-gray-200 px-3 py-2 font-mono text-sm" rows={4} value={form.params} onChange={e => setForm({ ...form, params: e.target.value })} />
            </div>
            <label className="flex items-center gap-2 text-sm text-ink-soft/70">
              <input type="checkbox" checked={form.enabled} onChange={e => setForm({ ...form, enabled: e.target.checked })} className="h-4 w-4 rounded" />
              Enabled
            </label>
          </div>
        </Modal>
      )}
    </div>
  )
}