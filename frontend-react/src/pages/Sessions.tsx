import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, getApiKey } from '@/lib/api'
import { Card, CardSection, CardHeader } from '@/components/Card'
import { Button } from '@/components/Button'
import { Badge } from '@/components/Badge'
import { Modal } from '@/components/Modal'
import { EmptyState, SkeletonCard } from '@/components/EmptyState'
import { useToast } from '@/hooks/useToast'
import { timeAgo } from '@/lib/format'
import type { SessionV2 } from '@/types'

export function Sessions() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [nodeId, setNodeId] = useState<string>('')
  const [detailId, setDetailId] = useState<number | null>(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [cookiePlatform, setCookiePlatform] = useState('')
  const [cookieResult, setCookieResult] = useState('')

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
    queryClient.invalidateQueries({ queryKey: ['accounts'] })
  }

  const { data, isLoading } = useQuery({ queryKey: ['sessions'], queryFn: api.sessions.list, refetchInterval: 20000 })
  const { data: gridData } = useQuery({ queryKey: ['grids'], queryFn: api.grids.list })

  const sessions = data?.sessions ?? []
  const grids = gridData?.grids ?? []
  const detailSession = sessions.find(s => s.id === detailId) ?? null

  const createMutation = useMutation({
    mutationFn: () => api.sessions.create({ name: name.trim(), node_id: parseInt(nodeId, 10) || 1 }),
    onSuccess: () => { toast('Session created', 'success'); setName(''); setNodeId(''); setShowCreate(false); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.sessions.remove(id),
    onSuccess: () => { toast('Deleted', 'success'); setDetailId(null); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const unbindMutation = useMutation({
    mutationFn: ({ sid, aid }: { sid: number; aid: number }) => api.sessions.unbindAccount(sid, aid),
    onSuccess: () => { toast('Unbound', 'success'); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  async function startSession(id: number) {
    setActionLoading(true)
    try { await api.sessions.startLogin(id); toast('Browser started', 'success'); invalidate() }
    catch (e: any) { toast('Failed: ' + e.message, 'error') }
    finally { setActionLoading(false) }
  }

  async function completeSession(id: number) {
    try { await api.sessions.completeLogin(id); toast('Session ACTIVE', 'success'); invalidate() }
    catch (e: any) { toast('Failed: ' + e.message, 'error') }
  }

  async function stopSession(id: number) {
    if (!confirm('Stop this browser? Bound accounts will need re-login.')) return
    try { await fetch(`/api/sessions/${id}/login/cancel`, { method: 'POST', headers: { 'X-API-Key': getApiKey() } }); toast('Stopped', 'success'); invalidate() }
    catch (e: any) { toast('Failed: ' + e.message, 'error') }
  }

  async function extractCookies(sessionId: number) {
    try {
      const p = cookiePlatform.trim()
      const url = p ? `/api/sessions/${sessionId}/cookies/plain?platform=${encodeURIComponent(p)}` : `/api/sessions/${sessionId}/cookies/plain`
      const text = await (await fetch(url, { headers: { 'X-API-Key': getApiKey() } })).text()
      setCookieResult(text || '(empty)')
      if (text) navigator.clipboard.writeText(text).then(() => toast('Copied!', 'success')).catch(() => {})
    } catch (e: any) { toast('Failed: ' + e.message, 'error') }
  }

  function actionButton(s: SessionV2) {
    switch (s.status) {
      case 'IDLE': case 'CLOSED': case 'FAILED':
        return <Button variant="success" size="sm" loading={actionLoading} onClick={() => startSession(s.id)}>Start</Button>
      case 'LOGIN': case 'CREATING': case 'READY':
        return <Button variant="success" size="sm" onClick={() => completeSession(s.id)}>Complete</Button>
      case 'ACTIVE':
        return <Button variant="outline" size="sm" onClick={() => stopSession(s.id)}>Stop</Button>
      default:
        return <Button variant="primary" size="sm" loading={actionLoading} onClick={() => startSession(s.id)}>Start</Button>
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Sessions</h1>
          <p className="page-subtitle">{sessions.length} session(s) · {sessions.filter(s => s.status === 'ACTIVE').length} active</p>
        </div>
        <Button variant="success" onClick={() => setShowCreate(!showCreate)}>{showCreate ? 'Cancel' : '+ New Session'}</Button>
      </div>

      {showCreate && (
        <Card>
          <CardHeader title="New Session" subtitle="Create a persistent browser session to host multiple platform accounts" />
          <CardSection>
            <div className="flex flex-wrap items-end gap-3">
              <div className="min-w-[160px] flex-1"><label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Name</label>
                <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" placeholder="ad-pool-01" value={name} onChange={e => setName(e.target.value)} onKeyDown={e => e.key === 'Enter' && !createMutation.isPending && createMutation.mutate()} /></div>
              <div className="min-w-[140px] flex-1"><label className="mb-1 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Node</label>
                <select className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={nodeId} onChange={e => setNodeId(e.target.value)}>{grids.filter(g => g.status === 'ONLINE').map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select></div>
              <Button variant="success" loading={createMutation.isPending} onClick={() => { if (!name.trim()) { toast('Name required', 'error'); return } createMutation.mutate() }}>Create</Button>
            </div>
          </CardSection>
        </Card>
      )}

      <Card>
        {isLoading ? <div className="space-y-2 p-5">{[1, 2].map(i => <SkeletonCard key={i} />)}</div>
        : sessions.length === 0 ? <EmptyState icon="🖥️" message="No sessions yet. Create one to get started." />
        : <div className="divide-y divide-gray-100">
            {sessions.map(s => (
              <div key={s.id} className="flex flex-wrap items-center gap-4 px-5 py-4 transition-colors hover:bg-gray-50/70 sm:gap-6">
                <div className="min-w-0 flex-[2]">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-ink truncate cursor-pointer hover:text-brand" onClick={() => setDetailId(s.id)}>{s.name}</span>
                    <Badge status={s.status as any} />
                  </div>
                  <p className="mt-0.5 text-xs text-ink-soft/40">{s.accounts?.length || 0} account(s) · {grids.find(g => g.id === s.node_id)?.name ?? `Node #${s.node_id}`}</p>
                </div>
                <div className="hidden text-xs text-ink-soft/40 sm:block">{s.created_at ? timeAgo(s.created_at) : ''}</div>
                <div className="flex items-center gap-1.5">
                  {actionButton(s)}
                  <Button variant="ghost" size="sm" onClick={() => setDetailId(s.id)}>Detail</Button>
                  <button onClick={() => { if (confirm(`Delete "${s.name}"?`)) deleteMutation.mutate(s.id) }}
                    className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft/30 transition-colors hover:bg-red-50 hover:text-red-500"><svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}><path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg></button>
                </div>
              </div>
            ))}
          </div>}
      </Card>

      {detailSession && (
        <Modal open title={`Session: ${detailSession.name}`} size="wide" onClose={() => { setDetailId(null); setCookieResult('') }}
          footer={<div className="flex w-full flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">{actionButton(detailSession)}</div>
            <Button variant="outline" size="sm" onClick={() => { if (confirm('Delete?')) deleteMutation.mutate(detailSession.id) }}>Delete</Button>
          </div>}>
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium">Status:</span><Badge status={detailSession.status as any} />
              <span className="text-xs text-ink-soft/40">Node: {grids.find(g => g.id === detailSession.node_id)?.name ?? '?'}</span>
              {detailSession.novnc_url && <a href={detailSession.novnc_url} target="_blank" rel="noopener noreferrer" className="ml-auto text-xs text-brand underline">noVNC ↗</a>}
            </div>

            {/* noVNC — shown when ACTIVE or LOGIN */}
            {(detailSession.status === 'ACTIVE' || detailSession.status === 'LOGIN') && detailSession.novnc_url && (
              <div>
                <div className="mb-2 flex items-center justify-between"><span className="text-sm font-medium">noVNC Browser</span>
                  <a href={detailSession.novnc_url} target="_blank" rel="noopener noreferrer" className="text-xs text-brand underline">Open in new tab ↗</a></div>
                <div className="overflow-hidden rounded-xl border border-gray-200 bg-gray-900"><iframe src={detailSession.novnc_url} className="block w-full" style={{ height: '480px' }} title="noVNC" /></div>
                {detailSession.status === 'LOGIN' && <p className="mt-2 text-xs text-ink-soft/50">Log in to all platforms, then click "Complete".</p>}
              </div>
            )}

            <div>
              <h4 className="mb-2 text-sm font-semibold">Bound Accounts ({detailSession.accounts?.length || 0})</h4>
              {!detailSession.accounts?.length ? <p className="text-xs text-ink-soft/40">None. Go to Accounts page to bind.</p>
              : <div className="divide-y divide-gray-100 rounded-lg border">
                  {detailSession.accounts.map(sa => (
                    <div key={sa.id} className="flex items-center gap-3 px-4 py-2.5">
                      <span className="min-w-[90px] rounded bg-gray-100 px-2 py-0.5 text-xs font-mono text-ink-soft/60">{sa.platform}</span>
                      <span className="text-sm">{sa.account?.name ?? `#${sa.account_id}`}</span><Badge status={sa.account?.status ?? 'WAIT_LOGIN'} />
                      <button onClick={() => unbindMutation.mutate({ sid: detailSession.id, aid: sa.account_id })} className="ml-auto text-xs text-red-400 hover:text-red-600">Unbind</button>
                    </div>))}
                </div>}
            </div>

            {(detailSession.status === 'ACTIVE' || detailSession.status === 'LOGIN') && (
              <div>
                <h4 className="mb-2 text-sm font-semibold">Extract Cookies</h4>
                <div className="flex items-center gap-2">
                  <input className="flex-1 rounded-lg border border-gray-200 px-3 py-1.5 text-sm font-mono" placeholder="tiktok.com (or empty for all)" value={cookiePlatform} onChange={e => setCookiePlatform(e.target.value)} onKeyDown={e => e.key === 'Enter' && extractCookies(detailSession.id)} />
                  <Button variant="primary" size="sm" onClick={() => extractCookies(detailSession.id)}>Extract & Copy</Button>
                </div>
                {cookieResult && <pre className="mt-2 max-h-32 overflow-auto rounded-lg bg-gray-50 p-3 text-xs font-mono text-ink-soft/70 break-all">{cookieResult}</pre>}
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  )
}