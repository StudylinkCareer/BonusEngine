import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../api/AuthProvider.jsx'
import { getBonusReport, downloadPDF, sendEmail } from '../api/client.js'

const MONTHS = ['','January','February','March','April','May','June',
                'July','August','September','October','November','December']
const MONTHS_VN = ['','Tháng 1','Tháng 2','Tháng 3','Tháng 4','Tháng 5','Tháng 6',
                   'Tháng 7','Tháng 8','Tháng 9','Tháng 10','Tháng 11','Tháng 12']

export default function BonusReport() {
  const { id }     = useParams()
  const { user }   = useAuth()
  const navigate   = useNavigate()
  const reportRef  = useRef()
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(true)
  const [emailing, setEmailing] = useState(false)
  const [emailSent, setEmailSent] = useState(false)
  const [printing, setPrinting]  = useState(false)

  useEffect(() => { fetchReport() }, [id])

  const fetchReport = async () => {
    try {
      const token = localStorage.getItem('sl_token')
      const res = await fetch(`${API}/reports/${id}/bonus-report`,
        { headers: { Authorization: `Bearer ${token}` } })
      setData(await res.json())
    } catch { setData(DEMO_DATA) }
    finally { setLoading(false) }
  }

  const handlePDF = async () => {
    setPrinting(true)
    try {
      const token = localStorage.getItem('sl_token')
      const res = await fetch(`${API}/reports/${id}/pdf`,
        { headers: { Authorization: `Bearer ${token}` } })
      const blob = await res.blob()
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href     = url
      a.download = `BonusReport_${data?.staff_name?.replace(/\s/g,'_')}_${data?.month}_${data?.year}.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      // Fallback: print via browser
      window.print()
    } finally { setPrinting(false) }
  }

  const handleEmail = async (recipient) => {
    setEmailing(true)
    try {
      const token = localStorage.getItem('sl_token')
      await fetch(`${API}/reports/${id}/email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ recipient }),
      })
      setEmailSent(true)
      setTimeout(() => setEmailSent(false), 3000)
    } catch { alert('Email sending failed. Please try again.') }
    finally { setEmailing(false) }
  }

  if (loading) return (
    <div style={{ display:'flex', justifyContent:'center', alignItems:'center', height:400 }}>
      <div className="spinner" />
    </div>
  )
  if (!data) return <div>Report not found.</div>

  const enrolledCases = data.cases?.filter(c => c.section === 'enrolled') || []
  const closedCases   = data.cases?.filter(c => c.section === 'closed')   || []
  const totalBonus    = data.total_enrolled_bonus + data.total_priority_bonus

  return (
    <div className="fade-in">
      {/* Toolbar */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:24 }}>
        <div style={{ display:'flex', alignItems:'center', gap:10 }}>
          <button className="btn btn-ghost" style={{ padding:'4px 8px', fontSize:12 }}
            onClick={() => navigate('/dashboard')}>← Dashboard</button>
          <span style={{ color:'var(--text-3)' }}>›</span>
          <button className="btn btn-ghost" style={{ padding:'4px 8px', fontSize:12 }}
            onClick={() => navigate(`/review/${id}`)}>Input Report</button>
          <span style={{ color:'var(--text-3)' }}>›</span>
          <span style={{ fontSize:13, color:'var(--text-2)' }}>Bonus Report</span>
        </div>

        <div style={{ display:'flex', gap:8 }}>
          <button className="btn btn-ghost" onClick={handlePDF}
            style={{ fontSize:12 }} disabled={printing}>
            {printing ? <><span className="spinner" style={{width:13,height:13}} /> Generating…</> : '⬇ Download PDF'}
          </button>
          <div style={{ position:'relative' }}>
            <button className="btn btn-ghost" style={{ fontSize:12 }}
              onClick={() => handleEmail('staff')}>
              {emailing ? <><span className="spinner" style={{width:13,height:13}} /> Sending…</> : '✉ Email Staff'}
            </button>
          </div>
          <button className="btn btn-primary" style={{ fontSize:12 }}
            onClick={() => handleEmail('payroll')}>
            ✉ Email Payroll
          </button>
        </div>
      </div>

      {emailSent && (
        <div style={{ background:'#d1fae5', border:'1px solid #6ee7b7', borderRadius:8, padding:'10px 16px', marginBottom:16, color:'#065f46', fontSize:13 }}>
          ✓ Email sent successfully
        </div>
      )}

      {/* Approval badge */}
      <div style={{ display:'flex', gap:10, marginBottom:20 }}>
        <div style={{ background:'#d1fae5', border:'1px solid #6ee7b7', borderRadius:8, padding:'8px 14px', fontSize:12, color:'#065f46', display:'flex', alignItems:'center', gap:6 }}>
          ✓ Approved by {data.approved_by} · {new Date(data.approved_at).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' })}
        </div>
      </div>

      {/* ── The Báo cáo ───────────────────────────────────────────── */}
      <div ref={reportRef} id="bonus-report" style={{
        background:'#fff', border:'1px solid var(--border)', borderRadius:12,
        padding:0, overflow:'hidden', boxShadow:'var(--shadow-md)',
      }}>
        {/* Report header */}
        <div style={{
          background: 'var(--navy)', padding:'24px 32px',
          display:'flex', justifyContent:'space-between', alignItems:'center',
        }}>
          <div>
            <div style={{ color:'var(--gold)', fontSize:11, fontWeight:700, letterSpacing:3, marginBottom:4 }}>STUDYLINK CAREER</div>
            <div style={{ color:'#fff', fontSize:20, fontWeight:700, marginBottom:2 }}>Performance Bonus Report</div>
            <div style={{ color:'rgba(255,255,255,0.55)', fontSize:12 }}>Báo cáo thưởng hiệu suất</div>
          </div>
          <div style={{ textAlign:'right' }}>
            <div style={{ color:'rgba(255,255,255,0.55)', fontSize:11 }}>Period / Kỳ báo cáo</div>
            <div style={{ color:'#fff', fontSize:16, fontWeight:600 }}>
              {MONTHS[data.month]} {data.year}
            </div>
            <div style={{ color:'rgba(255,255,255,0.4)', fontSize:11, marginTop:2 }}>
              {MONTHS_VN[data.month]} năm {data.year}
            </div>
          </div>
        </div>

        {/* Staff info bar */}
        <div style={{ background:'#f8f9fc', borderBottom:'1px solid var(--border)', padding:'16px 32px' }}>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(4, 1fr)', gap:24 }}>
            {[
              ['Staff Member / Nhân viên', data.staff_name],
              ['Office / Văn phòng', data.office],
              ['Target / Chỉ tiêu', data.target],
              ['Total Enrolled / Tổng nhập học', data.enrolled],
            ].map(([label, value]) => (
              <div key={label}>
                <div style={{ fontSize:10, color:'var(--text-3)', marginBottom:2, textTransform:'uppercase', letterSpacing:0.5 }}>{label}</div>
                <div style={{ fontSize:15, fontWeight:700, color:'var(--text)' }}>{value}</div>
              </div>
            ))}
          </div>
        </div>

        <div style={{ padding:'0 32px 32px' }}>

          {/* Tier badge */}
          <div style={{ margin:'20px 0 16px', display:'flex', alignItems:'center', gap:12 }}>
            <div style={{
              background: tierColor(data.tier).bg, border:`1px solid ${tierColor(data.tier).border}`,
              borderRadius:8, padding:'8px 16px', display:'inline-flex', alignItems:'center', gap:8,
            }}>
              <div style={{ width:8, height:8, borderRadius:'50%', background: tierColor(data.tier).dot }} />
              <span style={{ fontWeight:700, fontSize:13, color: tierColor(data.tier).text }}>
                {data.tier?.replace('_', ' ')} TIER
              </span>
              <span style={{ color:'var(--text-2)', fontSize:12 }}>
                — Base rate: {(data.base_rate || 0).toLocaleString('vi-VN')} VND/case
              </span>
            </div>
          </div>

          {/* Section: Enrolled cases */}
          {enrolledCases.length > 0 && (
            <ReportSection
              title="Closed Files — Enrolled / Hồ sơ đã nhập học"
              cases={enrolledCases}
              showPriority
            />
          )}

          {/* Section: Closed non-enrolled */}
          {closedCases.length > 0 && (
            <ReportSection
              title="Closed Files — Other / Hồ sơ đóng khác"
              cases={closedCases}
              showPriority={false}
            />
          )}

          {/* Totals */}
          <div style={{ marginTop:24, display:'flex', justifyContent:'flex-end' }}>
            <div style={{ width:360, border:'1px solid var(--border)', borderRadius:10, overflow:'hidden' }}>
              <TotalRow label="Bonus Enrolled / Bonus nhập học" value={data.total_enrolled_bonus} />
              <TotalRow label="Priority Bonus / Bonus ưu tiên" value={data.total_priority_bonus} />
              <TotalRow label="Total Payable / Tổng thực nhận" value={totalBonus} bold gold />
            </div>
          </div>

          {/* Footer */}
          <div style={{ marginTop:24, paddingTop:16, borderTop:'1px solid var(--border)', display:'flex', justifyContent:'space-between' }}>
            <div style={{ fontSize:11, color:'var(--text-3)' }}>
              Generated {new Date().toLocaleDateString('en-GB', { day:'2-digit', month:'long', year:'numeric' })}
            </div>
            <div style={{ fontSize:11, color:'var(--text-3)' }}>
              Approved by {data.approved_by} · Document #{data.id}
            </div>
          </div>
        </div>
      </div>

      {/* Print styles */}
      <style>{`
        @media print {
          body > * { display: none !important; }
          #bonus-report { display: block !important; box-shadow: none !important; border: none !important; }
        }
      `}</style>
    </div>
  )
}

function ReportSection({ title, cases, showPriority }) {
  const total = cases.reduce((sum, c) => sum + (c.bonus_enrolled || 0) + (c.bonus_priority || 0), 0)
  return (
    <div style={{ marginBottom:20 }}>
      <div style={{ fontWeight:700, fontSize:13, marginBottom:10, paddingBottom:6, borderBottom:'2px solid var(--border)', color:'var(--navy)' }}>
        {title}
      </div>
      <table>
        <thead>
          <tr>
            <th style={{ width:32, textAlign:'center' }}>No.</th>
            <th>Student / Học sinh</th>
            <th>Contract ID</th>
            <th>Status / Trạng thái</th>
            <th>Institution / Trường</th>
            <th style={{ textAlign:'right' }}>Enrolled Bonus</th>
            {showPriority && <th style={{ textAlign:'right' }}>Priority</th>}
            <th style={{ textAlign:'right' }}>Note / Ghi chú</th>
          </tr>
        </thead>
        <tbody>
          {cases.map((c, i) => (
            <tr key={c.contract_id}>
              <td style={{ textAlign:'center', color:'var(--text-3)', fontSize:11 }}>{i + 1}</td>
              <td style={{ fontWeight:500 }}>{c.student_name}</td>
              <td style={{ fontFamily:'var(--mono)', fontSize:11 }}>{c.contract_id}</td>
              <td style={{ fontSize:11 }}>
                <StatusChip status={c.app_status} />
              </td>
              <td style={{ fontSize:12 }}>{c.institution}</td>
              <td style={{ textAlign:'right', fontFamily:'var(--mono)', fontWeight:600,
                color: c.bonus_enrolled > 0 ? 'var(--text)' : 'var(--text-3)' }}>
                {c.bonus_enrolled > 0 ? c.bonus_enrolled.toLocaleString('vi-VN') : '—'}
              </td>
              {showPriority && (
                <td style={{ textAlign:'right', fontFamily:'var(--mono)',
                  color: c.bonus_priority > 0 ? 'var(--blue)' : 'var(--text-3)' }}>
                  {c.bonus_priority > 0 ? c.bonus_priority.toLocaleString('vi-VN') : '—'}
                </td>
              )}
              <td style={{ fontSize:11, color:'var(--text-2)', maxWidth:200 }}>{c.note_enrolled}</td>
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr>
            <td colSpan={showPriority ? 5 : 4} />
            <td style={{ textAlign:'right', fontWeight:700, fontFamily:'var(--mono)', borderTop:'2px solid var(--border)', paddingTop:8 }}>
              {cases.reduce((s,c) => s + (c.bonus_enrolled||0), 0).toLocaleString('vi-VN')}
            </td>
            {showPriority && (
              <td style={{ textAlign:'right', fontWeight:700, fontFamily:'var(--mono)', borderTop:'2px solid var(--border)', paddingTop:8 }}>
                {cases.reduce((s,c) => s + (c.bonus_priority||0), 0).toLocaleString('vi-VN')}
              </td>
            )}
            <td style={{ borderTop:'2px solid var(--border)' }} />
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

function TotalRow({ label, value, bold, gold }) {
  return (
    <div style={{
      display:'flex', justifyContent:'space-between', alignItems:'center',
      padding:'10px 16px',
      borderBottom:'1px solid var(--border)',
      background: gold ? 'var(--navy)' : bold ? '#f8f9fc' : '#fff',
    }}>
      <span style={{ fontSize:12, fontWeight: bold ? 600 : 400, color: gold ? 'rgba(255,255,255,0.7)' : 'var(--text-2)' }}>
        {label}
      </span>
      <span style={{
        fontFamily:'var(--mono)', fontWeight:700, fontSize: gold ? 16 : 13,
        color: gold ? 'var(--gold)' : 'var(--text)',
      }}>
        {(value || 0).toLocaleString('vi-VN')} ₫
      </span>
    </div>
  )
}

function StatusChip({ status }) {
  const short = status?.includes('enrolled') ? '✓ Enrolled'
    : status?.includes('Cancelled') ? '✗ Cancelled'
    : status?.includes('refused') ? '✗ Refused'
    : status?.includes('granted') ? '● Visa granted'
    : status || '—'
  const color = status?.includes('enrolled') ? 'var(--approved)'
    : status?.includes('Cancelled') ? 'var(--text-3)'
    : status?.includes('refused') ? 'var(--returned)'
    : 'var(--review)'
  return <span style={{ color, fontWeight:500, fontSize:11 }}>{short}</span>
}

function tierColor(tier) {
  if (!tier) return { bg:'#f1f5f9', border:'#e2e8f0', text:'var(--text-2)', dot:'#94a3b8' }
  if (tier.includes('OVER'))  return { bg:'#d1fae5', border:'#6ee7b7', text:'#065f46', dot:'#10b981' }
  if (tier.includes('MEET'))  return { bg:'#dbeafe', border:'#93c5fd', text:'#1e40af', dot:'#3b82f6' }
  return { bg:'#fef3c7', border:'#fde047', text:'#92400e', dot:'#f59e0b' }
}

/* Demo */
const DEMO_DATA = {
  id:'1', staff_name:'Lê Thị Trường An', month:1, year:2024, office:'HCM',
  target:13, enrolled:19, tier:'OVER', base_rate:1100000,
  total_enrolled_bonus:22200000, total_priority_bonus:1600000,
  approved_by:'Ngọc Viên', approved_at:'2025-03-05T14:00:00',
  cases:[
    { section:'enrolled', contract_id:'SLC-13245', student_name:'Nguyễn Ngọc Phương Dao', app_status:'Closed - Visa granted, then enrolled', institution:'Education Queensland International', bonus_enrolled:1100000, bonus_priority:165000, note_enrolled:'OVER rate + 30% EQI priority' },
    { section:'enrolled', contract_id:'SLC-13297', student_name:'Nguyễn Ngọc Đức', app_status:'Closed - Visa granted, then enrolled', institution:'NSW Dept of Education', bonus_enrolled:1100000, bonus_priority:0, note_enrolled:'OVER rate' },
    { section:'enrolled', contract_id:'SLC-13414', student_name:'Hồ Hưng Phú', app_status:'Closed - Visa granted, then enrolled', institution:'RMIT University', bonus_enrolled:1100000, bonus_priority:110000, note_enrolled:'OVER rate + 20% RMIT priority' },
    { section:'closed', contract_id:'SLC-12863', student_name:'Nguyễn Thụy Thùy Anh', app_status:'Closed - Enrolled, then Visa granted', institution:'Perth International College', bonus_enrolled:550000, bonus_priority:0, note_enrolled:'Carry-over: 1,100,000 × 50%' },
  ],
}
