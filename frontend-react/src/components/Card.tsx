import type { ReactNode } from 'react'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`mb-6 rounded-xl border border-gray-100 bg-white p-6 shadow-sm ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({
  title,
  subtitle,
  action,
}: {
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <div>
        <h2 className="text-[1.05rem] font-semibold text-ink">{title}</h2>
        {subtitle && <div className="mt-0.5 text-xs text-gray-400">{subtitle}</div>}
      </div>
      {action}
    </div>
  )
}