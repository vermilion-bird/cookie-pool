import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardHeader } from '@/components/Card'
import { Button } from '@/components/Button'
import { Badge } from '@/components/Badge'
import { FilterBar } from '@/components/FilterBar'
import { EmptyState, SkeletonRow } from '@/components/EmptyState'
import { Modal } from '@/components/Modal'
import { useToast } from '@/hooks/useToast'
import { fmtDate } from '@/lib/format'
import type { Task, TaskStatus } from '@/types'

type FilterValue = 'ALL' | TaskStatus

const filterOptions: { label: string; value: FilterValue }[] = [
  { label: 'All', value: 'ALL' },
  { label: 'Pending', value: 'PENDING' },
  { label: 'Running', value: 'RUNNING' },
  { label: 'Completed', value: 'COMPLETED' },
  { label: 'Failed', value: 'FAILED' },
]

export function Tasks() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<FilterValue>('ALL')
  const [accountId, setAccountId] = useState('')
  const [taskType, setTaskType] = useState('')
  const [params, setParams] = useState('{}')
  const [detailTask, setDetailTask] = useState<Task | null>(null)

  const { data: taskData, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: api.tasks.list,
    refetchInterval: 10000,
  })
  const { data: acctData } = useQuery({ queryKey: ['accounts'], queryFn: api.accounts.list })

  const tasks = taskData?.tasks ?? []
  const activeAccounts = (acctData?.accounts ?? []).filter((a) => a.status === 'ACTIVE')
  const filtered = useMemo(() => (filter === 'ALL' ? tasks : tasks.filter((t) => t.status === filter)), [tasks, filter])

  const invalidateTasks = () => queryClient.invalidateQueries({ queryKey: ['tasks'] })

  const createMutation = useMutation({
    mutationFn: () => api.tasks.create({ account_id: parseInt(accountId, 10), type: taskType.trim(), params }),
    onSuccess: () => {
      toast('Task created', 'success')
      setTaskType('')
      setParams('{}')
      invalidateTasks()
    },
    onError: (e: Error) => toast('Failed to create task: ' + e.message, 'error'),
  })

  const runMutation = useMutation({
    mutationFn: (id: number) => api.tasks.run(id),
    onMutate: (id) => toast(`Running task #${id}...`, 'info'),
    onSuccess: (_, id) => {
      toast(`Task #${id} finished`, 'success')
      invalidateTasks()
    },
    onError: (e: Error, id) => {
      toast(`Task #${id} failed: ` + e.message, 'error')
      invalidateTasks()
    },
  })

  const cancelMutation = useMutation({
    mutationFn: (id: number) => api.tasks.cancel(id),
    onSuccess: (_, id) => {
      toast(`Task #${id} cancelled`, 'success')
      invalidateTasks()
    },
    onError: (e: Error) => toast('Failed to cancel: ' + e.message, 'error'),
  })

  function handleCreate() {
    if (!accountId) {
      toast('Select an account', 'error')
      return
    }
    if (!taskType.trim()) {
      toast('Task type is required', 'error')
      return
    }
    try {
      JSON.parse(params || '{}')
    } catch {
      toast('Params must be valid JSON', 'error')
      return
    }
    createMutation.mutate()
  }

  return (
    <>
      <Card>
        <CardHeader title="➕ New Task" subtitle="Queue an automation task against an ACTIVE account" />
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[150px] flex-1">
            <label className="mb-1 block text-xs font-medium text-gray-400">Account</label>
            <select
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-ink focus:outline-none"
              value={accountId}
              onChange={(e) => setAccountId(e.target.value)}
            >
              <option value="">{activeAccounts.length === 0 ? 'No ACTIVE accounts available' : 'Select account...'}</option>
              {activeAccounts.map((a) => (
                <option key={a.id} value={a.id}>
                  #{a.id} — {a.name}
                </option>
              ))}
            </select>
          </div>
          <div className="min-w-[150px] flex-1">
            <label className="mb-1 block text-xs font-medium text-gray-400">Task Type</label>
            <input
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-ink focus:outline-none"
              placeholder="e.g. check_balance"
              value={taskType}
              onChange={(e) => setTaskType(e.target.value)}
            />
          </div>
          <div className="min-w-[150px] flex-[2]">
            <label className="mb-1 block text-xs font-medium text-gray-400">Params (JSON)</label>
            <input
              className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono focus:border-ink focus:outline-none"
              placeholder='{"url": "https://example.com"}'
              value={params}
              onChange={(e) => setParams(e.target.value)}
            />
          </div>
          <Button variant="green" loading={createMutation.isPending} onClick={handleCreate}>
            Create Task
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader
          title="📋 Tasks"
          subtitle={isLoading ? 'Loading...' : `${tasks.length} task(s) total · showing ${filtered.length}`}
          action={
            <Button variant="ghost" size="sm" onClick={invalidateTasks}>
              ↻ Refresh
            </Button>
          }
        />
        <FilterBar options={filterOptions} value={filter} onChange={setFilter} />
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
              <th className="border-b border-gray-100 bg-gray-50 p-3">ID</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Account</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Type</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Status</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Created</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRow cols={6} />
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6}>
                  <EmptyState icon="📭" message={tasks.length === 0 ? 'No tasks yet. Create one above.' : 'No tasks match this filter.'} />
                </td>
              </tr>
            ) : (
              filtered.map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="border-b border-gray-100 p-3 font-mono text-sm text-ink-soft">#{t.id}</td>
                  <td className="border-b border-gray-100 p-3 text-sm">{t.account_id}</td>
                  <td className="border-b border-gray-100 p-3 text-sm">{t.type}</td>
                  <td className="border-b border-gray-100 p-3">
                    <Badge status={t.status} />
                  </td>
                  <td className="border-b border-gray-100 p-3 text-xs text-gray-400">{fmtDate(t.created_at)}</td>
                  <td className="border-b border-gray-100 p-3">
                    <div className="flex flex-wrap gap-1.5">
                      {t.status === 'PENDING' && (
                        <Button variant="green" size="sm" loading={runMutation.isPending} onClick={() => runMutation.mutate(t.id)}>
                          ▶ Run
                        </Button>
                      )}
                      {(t.status === 'PENDING' || t.status === 'RUNNING') && (
                        <Button variant="red" size="sm" loading={cancelMutation.isPending} onClick={() => cancelMutation.mutate(t.id)}>
                          ✕ Cancel
                        </Button>
                      )}
                      <Button variant="ghost" size="sm" onClick={() => setDetailTask(t)}>
                        Detail
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>

      {detailTask && (
        <Modal open title="Task Detail" onClose={() => setDetailTask(null)}>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-gray-50 p-4 font-mono text-xs">{JSON.stringify(detailTask, null, 2)}</pre>
        </Modal>
      )}
    </>
  )
}