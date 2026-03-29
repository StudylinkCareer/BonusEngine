import { useState, useEffect, useRef, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../api/AuthProvider.jsx'
import { getReport, getCases, getTrail, updateField, approveReport, returnReport, submitReport } from '../api/client.js'

const MONTHS = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

/* ── Master column list ───────────────────────────────────────────
   All 42 columns from the Input Template plus engine additions.
   type: crm | engine | input
   filter: text | select | number                                  */
const ALL_COLS = [
  // ── CRM Data (green) ─────────────────────────────────────────
  { key:'contract_id',        vn:'Mã hợp đồng',                 en:'Contract ID',                   type:'crm',    w:120, filter:'text'   },
  { key:'student_name',       vn:'Tên học sinh',                 en:'Student Name',                  type:'crm',    w:180, filter:'text'   },
  { key:'student_id',         vn:'Mã học sinh',                  en:'Student ID',                    type:'crm',    w:100, filter:'text'   },
  { key:'contract_date',      vn:'Ngày ký HĐ',                   en:'Contract Signed Date',          type:'crm',    w:130, filter:'text'   },
  { key:'client_type',        vn:'Loại khách hàng',              en:'Client Type',                   type:'crm',    w:180, filter:'select' },
  { key:'country',            vn:'Quốc gia du học',              en:'Country of Study',              type:'crm',    w:110, filter:'select' },
  { key:'refer_agent',        vn:'Đại lý giới thiệu',            en:'Refer Source Agent',            type:'crm',    w:200, filter:'text'   },
  { key:'system_type',        vn:'Hệ thống',                     en:'System Type',                   type:'crm',    w:130, filter:'select' },
  { key:'app_status',         vn:'Trạng thái hồ sơ',            en:'Application Report Status',     type:'crm',    w:240, filter:'select' },
  { key:'visa_date',          vn:'Ngày nhận visa',               en:'Visa Received Date',            type:'crm',    w:130, filter:'text'   },
  { key:'institution',        vn:'Tên trường',                   en:'Institution Name',              type:'crm',    w:220, filter:'text'   },
  { key:'course_start',       vn:'Ngày bắt đầu khóa học',       en:'Course Start Date',             type:'crm',    w:130, filter:'text'   },
  { key:'course_status',      vn:'Tình trạng khóa học',          en:'Course Status',                 type:'crm',    w:120, filter:'select' },
  { key:'counsellor_name',    vn:'Tên tư vấn viên',              en:'Counsellor Name',               type:'crm',    w:170, filter:'text'   },
  { key:'case_officer_name',  vn:'Tên case officer',             en:'Case Officer Name',             type:'crm',    w:170, filter:'text'   },
  { key:'pre_sales_agent',    vn:'Đại lý pre-sales',             en:'Pre-Sales Agent',               type:'crm',    w:160, filter:'text'   },
  { key:'customer_incentive', vn:'Mức ưu đãi (VND)',             en:'Customer Incentive (VND)',      type:'crm',    w:160, filter:'number', mono:true },
  { key:'notes',              vn:'Ghi chú',                      en:'Notes',                         type:'crm',    w:200, filter:'text'   },
  // ── Engine Classified (blue) ──────────────────────────────────
  { key:'service_fee_type',   vn:'Mã phí dịch vụ',              en:'Service Fee Type',              type:'engine', w:150, filter:'select' },
  { key:'deferral',           vn:'Mã hoãn/miễn',                en:'Deferral / Waiver',             type:'input',  w:130, filter:'select' },
  { key:'package_type',       vn:'Loại gói dịch vụ',            en:'Package Type',                  type:'engine', w:200, filter:'select' },
  { key:'office',             vn:'Văn phòng',                    en:'Office Override',               type:'engine', w:110, filter:'select' },
  { key:'handover',           vn:'Bàn giao',                     en:'Handover',                      type:'input',  w:90,  filter:'select' },
  { key:'target_owner',       vn:'Chủ hồ sơ (nếu bàn giao)',   en:'Target Owner',                  type:'input',  w:160, filter:'text'   },
  { key:'case_transition',    vn:'Chuyển hồ sơ',                en:'Case Transition',               type:'input',  w:120, filter:'select' },
  { key:'prior_month_rate',   vn:'Mức bonus tháng trước (VND)', en:'Prior Month Rate (VND)',        type:'input',  w:170, filter:'number' },
  { key:'institution_type',   vn:'Loại cơ sở đào tạo',          en:'Institution Type',              type:'engine', w:150, filter:'select' },
  { key:'group_agent_name',   vn:'Tên đại lý nhóm',             en:'Group / Master Agent Name',     type:'engine', w:180, filter:'text'   },
  { key:'targets_sheet_name', vn:'Tên trong bảng chỉ tiêu',     en:'Targets Sheet Name',            type:'engine', w:160, filter:'text'   },
  { key:'row_type',           vn:'Loại dòng',                    en:'Row Type (BASE/ADDON)',          type:'engine', w:130, filter:'select' },
  { key:'addon_code',         vn:'Mã ADDON',                    en:'Add-on Service Code',           type:'engine', w:140, filter:'text'   },
  { key:'addon_count',        vn:'Số lượng ADDON',              en:'Add-on Count',                  type:'engine', w:110, filter:'number', mono:true },
  // ── Engine additions ──────────────────────────────────────────
  { key:'scheme',             vn:'Sơ đồ tính thưởng',           en:'Calculation Scheme',            type:'engine', w:130, filter:'select' },
  { key:'is_vietnam',         vn:'Trong nước VN',               en:'Vietnam Domestic',              type:'engine', w:120, filter:'select' },
  { key:'is_agent_referred',  vn:'Qua đại lý bên ngoài',        en:'Via External Agent',            type:'engine', w:130, filter:'select' },
  { key:'counts_as_enrolled', vn:'Tính vào chỉ tiêu KPI',       en:'Counts Toward KPI',             type:'engine', w:130, filter:'select' },
  // ── Engine Output ─────────────────────────────────────────────
  { key:'base_rate',          vn:'Mức bonus cơ sở (VND)',       en:'Base Rate (VND)',               type:'engine', w:140, filter:'number', mono:true },
  { key:'bonus_enrolled',     vn:'Bonus nhập học (VND)',        en:'Bonus Enrolled (VND)',          type:'engine', w:150, filter:'number', mono:true },
  { key:'note_enrolled',      vn:'Ghi chú bonus nhập học',      en:'Note Bonus Enrolled',           type:'engine', w:220, filter:'text'   },
  { key:'bonus_priority',     vn:'Bonus priority (VND)',        en:'Bonus Priority (VND)',          type:'engine', w:140, filter:'number', mono:true },
  { key:'note_priority',      vn:'Ghi chú bonus priority',      en:'Note Bonus Priority',           type:'engine', w:200, filter:'text'   },
  { key:'gap',                vn:'Chênh lệch (VND)',            en:'Engine vs Manual Gap',          type:'engine', w:150, filter:'number', mono:true },
]

const TYPE_STYLE = {
  crm:    { bg:'var(--crm-bg)',    border:'var(--crm-border)',    text:'var(--crm-text)',    hdr:'#dcfce7' },
  engine: { bg:'var(--engine-bg)', border:'var(--engine-border)', text:'var(--engine-text)', hdr:'#dbeafe' },
  input:  { bg:'var(--input-bg)',  border:'var(--input-border)',  text:'var(--input-text)',  hdr:'#fef9c3' },
}

const ENGINE_FIELDS = new Set([
  'service_fee_type','package_type','institution_type','scheme','office','row_type',
  'is_vietnam','is_agent_referred','counts_as_enrolled','group_agent_name',
  'targets_sheet_name','addon_code','addon_count',
  'base_rate','bonus_enrolled','note_enrolled','bonus_priority','note_priority','gap',
])

const INPUT_FIELDS = new Set([
  'prior_month_rate','deferral','handover','target_owner','case_transition',
])

export default function Review() {
  const { id }   = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [report,       setReport]       = useState(null)
  const [cases,        setCases]        = useState([])
  const [changes,      setChanges]      = useState({})
  const [trail,        setTrail]        = useState([])
  const [editCell,     setEditCell]     = useState(null)
  const [editVal,      setEditVal]      = useState('')
  const [editComment,  setEditComment]  = useState('')
  const [showTrail,    setShowTrail]    = useState(false)
  const [submitting,   setSubmitting]   = useState(false)
  const [loading,      setLoading]      = useState(true)

  // Search / sort / filter
  const [globalSearch, setGlobalSearch] = useState('')
  const [sortCol,      setSortCol]      = useState(null)
  const [sortDir,      setSortDir]      = useState('asc')
  const [colFilters,   setColFilters]   = useState({})
  const [showFilters,  setShowFilters]  = useState(false)

  // Column management — order and visibility
  const [colOrder,     setColOrder]     = useState(() => ALL_COLS.map(c => c.key))
  const [hiddenCols,   setHiddenCols]   = useState(() => new Set())
  const [showColMgr,   setShowColMgr]   = useState(false)
  const [dragKey,      setDragKey]      = useState(null)
  const [dragOverKey,  setDragOverKey]  = useState(null)

  const commentRef  = useRef()
  const colMgrRef   = useRef()

  useEffect(() => { fetchReport() }, [id])

  // Close column manager on outside click
  useEffect(() => {
    const handler = e => {
      if (colMgrRef.current && !colMgrRef.current.contains(e.target)) setShowColMgr(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const fetchReport = async () => {
    try {
      const [r, c, t] = await Promise.all([getReport(id), getCases(id), getTrail(id)])
      setReport(r); setCases(c); setTrail(t)
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  // Active columns = ordered + not hidden
  const COLS = useMemo(() =>
    colOrder
      .map(key => ALL_COLS.find(c => c.key === key))
      .filter(c => c && !hiddenCols.has(c.key)),
    [colOrder, hiddenCols]
  )

  const getCellValue = (caseId, field) => {
    const key = `${caseId}_${field}`
    if (changes[key]) return changes[key].value
    const c = cases.find(c => c.id === caseId)
    return c ? c[field] : ''
  }
  const hasChange = (caseId, field) => !!changes[`${caseId}_${field}`]

  // Unique values for select dropdowns
  const uniqueVals = useMemo(() => {
    const out = {}
    ALL_COLS.filter(c => c.filter === 'select').forEach(col => {
      out[col.key] = [...new Set(
        cases.map(c => c[col.key]).filter(v => v != null && v !== '')
      )].sort()
    })
    return out
  }, [cases])

  // Filtered + sorted rows
  const displayCases = useMemo(() => {
    let rows = cases.map(c => {
      const merged = { ...c }
      ALL_COLS.forEach(col => {
        const key = `${c.id}_${col.key}`
        if (changes[key]) merged[col.key] = changes[key].value
      })
      return merged
    })
    if (globalSearch.trim()) {
      const q = globalSearch.toLowerCase()
      rows = rows.filter(r =>
        ALL_COLS.some(col => String(r[col.key] ?? '').toLowerCase().includes(q))
      )
    }
    Object.entries(colFilters).forEach(([field, val]) => {
      if (!val && val !== 0) return
      const col = ALL_COLS.find(c => c.key === field)
      if (!col) return
      if (col.filter === 'select') {
        rows = rows.filter(r => String(r[field] ?? '') === String(val))
      } else {
        rows = rows.filter(r =>
          String(r[field] ?? '').toLowerCase().includes(String(val).toLowerCase())
        )
      }
    })
    if (sortCol) {
      rows = [...rows].sort((a, b) => {
        const av = a[sortCol] ?? '', bv = b[sortCol] ?? ''
        const cmp = typeof av === 'number' && typeof bv === 'number'
          ? av - bv : String(av).localeCompare(String(bv), undefined, { numeric:true })
        return sortDir === 'asc' ? cmp : -cmp
      })
    }
    return rows
  }, [cases, changes, globalSearch, colFilters, sortCol, sortDir])

  const handleSort = key => {
    if (sortCol === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(key); setSortDir('asc') }
  }

  // ── Column drag-to-reorder ────────────────────────────────────
  const handleDragStart = (e, key) => {
    setDragKey(key)
    e.dataTransfer.effectAllowed = 'move'
  }
  const handleDragOver = (e, key) => {
    e.preventDefault()
    e.dataTransfer.dropEffect = 'move'
    if (key !== dragKey) setDragOverKey(key)
  }
  const handleDrop = (e, targetKey) => {
    e.preventDefault()
    if (!dragKey || dragKey === targetKey) { setDragKey(null); setDragOverKey(null); return }
    setColOrder(prev => {
      const next  = [...prev]
      const fromI = next.indexOf(dragKey)
      const toI   = next.indexOf(targetKey)
      next.splice(fromI, 1)
      next.splice(toI, 0, dragKey)
      return next
    })
    setDragKey(null); setDragOverKey(null)
  }

  // ── Column visibility ─────────────────────────────────────────
  const toggleHide = key => {
    setHiddenCols(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }
  const showAll  = () => setHiddenCols(new Set())
  const resetOrder = () => setColOrder(ALL_COLS.map(c => c.key))

  // ── Editing ───────────────────────────────────────────────────
  const canEdit = field =>
    ENGINE_FIELDS.has(field) || INPUT_FIELDS.has(field)

  const startEdit = (caseId, field, currentVal) => {
    if (!canEdit(field)) return
    setEditCell({ caseId, field })
    setEditVal(currentVal != null ? String(currentVal) : '')
    setEditComment('')
    setTimeout(() => commentRef.current?.focus(), 50)
  }

  const saveEdit = async () => {
    const { caseId, field } = editCell
    const needsComment = ENGINE_FIELDS.has(field)
    if (needsComment && !editComment.trim()) {
      alert('A comment is required when changing an engine-suggested value.'); return
    }
    setChanges(prev => ({ ...prev, [`${caseId}_${field}`]: {
      value: editVal, comment: editComment,
      changed_by: user?.full_name || user?.username,
      changed_at: new Date().toISOString(),
    }}))
    setTrail(prev => [{
      case_id: caseId,
      field_label: ALL_COLS.find(c => c.key === field)?.en || field,
      old_value: getCellValue(caseId, field),
      new_value: editVal, comment: editComment,
      changed_by: user?.full_name || user?.username,
      changed_at: new Date().toISOString(),
    }, ...prev])
    try { await updateField(id, caseId, field, editVal, editComment) }
    catch (e) { console.error(e) }
    setEditCell(null)
  }

  const missingRequired = cases.reduce((acc, c) => {
    INPUT_FIELDS.forEach(f => { if (!getCellValue(c.id, f)) acc++ })
    return acc
  }, 0)

  const canApprove = missingRequired === 0 && ['manager','owner','admin'].includes(user?.role)
  const canSubmit  = missingRequired === 0

  const clearFilters = () => { setGlobalSearch(''); setColFilters({}); setSortCol(null) }
  const activeFilterCount =
    Object.values(colFilters).filter(v => v !== '' && v != null).length + (globalSearch ? 1 : 0)

  if (loading) return (
    <div style={{ display:'flex', justifyContent:'center', alignItems:'center', height:400 }}>
      <div className="spinner" />
    </div>
  )
  if (!report) return <div style={{ padding:32, color:'var(--text-2)' }}>Report not found.</div>

  const tableWidth = COLS.reduce((s, c) => s + c.w, 0)

  return (
    <div className="fade-in"
      style={{ display:'flex', flexDirection:'column', height:'calc(100vh - 64px)', gap:10 }}>

      {/* ── Header ───────────────────────────────────────────── */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', flexShrink:0 }}>
        <div>
          <div style={{ display:'flex', alignItems:'center', gap:8, marginBottom:4 }}>
            <button className="btn btn-ghost" style={{ padding:'4px 8px', fontSize:12 }}
              onClick={() => navigate('/dashboard')}>← Dashboard</button>
            <span style={{ color:'var(--text-3)' }}>›</span>
            <span style={{ fontSize:12, color:'var(--text-2)' }}>Review</span>
          </div>
          <h1 className="page-title" style={{ marginBottom:2 }}>{report.staff_name}</h1>
          <p className="page-subtitle" style={{ marginBottom:0 }}>
            {MONTHS[report.month]} {report.year} · {report.office} ·{' '}
            <span className={`badge badge-${report.status === 'in_review' ? 'review' : (report.status || 'pending')}`}>
              {(report.status || '').replace('_', ' ')}
            </span>
          </p>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          {trail.length > 0 && (
            <button className="btn btn-ghost" onClick={() => setShowTrail(!showTrail)} style={{ fontSize:12 }}>
              📋 {trail.length} change{trail.length !== 1 ? 's' : ''}
            </button>
          )}
          {missingRequired > 0 && (
            <div style={{ background:'#fef3c7', border:'1px solid #fde047', borderRadius:8,
              padding:'7px 12px', fontSize:12, color:'#92400e' }}>
              ⚠ {missingRequired} required field{missingRequired !== 1 ? 's' : ''} incomplete
            </div>
          )}
          {canApprove ? (
            <>
              <button className="btn btn-danger" style={{ fontSize:12 }}
                onClick={async () => {
                  const r = prompt('Reason for returning:')
                  if (r) { try { await returnReport(id, r); navigate('/dashboard') } catch(e){} }
                }}>Return</button>
              <button className="btn btn-gold" disabled={submitting}
                onClick={async () => {
                  setSubmitting(true)
                  try { await approveReport(id); navigate(`/report/${id}`) }
                  catch(e){} finally { setSubmitting(false) }
                }}>✓ Approve &amp; Calculate</button>
            </>
          ) : (
            <button className="btn btn-primary" disabled={!canSubmit || submitting}
              style={{ opacity: canSubmit ? 1 : 0.4 }}
              onClick={async () => {
                setSubmitting(true)
                try { await submitReport(id); navigate('/dashboard') }
                catch(e){} finally { setSubmitting(false) }
              }}>Submit for Approval</button>
          )}
        </div>
      </div>

      {/* ── Stats ────────────────────────────────────────────── */}
      <div style={{ display:'flex', gap:10, flexShrink:0 }}>
        {[
          { label:'Total Cases',  value: cases.length },
          { label:'Enrolled',     value: cases.filter(c => c.counts_as_enrolled).length },
          { label:'Tier',         value: report.tier || '—',          mono:true },
          { label:'Engine Total', value: fmtNum(report.engine_total), mono:true },
          { label:'Manual Total', value: fmtNum(report.manual_total), mono:true },
          { label:'Gap',          value: fmtGap(report.gap),          mono:true, isGap:true, gapVal:report.gap },
        ].map(s => (
          <div key={s.label} className="card" style={{ padding:'10px 14px', flex:1 }}>
            <div style={{
              fontSize:16, fontWeight:700, lineHeight:1,
              fontFamily: s.mono ? 'var(--mono)' : 'inherit',
              color: s.isGap ? (s.gapVal===0?'var(--approved)':'var(--returned)') : 'var(--text)',
            }}>{s.value}</div>
            <div style={{ fontSize:10, color:'var(--text-2)', marginTop:3 }}>{s.label}</div>
          </div>
        ))}
      </div>

      {/* ── Toolbar ──────────────────────────────────────────── */}
      <div style={{ display:'flex', gap:8, alignItems:'center', flexShrink:0, flexWrap:'wrap' }}>
        {/* Global search */}
        <div style={{ position:'relative', width:280 }}>
          <span style={{ position:'absolute', left:9, top:'50%', transform:'translateY(-50%)',
            color:'var(--text-3)', fontSize:14, pointerEvents:'none' }}>⌕</span>
          <input value={globalSearch} onChange={e => setGlobalSearch(e.target.value)}
            placeholder="Search all columns…" style={{ paddingLeft:28, fontSize:12 }} />
        </div>

        {/* Column filters toggle */}
        <button className="btn btn-ghost" onClick={() => setShowFilters(!showFilters)}
          style={{ fontSize:12, position:'relative' }}>
          ⚙ Filters
          {activeFilterCount > 0 && (
            <span style={{ position:'absolute', top:-6, right:-6, background:'var(--blue)',
              color:'#fff', borderRadius:'50%', width:16, height:16,
              fontSize:9, display:'flex', alignItems:'center', justifyContent:'center', fontWeight:700 }}>
              {activeFilterCount}
            </span>
          )}
        </button>

        {/* Column manager */}
        <div style={{ position:'relative' }} ref={colMgrRef}>
          <button className="btn btn-ghost" onClick={() => setShowColMgr(!showColMgr)}
            style={{ fontSize:12, position:'relative' }}>
            ☰ Columns
            {hiddenCols.size > 0 && (
              <span style={{ position:'absolute', top:-6, right:-6, background:'var(--gold)',
                color:'#fff', borderRadius:'50%', width:16, height:16,
                fontSize:9, display:'flex', alignItems:'center', justifyContent:'center', fontWeight:700 }}>
                {hiddenCols.size}
              </span>
            )}
          </button>

          {showColMgr && (
            <div style={{
              position:'absolute', top:'calc(100% + 6px)', left:0, zIndex:200,
              background:'#fff', border:'1px solid var(--border-2)', borderRadius:10,
              boxShadow:'var(--shadow-md)', width:320, maxHeight:460, display:'flex', flexDirection:'column',
            }}>
              <div style={{ padding:'12px 14px 8px', borderBottom:'1px solid var(--border)', display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                <div style={{ fontWeight:600, fontSize:13 }}>Manage Columns</div>
                <div style={{ display:'flex', gap:6 }}>
                  <button onClick={showAll} style={{ fontSize:11, background:'none', border:'none',
                    cursor:'pointer', color:'var(--blue)', padding:0 }}>Show all</button>
                  <span style={{ color:'var(--text-3)' }}>·</span>
                  <button onClick={resetOrder} style={{ fontSize:11, background:'none', border:'none',
                    cursor:'pointer', color:'var(--blue)', padding:0 }}>Reset order</button>
                </div>
              </div>
              <div style={{ fontSize:10, color:'var(--text-2)', padding:'6px 14px 4px' }}>
                ☑ Toggle visibility · Drag ⋮⋮ to reorder
              </div>
              <div style={{ overflowY:'auto', flex:1 }}>
                {colOrder.map(key => {
                  const col = ALL_COLS.find(c => c.key === key)
                  if (!col) return null
                  const hidden = hiddenCols.has(key)
                  const s = TYPE_STYLE[col.type]
                  return (
                    <div key={key}
                      draggable
                      onDragStart={e => handleDragStart(e, key)}
                      onDragOver={e => handleDragOver(e, key)}
                      onDrop={e => handleDrop(e, key)}
                      onDragEnd={() => { setDragKey(null); setDragOverKey(null) }}
                      style={{
                        display:'flex', alignItems:'center', gap:8,
                        padding:'6px 14px', cursor:'grab',
                        background: dragOverKey === key ? '#f0f9ff' : hidden ? '#fafafa' : '#fff',
                        borderLeft: dragOverKey === key ? '2px solid var(--blue)' : '2px solid transparent',
                        opacity: hidden ? 0.45 : 1,
                      }}>
                      <span style={{ color:'var(--text-3)', fontSize:13, cursor:'grab', flexShrink:0 }}>⋮⋮</span>
                      <input type="checkbox" checked={!hidden} onChange={() => toggleHide(key)}
                        style={{ width:14, height:14, cursor:'pointer', flexShrink:0 }} />
                      <div style={{ flex:1, minWidth:0 }}>
                        <div style={{ fontSize:11, fontWeight:600, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                          {col.en}
                        </div>
                        <div style={{ fontSize:9, color:'var(--text-3)' }}>{col.vn}</div>
                      </div>
                      <span style={{ fontSize:9, padding:'1px 6px', borderRadius:10,
                        background: s.hdr, color: s.text, fontWeight:600, flexShrink:0 }}>
                        {col.type.toUpperCase()}
                      </span>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>

        {/* Sort indicator */}
        {sortCol && (
          <div style={{ fontSize:11, color:'var(--text-2)', background:'var(--bg)',
            border:'1px solid var(--border-2)', borderRadius:6, padding:'4px 10px',
            display:'flex', alignItems:'center', gap:6 }}>
            {ALL_COLS.find(c => c.key === sortCol)?.en} {sortDir === 'asc' ? '↑' : '↓'}
            <button onClick={() => setSortCol(null)} style={{ background:'none', border:'none',
              cursor:'pointer', color:'var(--text-3)', fontSize:13, padding:0 }}>×</button>
          </div>
        )}

        {activeFilterCount > 0 && (
          <button className="btn btn-ghost" onClick={clearFilters}
            style={{ fontSize:12, color:'var(--returned)' }}>✕ Clear</button>
        )}

        <div style={{ marginLeft:'auto', fontSize:12, color:'var(--text-2)', whiteSpace:'nowrap' }}>
          {displayCases.length} of {cases.length} · {COLS.length} of {ALL_COLS.length} columns
        </div>

        {/* Legend */}
        {[['crm','🟢 CRM'],['engine','🔵 Engine'],['input','🟡 Required']].map(([type, lbl]) => {
          const s = TYPE_STYLE[type]
          return (
            <div key={type} style={{ padding:'3px 9px', borderRadius:6, fontSize:10,
              fontWeight:600, background:s.bg, border:`1px solid ${s.border}`, color:s.text,
              whiteSpace:'nowrap' }}>{lbl}</div>
          )
        })}
      </div>

      {/* ── Table ────────────────────────────────────────────── */}
      <div style={{ flex:1, overflow:'auto', border:'1px solid var(--border)',
        borderRadius:'var(--radius)', background:'#fff', minHeight:0 }}>
        <table style={{ width:tableWidth, borderCollapse:'collapse', tableLayout:'fixed' }}>
          <thead>
            <tr>
              {COLS.map(col => {
                const s        = TYPE_STYLE[col.type]
                const isSorted = sortCol === col.key
                const isDragOver = dragOverKey === col.key
                return (
                  <th key={col.key}
                    draggable
                    onDragStart={e => handleDragStart(e, col.key)}
                    onDragOver={e => handleDragOver(e, col.key)}
                    onDrop={e => handleDrop(e, col.key)}
                    onDragEnd={() => { setDragKey(null); setDragOverKey(null) }}
                    title={`${col.vn}  /  ${col.en}\nDrag to reorder · Click to sort`}
                    style={{
                      width:col.w, minWidth:col.w,
                      background: isDragOver ? '#fef3c7' : isSorted ? '#fff7ed' : s.hdr,
                      color: s.text,
                      borderBottom: showFilters ? 'none' : `2px solid ${s.border}`,
                      borderRight:'1px solid rgba(0,0,0,0.06)',
                      borderLeft: isDragOver ? '2px solid var(--gold)' : undefined,
                      padding:'5px 8px',
                      position:'sticky', top:0, zIndex:10,
                      cursor:'grab', userSelect:'none',
                      whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis',
                    }}>
                    <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', gap:2 }}>
                      <div style={{ overflow:'hidden' }}
                        onClick={e => { e.stopPropagation(); handleSort(col.key) }}>
                        <div style={{ fontSize:8, opacity:0.65, marginBottom:1 }}>{col.vn}</div>
                        <div style={{ fontSize:10, fontWeight:700 }}>
                          {col.en}
                          {col.type === 'input' && <span style={{ color:'var(--returned)', marginLeft:2 }}>*</span>}
                        </div>
                      </div>
                      <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:1, flexShrink:0 }}>
                        <span style={{ fontSize:8, opacity:0.3 }}>⋮⋮</span>
                        <span style={{ fontSize:9, opacity: isSorted ? 1 : 0.2 }}>
                          {isSorted ? (sortDir === 'asc' ? '↑' : '↓') : '↕'}
                        </span>
                      </div>
                    </div>
                  </th>
                )
              })}
            </tr>

            {showFilters && (
              <tr>
                {COLS.map(col => {
                  const s   = TYPE_STYLE[col.type]
                  const val = colFilters[col.key] || ''
                  return (
                    <td key={col.key} style={{ width:col.w, minWidth:col.w, padding:'3px 4px',
                      background: s.hdr, borderBottom:`2px solid ${s.border}`,
                      position:'sticky', top:42, zIndex:9 }}>
                      {col.filter === 'select' ? (
                        <select value={val} onChange={e => setColFilters(p => ({...p,[col.key]:e.target.value}))}
                          style={{ fontSize:10, padding:'2px 4px', width:'100%', height:22,
                            border:'1px solid var(--border-2)', borderRadius:3, fontFamily:'var(--font)' }}>
                          <option value="">All</option>
                          {(uniqueVals[col.key]||[]).map(v => (
                            <option key={v} value={v}>{String(v)}</option>
                          ))}
                        </select>
                      ) : col.filter === 'text' || col.filter === 'number' ? (
                        <input value={val} onChange={e => setColFilters(p => ({...p,[col.key]:e.target.value}))}
                          placeholder="Filter…"
                          style={{ fontSize:10, padding:'2px 5px', width:'100%',
                            height:22, border:'1px solid var(--border-2)', borderRadius:3 }} />
                      ) : <div style={{ height:22 }} />}
                    </td>
                  )
                })}
              </tr>
            )}
          </thead>

          <tbody>
            {displayCases.length === 0 ? (
              <tr><td colSpan={COLS.length} style={{ textAlign:'center', padding:40, color:'var(--text-3)' }}>
                No cases match current filters.{' '}
                <button onClick={clearFilters}
                  style={{ background:'none', border:'none', color:'var(--blue)', cursor:'pointer', fontSize:13 }}>
                  Clear filters
                </button>
              </td></tr>
            ) : displayCases.map((c, idx) => (
              <tr key={c.id} style={{ background: idx%2===0 ? '#fff' : '#fafbfc' }}>
                {COLS.map(col => {
                  const rawVal  = c[col.key]
                  const changed = hasChange(c.id, col.key)
                  const isCRM   = col.type === 'crm'
                  const s       = TYPE_STYLE[col.type]
                  const isGap   = col.key === 'gap'
                  let display   = rawVal
                  if (col.mono && rawVal != null && rawVal !== '') {
                    const n = Number(rawVal)
                    if (!isNaN(n)) display = isGap
                      ? (n===0 ? '✓ 0' : (n>0?'+':'') + n.toLocaleString('vi-VN'))
                      : n.toLocaleString('vi-VN')
                  }
                  return (
                    <td key={col.key}
                      onClick={() => canEdit(col.key) && startEdit(c.id, col.key, rawVal)}
                      title={rawVal != null ? String(rawVal) : ''}
                      style={{
                        width:col.w, minWidth:col.w, maxWidth:col.w, padding:'6px 8px',
                        background: changed ? '#fff7ed' : '#fff',
                        borderLeft: changed ? '2px solid var(--gold)' : '2px solid transparent',
                        borderBottom:'1px solid var(--border)',
                        cursor: canEdit(col.key) ? 'pointer' : 'default',
                        fontFamily: col.mono ? 'var(--mono)' : 'inherit',
                        fontSize:11,
                        color: isGap
                          ? (Number(rawVal||0)===0 ? 'var(--approved)' : 'var(--returned)')
                          : changed ? 'var(--gold-2)' : s.text,
                        whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis',
                      }}>
                      {changed && <span style={{ color:'var(--gold)', marginRight:3, fontSize:9 }}>✎</span>}
                      {display != null && display !== ''
                        ? String(display)
                        : col.type === 'input'
                          ? <span style={{ color:'var(--text-3)', fontStyle:'italic', fontSize:10 }}>— required</span>
                          : <span style={{ color:'#e2e8f0' }}>—</span>}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Audit trail ──────────────────────────────────────── */}
      {showTrail && (
        <div className="card fade-in"
          style={{ flexShrink:0, maxHeight:260, overflowY:'auto', padding:16 }}>
          <div style={{ display:'flex', justifyContent:'space-between', marginBottom:10 }}>
            <div style={{ fontWeight:600, fontSize:13 }}>Change Trail</div>
            <button className="btn btn-ghost" style={{ fontSize:11, padding:'3px 8px' }}
              onClick={() => setShowTrail(false)}>Close</button>
          </div>
          {trail.length === 0
            ? <div style={{ color:'var(--text-3)', textAlign:'center', padding:12 }}>No changes yet.</div>
            : trail.map((t, i) => (
              <div key={i} style={{ padding:'8px 10px', borderRadius:7,
                border:'1px solid var(--border)', marginBottom:5,
                background: i%2===0 ? '#fafbfc' : '#fff' }}>
                <div style={{ display:'flex', justifyContent:'space-between', marginBottom:4 }}>
                  <span style={{ fontWeight:600, fontSize:11 }}>
                    {t.field_label}
                    <span style={{ color:'var(--text-3)', marginLeft:5, fontFamily:'var(--mono)', fontSize:10 }}>
                      {t.case_id}
                    </span>
                  </span>
                  <span style={{ fontSize:10, color:'var(--text-3)' }}>
                    {t.changed_by} · {new Date(t.changed_at).toLocaleString('en-GB')}
                  </span>
                </div>
                <div style={{ display:'flex', alignItems:'center', gap:6, fontSize:11, marginBottom:t.comment?4:0 }}>
                  <span style={{ fontFamily:'var(--mono)', background:'#fee2e2',
                    padding:'1px 5px', borderRadius:3, color:'#dc2626', textDecoration:'line-through' }}>
                    {t.old_value||'(empty)'}
                  </span>
                  <span style={{ color:'var(--text-3)' }}>→</span>
                  <span style={{ fontFamily:'var(--mono)', background:'#d1fae5',
                    padding:'1px 5px', borderRadius:3, color:'#065f46' }}>
                    {t.new_value||'(empty)'}
                  </span>
                </div>
                {t.comment && (
                  <div style={{ fontSize:11, color:'var(--text-2)', fontStyle:'italic',
                    background:'#f8f9fa', borderRadius:5, padding:'4px 8px' }}>
                    💬 {t.comment}
                  </div>
                )}
              </div>
            ))}
        </div>
      )}

      {/* ── Edit modal ───────────────────────────────────────── */}
      {editCell && (() => {
        const col = ALL_COLS.find(c => c.key === editCell.field)
        const needsComment = ENGINE_FIELDS.has(editCell.field)
        return (
          <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.4)',
            zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center' }}
            onClick={() => setEditCell(null)}>
            <div className="card fade-in" style={{ padding:24, width:440, maxWidth:'90vw' }}
              onClick={e => e.stopPropagation()}>
              <div style={{ fontSize:9, color:'var(--text-3)', marginBottom:2 }}>{col?.vn}</div>
              <div style={{ fontWeight:700, fontSize:14, marginBottom: needsComment ? 6 : 14 }}>
                {col?.en}
              </div>
              {needsComment && (
                <div style={{ fontSize:11, color:'var(--returned)', marginBottom:12 }}>
                  Comment required — engine-suggested value
                </div>
              )}
              <div style={{ marginBottom:12 }}>
                <label>New Value</label>
                <input value={editVal} onChange={e => setEditVal(e.target.value)}
                  autoFocus={!needsComment}
                  onKeyDown={e => e.key === 'Escape' && setEditCell(null)}
                  style={{ fontFamily: col?.mono ? 'var(--mono)' : 'inherit' }} />
              </div>
              <div style={{ marginBottom:16 }}>
                <label>{needsComment ? '* Reason for change (required)' : 'Comment (optional)'}</label>
                <textarea ref={commentRef} rows={3} value={editComment}
                  onChange={e => setEditComment(e.target.value)}
                  placeholder={needsComment
                    ? 'Explain why this engine value is being overridden…'
                    : 'Optional note…'}
                  style={{ resize:'vertical' }} autoFocus={needsComment} />
              </div>
              <div style={{ display:'flex', gap:8 }}>
                <button className="btn btn-primary" onClick={saveEdit}
                  disabled={needsComment && !editComment.trim()}
                  style={{ opacity: needsComment && !editComment.trim() ? 0.4 : 1 }}>
                  Save Change
                </button>
                <button className="btn btn-ghost" onClick={() => setEditCell(null)}>Cancel</button>
              </div>
            </div>
          </div>
        )
      })()}
    </div>
  )
}

const fmtNum = n => n != null ? Number(n).toLocaleString('vi-VN') : '—'
const fmtGap = n => {
  if (n == null) return '—'
  if (n === 0)   return '✓ 0'
  return (n > 0 ? '+' : '') + Number(n).toLocaleString('vi-VN')
}
