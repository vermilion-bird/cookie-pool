import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardSection, CardHeader } from '@/components/Card'
import { Button } from '@/components/Button'
import { Badge } from '@/components/Badge'
import { FilterBar } from '@/components/FilterBar'
import { EmptyState, SkeletonCard } from '@/components/EmptyState'
import { LoginModal } from '@/components/LoginModal'
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
  YouTube: '▶️',
  Google: '🔍',
  Facebook: '📘',
  TikTok: '🎵',
  Instagram: '📷',
  Twitter: '𝕏',
  LinkedIn: '💼',
}

function getIcon(platform: string, name: string): string {
  for (const [key, icon] of Object.entries(platformIcons)) {
    if (platform.toLowerCase().includes(key.toLowerCase())) return icon
  }
  return '🔑'
}

export function Accounts() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState<FilterValue>('ALL')
  const [name, setName] = useState('')
  const [platform, setPlatform] = useState('')
  const [selectedGridId, setSelectedGridId] = useState<number | string>('')
  const [showCreate, setShowCreate] = useState(false)
  const [loginAccountId, setLoginAccountId] = useState<number | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['accounts'],
    queryFn: api.accounts.list,
    refetchInterval: loginAccountId !== null ? false : 15000,
  })

  const { data: gridData } = useQuery({
    queryKey: ['grids'],
    queryFn: api.grids.list,
  })

  const accounts = data?.accounts ?? []
  const grids = gridData?.grids ?? []
  const filtered = useMemo(
    () => (filter === 'ALL' ? accounts : accounts.filter(a => a.status === filter)),
    [accounts, filter],
  )

  const createMutation = useMutation({
    mutationFn: () =>
      api.accounts.create({
        name: name.trim(),
        platform: platform.trim(),
        grid_id: selectedGridId ? parseInt(selectedGridId as string, 10) : null,
      }),
    onSuccess: () => {
      toast(`Created "${name}"`, 'success')
      setName('')
      setPlatform('')
      setSelectedGridId('')
      setShowCreate(false)
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
    },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.accounts.remove(id),
    onSuccess: (_, id) => {
      const acc = accounts.find(a => a.id === id)
      toast(`Deleted "${acc?.name ?? id}"`, 'success')
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
    },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  function handleCreate() {
    if (!name.trim() || !platform.trim()) {
      toast('Name and platform are required', 'error')
      return
    }
    createMutation.mutate()
  }

  function handleDelete(acc: Account) {
    if (!confirm(`Delete "${acc.name}"? This cannot be undone.`)) return
    deleteMutation.mutate(acc.id)
  }

  function gridName(acc: Account): string {
    if (!acc.grid_id) return 'Default'
    const g = grids.find(g => g.id === acc.grid_id)
    return g ? g.name : `Grid #${acc.grid_id}`
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Accounts</h1>
          <p className="page-subtitle">{accounts.length} account(s) · {filtered.length} showing</p>
        </div>
        <Button variant="success" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'Cancel' : '+ New Account'}
        </Button>
      </div>

      {/* Create Account form */}
      {showCreate && (
        <Card>
          <CardHeader title="New Account" subtitle="Register a platform account for manual login via noVNC" />
          <CardSection>
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[140px] flex-1">
                <label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Account Name</label>
                <input
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm placeholder:text-gray-300"
                  placeholder="google_ads_01"
                  value={name}
                  onChange={e => setName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleCreate()}
                />
              </div>
              <div className="min-w-[140px] flex-1">
                <label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Platform</label>
                <input
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm placeholder:text-gray-300"
                  placeholder="ads.google.com"
                  value={platform}
                  onChange={e => setPlatform(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleCreate()}
                />
              </div>
              <div className="min-w-[150px] flex-1">
                <label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Grid</label>
                <select
                  className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
                  value={selectedGridId}
                  onChange={e => setSelectedGridId(e.target.value)}
                >
                  <option value="">Default</option>
                  {grids.map(g => (
                    <option key={g.id} value={g.id}>{g.name}</option>
                  ))}
                </select>
              </div>
              <Button variant="success" loading={createMutation.isPending} onClick={handleCreate}>
                Create Account
              </Button>
            </div>
          </CardSection>
        </Card>
      )}

      {/* Account list */}
      <Card>
        <FilterBar options={filterOptions} value={filter} onChange={setFilter} />
        {isLoading ? (
          <div className="space-y-2 p-5">
            {[1, 2, 3].map(i => <SkeletonCard key={i} />)}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon="🍪"
            message={accounts.length === 0 ? 'No accounts yet. Create your first account above.' : 'No accounts match this filter.'}
          />
        ) : (
          <div className="divide-y divide-gray-100">
            {filtered.map(acc => (
              <AccountItem
                key={acc.id}
                account={acc}
                icon={getIcon(acc.platform, acc.name)}
                gridName={gridName(acc)}
                onLogin={() => setLoginAccountId(acc.id)}
                onDelete={() => handleDelete(acc)}
              />
            ))}
          </div>
        )}
      </Card>

      {/* Login modal */}
      {loginAccountId !== null && (
        <LoginModal accountId={loginAccountId} onClose={() => setLoginAccountId(null)} />
      )}
    </div>
  )
}

function AccountItem({
  account,
  icon,
  gridName,
  onLogin,
  onDelete,
}: {
  account: Account
  icon: string
  gridName: string
  onLogin: () => void
  onDelete: () => void
}) {
  const last = account.last_login_at || account.last_used_at
  const isLoginable = account.status !== 'IN_USE'

  return (
    <div className="flex flex-wrap items-center gap-4 px-5 py-4 transition-colors hover:bg-gray-50/70 sm:gap-6">
      {/* Icon & Name */}
      <div className="flex items-center gap-3 min-w-0 flex-[2]">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-base">
          {icon}
        </span>
        <div className="min-w-0">
          <div className="text-sm font-semibold text-ink truncate">{account.name}</div>
          <div className="text-xs text-ink-soft/50">{account.platform}</div>
        </div>
      </div>

      {/* Status & Grid */}
      <div className="flex items-center gap-3">
        <Badge status={account.status} />
        <span className="text-xs text-ink-soft/40 font-mono">{gridName}</span>
      </div>

      {/* Last activity */}
      <div className="hidden text-xs text-ink-soft/40 lg:block">
        {last ? `Last: ${timeAgo(last)}` : 'Never used'}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5">
        <Button variant="success" size="sm" disabled={!isLoginable} onClick={onLogin}>
          Login
        </Button>
        <button
          onClick={onDelete}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft/30 transition-colors hover:bg-red-50 hover:text-red-500"
          title="Delete account"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </div>
  )
}