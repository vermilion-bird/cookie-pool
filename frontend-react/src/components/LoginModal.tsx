import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Modal } from './Modal'
import { Button } from './Button'
import { useToast } from '@/hooks/useToast'

export function LoginModal({ accountId, onClose }: { accountId: number; onClose: () => void }) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [novncUrl, setNovncUrl] = useState<string | null>(null)
  const [status, setStatus] = useState<string>('')
  const [starting, setStarting] = useState(true)
  const [startError, setStartError] = useState<string | null>(null)

  // Kick off login session creation once, on mount
  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    api.accounts
      .startLogin(accountId)
      .then((data) => {
        setNovncUrl(data.novnc_url)
        queryClient.invalidateQueries({ queryKey: ['accounts'] })
      })
      .catch((e) => setStartError(e.message))
      .finally(() => setStarting(false))
  }, [accountId, queryClient])

  const completeMutation = useMutation({
    mutationFn: () => api.accounts.completeLogin(accountId),
    onSuccess: (data) => {
      setStatus(data.message)
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      if (data.status === 'ok') {
        toast('Login confirmed — account is now ACTIVE', 'success')
        setTimeout(onClose, 1200)
      }
    },
    onError: (e: Error) => setStatus('Error: ' + e.message),
  })

  const cancelMutation = useMutation({
    mutationFn: () => api.accounts.cancelLogin(accountId),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      onClose()
    },
  })

  return (
    <Modal
      open
      title={`Login Account #${accountId}`}
      onClose={() => cancelMutation.mutate()}
      footer={
        <>
          <Button variant="green" loading={completeMutation.isPending} onClick={() => completeMutation.mutate()} disabled={!novncUrl}>
            ✅ Login Complete
          </Button>
          <Button variant="red" loading={cancelMutation.isPending} onClick={() => cancelMutation.mutate()}>
            ✕ Cancel
          </Button>
        </>
      }
    >
      {starting && <p className="flex items-center gap-2 text-sm text-gray-400"><span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-gray-300 border-t-ink" /> Creating browser session...</p>}
      {startError && (
        <div className="py-10 text-center text-gray-400">
          <div className="mb-2 text-4xl opacity-50">⚠️</div>
          <p className="text-sm">{startError}</p>
        </div>
      )}
      {novncUrl && (
        <>
          <p className="mb-1.5 text-sm text-gray-500">1. Log in to the target platform in the browser below</p>
          <p className="mb-1.5 text-sm text-gray-500">
            2. Click <strong>✓ Login Complete</strong> when done
          </p>
          <iframe src={novncUrl} className="my-3 h-[500px] w-full rounded-md border border-gray-200 bg-black" />
        </>
      )}
      {status && <div className="min-h-[1.3em] py-1 text-sm text-gray-500">{status}</div>}
    </Modal>
  )
}