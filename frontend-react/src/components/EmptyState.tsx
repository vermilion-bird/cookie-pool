import type { ReactNode } from 'react'

export function EmptyState({ icon = '🍪', message }: { icon?: ReactNode; message: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-5 py-12">
      <div className="mb-3 text-3xl opacity-40">{icon}</div>
      <p className="max-w-xs text-center text-sm text-ink-soft/60">{message}</p>
    </div>
  )
}

export function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="p-3">
          <span className="block h-4 animate-pulse rounded bg-gray-100" style={{ width: `${60 + Math.random() * 40}%` }} />
        </td>
      ))}
    </tr>
  )
}

export function SkeletonCard() {
  return (
    <div className="animate-pulse rounded-xl border border-gray-100 bg-white p-5 shadow-card">
      <div className="mb-3 h-4 w-1/3 rounded bg-gray-100" />
      <div className="mt-3 space-y-2">
        <div className="h-3 w-full rounded bg-gray-100" />
        <div className="h-3 w-3/4 rounded bg-gray-100" />
      </div>
    </div>
  )
}