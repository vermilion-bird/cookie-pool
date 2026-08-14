import type { ReactNode } from 'react'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-xl border border-gray-100 bg-white shadow-card ${className}`}>
      {children}
    </div>
  )
}

export function CardSection({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className={`border-b border-gray-100 px-5 py-4 last:border-b-0 ${className}`}>
      {children}
    </div>
  )
}

export function CardHeader({ title, subtitle, action, className = '' }: { title: string; subtitle?: string; action?: ReactNode; className?: string }) {
  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 px-5 py-4 ${className}`}>
      <div className="min-w-0 flex-1">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        {subtitle && <p className="mt-0.5 text-[0.7rem] text-ink-soft/60">{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}