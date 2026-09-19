import { Link, useLocation } from 'react-router'

const NAV_ITEMS = [
  { to: '/employee', label: '员工端' },
  { to: '/agent', label: '客服工作台' },
  { to: '/knowledge', label: '知识库' },
] as const

export default function AppHeader() {
  const location = useLocation()

  return (
    <header className="topbar">
      <div className="brand">智能客服系统</div>
      <nav className="nav" aria-label="三端入口">
        {NAV_ITEMS.map((item) => {
          const current = location.pathname === item.to
          if (current) {
            return (
              <span key={item.to} className="nav-item active" aria-current="page">
                {item.label}
              </span>
            )
          }
          return (
            <Link key={item.to} to={item.to} className="nav-item">
              {item.label}
            </Link>
          )
        })}
      </nav>
    </header>
  )
}
