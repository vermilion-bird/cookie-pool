import clsx from 'clsx'
import type { AccountStatus, TaskStatus, SessionStatus, GridStatus } from '@/types'

type Status = AccountStatus | TaskStatus | SessionStatus | GridStatus

const dotStyles: Record<string, string> = {
  ONLINE: 'bg-emerald-500',
  OFFLINE: 'bg-red-500',
  UNKNOWN: 'bg-gray-400',
  WAIT_LOGIN: 'bg-amber-500',
  ACTIVE: 'bg-emerald-500',
  IN_USE: 'bg-blue-500',
  LOGIN_EXPIRED: 'bg-red-500',
  DISABLED: 'bg-gray-400',
  ERROR: 'bg-red-500',
  PENDING: 'bg-amber-500',
  RUNNING: 'bg-blue-500',
  COMPLETED: 'bg-emerald-500',
  FAILED: 'bg-red-500',
  CANCELLED: 'bg-gray-400',
  CREATING: 'bg-amber-500',
  READY: 'bg-blue-500',
  LOGIN: 'bg-indigo-500',
  CLOSED: 'bg-gray-400',
}

const labelStyles: Record<string, string> = {
  ONLINE: 'text-emerald-700',
  OFFLINE: 'text-red-700',
  UNKNOWN: 'text-gray-500',
  WAIT_LOGIN: 'text-amber-700',
  ACTIVE: 'text-emerald-700',
  IN_USE: 'text-blue-700',
  LOGIN_EXPIRED: 'text-red-700',
  DISABLED: 'text-gray-500',
  ERROR: 'text-red-700',
  PENDING: 'text-amber-700',
  RUNNING: 'text-blue-700',
  COMPLETED: 'text-emerald-700',
  FAILED: 'text-red-700',
  CANCELLED: 'text-gray-500',
  CREATING: 'text-amber-700',
  READY: 'text-blue-700',
  LOGIN: 'text-indigo-700',
  CLOSED: 'text-gray-500',
}

export function Badge({ status }: { status: Status }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-gray-50 px-2.5 py-1">
      <span className={clsx('h-1.5 w-1.5 rounded-full', dotStyles[status] ?? 'bg-gray-400')} />
      <span className={clsx('text-[0.7rem] font-semibold uppercase tracking-wider', labelStyles[status] ?? 'text-gray-600')}>
        {status === 'WAIT_LOGIN' ? 'WAITING' : status === 'LOGIN_EXPIRED' ? 'EXPIRED' : status === 'IN_USE' ? 'IN USE' : status}
      </span>
    </span>
  )
}