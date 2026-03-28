import { Routes, Route, Navigate } from 'react-router-dom'
import NavBar from './components/NavBar.jsx'
import Upload from './pages/Upload.jsx'
import Review from './pages/Review.jsx'
import Results from './pages/Results.jsx'
import History from './pages/History.jsx'
import { useAuth } from './api/client.js'

export default function App() {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100vh' }}>
        <p style={{ color: '#2E75B6', fontSize: '16px' }}>Loading...</p>
      </div>
    )
  }

  if (!user) {
    return <LoginPage />
  }

  return (
    <div>
      <NavBar user={user} />
      <main style={{ maxWidth: '1400px', margin: '0 auto', padding: '24px 16px' }}>
        <Routes>
          <Route path="/"           element={<Navigate to="/history" replace />} />
          <Route path="/upload"     element={<Upload />} />
          <Route path="/review/:id" element={<Review />} />
          <Route path="/results/:id" element={<Results />} />
          <Route path="/history"    element={<History />} />
        </Routes>
      </main>
    </div>
  )
}

function LoginPage() {
  const { login, error } = useAuth()
  const [username, setUsername] = React.useState('')
  const [password, setPassword] = React.useState('')

  const handleSubmit = async (e) => {
    e.preventDefault()
    await login(username, password)
  }

  return (
    <div style={{
      display: 'flex', justifyContent: 'center', alignItems: 'center',
      height: '100vh', background: '#f5f7fa'
    }}>
      <div style={{
        background: '#fff', borderRadius: '12px',
        border: '0.5px solid #ddd', padding: '40px',
        width: '360px', boxShadow: '0 2px 12px rgba(0,0,0,0.08)'
      }}>
        <div style={{ textAlign: 'center', marginBottom: '28px' }}>
          <h1 style={{ color: '#1E4E79', fontSize: '20px', fontWeight: '500', margin: 0 }}>
            StudyLink Bonus Engine
          </h1>
          <p style={{ color: '#666', fontSize: '13px', marginTop: '6px' }}>
            Sign in to continue
          </p>
        </div>
        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', fontSize: '13px', color: '#444', marginBottom: '6px' }}>
              Username
            </label>
            <input
              type="text"
              value={username}
              onChange={e => setUsername(e.target.value)}
              required
              style={{ width: '100%' }}
            />
          </div>
          <div style={{ marginBottom: '24px' }}>
            <label style={{ display: 'block', fontSize: '13px', color: '#444', marginBottom: '6px' }}>
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              style={{ width: '100%' }}
            />
          </div>
          {error && (
            <p style={{ color: '#A32D2D', fontSize: '13px', marginBottom: '16px' }}>
              {error}
            </p>
          )}
          <button type="submit" style={{ width: '100%', padding: '10px' }}>
            Sign in
          </button>
        </form>
      </div>
    </div>
  )
}
