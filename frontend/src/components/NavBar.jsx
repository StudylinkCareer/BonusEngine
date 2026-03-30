import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../api/AuthProvider.jsx'

export default function NavBar({ user }) {
  const navigate  = useNavigate()
  const location  = useLocation()
  const { logout } = useAuth()

  const nav = [
    { path:'/dashboard',  label:'Dashboard',        icon:'▦' },
    { path:'/upload',     label:'Upload',            icon:'↑' },
    ...(user?.is_admin ? [{ path:'/reference', label:'Reference Tables', icon:'⚙' }] : []),
  ]

  return (
    <nav style={{
      position:'fixed', left:0, top:0, bottom:0, width:220,
      background:'var(--navy)', display:'flex', flexDirection:'column',
      padding:'0 0 24px', zIndex:100,
      boxShadow:'2px 0 12px rgba(0,0,0,0.15)',
    }}>
      {/* Logo */}
      <div style={{ padding:'28px 24px 20px', borderBottom:'1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ color:'var(--gold)', fontSize:11, fontWeight:700, letterSpacing:3, marginBottom:4 }}>
          STUDYLINK
        </div>
        <div style={{ color:'rgba(255,255,255,0.4)', fontSize:11 }}>Bonus Engine</div>
      </div>

      {/* Nav links */}
      <div style={{ flex:1, padding:'16px 12px' }}>
        {nav.map(item => {
          const active = location.pathname.startsWith(item.path)
          return (
            <button key={item.path} onClick={() => navigate(item.path)}
              style={{
                display:'flex', alignItems:'center', gap:10, width:'100%',
                padding:'10px 12px', borderRadius:8, border:'none', cursor:'pointer',
                marginBottom:4, fontSize:13, fontWeight: active ? 600 : 400,
                background: active ? 'rgba(255,255,255,0.12)' : 'transparent',
                color: active ? '#fff' : 'rgba(255,255,255,0.55)',
                transition:'all 0.15s',
              }}>
              <span style={{ fontSize:16 }}>{item.icon}</span>
              {item.label}
            </button>
          )
        })}
      </div>

      {/* User block */}
      <div style={{ padding:'16px 16px 0', borderTop:'1px solid rgba(255,255,255,0.08)' }}>
        <div style={{ color:'rgba(255,255,255,0.35)', fontSize:10, marginBottom:8, letterSpacing:1 }}>
          SIGNED IN AS
        </div>
        <div style={{ color:'#fff', fontSize:12, fontWeight:600, marginBottom:2 }}>
          {user?.name || user?.username}
        </div>
        <div style={{ color:'rgba(255,255,255,0.4)', fontSize:11, marginBottom:12, textTransform:'capitalize' }}>
          {user?.role?.replace('_',' ')}
        </div>
        <button onClick={logout} style={{
          width:'100%', padding:'7px 0', borderRadius:6,
          border:'1px solid rgba(255,255,255,0.15)',
          background:'transparent', color:'rgba(255,255,255,0.5)',
          fontSize:11, cursor:'pointer', fontFamily:'var(--font)',
          transition:'all 0.15s',
        }}>
          Sign out
        </button>
      </div>
    </nav>
  )
}
