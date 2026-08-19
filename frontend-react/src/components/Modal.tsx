import type { ReactNode } from 'react'
import { Button } from './Button'

const sizeClasses: Record<string, string> = {
  default: 'max-w-3xl',
  wide:   'max-w-5xl',
  xl:     'max-w-[95vw]',
}

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
  size = 'default',
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
  size?: 'default' | 'wide' | 'xl'
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[100] flex items-end sm:items-center justify-center bg-black/40 backdrop-blur-sm sm:p-4">
      <div className={`animate-slide-up sm:animate-scale-in max-h-[92vh] sm:max-h-[90vh] w-full overflow-y-auto rounded-t-2xl sm:rounded-2xl bg-white shadow-modal sm:mx-4 ${sizeClasses[size]}`}>
        <div className="flex items-center justify-between border-b border-gray-100 px-4 sm:px-6 py-3 sm:py-4 sticky top-0 bg-white rounded-t-2xl z-10">
          <h3 className="text-sm sm:text-base font-semibold text-ink truncate mr-2">{title}</h3>
          <button onClick={onClose} className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-ink-soft/50 transition-colors hover:bg-gray-100 hover:text-ink">
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="px-4 sm:px-6 py-4 sm:py-5">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 border-t border-gray-100 px-4 sm:px-6 py-3 sm:py-4 sticky bottom-0 bg-white rounded-b-2xl">
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}