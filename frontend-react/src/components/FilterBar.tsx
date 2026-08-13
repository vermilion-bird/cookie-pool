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
    <div className="mb-4 flex flex-wrap items-center gap-2">
      {options.map((opt) => (
        <span
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={clsx(
            'cursor-pointer rounded-full border px-3.5 py-1.5 text-xs transition-colors',
            value === opt.value
              ? 'border-ink bg-ink text-white'
              : 'border-gray-200 bg-white text-ink-soft hover:bg-gray-50'
          )}
        >
          {opt.label}
        </span>
      ))}
    </div>
  )
}