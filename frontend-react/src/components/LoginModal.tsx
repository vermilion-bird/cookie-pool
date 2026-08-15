import { useEffect, useRef, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { Modal } from './Modal'
import { Button } from './Button'
import { useToast } from '@/hooks/useToast'

type Step = 'connecting' | 'ready' | 'complete' | 'error' | 'success'

export function LoginModal({ accountId, onClose }: { accountId: number; onClose: () => void }) {
  const toast = useToast()
  const queryClient = useQueryClient()
  const [step, setStep] = useState<Step>('connecting')
  const [novncUrl, setNovncUrl] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const started = useRef(false)
  useEffect(() => {
    if (started.current) return
    started.current = true
    api.accounts
      .startLogin(accountId)
      .then(data => {
        setNovncUrl(data.novnc_url)
        setStep('ready')
        queryClient.invalidateQueries({ queryKey: ['accounts'] })
      })
      .catch(e => {
        setError(e.message)
        setStep('error')
      })
  }, [accountId, queryClient])

  const completeMutation = useMutation({
    mutationFn: () => api.accounts.completeLogin(accountId),
    onSuccess: data => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      if (data.status === 'ok') {
        setStep('success')
        toast('Login confirmed — account is now ACTIVE', 'success')
        setTimeout(onClose, 1500)
      } else {
        toast('Login not detected. Try again.', 'error')
      }
    },
    onError: (e: Error) => {
      toast('Failed: ' + e.message, 'error')
      setError(e.message)
      setStep('error')
    },
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
      size="xl"
      footer={
        step !== 'success' && (
          <>
            <Button
              variant="success"
              loading={completeMutation.isPending}
              onClick={() => completeMutation.mutate()}
              disabled={step !== 'ready'}
            >
              ✔ Login Complete
            </Button>
            <Button variant="outline" loading={cancelMutation.isPending} onClick={() => cancelMutation.mutate()}>
              Cancel
            </Button>
          </>
        )
      }
    >
      {/* Step indicator */}
      <div className="mb-5 flex items-center justify-center gap-2">
        <StepDot label="Connect" active={step === 'connecting'} done={step !== 'connecting' && step !== 'error'} />
        <StepLine active={step !== 'connecting' && step !== 'error'} />
        <StepDot label="Login" active={step === 'ready'} done={step === 'complete' || step === 'success'} />
        <StepLine active={step === 'complete' || step === 'success'} />
        <StepDot label="Done" active={step === 'complete'} done={step === 'success'} />
      </div>

      {/* Connecting state */}
      {step === 'connecting' && (
        <div className="flex flex-col items-center justify-center py-12">
          <svg className="mb-4 h-10 w-10 animate-spin text-brand" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2.5" opacity="0.15" />
            <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
          </svg>
          <p className="text-sm font-medium text-ink">Creating browser session...</p>
          <p className="mt-1 text-xs text-ink-soft/50">Launching Chromium with the account profile</p>
        </div>
      )}

      {/* Error state */}
      {step === 'error' && (
        <div className="flex flex-col items-center justify-center py-12">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-500">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
            </svg>
          </div>
          <p className="text-sm font-medium text-ink">Failed to start session</p>
          <p className="mt-1 text-xs text-ink-soft/60">{error}</p>
        </div>
      )}

      {/* Browser ready */}
      {step === 'ready' && novncUrl && (
        <div>
          <div className="mb-3 flex items-center justify-between rounded-lg bg-indigo-50 px-4 py-2.5 text-sm text-indigo-700">
            <span>
              <span className="text-base">👆</span>{' '}
              Log in to the target platform below. Click <strong>Login Complete</strong> when done.
            </span>
            <a
              href={novncUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-medium text-indigo-500 underline transition-colors hover:text-indigo-700"
            >
              Open in new tab ↗
            </a>
          </div>
          <div className="overflow-hidden rounded-xl border border-gray-200 bg-gray-900 shadow-inner">
            <iframe
              src={novncUrl}
              className="block w-full"
              style={{ height: 'calc(90vh - 240px)', minHeight: '600px' }}
              title="noVNC Browser"
            />
          </div>
        </div>
      )}

      {/* Success state */}
      {step === 'success' && (
        <div className="flex flex-col items-center justify-center py-12">
          <div className="mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50">
            <svg className="h-7 w-7 text-emerald-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          </div>
          <p className="text-base font-semibold text-ink">Login Complete!</p>
          <p className="mt-1 text-sm text-ink-soft/50">Account is now ACTIVE. Closing...</p>
        </div>
      )}
    </Modal>
  )
}

function StepDot({ label, active, done }: { label: string; active: boolean; done: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold transition-colors ${
          done ? 'bg-emerald-500 text-white' : active ? 'bg-brand text-white ring-4 ring-brand-light' : 'bg-gray-200 text-gray-400'
        }`}
      >
        {done ? '✓' : '-'}
      </div>
      <span className={`text-xs font-medium ${active || done ? 'text-ink' : 'text-gray-300'}`}>{label}</span>
    </div>
  )
}

function StepLine({ active }: { active: boolean }) {
  return <div className={`h-0.5 w-8 rounded-full transition-colors ${active ? 'bg-brand' : 'bg-gray-200'}`} />
}