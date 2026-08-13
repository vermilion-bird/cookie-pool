import type { ReactNode } from 'react'
import { Button } from './Button'

export function Modal({
  open,
  title,
  onClose,
  children,
  footer,
}: {
  open: boolean
  title: string
  onClose: () => void
  children: ReactNode
  footer?: ReactNode
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/55 p-4">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white p-7 shadow-2xl">
        <h3 className="mb-3 text-lg font-semibold text-ink">{title}</h3>
        {children}
        <div className="mt-4 flex justify-end gap-2">
          {footer}
          <Button variant="ghost" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  )
}