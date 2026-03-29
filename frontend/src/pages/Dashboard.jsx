import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getReports } from '../api/client.js'

const STATUS_LABEL = {
  pending:'Pending Review', in_review:'In Review', submitted:'Awaiting Approval',
  approved:'Approved', returned:'Returned', distributed:'Distributed',
}
const STATUS_CLASS = {
  pending:'pending', in_review:'review', submitted:'submitted',
  approved:'approved', returned:'returned', distributed:'distributed',
}
const STATUS_ORDER = ['pending','in_review','submitted','approved','returned','distributed']
const MONTHS = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

export default function Dashboard() {
  const [reports, setReports] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter]   = useState('all')
  const [search, setSearch]   = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    getReports()
      .then(setReports)
      .catch(() => setReports(DEMO))
      .finally(() => setLoading(false))
  }, [])

  const counts = { all: reports.length }
  STATUS_ORDER.forEach(s => { counts[s] = reports.filter(r => r.status === s).length })

  const filtered = reports
    .filter(r => filter === 'all' || r.status === filter)
    .filter(r => !search || r.staff_name?.toLowerCase().includes(search.toLowerCase()))

  const actionable = reports.filter(r => ['pending','in_review','returned'].includes(r.status)).length

  return (
    <div className="fade-in">
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom:28 }}>
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">
            {actionable > 0
              ? `${actionable} report${actionable !== 1 ? 's' : ''} require your attention`
              : 'All reports are up to date'}
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => navigate('/upload')}>↑  Upload Report</button>
      </div>

      {/* Stats */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:14, marginBottom:28 }}>
        {[
          { label:'Total',     value: counts.all,                                      color:'var(--navy)' },
          { label:'Pending',   value: counts.pending   || 0,                           color:'var(--pending)' },
          { label:'In Review', value:(counts.in_review || 0)+(counts.submitted || 0),  color:'var(--review)' },
          { label:'Approved',  value: counts.approved  || 0,                           color:'var(--approved)' },
          { label:'Returned',  value: counts.returned  || 0,                           color:'var(--returned)' },
        ].map(s => (
          <div key={s.label} className="card" style={{ padding:'16px 18px' }}>
            <div style={{ fontSize:28, fontWeight:700, color:s.color, lineHeight:1 }}>{s.value}</div>
            <div style={{ fontSize:11, color:'var(--text-2)', marginTop:4 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div style={{ display:'flex', gap:10, marginBottom:16, alignItems:'center' }}>
        <div style={{ position:'relative', maxWidth:280, flex:1 }}>
          <span style={{ position:'absolute', left:10, top:'50%', transform:'translateY(-50%)', color:'var(--text-3)' }}>⌕</span>
          <input placeholder="Search staff name…" value={search}
            onChange={e => setSearch(e.target.value)} style={{ paddingLeft:30 }} />
        </div>
        <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
          {[['all','All'], ...STATUS_ORDER.map(s => [s, STATUS_LABEL[s]])].map(([val, lbl]) => (
            <button key={val} onClick={() => setFilter(val)} style={{
              padding:'6px 12px', borderRadius:20, border:'1px solid var(--border-2)',
              fontSize:12, fontWeight:500, cursor:'pointer',
              background: filter === val ? 'var(--navy)' : '#fff',
              color: filter === val ? '#fff' : 'var(--text-2)',
              transition:'all 0.15s', fontFamily:'var(--font)',
            }}>
              {lbl} {counts[val] ? `(${counts[val]})` : ''}
            </button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="card" style={{ overflow:'hidden' }}>
        <div style={{ overflowX:'auto' }}>
          <table>
            <thead>
              <tr>
                <th>Staff Member</th><th>Period</th><th>Office</th>
                <th>Uploaded</th><th>By</th><th>Status</th>
                <th>Cases</th><th>Updated</th>
                <th style={{ textAlign:'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={9} style={{ textAlign:'center', padding:40, color:'var(--text-3)' }}>
                  Loading…
                </td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={9} style={{ textAlign:'center', padding:40, color:'var(--text-3)' }}>
                  No reports found
                </td></tr>
              ) : filtered.map(r => (
                <tr key={r.id} style={{ cursor:'pointer' }}
                  onClick={() => navigate(
                    ['approved','distributed'].includes(r.status) ? `/report/${r.id}` : `/review/${r.id}`
                  )}>
                  <td style={{ fontWeight:600 }}>{r.staff_name}</td>
                  <td style={{ fontFamily:'var(--mono)', fontSize:12 }}>{MONTHS[r.month]} {r.year}</td>
                  <td>
                    <span style={{
                      background: r.office==='HCM' ? '#dbeafe' : r.office==='HN' ? '#d1fae5' : '#fef3c7',
                      color: r.office==='HCM' ? '#1e40af' : r.office==='HN' ? '#065f46' : '#92400e',
                      padding:'2px 8px', borderRadius:12, fontSize:11, fontWeight:600,
                    }}>{r.office}</span>
                  </td>
                  <td style={{ color:'var(--text-2)', fontSize:12 }}>{fmtDate(r.uploaded_at)}</td>
                  <td style={{ color:'var(--text-2)', fontSize:12 }}>{r.uploaded_by}</td>
                  <td>
                    <span className={`badge badge-${STATUS_CLASS[r.status] || 'pending'}`}>
                      {STATUS_LABEL[r.status] || r.status}
                    </span>
                  </td>
                  <td style={{ fontFamily:'var(--mono)', fontSize:12, textAlign:'center' }}>{r.case_count ?? '—'}</td>
                  <td style={{ color:'var(--text-2)', fontSize:12 }}>{fmtDate(r.updated_at)}</td>
                  <td style={{ textAlign:'right' }}>
                    <button className={`btn ${['pending','in_review','returned'].includes(r.status) ? 'btn-primary' : 'btn-ghost'}`}
                      style={{ fontSize:12, padding:'6px 12px' }}
                      onClick={e => { e.stopPropagation(); navigate(
                        ['approved','distributed'].includes(r.status) ? `/report/${r.id}` : `/review/${r.id}`
                      )}}>
                      {['pending','in_review','returned'].includes(r.status) ? 'Open' : 'View'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

const fmtDate = iso => {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString('en-GB',{day:'2-digit',month:'short'}) + ', ' +
    d.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'})
}

const DEMO = [
  { id:'1', staff_name:'Trần Thanh Gia Mẫn', month:1, year:2025, office:'HCM', status:'approved',  uploaded_at:'2025-03-02T09:14:00', uploaded_by:'Ngọc Viên', updated_at:'2025-03-05T11:30:00', case_count:8  },
  { id:'2', staff_name:'Lê Thị Trường An',   month:1, year:2025, office:'HCM', status:'in_review', uploaded_at:'2025-03-02T09:31:00', uploaded_by:'Ngọc Viên', updated_at:'2025-03-03T14:20:00', case_count:45 },
  { id:'3', staff_name:'Quan Hoàng Yến',      month:1, year:2025, office:'HCM', status:'pending',   uploaded_at:'2025-03-03T14:02:00', uploaded_by:'Ngọc Viên', updated_at:'2025-03-03T14:02:00', case_count:7  },
  { id:'4', staff_name:'Nguyễn Thành Vinh',   month:1, year:2025, office:'HCM', status:'submitted', uploaded_at:'2025-03-04T08:45:00', uploaded_by:'Ngọc Viên', updated_at:'2025-03-06T16:00:00', case_count:12 },
  { id:'5', staff_name:'Phạm Thị Lợi',        month:1, year:2025, office:'DN',  status:'returned',  uploaded_at:'2025-03-02T10:00:00', uploaded_by:'Ngọc Viên', updated_at:'2025-03-04T09:15:00', case_count:15 },
]
