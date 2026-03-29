import { useState } from 'react'
import { useAuth } from '../api/AuthProvider.jsx'

export default function Login() {
  const { login, error: authError } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState('')

  const handleSubmit = async e => {
    e.preventDefault(); setError(''); setLoading(true)
    try { await login(username, password) }
    catch { setError(authError || 'Invalid username or password.') }
    finally { setLoading(false) }
  }

  return (
    <div style={{
      minHeight:'100vh', background:'var(--navy)',
      display:'flex', alignItems:'center', justifyContent:'center',
      fontFamily:'var(--font)',
    }}>
      <div style={{
        position:'absolute', inset:0, opacity:0.03,
        backgroundImage:'radial-gradient(circle, #fff 1px, transparent 1px)',
        backgroundSize:'32px 32px',
      }} />
      <div style={{ position:'relative', width:380 }}>
        <div style={{ textAlign:'center', marginBottom:40 }}>
          <div style={{ color:'var(--gold)', fontSize:13, fontWeight:700, letterSpacing:4, marginBottom:6 }}>
            STUDYLINK CAREER
          </div>
          <div style={{ color:'rgba(255,255,255,0.4)', fontSize:12 }}>Bonus Engine — Administration</div>
        </div>
        <div style={{
          background:'rgba(255,255,255,0.05)', backdropFilter:'blur(12px)',
          border:'1px solid rgba(255,255,255,0.1)', borderRadius:16, padding:'36px 32px',
        }}>
          <h2 style={{ color:'#fff', fontSize:18, fontWeight:700, marginBottom:4 }}>Sign in</h2>
          <p style={{ color:'rgba(255,255,255,0.4)', fontSize:12, marginBottom:28 }}>
            Access restricted to authorised users only.
          </p>
          <form onSubmit={handleSubmit}>
            <div style={{ marginBottom:14 }}>
              <label style={{ display:'block', fontSize:12, fontWeight:500, marginBottom:5, color:'rgba(255,255,255,0.5)' }}>
                Username
              </label>
              <input value={username} onChange={e => setUsername(e.target.value)}
                placeholder="Enter username" autoComplete="username" autoFocus
                style={{ background:'rgba(255,255,255,0.07)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff' }}
              />
            </div>
            <div style={{ marginBottom:24 }}>
              <label style={{ display:'block', fontSize:12, fontWeight:500, marginBottom:5, color:'rgba(255,255,255,0.5)' }}>
                Password
              </label>
              <input type="password" value={password} onChange={e => setPassword(e.target.value)}
                placeholder="Enter password" autoComplete="current-password"
                style={{ background:'rgba(255,255,255,0.07)', border:'1px solid rgba(255,255,255,0.12)', color:'#fff' }}
              />
            </div>
            {(error || authError) && (
              <div style={{ background:'rgba(239,68,68,0.15)', border:'1px solid rgba(239,68,68,0.3)', borderRadius:8, padding:'8px 12px', marginBottom:16, color:'#fca5a5', fontSize:13 }}>
                {error || authError}
              </div>
            )}
            <button type="submit"
              disabled={loading || !username || !password}
              style={{
                width:'100%', padding:'11px 0', borderRadius:6,
                background:'var(--gold)', border:'none', color:'#fff',
                fontSize:14, fontWeight:600, cursor: loading ? 'not-allowed' : 'pointer',
                opacity: (loading || !username || !password) ? 0.6 : 1,
                fontFamily:'var(--font)',
              }}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
        <div style={{ textAlign:'center', marginTop:24, color:'rgba(255,255,255,0.2)', fontSize:11 }}>
          StudyLink Career · Bonus Engine v2.0
        </div>
      </div>
    </div>
  )
}
