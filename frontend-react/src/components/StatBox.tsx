export function StatBox({
  label,
  value,
  accent,
}: {
  label: string
  value: number | string
  accent?: 'active' | 'inuse' | 'expired'
}) {
  const accentColor =
    accent === 'active' ? 'before:bg-emerald-600' : accent === 'inuse' ? 'before:bg-blue-600' : accent === 'expired' ? 'before:bg-red-700' : 'before:bg-ink'

  return (
    <div className={`relative flex-1 min-w-[140px] overflow-hidden rounded-xl border border-gray-100 bg-white p-5 text-center shadow-sm before:absolute before:inset-x-0 before:top-0 before:h-[3px] ${accentColor}`}>
      <div className="text-3xl font-bold text-ink">{value}</div>
      <div className="mt-1 text-xs text-gray-400">{label}</div>
    </div>
  )
}