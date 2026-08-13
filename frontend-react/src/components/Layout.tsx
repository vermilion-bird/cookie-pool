import { NavLink, Outlet } from 'react-router-dom'
import clsx from 'clsx'
import { useHealth } from '@/hooks/useHealth'

const navItems = [
  { to: '/', label: 'Dashboard' },
  { to: '/accounts', label: 'Accounts' },
  { to: '/tasks', label: 'Tasks' },
  { to: '/grids', label: 'Grids' },
]

export function Layout() {
  const { isError } = useHealth()

  return (
    <div className="min-h-screen bg-[#f5f6fa]">
      <header className="sticky top-0 z-50 flex items-center justify-between bg-ink px-8 py-3.5 text-white shadow-md">
        <h1 className="flex items-center text-[1.3rem] font-semibold">
          <NavLink to="/" className="text-white no-underline">
            🍪 Cookie Pool
          </NavLink>
          <span
            title="API health"
            className={clsx(
              'ml-2.5 inline-block h-2 w-2 rounded-full',
              isError ? 'bg-red-400 shadow-[0_0_6px_#f87171]' : 'bg-emerald-400 shadow-[0_0_6px_#4ade80]'
            )}
          />
        </h1>
        <nav className="flex gap-1">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'rounded-md px-3.5 py-1.5 text-sm transition-colors',
                  isActive ? 'bg-white/15 font-medium text-white' : 'text-white/65 hover:bg-white/10 hover:text-white'
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="mx-auto max-w-6xl px-5 py-8">
        <Outlet />
      </main>
    </div>
  )
}