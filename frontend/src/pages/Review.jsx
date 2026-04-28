import { useState, useEffect, useRef, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../api/AuthProvider.jsx'
import {
  getReport, getCases, getTrail, updateField,
  approveReport, returnReport, submitReport,
  getValidation, getReferenceList, recalculateReport,
} from '../api/client.js'

const MONTHS = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']

/* ── Master column list ───────────────────────────────────────────
   All 42 columns from the Input Template plus engine additions.
   type:   crm | engine | input
   filter: text | select | number | date
   ref:    reference type for backend dropdowns (omit if not applicable)
   isDate: true for fields stored/edited as ISO date strings              */
const ALL_COLS = [
  // ── CRM Data (green) ─────────────────────────────────────────
  { key:'contract_id',        vn:'Mã hợp đồng',                 en:'Contract ID',                   type:'crm',    w:120, filter:'text'   },
  { key:'student_name',       vn:'Tên học sinh',                 en:'Student Name',                  type:'crm',    w:180, filter:'text'   },
  { key:'student_id',         vn:'Mã học sinh',                  en:'Student ID',                    type:'crm',    w:100, filter:'text'   },
  { key:'contract_date',      vn:'Ngày ký HĐ',                   en:'Contract Signed Date',          type:'crm',    w:130, filter:'date',   isDate:true },
  { key:'client_type',        vn:'Loại khách hàng',              en:'Client Type',                   type:'crm',    w:180, filter:'select', ref:'client_type' },
  { key:'country',            vn:'Quốc gia du học',              en:'Country of Study',              type:'crm',    w:110, filter:'select', ref:'country' },
  { key:'refer_agent',        vn:'Đại lý giới thiệu',            en:'Refer Source Agent',            type:'crm',    w:200, filter:'text'   },
  { key:'system_type',        vn:'Hệ thống',                     en:'System Type',                   type:'crm',    w:130, filter:'select', ref:'system_type' },
  { key:'app_status',         vn:'Trạng thái hồ sơ',            en:'Application Report Status',     type:'crm',    w:240, filter:'select', ref:'app_status' },
  { key:'visa_date',          vn:'Ngày nhận visa',               en:'Visa Received Date',            type:'crm',    w:130, filter:'date',   isDate:true },
  { key:'institution',        vn:'Tên trường',                   en:'Institution Name',              type:'crm',    w:220, filter:'text',   ref:'institution' },
  { key:'course_start',       vn:'Ngày bắt đầu khóa học',       en:'Course Start Date',             type:'crm',    w:130, filter:'date',   isDate:true },
  { key:'course_status',      vn:'Tình trạng khóa học',          en:'Course Status',                 type:'crm',    w:120, filter:'select' },
  { key:'counsellor_name',    vn:'Tên tư vấn viên',              en:'Counsellor Name',               type:'crm',    w:170, filter:'text'   },
  { key:'case_officer_name',  vn:'Tên case officer',             en:'Case Officer Name',             type:'crm',    w:170, filter:'text'   },
  { key:'pre_sales_agent',    vn:'Đại lý pre-sales',             en:'Pre-Sales Agent',               type:'crm',    w:160, filter:'text'   },
  { key:'customer_incentive', vn:'Mức ưu đãi (VND)',             en:'Customer Incentive (VND)',      type:'crm',    w:160, filter:'number', mono:true },
  { key:'notes',              vn:'Ghi chú',                      en:'Notes',                         type:'crm',    w:200, filter:'text'   },
  // ── Engine Classified (blue) ──────────────────────────────────
  { key:'service_fee_type',   vn:'Mã phí dịch vụ',              en:'Service Fee Type',              type:'engine', w:150, filter:'select', ref:'service_fee_type' },
  { key:'deferral',           vn:'Mã hoãn/miễn',                en:'Deferral / Waiver',             type:'input',  w:130, filter:'select', ref:'deferral' },
  { key:'package_type',       vn:'Loại gói dịch vụ',            en:'Package Type',                  type:'engine', w:200, filter:'select', ref:'package_type' },
  { key:'office',             vn:'Văn phòng',                    en:'Office Override',               type:'engine', w:110, filter:'select', ref:'office' },
  { key:'handover',           vn:'Bàn giao',                     en:'Handover',                      type:'input',  w:90,  filter:'select', ref:'handover' },
  { key:'target_owner',       vn:'Chủ hồ sơ (nếu bàn giao)',   en:'Target Owner',                  type:'input',  w:160, filter:'text'   },
  { key:'case_transition',    vn:'Chuyển hồ sơ',                en:'Case Transition',               type:'input',  w:120, filter:'select', ref:'case_transition' },
  { key:'prior_month_rate',   vn:'Mức bonus tháng trước (VND)', en:'Prior Month Rate (VND)',        type:'input',  w:170, filter:'number' },
  { key:'institution_type',   vn:'Loại cơ sở đào tạo',          en:'Institution Type',              type:'engine', w:150, filter:'select', ref:'institution_type' },
  { key:'group_agent_name',   vn:'Tên đại lý nhóm',             en:'Group / Master Agent Name',     type:'engine', w:180, filter:'text'   },
  { key:'targets_sheet_name', vn:'Tên trong bảng chỉ tiêu',     en:'Targets Sheet Name',            type:'engine', w:160, filter:'text'   },
  { key:'row_type',           vn:'Loại dòng',                    en:'Row Type (BASE/ADDON)',          type:'engine', w:130, filter:'select', ref:'row_type' },
  { key:'addon_code',         vn:'Mã ADDON',                    en:'Add-on Service Code',           type:'engine', w:140, filter:'text'   },
  { key:'addon_count',        vn:'Số lượng ADDON',              en:'Add-on Count',                  type:'engine', w:110, filter:'number', mono:true },
  // ── Engine additions ──────────────────────────────────────────
  // Stage 4: scheme is now editable per case via dropdown (ref:'scheme')
  { key:'scheme',             vn:'Sơ đồ tính thưởng',           en:'Calculation Scheme',            type:'engine', w:130, filter:'select', ref:'scheme' },
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

// Cell colouring based on validation status (Stage 2a).
const VALIDATION_STYLE = {
  alias:   { bg:'#fef9c3', border:'#fde047' },
  missing: { bg:'#fee2e2', border:'#fca5a5' },
  unknown: { bg:'#fee2e2', border:'#fca5a5' },
}

// Stage 4 — tier badge colour helper for multi-bucket header display.
// Used by the per-bucket tier badges. Single-bucket reports use the
// existing single-tier rendering in the stats card.
const tierColor = (tier) => {
  if (!tier) return '#94a3b8'
  if (tier === 'OVER')          return '#16a34a'   // green
  if (String(tier).startsWith('MEET')) return '#2563eb' // blue
  if (tier === 'UNDER')         return '#dc2626'   // red
  return '#64748b'                                  // gray fallback
}

// ── Stage 2b: format helpers for date display ──────────────────────────────
const isoToDisplayDate = (iso) => {
  if (!iso) return ''
  const m = String(iso).match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (!m) return iso
  return `${m[3]}/${m[2]}/${m[1]}`
}

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

  const [validation, setValidation] = useState({})
  const [validationSummary, setValidationSummary] = useState(null)

  const [referenceCache, setReferenceCache] = useState({})

  const [recalculating, setRecalculating] = useState(false)
  const [recalcResult, setRecalcResult] = useState(null)

  const [globalSearch, setGlobalSearch] = useState('')
  const [sortCol,      setSortCol]      = useState(null)
  const [sortDir,      setSortDir]      = useState('asc')
  const [colFilters,   setColFilters]   = useState({})
  const [showFilters,  setShowFilters]  = useState(false)

  const [colOrder,     setColOrder]     = useState(() => ALL_COLS.map(c => c.key))
  const [hiddenCols,   setHiddenCols]   = useState(() => new Set())
  const [showColMgr,   setShowColMgr]   = useState(false)
  const [dragKey,      setDragKey]      = useState(null)
  const [dragOverKey,  setDragOverKey]  = useState(null)

  // Stage 3 — only show cases with engine warnings (when toggled on)
  const [showOnlyWarnings, setShowOnlyWarnings] = useState(false)

  const commentRef  = useRef()
  const colMgrRef   = useRef()

  useEffect(() => { fetchReport() }, [id])

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
      try {
        const v = await getValidation(id)
        const byCaseId = {}
        for (const cv of v.case_validations || []) {
          byCaseId[cv.case_id] = cv.fields
        }
        setValidation(byCaseId)
        setValidationSummary(v.summary)
      } catch (vErr) {
        console.warn('Validation load failed (non-blocking):', vErr)
      }
    } catch (e) { console.error(e) }
    finally { setLoading(false) }
  }

  const loadReference = async (refType) => {
    if (!refType) return null
    if (referenceCache[refType]) return referenceCache[refType]
    try {
      const data = await getReferenceList(refType)
      setReferenceCache(prev => ({ ...prev, [refType]: data }))
      return data
    } catch (e) {
      console.warn(`Reference load failed for ${refType}:`, e)
      return null
    }
  }

  const COLS = useMemo(() =>
    colOrder.map(key => ALL_COLS.find(c => c.key === key))
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

  const getValidationStatus = (caseId, field) => {
    return validation[caseId]?.[field]?.status ?? null
  }
  const getValidationTooltip = (caseId, field) => {
    const v = validation[caseId]?.[field]
    if (!v) return null
    if (v.status === 'alias' && v.canonical) {
      return `Acceptable variant — preferred form is "${v.canonical}"`
    }
    if (v.status === 'missing') return 'Required field is empty'
    if (v.status === 'unknown') return `"${v.current}" is not a recognised value for this field`
    return null
  }

  // Stage 3 — count cases with engine warnings
  const warningCount = useMemo(
    () => cases.filter(c => c.has_warnings).length,
    [cases]
  )

  // Stage 4 — parse tier_breakdown JSON from report.
  // Single-bucket reports have either no breakdown or a one-element array;
  // multi-bucket reports (Phạm Thị Lợi etc.) have multiple entries.
  const tierBreakdown = useMemo(() => {
    if (!report?.tier_breakdown) return null
    try {
      const parsed = JSON.parse(report.tier_breakdown)
      return Array.isArray(parsed) ? parsed : null
    } catch (e) {
      console.warn('Failed to parse tier_breakdown JSON:', e)
      return null
    }
  }, [report?.tier_breakdown])

  const isMultiBucket = tierBreakdown && tierBreakdown.length > 1

  const uniqueVals = useMemo(() => {
    const out = {}
    ALL_COLS.filter(c => c.filter === 'select').forEach(col => {
      out[col.key] = [...new Set(
        cases.map(c => c[col.key]).filter(v => v != null && v !== '')
      )].sort()
    })
    return out
  }, [cases])

  const displayCases = useMemo(() => {
    let rows = cases.map(c => {
      const merged = { ...c }
      ALL_COLS.forEach(col => {
        const key = `${c.id}_${col.key}`
        if (changes[key]) merged[col.key] = changes[key].value
      })
      return merged
    })
    // Stage 3 — filter by warnings if toggled
    if (showOnlyWarnings) {
      rows = rows.filter(r => r.has_warnings)
    }
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
      rows.sort((a, b) => {
        const av = a[sortCol] ?? ''; const bv = b[sortCol] ?? ''
        const an = Number(av); const bn = Number(bv)
        let cmp = (!isNaN(an) && !isNaN(bn))
          ? an - bn
          : String(av).localeCompare(String(bv))
        return sortDir === 'asc' ? cmp : -cmp
      })
    }
    return rows
  }, [cases, changes, globalSearch, colFilters, sortCol, sortDir, showOnlyWarnings])

  const handleSort = (key) => {
    if (sortCol === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortCol(key); setSortDir('asc') }
  }

  const EDITABLE_FRONTEND = new Set([
    'institution_type', 'service_fee_type', 'package_type',
    'office', 'row_type', 'scheme', 'note_enrolled',
    'prior_month_rate', 'deferral', 'handover', 'target_owner',
    'targets_name', 'case_transition', 'presales_agent', 'incentive',
    'group_agent_name',
    'student_id', 'student_name', 'contract_id',
    'client_type', 'country', 'app_status', 'institution', 'system_type',
    'contract_date', 'visa_date', 'course_start',
    // Apr 2026 — direct bonus override for management exceptions.
    // Editing requires a comment; sets manual_override=True so recalc preserves it.
    'bonus_enrolled', 'bonus_priority',
  ])
  const canEdit = (field) => EDITABLE_FRONTEND.has(field)

  const handleDragStart = (e, key) => { setDragKey(key); e.dataTransfer.effectAllowed = 'move' }
  const handleDragOver  = (e, key) => { e.preventDefault(); setDragOverKey(key) }
  const handleDrop = (e, targetKey) => {
    e.preventDefault()
    if (!dragKey || dragKey === targetKey) { setDragKey(null); setDragOverKey(null); return }
    setColOrder(prev => {
      const next = [...prev]
      const fromIdx = next.indexOf(dragKey)
      const toIdx   = next.indexOf(targetKey)
      next.splice(fromIdx, 1)
      next.splice(toIdx, 0, dragKey)
      return next
    })
    setDragKey(null); setDragOverKey(null)
  }
  const toggleHide = (key) => {
    setHiddenCols(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key); else next.add(key)
      return next
    })
  }
  const showAll    = () => setHiddenCols(new Set())
  const resetOrder = () => setColOrder(ALL_COLS.map(c => c.key))

  const startEdit = async (caseId, field, currentVal) => {
    if (!canEdit(field)) return
    const col = ALL_COLS.find(c => c.key === field)
    if (col?.ref) await loadReference(col.ref)
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
    try {
      await updateField(id, caseId, field, editVal, editComment)
      try {
        const v = await getValidation(id)
        const byCaseId = {}
        for (const cv of v.case_validations || []) {
          byCaseId[cv.case_id] = cv.fields
        }
        setValidation(byCaseId)
        setValidationSummary(v.summary)
      } catch (vErr) {
        console.warn('Validation refresh failed (non-blocking):', vErr)
      }
    }
    catch (e) {
      console.error(e)
      alert('Save failed: ' + (e.response?.data?.detail || e.message))
    }
    setEditCell(null)
  }

  const handleRecalculate = async () => {
    if (recalculating) return
    setRecalculating(true)
    setRecalcResult(null)
    try {
      const result = await recalculateReport(id)
      setRecalcResult(result)
      const [r, c, t] = await Promise.all([getReport(id), getCases(id), getTrail(id)])
      setReport(r); setCases(c); setTrail(t)
      setChanges({})
    } catch (e) {
      console.error(e)
      alert('Recalculation failed: ' + (e.response?.data?.detail || e.message))
    } finally {
      setRecalculating(false)
    }
  }

  const missingRequired = cases.reduce((acc, c) => {
    INPUT_FIELDS.forEach(f => { if (!getCellValue(c.id, f)) acc++ })
    return acc
  }, 0)

  const blockingValidationCount = (validationSummary?.fields_missing || 0)
    + (validationSummary?.fields_unknown || 0)

  const canApprove = missingRequired === 0 && blockingValidationCount === 0
    && ['manager','owner','admin'].includes(user?.role)
  const canSubmit  = missingRequired === 0 && blockingValidationCount === 0
  const canRecalc  = !recalculating
    && !['approved','distributed'].includes(report?.status)

  const clearFilters = () => {
    setGlobalSearch(''); setColFilters({}); setSortCol(null); setShowOnlyWarnings(false)
  }
  const activeFilterCount =
    Object.values(colFilters).filter(v => v !== '' && v != null).length
    + (globalSearch ? 1 : 0)
    + (showOnlyWarnings ? 1 : 0)

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

          {validationSummary && (validationSummary.fields_missing > 0 || validationSummary.fields_unknown > 0) && (
            <div style={{ background:'#fee2e2', border:'1px solid #fca5a5', borderRadius:8,
              padding:'7px 12px', fontSize:12, color:'#991b1b' }}
              title={`${validationSummary.fields_missing} missing · ${validationSummary.fields_unknown} unknown · ${validationSummary.fields_alias} alias`}>
              ⛔ {validationSummary.fields_missing + validationSummary.fields_unknown} field
              {(validationSummary.fields_missing + validationSummary.fields_unknown) !== 1 ? 's' : ''} need attention
            </div>
          )}
          {validationSummary && validationSummary.fields_alias > 0 && validationSummary.fields_missing === 0 && validationSummary.fields_unknown === 0 && (
            <div style={{ background:'#fef9c3', border:'1px solid #fde047', borderRadius:8,
              padding:'7px 12px', fontSize:12, color:'#92400e' }}>
              ⚠ {validationSummary.fields_alias} alias{validationSummary.fields_alias !== 1 ? 'es' : ''} — preferred values available
            </div>
          )}

          {/* Stage 3 — engine warnings banner. Click to filter table to flagged cases. */}
          {warningCount > 0 && (
            <button onClick={() => setShowOnlyWarnings(v => !v)}
              style={{ background: showOnlyWarnings ? '#d97706' : '#fef3c7',
                border:`1px solid ${showOnlyWarnings ? '#b45309' : '#fbbf24'}`,
                color: showOnlyWarnings ? '#fff' : '#92400e',
                borderRadius:8, padding:'7px 12px', fontSize:12, cursor:'pointer',
                fontWeight: showOnlyWarnings ? 700 : 500 }}
              title="Click to toggle filter to flagged cases only">
              🚩 {warningCount} engine warning{warningCount !== 1 ? 's' : ''}
              {showOnlyWarnings ? ' (filtered)' : ''}
            </button>
          )}

          {missingRequired > 0 && (
            <div style={{ background:'#fef3c7', border:'1px solid #fde047', borderRadius:8,
              padding:'7px 12px', fontSize:12, color:'#92400e' }}>
              ⚠ {missingRequired} required field{missingRequired !== 1 ? 's' : ''} incomplete
            </div>
          )}

          <button className="btn btn-ghost"
            onClick={handleRecalculate}
            disabled={!canRecalc}
            style={{ fontSize:12, opacity: canRecalc ? 1 : 0.4 }}
            title="Re-run the bonus engine over all cases in this report">
            {recalculating ? '⟳ Recalculating…' : '⟳ Recalculate'}
          </button>

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

      {/* ── Stage 4: Multi-bucket tier breakdown banner ───────
          Shown only when the report has more than one (scheme, office)
          bucket. Single-bucket reports use the regular tier stats card. */}
      {isMultiBucket && (
        <div style={{
          flexShrink:0, padding:'10px 14px',
          background:'linear-gradient(to right, #f0f9ff, #fff)',
          border:'1px solid #bae6fd', borderRadius:8,
          display:'flex', alignItems:'center', gap:12, flexWrap:'wrap',
        }}>
          <span style={{ fontSize:11, fontWeight:600, color:'#0369a1', textTransform:'uppercase', letterSpacing:0.4 }}>
            Multi-bucket calculation
          </span>
          <div style={{ display:'flex', gap:6, flexWrap:'wrap' }}>
            {tierBreakdown.map((b, i) => (
              <span key={i}
                title={`${b.case_count} case${b.case_count !== 1 ? 's' : ''} · ${fmtNum(b.bucket_total)} VND`}
                style={{
                  padding:'4px 10px', borderRadius:4, fontSize:11, fontWeight:600,
                  background: tierColor(b.tier), color:'#fff',
                }}>
                {b.scheme} @ {b.office}: {b.tier} ({b.enrolled}/{b.target})
              </span>
            ))}
          </div>
          <div style={{ marginLeft:'auto', fontSize:11, color:'var(--text-2)' }}>
            Sum: <strong style={{ fontFamily:'var(--mono)', color:'var(--text)' }}>
              {fmtNum(tierBreakdown.reduce((s, b) => s + (b.bucket_total || 0), 0))}
            </strong>
          </div>
        </div>
      )}

      {/* ── Recalc result banner (transient) ────────────────── */}
      {recalcResult && (
        <div style={{
          background: recalcResult.cases_updated > 0 ? '#d1fae5' : '#f0f9ff',
          border: `1px solid ${recalcResult.cases_updated > 0 ? '#6ee7b7' : '#bae6fd'}`,
          borderRadius:8, padding:'7px 12px', fontSize:12, flexShrink:0,
          display:'flex', justifyContent:'space-between', alignItems:'center',
        }}>
          <span>
            ✓ Recalculation complete.{' '}
            {recalcResult.cases_updated > 0
              ? `${recalcResult.cases_updated} case${recalcResult.cases_updated !== 1 ? 's' : ''} updated.`
              : 'No bonus values changed.'}
            {' '}Engine total: <strong>{fmtNum(recalcResult.engine_total)}</strong>
            {recalcResult.tier ? ` · Tier: ${recalcResult.tier}` : ''}
            {' '}({recalcResult.enrolled} enrolled / {recalcResult.target} target)
          </span>
          <button onClick={() => setRecalcResult(null)} style={{
            background:'none', border:'none', cursor:'pointer', fontSize:14, color:'var(--text-3)',
          }}>×</button>
        </div>
      )}

      {/* ── Stats ────────────────────────────────────────────── */}
      <div style={{ display:'flex', gap:10, flexShrink:0 }}>
        {[
          { label:'Total Cases',  value: cases.length },
          { label:'Enrolled',     value: cases.filter(c => c.counts_as_enrolled).length },
          { label: isMultiBucket ? 'Home Tier' : 'Tier',
            value: report.tier || '—',          mono:true },
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
        <div style={{ position:'relative', width:280 }}>
          <span style={{ position:'absolute', left:9, top:'50%', transform:'translateY(-50%)',
            color:'var(--text-3)', fontSize:14, pointerEvents:'none' }}>⌕</span>
          <input value={globalSearch} onChange={e => setGlobalSearch(e.target.value)}
            placeholder="Search all columns…" style={{ paddingLeft:28, fontSize:12 }} />
        </div>

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
                      ) : col.filter === 'date' ? (
                        <input type="date" value={val}
                          onChange={e => setColFilters(p => ({...p,[col.key]:e.target.value}))}
                          style={{ fontSize:10, padding:'2px 5px', width:'100%',
                            height:22, border:'1px solid var(--border-2)', borderRadius:3 }} />
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
                  const s       = TYPE_STYLE[col.type]
                  const isGap   = col.key === 'gap'

                  let display = rawVal
                  if (col.isDate && rawVal) {
                    display = isoToDisplayDate(rawVal)
                  } else if (col.mono && rawVal != null && rawVal !== '') {
                    const n = Number(rawVal)
                    if (!isNaN(n)) display = isGap
                      ? (n===0 ? '✓ 0' : (n>0?'+':'') + n.toLocaleString('vi-VN'))
                      : n.toLocaleString('vi-VN')
                  }

                  const vStatus = getValidationStatus(c.id, col.key)
                  const vTooltip = getValidationTooltip(c.id, col.key)
                  const vStyle = !changed && vStatus && VALIDATION_STYLE[vStatus]

                  const cellBg = changed
                    ? '#fff7ed'
                    : (vStyle?.bg ?? '#fff')
                  const cellBorderLeft = changed
                    ? '2px solid var(--gold)'
                    : (vStyle ? `2px solid ${vStyle.border}` : '2px solid transparent')

                  // Stage 3 — show engine warning tooltip on contract_id cell
                  // when the case has an unresolved engine warning. Other cells
                  // keep the original validation tooltip behaviour.
                  const isContractCell = col.key === 'contract_id'
                  const cellTitle = (isContractCell && c.has_warnings && c.warn_msg)
                    ? c.warn_msg
                    : (vTooltip || (rawVal != null ? String(rawVal) : ''))

                  return (
                    <td key={col.key}
                      onClick={() => canEdit(col.key) && startEdit(c.id, col.key, rawVal)}
                      title={cellTitle}
                      style={{
                        width:col.w, minWidth:col.w, maxWidth:col.w, padding:'6px 8px',
                        background: cellBg,
                        borderLeft: cellBorderLeft,
                        borderBottom:'1px solid var(--border)',
                        cursor: canEdit(col.key) ? 'pointer' : 'default',
                        fontFamily: col.mono ? 'var(--mono)' : 'inherit',
                        fontSize:11,
                        color: isGap
                          ? (Number(rawVal||0)===0 ? 'var(--approved)' : 'var(--returned)')
                          : changed ? 'var(--gold-2)' : s.text,
                        whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis',
                      }}>
                      {/* Stage 3 — engine warning flag on contract_id cell */}
                      {isContractCell && c.has_warnings && (
                        <span style={{ color:'#d97706', marginRight:4, fontSize:10, cursor:'help' }}
                          title={c.warn_msg || 'Engine warning'}>
                          🚩
                        </span>
                      )}
                      {changed && <span style={{ color:'var(--gold)', marginRight:3, fontSize:9 }}>✎</span>}
                      {!changed && vStatus === 'alias' && (
                        <span style={{ color:'#92400e', marginRight:3, fontSize:9 }}>⚠</span>
                      )}
                      {!changed && (vStatus === 'missing' || vStatus === 'unknown') && (
                        <span style={{ color:'#991b1b', marginRight:3, fontSize:9 }}>⛔</span>
                      )}
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

      {/* ── Edit modal ──────────────────────────────────────── */}
      {editCell && (() => {
        const col = ALL_COLS.find(c => c.key === editCell.field)
        const needsComment = ENGINE_FIELDS.has(editCell.field)
        const refData = col?.ref ? referenceCache[col.ref] : null
        const isDate = col?.isDate

        let inputWidget = null
        if (isDate) {
          inputWidget = (
            <input type="date" value={editVal}
              onChange={e => setEditVal(e.target.value)}
              autoFocus={!needsComment}
              onKeyDown={e => e.key === 'Escape' && setEditCell(null)} />
          )
        } else if (refData && refData.canonical) {
          inputWidget = (
            <select value={editVal} onChange={e => setEditVal(e.target.value)}
              autoFocus={!needsComment}
              onKeyDown={e => e.key === 'Escape' && setEditCell(null)}
              style={{ width:'100%' }}>
              <option value="">— select —</option>
              {refData.canonical.map(opt => (
                <option key={opt.value} value={opt.value}>
                  {opt.display || opt.value}
                </option>
              ))}
            </select>
          )
        } else {
          inputWidget = (
            <input value={editVal} onChange={e => setEditVal(e.target.value)}
              autoFocus={!needsComment}
              onKeyDown={e => e.key === 'Escape' && setEditCell(null)}
              style={{ fontFamily: col?.mono ? 'var(--mono)' : 'inherit' }} />
          )
        }

        const currentValidation = validation[editCell.caseId]?.[editCell.field]
        const aliasHint = currentValidation?.status === 'alias' && currentValidation.canonical
          ? `Current value "${currentValidation.current}" is a variant. Preferred: "${currentValidation.canonical}".`
          : null

        // Stage 3 — show engine warning in edit modal so operator sees the issue
        const editingCase = cases.find(c => c.id === editCell.caseId)
        const caseWarning = editingCase?.has_warnings ? editingCase.warn_msg : null

        // Stage 4 — when editing scheme or office, show a brief explainer
        // because changing these values re-buckets the case on next recalc
        const isBucketField = editCell.field === 'scheme' || editCell.field === 'office'

        return (
          <div style={{ position:'fixed', inset:0, background:'rgba(0,0,0,0.4)',
            zIndex:1000, display:'flex', alignItems:'center', justifyContent:'center' }}
            onClick={() => setEditCell(null)}>
            <div className="card fade-in" style={{ padding:24, width:480, maxWidth:'90vw' }}
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
              {/* Stage 4 — bucket-field explainer */}
              {isBucketField && (
                <div style={{ fontSize:11, color:'#0369a1', marginBottom:12,
                  background:'#f0f9ff', padding:'8px 10px', borderRadius:6,
                  border:'1px solid #bae6fd' }}>
                  ℹ Changing {editCell.field} moves this case into a different
                  bucket on next recalculation. The bucket determines which
                  tier and rate card apply.
                </div>
              )}
              {aliasHint && (
                <div style={{ fontSize:11, color:'#92400e', marginBottom:12,
                  background:'#fef9c3', padding:'6px 10px', borderRadius:6 }}>
                  ⚠ {aliasHint}
                </div>
              )}
              {/* Stage 3 — engine warning shown in edit modal */}
              {caseWarning && (
                <div style={{ fontSize:11, color:'#92400e', marginBottom:12,
                  background:'#fef3c7', padding:'8px 10px', borderRadius:6,
                  border:'1px solid #fbbf24' }}>
                  🚩 <strong>Engine warning on this case:</strong> {caseWarning}
                </div>
              )}
              <div style={{ marginBottom:12 }}>
                <label>New Value</label>
                {inputWidget}
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
