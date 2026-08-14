import clsx from 'clsx'

export function FilterBar<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { label: string; value: T }[]
  value: T
  onChange: (v: T) => void
}) {
  return (
    <div className="flex flex-wrap items-center gap-0.5 border-b border-gray-100 px-5">
      {options.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={clsx(
            'relative px-3 py-2.5 text-xs font-medium transition-colors',
            value === opt.value
              ? 'text-brand after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full after:bg-brand'
              : 'text-ink-soft/60 hover:text-ink-soft'
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}