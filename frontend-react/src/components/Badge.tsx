import clsx from 'clsx'
import type { AccountStatus, TaskStatus, SessionStatus, GridStatus } from '@/types'

type Status = AccountStatus | TaskStatus | SessionStatus | GridStatus

const styles: Record<string, string> = {
  ONLINE: 'bg-emerald-100 text-emerald-800',
  OFFLINE: 'bg-red-100 text-red-800',
  UNKNOWN: 'bg-gray-200 text-gray-600',
  WAIT_LOGIN: 'bg-amber-100 text-amber-800',
  ACTIVE: 'bg-emerald-100 text-emerald-800',
  IN_USE: 'bg-blue-100 text-blue-800',
  LOGIN_EXPIRED: 'bg-red-100 text-red-800',
  DISABLED: 'bg-gray-200 text-gray-600',
  ERROR: 'bg-red-100 text-red-800',
  PENDING: 'bg-amber-100 text-amber-800',
  RUNNING: 'bg-blue-100 text-blue-800',
  COMPLETED: 'bg-emerald-100 text-emerald-800',
  FAILED: 'bg-red-100 text-red-800',
  CANCELLED: 'bg-gray-200 text-gray-600',
  CREATING: 'bg-amber-100 text-amber-800',
  READY: 'bg-blue-100 text-blue-800',
  LOGIN: 'bg-blue-100 text-blue-800',
  CLOSED: 'bg-gray-200 text-gray-600',
}

export function Badge({ status }: { status: Status }) {
  return (
    <span className={clsx('inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold', styles[status] ?? 'bg-gray-100 text-gray-600')}>
      {status}
    </span>
  )
}