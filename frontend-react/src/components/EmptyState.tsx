import type { ReactNode } from 'react'

export function EmptyState({ icon = '🍪', message }: { icon?: ReactNode; message: string }) {
  return (
    <div className="py-10 text-center text-gray-400">
      <div className="mb-2 text-4xl opacity-50">{icon}</div>
      <p className="text-sm">{message}</p>
    </div>
  )
}

export function SkeletonRow({ cols }: { cols: number }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="p-3">
          <span className="block h-3.5 animate-pulse rounded bg-gray-100" />
        </td>
      ))}
    </tr>
  )
}