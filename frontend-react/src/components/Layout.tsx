import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import clsx from 'clsx'
import { useHealth } from '@/hooks/useHealth'
import { SetApiKeyModal } from '@/components/SetApiKeyModal'

const navItems = [
  { to: '/', label: 'Dashboard', icon: '◉' },
  { to: '/accounts', label: 'Accounts', icon: '◈' },
  { to: '/tasks', label: 'Tasks', icon: '◎' },
  { to: '/grids', label: 'Grids', icon: '◐' },
  { to: '/schedules', label: 'Schedules', icon: '⏰' },
  { to: '/sessions', label: 'Sessions', icon: '🖥️' },
]

export function Layout() {
  const { isError } = useHealth()
  const [showKeyModal, setShowKeyModal] = useState(false)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Top navigation */}
      <header className="sticky top-0 z-50 border-b border-gray-200/80 bg-white/80 shadow-sm backdrop-blur-lg">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5">
          <NavLink to="/" className="flex items-center gap-2 text-ink no-underline">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-sm">🍪</span>
            <span className="text-[0.95rem] font-bold tracking-tight">Cookie Pool</span>
            <span
              title="API health"
              className={clsx(
                'inline-block h-1.5 w-1.5 rounded-full',
                isError ? 'bg-red-500 shadow-[0_0_6px_#ef4444]' : 'bg-emerald-500 shadow-[0_0_6px_#22c55e]'
              )}
            />
          </NavLink>
          <nav className="flex items-center gap-1">
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === '/'}
                className={({ isActive }) =>
                  clsx(
                    'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm transition-colors',
                    isActive ? 'bg-indigo-50 font-medium text-brand' : 'text-ink-soft/70 hover:bg-gray-100 hover:text-ink'
                  )
                }
              >
                <span className="text-xs">{item.icon}</span>
                {item.label}
              </NavLink>
            ))}
            <button
              onClick={() => setShowKeyModal(true)}
              className="ml-1 flex h-8 w-8 items-center justify-center rounded-lg text-sm text-ink-soft/50 transition-colors hover:bg-gray-100 hover:text-ink"
              title="Set API key"
            >
              🔑
            </button>
          </nav>
        </div>
      </header>

      {/* Page content */}
      <main className="mx-auto max-w-6xl px-5 py-7">
        <Outlet />
      </main>

      {showKeyModal && <SetApiKeyModal onClose={() => setShowKeyModal(false)} />}
    </div>
  )
}