import clsx from 'clsx'

interface StatBoxProps {
  label: string
  value: number | string
  icon?: string
  accent?: 'active' | 'inuse' | 'expired' | 'wait'
}

const accentConfig = {
  active: { dot: 'bg-emerald-500', border: 'border-l-emerald-500', bg: 'from-emerald-50 to-white' },
  inuse: { dot: 'bg-blue-500', border: 'border-l-blue-500', bg: 'from-blue-50 to-white' },
  expired: { dot: 'bg-red-500', border: 'border-l-red-500', bg: 'from-red-50 to-white' },
  wait: { dot: 'bg-amber-500', border: 'border-l-amber-500', bg: 'from-amber-50 to-white' },
}

export function StatBox({ label, value, icon, accent }: StatBoxProps) {
  const cfg = accent ? accentConfig[accent] : null

  return (
    <div
      className={clsx(
        'relative flex flex-1 items-center gap-3 sm:gap-4 rounded-xl border border-gray-100 bg-white p-3 sm:p-4 shadow-card',
        cfg?.border && 'border-l-4',
        cfg?.border
      )}
    >
      {icon && <div className="text-lg sm:text-2xl opacity-60">{icon}</div>}
      <div className="flex-1 min-w-0">
        <div className={clsx('text-lg sm:text-2xl font-bold tracking-tight truncate', accent === 'active' && 'text-emerald-700', accent === 'inuse' && 'text-blue-700', accent === 'expired' && 'text-red-700', accent === 'wait' && 'text-amber-700', !accent && 'text-ink')}>
          {value}
        </div>
        <div className="mt-0.5 text-[0.6rem] sm:text-[0.7rem] font-medium uppercase tracking-wider text-ink-soft/60 truncate">{label}</div>
      </div>
      {cfg && <span className={clsx('h-1.5 w-1.5 rounded-full shrink-0', cfg.dot)} />}
    </div>
  )
}