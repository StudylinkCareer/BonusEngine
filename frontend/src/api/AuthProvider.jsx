import { useState, useEffect, createContext, useContext } from 'react'
import api from './client.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)

  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      api.get('/auth/me')
        .then(r => setUser(r.data))
        .catch(() => localStorage.removeItem('token'))
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (username, password) => {
    setError(null)
    try {
      const form = new FormData()
      form.append('username', username)
      form.append('password', password)
      const r  = await api.post('/api/auth/login', form)
      localStorage.setItem('token', r.data.access_token)
      const me = await api.get('/auth/me')
      setUser(me.data)
    } catch {
      setError('Invalid username or password')
      throw new Error('Invalid credentials')
    }
  }

  const logout = () => {
    localStorage.removeItem('token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, error, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() { return useContext(AuthContext) }
