import { useMemo, useState } from 'react'
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
import type { Account, Task, TaskStatus } from '@/types'

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
  const [showCreate, setShowCreate] = useState(false)
  const [detailTask, setDetailTask] = useState<Task | null>(null)

  const { data: taskData, isLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: api.tasks.list,
    refetchInterval: 10000,
  })
  const { data: acctData } = useQuery({ queryKey: ['accounts'], queryFn: api.accounts.list })

  const tasks = taskData?.tasks ?? []
  const activeAccounts = (acctData?.accounts ?? []).filter(a => a.status === 'ACTIVE')
  const filtered = useMemo(() => (filter === 'ALL' ? tasks : tasks.filter(t => t.status === filter)), [tasks, filter])

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['tasks'] })

  const createMutation = useMutation({
    mutationFn: () => api.tasks.create({ account_id: parseInt(accountId, 10), type: taskType.trim(), params }),
    onSuccess: () => {
      toast('Task created', 'success')
      setTaskType(''); setParams('{}')
      invalidate()
    },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const runMutation = useMutation({
    mutationFn: (id: number) => api.tasks.run(id),
    onMutate: id => toast(`Running task #${id}...`, 'info'),
    onSuccess: (_, id) => { toast(`Task #${id} completed`, 'success'); invalidate() },
    onError: (e: Error, id) => { toast(`Task #${id} failed: ` + e.message, 'error'); invalidate() },
  })

  const cancelMutation = useMutation({
    mutationFn: (id: number) => api.tasks.cancel(id),
    onSuccess: (_, id) => { toast(`Task #${id} cancelled`, 'success'); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  function handleCreate() {
    if (!accountId) { toast('Select an account', 'error'); return }
    if (!taskType.trim()) { toast('Task type is required', 'error'); return }
    try { JSON.parse(params || '{}') } catch { toast('Params must be valid JSON', 'error'); return }
    createMutation.mutate()
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Tasks</h1>
          <p className="page-subtitle">{tasks.length} total · {tasks.filter(t => t.status === 'RUNNING').length} running · {tasks.filter(t => t.status === 'PENDING').length} pending</p>
        </div>
        <Button variant="success" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Cancel' : '+ New Task'}
        </Button>
      </div>

      {/* Create Task form */}
      {showCreate && (
        <Card>
          <CardHeader title="New Task" subtitle="Queue an automation task against an ACTIVE account" />
          <CardSection>
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[150px] flex-1">
                <label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Account</label>
                <select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={accountId} onChange={e => setAccountId(e.target.value)}>
                  <option value="">{activeAccounts.length === 0 ? 'No ACTIVE accounts' : 'Select account...'}</option>
                  {activeAccounts.map(a => (
                    <option key={a.id} value={a.id}>#{a.id} — {a.name}</option>
                  ))}
                </select>
              </div>
              <div className="min-w-[150px] flex-1">
                <label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Task Type</label>
                <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm placeholder:text-gray-300" placeholder="check_balance" value={taskType} onChange={e => setTaskType(e.target.value)} />
              </div>
              <div className="min-w-[150px] flex-[2]">
                <label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Params (JSON)</label>
                <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono placeholder:text-gray-300" placeholder='{"url": "https://..."}' value={params} onChange={e => setParams(e.target.value)} />
              </div>
              <Button variant="success" loading={createMutation.isPending} onClick={handleCreate}>
                Create Task
              </Button>
            </div>
          </CardSection>
        </Card>
      )}

      {/* Task list */}
      <Card>
        <FilterBar options={filterOptions} value={filter} onChange={setFilter} />
        {isLoading ? (
          <div className="space-y-2 p-5">
            {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState icon="📭" message={tasks.length === 0 ? 'No tasks yet. Create one above.' : 'No tasks match this filter.'} />
        ) : (
          <div className="divide-y divide-gray-100">
            {filtered.map(t => (
              <TaskItem
                key={t.id}
                task={t}
                accounts={acctData?.accounts ?? []}
                onRun={() => runMutation.mutate(t.id)}
                onCancel={() => cancelMutation.mutate(t.id)}
                onDetail={() => setDetailTask(t)}
              />
            ))}
          </div>
        )}
      </Card>

      {/* Detail Modal */}
      {detailTask && (
        <Modal open title={`Task #${detailTask.id} · ${detailTask.type}`} onClose={() => setDetailTask(null)}>
          <div className="space-y-3">
            <div className="flex items-center gap-3 text-sm">
              <span className="font-semibold text-ink-soft">Status:</span>
              <Badge status={detailTask.status} />
            </div>
            <div className="text-sm">
              <span className="font-semibold text-ink-soft">Account ID:</span>
              <span className="ml-2 text-ink-soft/70">{detailTask.account_id}</span>
            </div>
            {detailTask.created_at && (
              <div className="text-sm">
                <span className="font-semibold text-ink-soft">Created:</span>
                <span className="ml-2 text-ink-soft/70">{detailTask.created_at}</span>
              </div>
            )}
            {detailTask.started_at && (
              <div className="text-sm">
                <span className="font-semibold text-ink-soft">Started:</span>
                <span className="ml-2 text-ink-soft/70">{detailTask.started_at}</span>
              </div>
            )}
            {detailTask.completed_at && (
              <div className="text-sm">
                <span className="font-semibold text-ink-soft">Completed:</span>
                <span className="ml-2 text-ink-soft/70">{detailTask.completed_at}</span>
              </div>
            )}
            <div>
              <p className="mb-2 text-sm font-semibold text-ink-soft">Params:</p>
              <pre className="overflow-x-auto rounded-lg bg-gray-50 p-3 font-mono text-xs text-ink-soft">{JSON.stringify(JSON.parse(detailTask.params || '{}'), null, 2)}</pre>
            </div>
            {detailTask.result && (
              <div>
                <p className="mb-2 text-sm font-semibold text-ink-soft">Result:</p>
                <pre className="overflow-x-auto rounded-lg bg-gray-50 p-3 font-mono text-xs text-ink-soft">{detailTask.result}</pre>
              </div>
            )}
            {detailTask.error && (
              <div>
                <p className="mb-2 text-sm font-semibold text-red-600">Error:</p>
                <pre className="overflow-x-auto rounded-lg bg-red-50 p-3 font-mono text-xs text-red-700">{detailTask.error}</pre>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}

function TaskItem({
  task,
  accounts,
  onRun,
  onCancel,
  onDetail,
}: {
  task: Task
  accounts: Account[]
  onRun: () => void
  onCancel: () => void
  onDetail: () => void
}) {
  const acc = accounts.find(a => a.id === task.account_id)

  return (
    <div className="flex flex-wrap items-center gap-4 px-5 py-4 transition-colors hover:bg-gray-50/70 sm:gap-6">
      {/* Info */}
      <div className="min-w-0 flex-[2]">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-semibold text-ink">#{task.id}</span>
          <span className="text-sm text-ink-soft/80">{task.type}</span>
          <Badge status={task.status} />
        </div>
        <p className="mt-1 text-xs text-ink-soft/40">
          {acc ? acc.name : `Account #${task.account_id}`}
          {task.created_at && <> · {timeAgo(task.created_at)}</>}
        </p>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5">
        {task.status === 'PENDING' && (
          <Button variant="success" size="sm" onClick={onRun}>
            ▶ Run
          </Button>
        )}
        {(task.status === 'PENDING' || task.status === 'RUNNING') && (
          <Button variant="danger" size="sm" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button variant="ghost" size="sm" onClick={onDetail}>
          Detail
        </Button>
      </div>
    </div>
  )
}

