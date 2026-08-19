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
    <div className="overflow-x-auto border-b border-gray-100 px-3 sm:px-5 scrollbar-none">
      <div className="flex items-center gap-0.5 min-w-max">
        {options.map((opt) => (
          <button
            key={opt.value}
            onClick={() => onChange(opt.value)}
            className={clsx(
              'relative px-2.5 sm:px-3 py-2.5 text-xs font-medium transition-colors whitespace-nowrap',
              value === opt.value
                ? 'text-brand after:absolute after:inset-x-2 after:bottom-0 after:h-0.5 after:rounded-full after:bg-brand'
                : 'text-ink-soft/60 hover:text-ink-soft'
            )}
          >
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}