import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import clsx from 'clsx'
import { useHealth } from '@/hooks/useHealth'
import { SetApiKeyModal } from '@/components/SetApiKeyModal'

const navItems = [
  { to: '/', label: 'Dashboard', icon: '◉' },
  { to: '/accounts', label: 'Accounts', icon: '◈' },
  { to: '/grids', label: 'Grids', icon: '◐' },
  { to: '/sessions', label: 'Sessions', icon: '🖥️' },
]

const mobileNavItems = [
  { to: '/', label: 'Home', icon: '◉' },
  { to: '/accounts', label: 'Accts', icon: '◈' },
  { to: '/grids', label: 'Grids', icon: '◐' },
  { to: '/sessions', label: 'Sess', icon: '🖥️' },
]

export function Layout() {
  const { isError } = useHealth()
  const [showKeyModal, setShowKeyModal] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div className="min-h-screen bg-gray-50 pb-16 md:pb-0">
      {/* Top navigation */}
      <header className="sticky top-0 z-50 border-b border-gray-200/80 bg-white/80 shadow-sm backdrop-blur-lg">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 sm:px-5">
          <NavLink to="/" className="flex items-center gap-2 text-ink no-underline shrink-0">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-50 text-sm">🍪</span>
            <span className="text-[0.95rem] font-bold tracking-tight hidden xs:inline">Cookie Pool</span>
            <span
              title="API health"
              className={clsx(
                'inline-block h-1.5 w-1.5 rounded-full',
                isError ? 'bg-red-500 shadow-[0_0_6px_#ef4444]' : 'bg-emerald-500 shadow-[0_0_6px_#22c55e]'
              )}
            />
          </NavLink>

          {/* Desktop nav */}
          <nav className="hidden md:flex items-center gap-1">
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

          {/* Mobile: hamburger + key */}
          <div className="flex items-center gap-1 md:hidden">
            <button
              onClick={() => setShowKeyModal(true)}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-sm text-ink-soft/50 transition-colors hover:bg-gray-100 hover:text-ink"
              title="Set API key"
            >
              🔑
            </button>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-soft/70 transition-colors hover:bg-gray-100"
              aria-label="Toggle menu"
            >
              {menuOpen ? (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Mobile dropdown menu */}
        {menuOpen && (
          <div className="border-t border-gray-100 bg-white md:hidden animate-slide-up">
            <nav className="px-2 py-2 space-y-0.5">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  onClick={() => setMenuOpen(false)}
                  className={({ isActive }) =>
                    clsx(
                      'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm transition-colors',
                      isActive ? 'bg-indigo-50 font-medium text-brand' : 'text-ink-soft/70 hover:bg-gray-50 hover:text-ink'
                    )
                  }
                >
                  <span className="text-base w-6 text-center">{item.icon}</span>
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
        )}
      </header>

      {/* Page content */}
      <main className="mx-auto max-w-6xl px-3 sm:px-5 py-4 sm:py-7">
        <Outlet />
      </main>

      {/* Mobile bottom tab bar */}
      <nav className="fixed bottom-0 inset-x-0 z-50 border-t border-gray-200/80 bg-white/90 backdrop-blur-lg md:hidden safe-bottom">
        <div className="flex items-center justify-around h-14 max-w-lg mx-auto">
          {mobileNavItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                clsx(
                  'flex flex-col items-center justify-center gap-0.5 min-w-0 flex-1 h-full transition-colors',
                  isActive ? 'text-brand' : 'text-ink-soft/50'
                )
              }
            >
              <span className="text-lg leading-none">{item.icon}</span>
              <span className="text-[0.6rem] font-medium leading-none">{item.label}</span>
            </NavLink>
          ))}
        </div>
      </nav>

      {showKeyModal && <SetApiKeyModal onClose={() => setShowKeyModal(false)} />}
    </div>
  )
}
