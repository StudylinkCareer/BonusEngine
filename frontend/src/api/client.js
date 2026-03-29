import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({ baseURL: API_BASE })

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// ── Reports ────────────────────────────────────────────────────────────────
export const getReports      = (params = {}) => api.get('/reports/', { params }).then(r => r.data)
export const getReport       = (id)          => api.get(`/reports/${id}`).then(r => r.data)
export const getCases        = (id)          => api.get(`/reports/${id}/cases`).then(r => r.data)
export const getTrail        = (id)          => api.get(`/reports/${id}/trail`).then(r => r.data)
export const getBonusReport  = (id)          => api.get(`/reports/${id}/bonus-report`).then(r => r.data)

export const uploadReport = (file, staffName, month, year, office, notes = '') => {
  const form = new FormData()
  form.append('file', file)
  form.append('staff_name', staffName)
  form.append('month', month)
  form.append('year', year)
  form.append('office', office)
  form.append('notes', notes)
  return api.post('/reports/upload', form).then(r => r.data)
}

export const updateField = (reportId, caseId, field, value, comment) =>
  api.patch(`/reports/${reportId}/cases/${caseId}/fields/${field}`, { value, comment })
    .then(r => r.data)

export const approveReport = (id) => api.post(`/reports/${id}/approve`).then(r => r.data)
export const returnReport  = (id, comment) =>
  api.post(`/reports/${id}/return`, { comment }).then(r => r.data)
export const submitReport  = (id) => api.post(`/reports/${id}/submit`).then(r => r.data)

export const downloadPDF = async (id, filename) => {
  const r = await api.get(`/reports/${id}/pdf`, { responseType: 'blob' })
  const url = URL.createObjectURL(r.data)
  const a   = document.createElement('a')
  a.href = url; a.download = filename || `report_${id}.pdf`; a.click()
  URL.revokeObjectURL(url)
}

export const sendEmail = (id, recipient) =>
  api.post(`/reports/${id}/email`, { recipient }).then(r => r.data)

// Legacy exports
export const uploadCRM  = (file, month, year) => uploadReport(file, '', month, year, 'HCM')
export const getRuns    = getReports
export const getRun     = getReport

export default api
