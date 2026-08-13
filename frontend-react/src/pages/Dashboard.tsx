import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api } from '@/lib/api'
import { Card, CardHeader } from '@/components/Card'
import { StatBox } from '@/components/StatBox'
import { Badge } from '@/components/Badge'
import { Button } from '@/components/Button'
import { EmptyState, SkeletonRow } from '@/components/EmptyState'
import { fmtDate } from '@/lib/format'

export function Dashboard() {
  const { data: acctData, isLoading: acctLoading } = useQuery({
    queryKey: ['accounts'],
    queryFn: api.accounts.list,
    refetchInterval: 15000,
  })
  const { data: gridData, isLoading: gridLoading } = useQuery({
    queryKey: ['grids'],
    queryFn: api.grids.list,
    refetchInterval: 30000,
  })
  const { data: taskData, isLoading: taskLoading } = useQuery({
    queryKey: ['tasks'],
    queryFn: api.tasks.list,
    refetchInterval: 10000,
  })
  const { data: health, isError: healthError } = useQuery({
    queryKey: ['health'],
    queryFn: api.health,
    refetchInterval: 15000,
    retry: false,
  })

  const accounts = acctData?.accounts ?? []
  const grids = gridData?.grids ?? []
  const tasks = taskData?.tasks ?? []
  const onlineGrids = grids.filter((g) => g.status === 'ONLINE')

  return (
    <>
      {/* Account Stats */}
      <div className="mb-6 flex flex-wrap gap-4">
        <StatBox label="Total Accounts" value={acctLoading ? '–' : accounts.length} />
        <StatBox label="Active" value={acctLoading ? '–' : accounts.filter((a) => a.status === 'ACTIVE').length} accent="active" />
        <StatBox label="In Use" value={acctLoading ? '–' : accounts.filter((a) => a.status === 'IN_USE').length} accent="inuse" />
        <StatBox label="Expired" value={acctLoading ? '–' : accounts.filter((a) => a.status === 'LOGIN_EXPIRED').length} accent="expired" />
      </div>

      {/* Grid Overview */}
      <Card>
        <CardHeader
          title="🌐 Grid Overview"
          subtitle={`${onlineGrids.length}/${grids.length} online`}
          action={
            <Link to="/grids">
              <Button variant="ghost" size="sm">Manage Grids →</Button>
            </Link>
          }
        />
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
              <th className="border-b border-gray-100 bg-gray-50 p-3">Name</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Hub URL</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Status</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Nodes</th>
            </tr>
          </thead>
          <tbody>
            {gridLoading ? (
              <SkeletonRow cols={4} />
            ) : grids.length === 0 ? (
              <tr>
                <td colSpan={4}>
                  <EmptyState icon="🌐" message="No grids configured." />
                </td>
              </tr>
            ) : (
              grids.map((g) => (
                <tr key={g.id} className="hover:bg-gray-50">
                  <td className="border-b border-gray-100 p-3 text-sm font-semibold">{g.name}</td>
                  <td className="border-b border-gray-100 p-3 text-xs font-mono text-gray-400">{g.hub_url}</td>
                  <td className="border-b border-gray-100 p-3"><Badge status={g.status} /></td>
                  <td className="border-b border-gray-100 p-3 text-sm">{'~'}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>

      {/* Recent Tasks */}
      <Card>
        <CardHeader
          title="📋 Recent Tasks"
          subtitle="Latest 10 automation task runs"
          action={
           <Link to="/tasks">
              <Button variant="ghost" size="sm">
                View all →
              </Button>
            </Link>
          }
        />
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
              <th className="border-b border-gray-100 bg-gray-50 p-3">ID</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Account</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Type</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Status</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Created</th>
            </tr>
          </thead>
          <tbody>
            {taskLoading ? (
              <SkeletonRow cols={5} />
            ) : tasks.length === 0 ? (
              <tr>
                <td colSpan={5}>
                  <EmptyState icon="📭" message="No tasks yet. Create one on the Tasks page." />
                </td>
              </tr>
            ) : (
              tasks.slice(0, 10).map((t) => (
                <tr key={t.id} className="hover:bg-gray-50">
                  <td className="border-b border-gray-100 p-3 font-mono text-sm text-ink-soft">#{t.id}</td>
                  <td className="border-b border-gray-100 p-3 text-sm">{t.account_id}</td>
                  <td className="border-b border-gray-100 p-3 text-sm">{t.type}</td>
                  <td className="border-b border-gray-100 p-3"><Badge status={t.status} /></td>
                  <td className="border-b border-gray-100 p-3 text-xs text-gray-400">{fmtDate(t.created_at)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>
    </>
  )
}