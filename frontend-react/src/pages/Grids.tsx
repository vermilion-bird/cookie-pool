import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Card, CardHeader } from '@/components/Card'
import { Button } from '@/components/Button'
import { Badge } from '@/components/Badge'
import { Modal } from '@/components/Modal'
import { EmptyState, SkeletonRow } from '@/components/EmptyState'
import { useToast } from '@/hooks/useToast'
import { fmtDate } from '@/lib/format'
import type { GridInstance } from '@/types'

export function Grids() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [editGrid, setEditGrid] = useState<GridInstance | null>(null)

  // Form state
  const [formName, setFormName] = useState('')
  const [formHubUrl, setFormHubUrl] = useState('')
  const [formNovnc, setFormNovnc] = useState('')
  const [formMaxSessions, setFormMaxSessions] = useState(1)
  const [formNotes, setFormNotes] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['grids'],
    queryFn: api.grids.list,
    refetchInterval: 30000,
  })

  const grids = data?.grids ?? []

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['grids'] })

  function resetForm() {
    setFormName('')
    setFormHubUrl('')
    setFormNovnc('')
    setFormMaxSessions(1)
    setFormNotes('')
  }

  function populateEdit(g: GridInstance) {
    setFormName(g.name)
    setFormHubUrl(g.hub_url)
    setFormNovnc(g.novnc_base_url ?? '')
    setFormMaxSessions(g.max_sessions)
    setFormNotes(g.notes)
  }

  const createMutation = useMutation({
    mutationFn: () => api.grids.create({
      name: formName.trim(), hub_url: formHubUrl.trim(),
      novnc_base_url: formNovnc.trim(), max_sessions: formMaxSessions, notes: formNotes.trim(),
    }),
    onSuccess: () => { toast('Grid created', 'success'); setShowCreate(false); resetForm(); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const updateMutation = useMutation({
    mutationFn: () => api.grids.update(editGrid!.id, {
      name: formName.trim(), hub_url: formHubUrl.trim(),
      novnc_base_url: formNovnc.trim() || null, max_sessions: formMaxSessions, notes: formNotes.trim(),
    } as any),
    onSuccess: () => { toast('Grid updated', 'success'); setEditGrid(null); resetForm(); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.grids.remove(id),
    onSuccess: () => { toast('Grid deleted', 'success'); invalidate() },
    onError: (e: Error) => toast('Failed: ' + e.message, 'error'),
  })

  const checkMutation = useMutation({
    mutationFn: (id: number) => api.grids.check(id),
    onSuccess: (data) => { toast(`${data.name}: ${data.status} (${data.nodes} node(s))`, data.status === 'ONLINE' ? 'success' : 'error'); invalidate() },
    onError: (e: Error) => toast('Check failed: ' + e.message, 'error'),
  })

  const modalOpen = showCreate || editGrid !== null
  const modalTitle = editGrid ? `Edit Grid #${editGrid.id}` : '➕ New Grid'

  function handleSave() {
    if (!formName.trim() || !formHubUrl.trim()) {
      toast('Name and Hub URL are required', 'error'); return
    }
    if (editGrid) updateMutation.mutate()
    else createMutation.mutate()
  }

  function handleClose() {
    setShowCreate(false); setEditGrid(null); resetForm()
  }

  function handleDelete(g: GridInstance) {
    if (!confirm(`Delete grid "${g.name}"? Accounts assigned to it will need reassignment.`)) return
    deleteMutation.mutate(g.id)
  }

  return (
    <>
      <Card>
        <CardHeader
          title="🌐 Grid Instances"
          subtitle={`${grids.length} grid(s) configured`}
          action={
            <Button variant="green" size="sm" onClick={() => setShowCreate(true)}>
              + Add Grid
            </Button>
          }
        />
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left text-[0.7rem] font-semibold uppercase tracking-wide text-ink-soft">
              <th className="border-b border-gray-100 bg-gray-50 p-3">ID</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Name</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Hub URL</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Status</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Max Sessions</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Created</th>
              <th className="border-b border-gray-100 bg-gray-50 p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRow cols={7} />
            ) : grids.length === 0 ? (
              <tr><td colSpan={7}><EmptyState icon="🌐" message="No grids configured. Add one to manage Selenium Grid instances." /></td></tr>
            ) : (
              grids.map((g) => (
                <tr key={g.id} className="hover:bg-gray-50">
                  <td className="border-b border-gray-100 p-3 font-mono text-sm text-ink-soft">#{g.id}</td>
                  <td className="border-b border-gray-100 p-3 text-sm font-semibold">{g.name}</td>
                  <td className="border-b border-gray-100 p-3 text-xs font-mono text-gray-400">{g.hub_url}</td>
                  <td className="border-b border-gray-100 p-3"><Badge status={g.status} /></td>
                  <td className="border-b border-gray-100 p-3 text-sm">{g.max_sessions}</td>
                  <td className="border-b border-gray-100 p-3 text-xs text-gray-400">{fmtDate(g.created_at)}</td>
                  <td className="border-b border-gray-100 p-3">
                    <div className="flex flex-wrap gap-1.5">
                      <Button variant="default" size="sm" loading={checkMutation.isPending} onClick={() => checkMutation.mutate(g.id)}>🔍 Check</Button>
                      <Button variant="ghost" size="sm" onClick={() => { setEditGrid(g); populateEdit(g) }}>Edit</Button>
                      <Button variant="red" size="sm" onClick={() => handleDelete(g)} disabled={g.id === 1}>🗑</Button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </Card>

      {(showCreate || editGrid) && (
        <Modal open title={modalTitle} onClose={handleClose}
          footer={
            <>
              <Button variant="green" loading={createMutation.isPending || updateMutation.isPending} onClick={handleSave}>Save</Button>
              <Button variant="ghost" onClick={handleClose}>Cancel</Button>
            </>
          }>
          <div className="flex flex-col gap-3 mt-2">
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-400">Name</label>
              <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-ink focus:outline-none" placeholder="e.g. US West Grid" value={formName} onChange={(e) => setFormName(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-400">Hub URL</label>
              <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono focus:border-ink focus:outline-none" placeholder="http://selenium-hub:4444" value={formHubUrl} onChange={(e) => setFormHubUrl(e.target.value)} />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-gray-400">noVNC Base URL (optional)</label>
              <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono focus:border-ink focus:outline-none" placeholder="http://host:7901/vnc.html" value={formNovnc} onChange={(e) => setFormNovnc(e.target.value)} />
            </div>
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="mb-1 block text-xs font-medium text-gray-400">Max Sessions</label>
                <input type="number" min={1} className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-ink focus:outline-none" value={formMaxSessions} onChange={(e) => setFormMaxSessions(parseInt(e.target.value) || 1)} />
              </div>
              <div className="flex-[2]">
                <label className="mb-1 block text-xs font-medium text-gray-400">Notes</label>
                <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm focus:border-ink focus:outline-none" placeholder="Optional" value={formNotes} onChange={(e) => setFormNotes(e.target.value)} />
              </div>
            </div>
          </div>
        </Modal>
      )}
    </>
  )
}