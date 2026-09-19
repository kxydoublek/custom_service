import { Navigate, Outlet, Route, Routes } from 'react-router'
import AppHeader from '../components/AppHeader'
import { useAuth } from '../hooks/useAuth'
import AgentPage from '../pages/AgentPage'
import EmployeePage from '../pages/EmployeePage'
import KnowledgePage from '../pages/KnowledgePage'
import LoginPage from '../pages/LoginPage'
import type { AuthStatus } from '../stores/authContext'

function RestoreStatus() {
  return (
    <p className="restore-status" role="status">
      正在恢复登录状态…
    </p>
  )
}

function RequireAuth({ status }: { status: AuthStatus }) {
  if (status === 'loading') return <RestoreStatus />
  return status === 'authenticated' ? <Outlet /> : <Navigate to="/login" replace />
}

function AppShell() {
  return (
    <div className="app">
      <AppHeader />
      <div className="workspace">
        <Outlet />
      </div>
    </div>
  )
}

function LoginRoute({ status }: { status: AuthStatus }) {
  if (status === 'loading') return <RestoreStatus />
  if (status === 'authenticated') return <Navigate to="/employee" replace />
  return <LoginPage />
}

export function AppRoutes() {
  const { status } = useAuth()

  return (
    <Routes>
      <Route path="/login" element={<LoginRoute status={status} />} />
      <Route element={<RequireAuth status={status} />}>
        <Route element={<AppShell />}>
          <Route path="/employee" element={<EmployeePage />} />
          <Route path="/agent" element={<AgentPage />} />
          <Route path="/knowledge" element={<KnowledgePage />} />
        </Route>
      </Route>
      <Route
        path="/"
        element={<Navigate to={status === 'authenticated' ? '/employee' : '/login'} replace />}
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
