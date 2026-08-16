import clsx from 'clsx'
import type { ButtonHTMLAttributes } from 'react'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'success' | 'danger' | 'warning' | 'outline' | 'ghost' | 'text'
  size?: 'sm' | 'md'
  loading?: boolean
}

export function Button({
  variant = 'primary',
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
        'inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-lg font-medium transition-all duration-150',
        size === 'sm' ? 'px-3 py-1.5 text-[0.75rem]' : 'px-4 py-2 text-sm',
        variant === 'primary' && 'bg-brand text-white shadow-sm hover:bg-brand-dark active:scale-[0.97]',
        variant === 'success' && 'bg-emerald-600 text-white shadow-sm hover:bg-emerald-700 active:scale-[0.97]',
        variant === 'danger' && 'bg-red-600 text-white shadow-sm hover:bg-red-700 active:scale-[0.97]',
        variant === 'warning' && 'bg-amber-500 text-white shadow-sm hover:bg-amber-600 active:scale-[0.97]',
        variant === 'outline' && 'border border-gray-200 bg-white text-ink-soft hover:border-gray-300 hover:text-ink active:bg-gray-50',
        variant === 'ghost' && 'text-ink-soft hover:bg-gray-100 hover:text-ink',
        variant === 'text' && 'text-brand hover:text-brand-dark underline-offset-2 hover:underline',
        (disabled || loading) && 'cursor-not-allowed opacity-50',
        className,
      )}
      disabled={disabled || loading}
      {...props}
    >
      {loading && (
        <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" opacity="0.25" />
          <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
        </svg>
      )}
      {children}
    </button>
  )
}