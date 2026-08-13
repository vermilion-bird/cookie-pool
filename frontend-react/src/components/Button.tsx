import clsx from 'clsx'
import type { ButtonHTMLAttributes } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'green' | 'red' | 'ghost'
  size?: 'sm' | 'md'
  loading?: boolean
}

export function Button({
  variant = 'default',
  size = 'md',
  loading = false,
  disabled,
  className,
  children,
  ...props
}: ButtonProps) {
  return (
    <button
      className={clsx(
        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg font-medium transition-colors',
        size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm',
        variant === 'default' && 'bg-ink text-white hover:bg-accent-hover',
        variant === 'green' && 'bg-emerald-800 text-white hover:bg-emerald-700',
        variant === 'red' && 'bg-red-800 text-white hover:bg-red-700',
        variant === 'ghost' && 'border border-gray-200 bg-transparent text-ink-soft hover:bg-gray-50 hover:text-ink',
        (disabled || loading) && 'cursor-not-allowed opacity-50',
        className
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white/30 border-t-white" />}
      {children}
    </button>
  )
}