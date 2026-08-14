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
import type { GridInstance } from '@/types'

export function Grids() {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [showCreate, setShowCreate] = useState(false)
  const [editGrid, setEditGrid] = useState<GridInstance | null>(null)

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
  const onlineGrids = grids.filter(g => g.status === 'ONLINE')

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ['grids'] })

  function resetForm() {
    setFormName(''); setFormHubUrl(''); setFormNovnc('')
    setFormMaxSessions(1); setFormNotes('')
  }

  function populateEdit(g: GridInstance) {
    setFormName(g.name); setFormHubUrl(g.hub_url)
    setFormNovnc(g.novnc_base_url ?? '')
    setFormMaxSessions(g.max_sessions); setFormNotes(g.notes)
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
    onSuccess: (data) => {
      toast(`${data.name}: ${data.status} (${data.nodes} node(s))`, data.status === 'ONLINE' ? 'success' : 'error')
      invalidate()
    },
    onError: (e: Error) => toast('Check failed: ' + e.message, 'error'),
  })

  const modalOpen = showCreate || editGrid !== null
  const modalTitle = editGrid ? `Edit Grid #${editGrid.id}` : 'New Grid'

  function handleSave() {
    if (!formName.trim() || !formHubUrl.trim()) { toast('Name and Hub URL are required', 'error'); return }
    if (editGrid) updateMutation.mutate()
    else createMutation.mutate()
  }

  function handleClose() { setShowCreate(false); setEditGrid(null); resetForm() }

  function handleDelete(g: GridInstance) {
    if (!confirm(`Delete "${g.name}"? Accounts assigned to it will need reassignment.`)) return
    deleteMutation.mutate(g.id)
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="page-title">Grid Instances</h1>
          <p className="page-subtitle">{grids.length} configured · {onlineGrids.length} online · {grids.reduce((s, g) => s + g.max_sessions, 0)} total slots</p>
        </div>
        <Button variant="success" onClick={() => setShowCreate(true)}>+ Add Grid</Button>
      </div>

      {/* Grid list */}
      <Card>
        {isLoading ? (
          <div className="space-y-2 p-5">
            {[1, 2].map(i => <SkeletonCard key={i} />)}
          </div>
        ) : grids.length === 0 ? (
          <EmptyState icon="🌐" message="No grids configured. Add one to manage Selenium Grid instances." />
        ) : (
          <div className="divide-y divide-gray-100">
            {grids.map(g => (
              <GridItem
                key={g.id}
                grid={g}
                onCheck={() => checkMutation.mutate(g.id)}
                onEdit={() => { setEditGrid(g); populateEdit(g) }}
                onDelete={() => handleDelete(g)}
                checkLoading={checkMutation.isPending}
              />
            ))}
          </div>
        )}
      </Card>

      {/* Create / Edit Modal */}
      {modalOpen && (
        <Modal
          open
          title={modalTitle}
          onClose={handleClose}
          footer={
            <>
              <Button variant="primary" loading={createMutation.isPending || updateMutation.isPending} onClick={handleSave}>Save</Button>
              <Button variant="outline" onClick={handleClose}>Cancel</Button>
            </>
          }
        >
          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Name</label>
              <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm placeholder:text-gray-300" placeholder="US West Grid" value={formName} onChange={e => setFormName(e.target.value)} />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Hub URL</label>
              <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono placeholder:text-gray-300" placeholder="http://selenium-hub:4444" value={formHubUrl} onChange={e => setFormHubUrl(e.target.value)} />
            </div>
            <div>
              <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">noVNC Base URL <span className="text-ink-soft/30">(optional)</span></label>
              <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm font-mono placeholder:text-gray-300" placeholder="http://host:7901/vnc.html" value={formNovnc} onChange={e => setFormNovnc(e.target.value)} />
            </div>
            <div className="flex gap-4">
              <div className="flex-1">
                <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Max Sessions</label>
                <input type="number" min={1} className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm" value={formMaxSessions} onChange={e => setFormMaxSessions(parseInt(e.target.value) || 1)} />
              </div>
              <div className="flex-[2]">
                <label className="mb-1.5 block text-xs font-semibold text-ink-soft/50 uppercase tracking-wider">Notes <span className="text-ink-soft/30">(optional)</span></label>
                <input className="w-full rounded-lg border border-gray-200 px-3 py-2 text-sm placeholder:text-gray-300" placeholder="Optional notes" value={formNotes} onChange={e => setFormNotes(e.target.value)} />
              </div>
            </div>
          </div>
        </Modal>
      )}
    </div>
  )
}

function GridItem({
  grid,
  onCheck,
  onEdit,
  onDelete,
  checkLoading,
}: {
  grid: GridInstance
  onCheck: () => void
  onEdit: () => void
  onDelete: () => void
  checkLoading: boolean
}) {
  return (
    <div className="flex flex-wrap items-center gap-4 px-5 py-4 transition-colors hover:bg-gray-50/70 sm:gap-6">
      {/* Name & Status */}
      <div className="min-w-0 flex-[2]">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-ink truncate">{grid.name}</span>
          <Badge status={grid.status} />
        </div>
        <p className="mt-0.5 truncate font-mono text-xs text-ink-soft/40">{grid.hub_url}</p>
      </div>

      {/* Info */}
      <div className="hidden sm:flex items-center gap-4 text-xs text-ink-soft/50">
        <span title="Max concurrent sessions">{grid.max_sessions} slot(s)</span>
        <span>{fmtDate(grid.created_at)}</span>
        {grid.notes && <span className="text-ink-soft/30 truncate max-w-[120px]">{grid.notes}</span>}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5">
        <Button variant="outline" size="sm" loading={checkLoading} onClick={onCheck}>
          Check Health
        </Button>
        <Button variant="ghost" size="sm" onClick={onEdit}>
          Edit
        </Button>
        <button
          onClick={onDelete}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft/30 transition-colors hover:bg-red-50 hover:text-red-500"
          title={`Delete ${grid.name}`}
          disabled={grid.id === 1}
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </div>
  )
}