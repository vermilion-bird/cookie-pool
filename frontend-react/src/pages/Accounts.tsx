import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardHeader } from '@/components/Card'
import { Button } from '@/components/Button'
import { Badge } from '@/components/Badge'
import { FilterBar } from '@/components/FilterBar'
import { EmptyState, SkeletonRow } from '@/components/EmptyState'
import { LoginModal } from '@/components/LoginModal'
import { useToast } from '@/hooks/useToast'
import { fmtDate } from '@/lib/format'
import type { Account, AccountStatus } from '@/types'

type FilterValue = 'ALL' | AccountStatus

const filterOptions: { label: string; value: FilterValue }[] = [
  { label: 'All', value: 'ALL' },
  { label: 'Wait Login', value: 'WAIT_LOGIN' },
  { label: 'Active', value: 'ACTIVE' },
  { label: 'In Use', value: 'IN_USE' },
  { label: 'Expired', value: 'LOGIN_EXPIRED' }]

export function Accounts() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<FilterValue>('ALL')
  const [name, setName] = useState('')
  const [platform, setPlatform] = useState('')
  const [selectedGridId, setSelectedGridId] = useState<number | string>('')
  const [loginAccountId, setLoginAccountId] = useState<number | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['accounts'],
    queryFn: api.accounts.list,
    refetchInterval: (query) => (loginAccountId !== null ? false : (query.state.data ? 15000 : false)),
  })

  const { data: gridData } = useQuery({
    queryKey: ['grids'],
    queryFn: api.grids.list,
  })

  const accounts = data?.accounts ?? []
  const grids = gridData?.grids ?? []
  const filtered = useMemo(() => (filter === 'ALL' ? accounts : accounts.filter((a) => a.status === filter)), [accounts, filter])

  const createMutation = useMutation({
    mutationFn: () => api.accounts.create({
      name: name.trim(), platform: platform.trim(),
      grid_id: selectedGridId ? parseInt(selectedGridId as string, 10) : null,
    }),
    onSuccess: () => {
      toast(`Account "${name}" created`, 'success')
      setName('')
      setPlatform('')
      setSelectedGridId('')
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
    },
    onError: (e: Error) => toast('Failed to create: ' + e.message, 'error'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.accounts.remove(id),
    onSuccess: (_, id) => {
      const acc = accounts.find((a) => a.id === id)
      toast(`Account "${acc?.name ?? id}" deleted`, 'success')
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
    },
    onError: (e: Error) => toast('Failed to delete: ' + e.message, 'error'),
  })

  function handleCreate() {
    if (!name.trim() || !platform.trim()) {
      toast('Name and platform are required', 'error')
      return
    }
    createMutation.mutate()
  }

  function handleDelete(acc: Account) {
    if (!confirm(`Delete account "${acc.name}"? This cannot be undone.`)) return
    deleteMutation.mutate(acc.id)
  }

  function gridName(acc: Account): string {
    if (!acc.grid_id) return 'Default'
    const g = grids.find((g) => g.id === acc.grid_id)
    return g ? g.name : `Grid #${acc.grid_id}`
  }

  return (
    <>
      <Card>
        <CardHeader title="➕ New Account" subtitle="Register a platform account, then log in manually via noVNC" />
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[130px] flex-1">
            <label className="mb-1 block text-xs font-medium text-gray-400">Account Name</label>
            <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-ink focus:outline-none" placeholder="e.g. google_ads_01" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="min-w-[130px] flex-1">
            <label className="mb-1 block text-xs font-medium text-gray-400">Platform</label>
            <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-ink focus:outline-none" placeholder="e.g. ads.google.com" value={platform} onChange={(e) => setPlatform(e.target.value)} />
          </div>
          <div className="min-w-[140px] flex-1">
            <label className="mb-1 block text-xs font-medium text-gray-400">Grid</label>
            <select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-ink focus:outline-none" value={selectedGridId} onChange={(e) => setSelectedGridId(e.target.value)}>
              <option value="">Default</option>
              {grids.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}            </select>
          </div>
          <Button variant="green" loading={createMutation.isPending} onClick={handleCreate}>
            Create Account
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader title="📋 Accounts" subtitle={isLoading ? 'Loading...' : `${accounts.length} account(s) total · showing ${filtered.length}`} />
        <FilterBar options={filterOptions} value={filter} onChange={setFilter} />
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
              <th className="border-b border-gray-100 bg-gray-50 p-3">ID</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Name</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Platform</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Grid</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Status</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Last Login</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRow cols={7} />
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={7}>
                  <EmptyState message={accounts.length === 0 ? 'No accounts yet. Create one above to get started.' : 'No accounts match this filter.'} />
                </td>
              </tr>
            ) : (
              filtered.map((a) => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <td className="border-b border-gray-100 p-3 font-mono text-sm text-ink-soft">#{a.id}</td>
                  <td className="border-b border-gray-100 p-3 text-sm font-semibold">{a.name}</td>
                  <td className="border-b border-gray-100 p-3 text-sm text-gray-400">{a.platform}</td>
                  <td className="border-b border-gray-100 p-3 text-xs text-gray-400">{gridName(a)}</td>
                  <td className="border-b border-gray-100 p-3"><Badge status={a.status} /></td>
                  <td className="border-b border-gray-100 p-3 text-xs text-gray-400">{fmtDate(a.last_login_at)}</td>
                  <td className="border-b border-gray-100 p-3">
                    <div className="flex flex-wrap gap-1.5">
                      <Button variant="green" size="sm" disabled={a.status === 'IN_USE'} title={a.status === 'IN_USE' ? 'Account is in use' : undefined} onClick={() => setLoginAccountId(a.id)}>
                        🔑 Login
                      </Button>
                      <Button variant="red" size="sm" onClick={() => handleDelete(a)}>
                        🗑 Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>

      {loginAccountId !== null && <LoginModal accountId={loginAccountId} onClose={() => setLoginAccountId(null)} />}
    </>
  )
}