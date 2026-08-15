import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Accounts } from '@/pages/Accounts'
import { Tasks } from '@/pages/Tasks'
import { Grids } from '@/pages/Grids'
import { Schedules } from '@/pages/Schedules'
import { Sessions } from '@/pages/Sessions'
import { ToastProvider } from '@/hooks/useToast'

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: 'accounts', element: <Accounts /> },
      { path: 'tasks', element: <Tasks /> },
      { path: 'grids', element: <Grids /> },
      { path: 'schedules', element: <Schedules /> },
      { path: 'sessions', element: <Sessions /> },
    ],
  },
])

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>
  )
}