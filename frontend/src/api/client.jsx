import axios from 'axios'
import { useState, useEffect, createContext, useContext } from 'react'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({ baseURL: API_BASE })

// Attach token to every request
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Auth context ─────────────────────────────────────────────────────────────

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)

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
      const r = await api.post('/auth/login', form)
      localStorage.setItem('token', r.data.access_token)
      const me = await api.get('/auth/me')
      setUser(me.data)
    } catch {
      setError('Invalid username or password')
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

export function useAuth() {
  return useContext(AuthContext)
}

// ── API calls ─────────────────────────────────────────────────────────────────

export const uploadCRM = (file, month, year) => {
  const form = new FormData()
  form.append('file', file)
  form.append('run_month', month)
  form.append('run_year', year)
  return api.post('/upload/crm', form)
}

export const uploadTemplate = (file, month, year) => {
  const form = new FormData()
  form.append('file', file)
  form.append('run_month', month)
  form.append('run_year', year)
  return api.post('/upload/template', form)
}

export const getRuns = (params = {}) =>
  api.get('/reports/', { params }).then(r => r.data)

export const getRun = (id) =>
  api.get(`/reports/${id}`).then(r => r.data)

export const getCases = (runId) =>
  api.get(`/cases/run/${runId}`).then(r => r.data)

export const updateCase = (caseId, data) =>
  api.patch(`/cases/${caseId}`, data).then(r => r.data)

export const calculate = (runId) =>
  api.post(`/calculate/run/${runId}`).then(r => r.data)

export const signOff = (runId, action, comment = '') =>
  api.post(`/calculate/run/${runId}/signoff`, { action, comment }).then(r => r.data)

export const exportRun = (runId) =>
  api.get(`/reports/${runId}/export`, { responseType: 'blob' }).then(r => r.data)

export default api
