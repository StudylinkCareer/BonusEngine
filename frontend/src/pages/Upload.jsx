import { useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadReport } from '../api/client.js'

const STAFF   = ['Đoàn Ngọc Trúc Quỳnh','Lê Thị Trường An','Nguyễn Thành Vinh','Nguyễn Thị Mỹ Ly','Phạm Thị Lợi','Phạm Thị Ngọc Thảo','Quan Hoàng Yến','Thái Thị Huỳnh Anh','Trần Thanh Gia Mẫn']
const MONTHS  = ['January','February','March','April','May','June','July','August','September','October','November','December']
const OFFICES = ['HCM','HN','DN']
const YEARS   = [2024, 2025, 2026]

export default function Upload() {
  const [file, setFile]       = useState(null)
  const [dragging, setDragging] = useState(false)
  const [staff, setStaff]     = useState('')
  const [month, setMonth]     = useState('')
  const [year, setYear]       = useState(new Date().getFullYear())
  const [office, setOffice]   = useState('HCM')
  const [notes, setNotes]     = useState('')
  const [uploading, setUploading] = useState(false)
  const [error, setError]     = useState('')
  const inputRef = useRef()
  const navigate = useNavigate()

  const handleDrop = e => {
    e.preventDefault(); setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f?.name.match(/\.(xlsx|xls)$/i)) setFile(f)
    else setError('Please upload an Excel file (.xlsx or .xls)')
  }

  const handleSubmit = async () => {
    if (!file || !staff || !month) { setError('Please complete all fields and select a file.'); return }
    setError(''); setUploading(true)
    try {
      const monthNum = MONTHS.indexOf(month) + 1
      const data = await uploadReport(file, staff, monthNum, year, office, notes)
      navigate(`/review/${data.id}`)
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Upload failed. Please try again.')
    } finally { setUploading(false) }
  }

  const ready = file && staff && month && year && office

  return (
    <div className="fade-in" style={{ maxWidth:700 }}>
      <h1 className="page-title">Upload CRM Report</h1>
      <p className="page-subtitle">The engine will parse and classify all cases automatically.</p>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        onClick={() => !file && inputRef.current.click()}
        style={{
          border:`2px dashed ${dragging ? 'var(--blue)' : file ? 'var(--approved)' : 'var(--border-2)'}`,
          borderRadius:12, padding:'40px 32px', textAlign:'center',
          background: dragging ? '#eff6ff' : file ? '#f0fdf4' : '#fafbfc',
          cursor: file ? 'default' : 'pointer', transition:'all 0.2s', marginBottom:28,
        }}>
        <input ref={inputRef} type="file" accept=".xlsx,.xls" style={{ display:'none' }}
          onChange={e => { const f = e.target.files[0]; if (f) { setFile(f); setError('') } }} />
        {file ? (
          <>
            <div style={{ fontSize:36, marginBottom:8 }}>✓</div>
            <div style={{ fontWeight:600, color:'var(--approved)', marginBottom:4 }}>{file.name}</div>
            <div style={{ color:'var(--text-2)', fontSize:12, marginBottom:12 }}>{(file.size/1024).toFixed(1)} KB</div>
            <button className="btn btn-ghost" style={{ fontSize:12 }}
              onClick={e => { e.stopPropagation(); setFile(null) }}>Remove</button>
          </>
        ) : (
          <>
            <div style={{ fontSize:36, marginBottom:12, opacity:0.3 }}>📂</div>
            <div style={{ fontWeight:600, marginBottom:4 }}>{dragging ? 'Drop here' : 'Drag & drop CRM closed-file report'}</div>
            <div style={{ color:'var(--text-2)', fontSize:12, marginBottom:14 }}>or click to browse — .xlsx or .xls only</div>
            <button className="btn btn-ghost" style={{ fontSize:12 }}
              onClick={e => { e.stopPropagation(); inputRef.current.click() }}>Browse files</button>
          </>
        )}
      </div>

      {/* Form */}
      <div className="card" style={{ padding:24, marginBottom:20 }}>
        <div style={{ fontWeight:600, marginBottom:18, fontSize:13 }}>Report Details</div>
        <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>
          <div style={{ gridColumn:'1/-1' }}>
            <label>Staff Member *</label>
            <select value={staff} onChange={e => setStaff(e.target.value)}>
              <option value="">Select staff member…</option>
              {STAFF.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label>Month *</label>
            <select value={month} onChange={e => setMonth(e.target.value)}>
              <option value="">Select month…</option>
              {MONTHS.map(m => <option key={m}>{m}</option>)}
            </select>
          </div>
          <div>
            <label>Year *</label>
            <select value={year} onChange={e => setYear(+e.target.value)}>
              {YEARS.map(y => <option key={y}>{y}</option>)}
            </select>
          </div>
          <div>
            <label>Office *</label>
            <select value={office} onChange={e => setOffice(e.target.value)}>
              {OFFICES.map(o => <option key={o}>{o}</option>)}
            </select>
          </div>
          <div style={{ gridColumn:'1/-1' }}>
            <label>Notes (optional)</label>
            <textarea rows={2} value={notes} onChange={e => setNotes(e.target.value)}
              placeholder="Special instructions…" style={{ resize:'vertical' }} />
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="card" style={{ padding:16, marginBottom:20 }}>
        <div style={{ fontSize:11, fontWeight:600, color:'var(--text-2)', marginBottom:10, letterSpacing:0.5 }}>
          AFTER UPLOAD, THE INPUT REPORT WILL SHOW:
        </div>
        <div style={{ display:'flex', gap:12 }}>
          {[
            ['crm-bg','crm-border','crm-text','🟢 CRM Data','Locked — from uploaded file'],
            ['engine-bg','engine-border','engine-text','🔵 Engine','Auto-classified — editable with comment'],
            ['input-bg','input-border','input-text','🟡 Required','Must complete before approval'],
          ].map(([bg,bdr,col,lbl,desc]) => (
            <div key={lbl} style={{ flex:1, padding:'10px 12px', borderRadius:8,
              background:`var(--${bg})`, border:`1px solid var(--${bdr})` }}>
              <div style={{ fontWeight:600, fontSize:12, color:`var(--${col})`, marginBottom:2 }}>{lbl}</div>
              <div style={{ fontSize:11, color:'var(--text-2)' }}>{desc}</div>
            </div>
          ))}
        </div>
      </div>

      {error && (
        <div style={{ background:'#fee2e2', border:'1px solid #fca5a5', borderRadius:8,
          padding:'10px 14px', marginBottom:16, color:'#dc2626', fontSize:13 }}>{error}</div>
      )}

      <div style={{ display:'flex', gap:10 }}>
        <button className="btn btn-primary" onClick={handleSubmit}
          disabled={!ready || uploading}
          style={{ opacity:(!ready||uploading) ? 0.5 : 1, cursor:(!ready||uploading) ? 'not-allowed':'pointer', minWidth:160 }}>
          {uploading ? 'Processing…' : '↑  Upload & Process'}
        </button>
        <button className="btn btn-ghost" onClick={() => navigate('/dashboard')}>Cancel</button>
      </div>
    </div>
  )
}
