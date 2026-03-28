import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadCRM, uploadTemplate } from '../api/client.jsx'

const MONTHS = [
  'January','February','March','April','May','June',
  'July','August','September','October','November','December'
]

export default function Upload() {
  const navigate = useNavigate()
  const [mode, setMode]     = useState('crm')       // 'crm' | 'template'
  const [file, setFile]     = useState(null)
  const [month, setMonth]   = useState(new Date().getMonth() + 1)
  const [year, setYear]     = useState(new Date().getFullYear())
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError]   = useState(null)

  const handleUpload = async () => {
    if (!file) return
    setLoading(true)
    setError(null)
    setResult(null)
    try {
      const fn = mode === 'crm' ? uploadCRM : uploadTemplate
      const r  = await fn(file, month, year)
      setResult(r.data)
    } catch (e) {
      const detail = e.response?.data?.detail
      setError(typeof detail === 'object' ? JSON.stringify(detail, null, 2) : detail || e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ maxWidth: '680px' }}>
      <h2 style={{ color: '#1E4E79', marginBottom: '20px' }}>Upload Report</h2>

      {/* Mode toggle */}
      <div className="card" style={{ marginBottom: '16px' }}>
        <p style={{ fontSize: '13px', color: '#444', marginBottom: '12px' }}>
          Select upload type:
        </p>
        <div style={{ display: 'flex', gap: '12px' }}>
          {[
            { key: 'crm',      label: 'CRM Report (Báo cáo)',   desc: 'Raw closed-file report — cases need review before calculation' },
            { key: 'template', label: 'Input Template (v7)',     desc: 'Pre-filled input template — validated and ready to calculate' },
          ].map(opt => (
            <div
              key={opt.key}
              onClick={() => setMode(opt.key)}
              style={{
                flex: 1, padding: '14px', borderRadius: '8px', cursor: 'pointer',
                border: mode === opt.key ? '2px solid #2E75B6' : '0.5px solid #ddd',
                background: mode === opt.key ? '#EFF6FB' : '#fff',
              }}
            >
              <div style={{ fontWeight: '500', fontSize: '13px', marginBottom: '4px' }}>
                {opt.label}
              </div>
              <div style={{ fontSize: '11px', color: '#666' }}>{opt.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Period selection */}
      <div className="card">
        <div style={{ display: 'flex', gap: '16px', marginBottom: '20px', flexWrap: 'wrap' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#555', marginBottom: '5px' }}>Month</label>
            <select value={month} onChange={e => setMonth(Number(e.target.value))}>
              {MONTHS.map((m, i) => (
                <option key={i+1} value={i+1}>{m}</option>
              ))}
            </select>
          </div>
          <div>
            <label style={{ display: 'block', fontSize: '12px', color: '#555', marginBottom: '5px' }}>Year</label>
            <select value={year} onChange={e => setYear(Number(e.target.value))}>
              {[2024, 2025, 2026].map(y => (
                <option key={y}>{y}</option>
              ))}
            </select>
          </div>
        </div>

        {/* File picker */}
        <div style={{
          border: '1.5px dashed #BDD7EE', borderRadius: '8px',
          padding: '28px', textAlign: 'center', marginBottom: '20px',
          background: '#f8fbff',
        }}>
          <input
            type="file"
            accept=".xlsx,.xls"
            onChange={e => setFile(e.target.files[0])}
            style={{ display: 'none' }}
            id="file-input"
          />
          <label htmlFor="file-input" style={{ cursor: 'pointer' }}>
            <div style={{ color: '#2E75B6', fontWeight: '500', marginBottom: '6px' }}>
              {file ? file.name : 'Choose Excel file'}
            </div>
            <div style={{ color: '#888', fontSize: '12px' }}>
              {file ? `${(file.size / 1024).toFixed(1)} KB` : '.xlsx or .xls files only'}
            </div>
          </label>
        </div>

        <button
          className="primary"
          onClick={handleUpload}
          disabled={!file || loading}
          style={{ width: '100%', padding: '11px' }}
        >
          {loading ? 'Uploading...' : 'Upload'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="card" style={{ borderColor: '#f09595', background: '#FCEBEB' }}>
          <p style={{ color: '#A32D2D', fontSize: '13px', whiteSpace: 'pre-wrap' }}>{error}</p>
        </div>
      )}

      {/* Success */}
      {result && (
        <div className="card" style={{ borderColor: '#97C459', background: '#E2EFDA' }}>
          <p style={{ color: '#276221', fontWeight: '500', marginBottom: '8px' }}>
            ✓ {result.message}
          </p>
          <p style={{ fontSize: '12px', color: '#3B6D11' }}>
            Staff: <strong>{result.staff_name}</strong> &nbsp;|&nbsp;
            Cases: <strong>{result.case_count}</strong> &nbsp;|&nbsp;
            Flagged: <strong>{result.flagged_count}</strong>
          </p>
          {result.warnings?.length > 0 && (
            <ul style={{ fontSize: '12px', color: '#5a4a00', marginTop: '10px', paddingLeft: '18px' }}>
              {result.warnings.map((w, i) => <li key={i}>{w}</li>)}
            </ul>
          )}
          <button
            className="primary"
            style={{ marginTop: '16px' }}
            onClick={() => navigate(`/review/${result.run_id}`)}
          >
            Review cases →
          </button>
        </div>
      )}
    </div>
  )
}
