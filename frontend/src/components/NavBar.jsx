import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../api/client.jsx'

export default function NavBar({ user }) {
  const { logout } = useAuth()
  const { pathname } = useLocation()

  const links = [
    { to: '/history', label: 'History' },
    { to: '/upload',  label: 'Upload' },
  ]

  const active = { borderBottom: '2px solid #fff', paddingBottom: '2px' }

  return (
    <nav style={{
      background: '#1E4E79',
      padding: '0 24px',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'space-between',
      height: '48px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
        <span style={{ color: '#fff', fontWeight: '500', fontSize: '15px' }}>
          StudyLink Bonus Engine
        </span>
        {links.map(l => (
          <Link
            key={l.to}
            to={l.to}
            style={{
              color: '#BDD7EE',
              textDecoration: 'none',
              fontSize: '13px',
              ...(pathname.startsWith(l.to) ? active : {}),
            }}
          >
            {l.label}
          </Link>
        ))}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        <span style={{ color: '#BDD7EE', fontSize: '13px' }}>
          {user?.full_name || user?.username}
        </span>
        <button
          onClick={logout}
          style={{
            background: 'transparent',
            border: '0.5px solid #BDD7EE',
            color: '#BDD7EE',
            fontSize: '12px',
            padding: '4px 12px',
            borderRadius: '4px',
            cursor: 'pointer',
          }}
        >
          Sign out
        </button>
      </div>
    </nav>
  )
}
