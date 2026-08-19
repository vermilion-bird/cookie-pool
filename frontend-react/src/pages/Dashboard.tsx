import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { Card, CardSection, CardHeader } from '@/components/Card'
import { StatBox } from '@/components/StatBox'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { EmptyState, SkeletonCard } from '@/components/EmptyState'
import { fmtDate, timeAgo } from '@/lib/format'
import type { Account, GridInstance, Task } from '@/types'

export function Dashboard() {
  const { data: acctData, isLoading: acctLoading } = useQuery({
    queryKey: ['accounts'], queryFn: () => api.accounts.list(), refetchInterval: 15000,
  })
  const { data: gridData, isLoading: gridLoading } = useQuery({
    queryKey: ['grids'], queryFn: api.grids.list, refetchInterval: 30000,
  })
  const { data: taskData, isLoading: taskLoading } = useQuery({
    queryKey: ['tasks'], queryFn: () => api.tasks.list(), refetchInterval: 10000,
  })

  const accounts = acctData?.accounts ?? []
  const grids = gridData?.grids ?? []
  const tasks = taskData?.tasks ?? []
  const onlineGrids = grids.filter(g => g.status === 'ONLINE')

  const activeCount = accounts.filter(a => a.status === 'ACTIVE').length
  const inUseCount = accounts.filter(a => a.status === 'IN_USE').length
  const waitCount = accounts.filter(a => a.status === 'WAIT_LOGIN').length
  const expiredCount = accounts.filter(a => a.status === 'LOGIN_EXPIRED').length

  const recentTasks = [...tasks].sort((a, b) => {
    const da = a.created_at ? new Date(a.created_at).getTime() : 0
    const db = b.created_at ? new Date(b.created_at).getTime() : 0
    return db - da
  }).slice(0, 5)

  const recentAccounts = [...accounts]
    .filter(a => a.last_used_at || a.last_login_at)
    .sort((a, b) => {
      const da = a.last_used_at || a.last_login_at || ''
      const db = b.last_used_at || b.last_login_at || ''
      return db.localeCompare(da)
    })
    .slice(0, 5)

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="mb-7">
        <h1 className="page-title">Dashboard</h1>
        <p className="page-subtitle">Overview of your Cookie Pool infrastructure</p>
      </div>

      {/* Stats row */}
      {acctLoading ? (
        <div className="mb-6 grid grid-cols-2 sm:flex sm:flex-wrap gap-3 sm:gap-4">
          {[1,2,3,4].map(i => <div key={i} className="h-20 sm:h-24 animate-pulse rounded-xl bg-white shadow-card" />)}
        </div>
      ) : (
        <div className="mb-8 grid grid-cols-2 sm:flex sm:flex-wrap gap-3 sm:gap-4">
          <StatBox label="Total" value={accounts.length} icon="📊" />
          <StatBox label="Active" value={activeCount} accent="active" icon="✅" />
          <StatBox label="In Use" value={inUseCount} accent="inuse" icon="🔒" />
          <StatBox label="Waiting" value={waitCount} accent="wait" icon="⏳" />
          <StatBox label="Expired" value={expiredCount} accent="expired" icon="⚠️" />
        </div>
      )}

      <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Grid Overview */}
        <Card>
          <CardHeader
            title="🌐 Grid Instances"
            subtitle={`${onlineGrids.length}/${grids.length} online · ${grids.reduce((s, g) => s + g.max_sessions, 0)} total slots`}
            action={<Link to="/grids"><Button variant="text" size="sm">Manage →</Button></Link>}
          />
          {gridLoading ? (
            <CardSection><SkeletonCard /></CardSection>
          ) : grids.length === 0 ? (
            <CardSection><EmptyState icon="🌐" message="No grids configured yet." /></CardSection>
          ) : (
            <div className="divide-y divide-gray-100">
              {grids.map(g => (
                <GridRow key={g.id} grid={g} />
              ))}
            </div>
          )}
        </Card>

        {/* Recently Used Accounts */}
        <Card>
          <CardHeader
            title="👤 Recently Used"
            subtitle="Latest account activity"
            action={<Link to="/accounts"><Button variant="text" size="sm">View all →</Button></Link>}
          />
          {acctLoading ? (
            <CardSection><SkeletonCard /></CardSection>
          ) : recentAccounts.length === 0 ? (
            <CardSection><EmptyState icon="👤" message="No recent account activity." /></CardSection>
          ) : (
            <div className="divide-y divide-gray-100">
              {recentAccounts.map(a => (
                <AccountRow key={a.id} account={a} />
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recent Tasks */}
        <Card>
          <CardHeader
            title="⚡ Recent Tasks"
            subtitle="Latest 5 automation task runs"
            action={<Link to="/tasks"><Button variant="text" size="sm">View all →</Button></Link>}
          />
          {taskLoading ? (
            <CardSection><SkeletonCard /></CardSection>
          ) : recentTasks.length === 0 ? (
            <CardSection><EmptyState icon="📭" message="No tasks yet." /></CardSection>
          ) : (
            <div className="divide-y divide-gray-100">
              {recentTasks.map(t => (
                <TaskRow key={t.id} task={t} accounts={accounts} />
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}

function GridRow({ grid }: { grid: GridInstance }) {
  return (
    <div className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-gray-50">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-ink truncate">{grid.name}</span>
          <Badge status={grid.status} />
        </div>
        <p className="mt-0.5 text-xs font-mono text-ink-soft/50 truncate">{grid.hub_url}</p>
      </div>
      <div className="text-xs text-ink-soft/60 whitespace-nowrap">{grid.max_sessions} slot(s)</div>
    </div>
  )
}

function AccountRow({ account }: { account: Account }) {
  const last = account.last_used_at || account.last_login_at
  return (
    <div className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-gray-50">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-ink truncate">{account.name}</span>
          <Badge status={account.status} />
        </div>
        <p className="mt-0.5 text-xs text-ink-soft/50 truncate">{account.platform}</p>
      </div>
      {last && <div className="text-xs text-ink-soft/40 whitespace-nowrap">{timeAgo(last)}</div>}
    </div>
  )
}function TaskRow({ task, accounts }: { task: Task; accounts: Account[] }) {
  const acc = accounts.find(a => a.id === task.account_id)
  return (
    <div className="flex items-center gap-3 px-5 py-3 transition-colors hover:bg-gray-50">
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-ink truncate">#{task.id} {task.type}</span>
          <Badge status={task.status} />
        </div>
        <p className="mt-0.5 text-xs text-ink-soft/50 truncate">{acc ? acc.name : `Account #${task.account_id}`}</p>
      </div>
      <div className="text-xs text-ink-soft/40 whitespace-nowrap">{fmtDate(task.created_at)}</div>
    </div>
  )
}