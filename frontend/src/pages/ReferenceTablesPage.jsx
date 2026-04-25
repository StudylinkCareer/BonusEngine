// frontend/src/pages/ReferenceTablesPage.jsx
import { useState, useEffect } from "react"
import api from "../api/client.js"

const MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

const TABLES = [
  // STAFF
  { key:"staff-names",      label:"12 — Staff Names",           endpoint:"/reference/staff-names",      download:true,  addable:true,  uploadable:false },
  { key:"staff-targets",    label:"04 — Staff Targets",         endpoint:"/reference/staff-targets",    download:true,  addable:false, uploadable:true,  pivotView:true },
  // INSTITUTIONS
  { key:"priority-instns",  label:"03 — Priority Institutions", endpoint:"/reference/priority-instns",  download:true,  addable:false, uploadable:false },
  { key:"master-agents",    label:"11 — Master Agents",         endpoint:"/reference/master-agents",    download:true,  addable:false, uploadable:true,
    columnOrder:["agent_name","agent_type","triggers_master_agent_rate","notes","is_active"] },
  { key:"partner-instns",   label:"Partner Instns (* / **)",    endpoint:"/reference/partner-instns",   download:true,  addable:false, uploadable:false, editableFields:["co_amount","coun_amount","end_date"] },
  // RATES (all editable)
  { key:"base-rates",       label:"02 — Base Bonus Rates",      endpoint:"/reference/base-rates",       download:true,  addable:false, uploadable:false, editableFields:["amount","start_date","end_date"] },
  { key:"special-rates",    label:"02 — Special Fixed Rates",   endpoint:"/reference/special-rates",    download:true,  addable:false, uploadable:false, editableFields:["amount","start_date","end_date"] },
  { key:"country-rates",    label:"Flat-Rate Countries",        endpoint:"/reference/country-rates",    download:true,  addable:false, uploadable:false, editableFields:["co_amount","coun_amount","start_date","end_date"] },
  { key:"incentive-tiers",  label:"Incentive Tiers (5M threshold)", endpoint:"/reference/incentive-tiers", download:true, addable:true, uploadable:false, editableFields:["threshold_amount","start_date","end_date"] },
  // RULES
  { key:"status-rules",     label:"05 — Status Rules & Splits", endpoint:"/reference/status-rules",     download:true,  addable:true,  uploadable:false, editableFields:["coun_pct","co_direct_pct","co_sub_pct","start_date","end_date"],
    columnOrder:["status_value","counts_as_enrolled","coun_pct","co_direct_pct","co_sub_pct","is_carry_over","is_current_enrolled","is_zero_bonus","fees_paid_non_enrolled","requires_visa","dedup_rank","note","is_eligible","requires_enrol","start_date","end_date"] },
  { key:"advance-rules",    label:"Advance Payment Rules",      endpoint:"/reference/advance-rules",    download:true,  addable:true,  uploadable:false, editableFields:["advance_pct","start_date","end_date"] },
  { key:"service-fee-rates",label:"09 — Service Fee Rates",     endpoint:"/reference/service-fee-rates",download:true,  addable:false, uploadable:false },
  { key:"contract-bonuses", label:"07 — Contract Bonuses",      endpoint:"/reference/contract-bonuses", download:true,  addable:false, uploadable:false },
  // COUNTRIES & TYPES
  { key:"country-codes",    label:"14 — Country Codes",         endpoint:"/reference/country-codes",    download:true,  addable:false, uploadable:false },
  { key:"client-type-map",  label:"15 — Client Type Map",       endpoint:"/reference/client-type-map",  download:true,  addable:false, uploadable:false },
  { key:"client-weights",   label:"06 — Client Weights",        endpoint:"/reference/client-weights",   download:true,  addable:false, uploadable:false },
  // TRACKERS
  { key:"ytd-tracker",      label:"08 — YTD Tracker",           endpoint:"/reference/ytd-tracker",      download:true,  addable:false, uploadable:false, pivotView:true },
  { key:"advance-payments", label:"09 — Advance Payments",      endpoint:"/reference/advance-payments", download:true,  addable:false, uploadable:false, dlKey:"advance_payments" },
  // DROPDOWN LISTS
  { key:"application_status",label:"Application Status List",  listName:"application_status",          download:false, addable:true,  uploadable:false },
  { key:"package_type",      label:"Package Type List",         listName:"package_type",                download:false, addable:true,  uploadable:false },
  { key:"service_fee_type",  label:"Service Fee Type List",     listName:"service_fee_type",            download:false, addable:true,  uploadable:false },
  { key:"addon_code",        label:"Add-on Code List",          listName:"addon_code",                  download:false, addable:true,  uploadable:false },
  { key:"deferral",          label:"Deferral List",             listName:"deferral",                    download:false, addable:true,  uploadable:false },
  { key:"institution_type",  label:"Institution Type List",     listName:"institution_type",            download:false, addable:true,  uploadable:false },
]

const SECTIONS = [
  { label:"STAFF",            keys:["staff-names","staff-targets"] },
  { label:"INSTITUTIONS",     keys:["priority-instns","master-agents","partner-instns"] },
  { label:"RATES",            keys:["base-rates","special-rates","country-rates","incentive-tiers"] },
  { label:"RULES",            keys:["status-rules","advance-rules","service-fee-rates","contract-bonuses"] },
  { label:"COUNTRIES & TYPES",keys:["country-codes","client-type-map","client-weights"] },
  { label:"TRACKERS",         keys:["ytd-tracker","advance-payments"] },
  { label:"DROPDOWN LISTS",   keys:["application_status","package_type","service_fee_type","addon_code","deferral","institution_type"] },
]

// Staff targets pivot
function StaffTargetsPivot({ rows }) {
  if (!rows.length) return <div style={{padding:20,color:"var(--color-text-secondary)",textAlign:"center"}}>No data</div>
  const years = [...new Set(rows.map(r=>r.year))].sort()
  const [selectedYear, setSelectedYear] = useState(years[years.length-1] || new Date().getFullYear())
  const yearRows = rows.filter(r=>r.year===selectedYear)
  const staffKeys = {}
  yearRows.forEach(r => {
    const k = `${r.staff_name}||${r.office||"HCM"}`
    if (!staffKeys[k]) staffKeys[k] = {name:r.staff_name, office:r.office||"HCM", months:{}}
    staffKeys[k].months[r.month] = r.target
  })
  const staffList = Object.values(staffKeys).sort((a,b)=>a.office.localeCompare(b.office)||a.name.localeCompare(b.name))
  return (
    <div>
      <div style={{display:"flex",gap:8,marginBottom:16}}>
        {years.map(y=>(
          <button key={y} onClick={()=>setSelectedYear(y)} style={{padding:"6px 14px",borderRadius:6,border:"none",cursor:"pointer",fontSize:12,fontWeight:600,background:selectedYear===y?"#1e40af":"var(--color-background-secondary)",color:selectedYear===y?"#fff":"var(--color-text-primary)"}}>
            {y}
          </button>
        ))}
      </div>
      <div style={{background:"var(--color-background-primary)",borderRadius:10,overflow:"hidden",boxShadow:"0 1px 4px rgba(0,0,0,0.08)"}}>
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}>
            <thead>
              <tr style={{background:"#0f2137"}}>
                <th style={{padding:"10px 14px",textAlign:"left",color:"#fff",fontWeight:600,whiteSpace:"nowrap"}}>STAFF MEMBER</th>
                <th style={{padding:"10px 8px",textAlign:"center",color:"#fff",fontWeight:600}}>OFFICE</th>
                {MONTHS.map(m=><th key={m} style={{padding:"10px 8px",textAlign:"center",color:"#f5a623",fontWeight:600,minWidth:42}}>{m}</th>)}
                <th style={{padding:"10px 10px",textAlign:"center",color:"#fff",fontWeight:600}}>TOTAL</th>
              </tr>
            </thead>
            <tbody>
              {staffList.map((s,i)=>{
                const total=Object.values(s.months).reduce((a,b)=>a+b,0)
                return (
                  <tr key={i} style={{background:i%2===0?"var(--color-background-primary)":"var(--color-background-secondary)"}}>
                    <td style={{padding:"8px 14px",fontWeight:600,color:"var(--color-text-primary)",borderBottom:"1px solid var(--color-border-tertiary)",whiteSpace:"nowrap"}}>{s.name}</td>
                    <td style={{padding:"8px 8px",textAlign:"center",borderBottom:"1px solid var(--color-border-tertiary)"}}>
                      <span style={{background:"#e0f2fe",color:"#0369a1",padding:"2px 8px",borderRadius:10,fontSize:11,fontWeight:600}}>{s.office}</span>
                    </td>
                    {[1,2,3,4,5,6,7,8,9,10,11,12].map(m=>(
                      <td key={m} style={{padding:"8px 8px",textAlign:"center",color:s.months[m]?"#1e40af":"var(--color-text-secondary)",fontWeight:s.months[m]?600:400,background:s.months[m]?"#eff6ff":"transparent",borderBottom:"1px solid var(--color-border-tertiary)"}}>
                        {s.months[m]||"—"}
                      </td>
                    ))}
                    <td style={{padding:"8px 10px",textAlign:"center",fontWeight:700,color:"#065f46",background:"#d1fae5",borderBottom:"1px solid var(--color-border-tertiary)"}}>{total}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

// YTD tracker pivot
function YtdTrackerPivot({ rows }) {
  if (!rows.length) return <div style={{padding:20,color:"var(--color-text-secondary)",textAlign:"center"}}>No data yet — auto-populated after each bonus run</div>
  const years = [...new Set(rows.map(r=>r.year))].sort()
  const [selectedYear, setSelectedYear] = useState(years[years.length-1]||new Date().getFullYear())
  const yearRows = rows.filter(r=>r.year===selectedYear)
  const instMap = {}
  yearRows.forEach(r=>{
    if(!instMap[r.institution_name]) instMap[r.institution_name]={}
    instMap[r.institution_name][r.month]=r.enrolment_count
  })
  const instList=Object.keys(instMap).sort()
  return (
    <div>
      <div style={{display:"flex",gap:8,marginBottom:16}}>
        {years.map(y=>(
          <button key={y} onClick={()=>setSelectedYear(y)} style={{padding:"6px 14px",borderRadius:6,border:"none",cursor:"pointer",fontSize:12,fontWeight:600,background:selectedYear===y?"#1e40af":"var(--color-background-secondary)",color:selectedYear===y?"#fff":"var(--color-text-primary)"}}>
            {y}
          </button>
        ))}
      </div>
      <div style={{background:"var(--color-background-primary)",borderRadius:10,overflow:"hidden",boxShadow:"0 1px 4px rgba(0,0,0,0.08)"}}>
        <div style={{overflowX:"auto"}}>
          <table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}>
            <thead>
              <tr style={{background:"#0f2137"}}>
                <th style={{padding:"10px 14px",textAlign:"left",color:"#fff",fontWeight:600}}>INSTITUTION</th>
                {MONTHS.map(m=><th key={m} style={{padding:"10px 8px",textAlign:"center",color:"#f5a623",fontWeight:600,minWidth:42}}>{m}</th>)}
                <th style={{padding:"10px 10px",textAlign:"center",color:"#fff",fontWeight:600}}>YTD</th>
              </tr>
            </thead>
            <tbody>
              {instList.map((inst,i)=>{
                const months=instMap[inst]
                const total=Object.values(months).reduce((a,b)=>a+b,0)
                return (
                  <tr key={i} style={{background:i%2===0?"var(--color-background-primary)":"var(--color-background-secondary)"}}>
                    <td style={{padding:"8px 14px",fontWeight:500,color:"var(--color-text-primary)",borderBottom:"1px solid var(--color-border-tertiary)"}}>{inst}</td>
                    {[1,2,3,4,5,6,7,8,9,10,11,12].map(m=>(
                      <td key={m} style={{padding:"8px 8px",textAlign:"center",color:months[m]?"#1e40af":"var(--color-text-secondary)",fontWeight:months[m]?600:400,borderBottom:"1px solid var(--color-border-tertiary)"}}>
                        {months[m]||"—"}
                      </td>
                    ))}
                    <td style={{padding:"8px 10px",textAlign:"center",fontWeight:700,color:"#065f46",background:"#d1fae5",borderBottom:"1px solid var(--color-border-tertiary)"}}>{total}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

export default function ReferenceTablesPage() {
  const [activeTable, setActiveTable] = useState(TABLES[0])
  const [rows, setRows]   = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)
  const [uploadFile, setUploadFile] = useState(null)
  const [newValue, setNewValue] = useState("")
  const [editingRow, setEditingRow] = useState(null)
  const [editValues, setEditValues] = useState({})

  useEffect(()=>{loadTable()},[activeTable])

  async function loadTable(){
    setLoading(true); setRows([]); setMessage(null); setEditingRow(null)
    try {
      const endpoint = activeTable.listName
        ? `/reference/ref-list/${activeTable.listName}`
        : activeTable.endpoint
      const res = await api.get(endpoint)
      setRows(res.data)
    } catch(e) { setMessage({type:"error",text:"Failed to load table."}) }
    setLoading(false)
  }

  async function handleDownload(){
    try {
      const dlKey = activeTable.dlKey || activeTable.key.replace(/-/g,"_")
      const res = await api.get(`/reference/download/${dlKey}`,{responseType:"blob"})
      const url = URL.createObjectURL(res.data)
      const a = document.createElement("a"); a.href=url
      a.download=`${activeTable.key}_${new Date().toISOString().slice(0,10)}.xlsx`
      a.click(); URL.revokeObjectURL(url)
    } catch(e){ setMessage({type:"error",text:"Download failed."}) }
  }

  async function handleUpload(){
    if(!uploadFile) return
    const form = new FormData(); form.append("file",uploadFile)
    try {
      const res = await api.post(`/reference/${activeTable.key}/upload`,form)
      setMessage({type:"success",text:`Uploaded: ${res.data.rows_added} rows. ${res.data.warnings?.join(", ")||""}`})
      loadTable()
    } catch(e){ setMessage({type:"error",text:e.response?.data?.detail||"Upload failed."}) }
    setUploadFile(null)
  }

  async function handleAddValue(){
    if(!newValue.trim()) return
    try {
      if(activeTable.key==="staff-names"){
        await api.post(`/reference/staff-names`,{full_name:newValue.trim(),is_active:true})
      } else if(activeTable.listName){
        await api.post(`/reference/ref-list/${activeTable.listName}`,{value:newValue.trim()})
      } else if(activeTable.key==="status-rules"){
        await api.post(`/reference/status-rules`,{status_value:newValue.trim(),is_eligible:true,counts_as_enrolled:false})
      } else if(activeTable.key==="advance-rules"){
        await api.post(`/reference/advance-rules`,{rule_name:newValue.trim(),advance_pct:0.5,trigger_status:"Current - Enrolled",start_date:new Date().toISOString().slice(0,10),is_active:true})
      } else if(activeTable.key==="incentive-tiers"){
        await api.post(`/reference/incentive-tiers`,{type:"MEET_THRESHOLD",name:newValue.trim(),threshold_amount:5000000,start_date:new Date().toISOString().slice(0,10),is_active:true})
      }
      setNewValue(""); setMessage({type:"success",text:"Added."}); loadTable()
    } catch(e){ setMessage({type:"error",text:e.response?.data?.detail||"Failed to add."}) }
  }

  async function handleDelete(row){
    const endpoint = activeTable.listName
      ? `/reference/ref-list/${activeTable.listName}/${row.id}`
      : `/reference/${activeTable.key}/${row.id}`
    try { await api.delete(endpoint); setMessage({type:"success",text:"Deleted."}); loadTable() }
    catch(e){ setMessage({type:"error",text:"Delete failed."}) }
  }

  async function handleSaveEdit(row){
    const endpoint = `/reference/${activeTable.key}/${row.id}`
    try {
      await api.put(endpoint, editValues)
      setMessage({type:"success",text:"Saved."}); setEditingRow(null); loadTable()
    } catch(e){ setMessage({type:"error",text:e.response?.data?.detail||"Save failed."}) }
  }

  const columns = rows.length>0
    ? activeTable.columnOrder
      ? activeTable.columnOrder.filter(c => c in rows[0])
      : Object.keys(rows[0]).filter(k=>!["id","updated_at","recorded_at"].includes(k))
    : []

  const isEditable = (col) => activeTable.editableFields?.includes(col)

  return (
    <div style={{display:"flex",height:"100vh",fontFamily:"Arial,sans-serif"}}>
      {/* Sidebar */}
      <div style={{width:260,background:"#1a2035",color:"#fff",padding:"16px 0",overflowY:"auto",flexShrink:0}}>
        <div style={{padding:"0 16px 12px",fontWeight:"bold",fontSize:11,color:"#f5a623",letterSpacing:1}}>REFERENCE TABLES</div>
        {SECTIONS.map(section=>(
          <div key={section.label}>
            <div style={{padding:"8px 16px 4px",fontSize:10,color:"#556",letterSpacing:1,fontWeight:600}}>{section.label}</div>
            {section.keys.map(key=>{
              const t=TABLES.find(t=>t.key===key); if(!t) return null
              const active=activeTable.key===key
              return (
                <div key={key} onClick={()=>{setActiveTable(t);setMessage(null)}} style={{padding:"7px 16px",cursor:"pointer",fontSize:12,background:active?"#2d3f6b":"transparent",color:active?"#fff":"#99a",borderLeft:active?"3px solid #f5a623":"3px solid transparent"}}>
                  {t.label}
                </div>
              )
            })}
          </div>
        ))}
      </div>

      {/* Main */}
      <div style={{flex:1,padding:24,overflowY:"auto",background:"var(--color-background-tertiary,#f4f6fa)"}}>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginBottom:16}}>
          <h2 style={{margin:0,fontSize:18,color:"#1a2035"}}>{activeTable.label}</h2>
          <div style={{display:"flex",gap:8}}>
            {activeTable.download && <button onClick={handleDownload} style={btn("#2563eb")}>⬇ Download Excel</button>}
            {activeTable.uploadable && (
              <label style={btn("#16a34a")}>⬆ Upload Excel
                <input type="file" accept=".xlsx" style={{display:"none"}} onChange={e=>setUploadFile(e.target.files[0])}/>
              </label>
            )}
          </div>
        </div>

        {uploadFile && (
          <div style={{background:"#fff3cd",padding:12,borderRadius:8,marginBottom:12,display:"flex",gap:12,alignItems:"center"}}>
            <span>Ready: <strong>{uploadFile.name}</strong></span>
            <button onClick={handleUpload} style={btn("#16a34a")}>Confirm</button>
            <button onClick={()=>setUploadFile(null)} style={btn("#6b7280")}>Cancel</button>
          </div>
        )}

        {message && (
          <div style={{padding:12,borderRadius:8,marginBottom:12,background:message.type==="error"?"#fee2e2":"#d1fae5",color:message.type==="error"?"#b91c1c":"#065f46",fontSize:13}}>
            {message.text}
          </div>
        )}

        {activeTable.addable && (
          <div style={{display:"flex",gap:8,marginBottom:16}}>
            <input value={newValue} onChange={e=>setNewValue(e.target.value)}
              placeholder={activeTable.key==="staff-names"?"Full name (Vietnamese OK)":"New value or name..."}
              style={{flex:1,padding:"8px 12px",borderRadius:6,border:"1px solid #ddd",fontSize:13,background:"var(--color-background-primary)",color:"var(--color-text-primary)"}}/>
            <button onClick={handleAddValue} style={btn("#7c3aed")}>+ Add</button>
          </div>
        )}

        {activeTable.editableFields && (
          <div style={{fontSize:11,color:"var(--color-text-secondary)",marginBottom:8}}>
            Editable fields: {activeTable.editableFields.join(", ")} — click ✏ to edit a row
          </div>
        )}

        {!loading && rows.length>0 && !activeTable.pivotView && (
          <div style={{fontSize:12,color:"var(--color-text-secondary)",marginBottom:8}}>{rows.length} records</div>
        )}

        {loading ? (
          <div style={{color:"#888",fontSize:13}}>Loading...</div>
        ) : activeTable.key==="staff-targets" ? (
          <StaffTargetsPivot rows={rows}/>
        ) : activeTable.key==="ytd-tracker" ? (
          <YtdTrackerPivot rows={rows}/>
        ) : (
          <div style={{background:"var(--color-background-primary)",borderRadius:10,overflow:"hidden",boxShadow:"0 1px 4px rgba(0,0,0,0.08)"}}>
            <div style={{overflowX:"auto"}}>
              <table style={{width:"100%",borderCollapse:"collapse",fontSize:12}}>
                <thead>
                  <tr style={{background:"var(--color-background-secondary)"}}>
                    {columns.map(c=>(
                      <th key={c} style={{padding:"9px 12px",textAlign:"left",fontWeight:600,color:"var(--color-text-primary)",borderBottom:"1px solid var(--color-border-tertiary)",whiteSpace:"nowrap",fontSize:11}}>
                        {c.replace(/_/g," ").toUpperCase()}
                        {isEditable(c) && <span style={{color:"#7c3aed",marginLeft:4}}>✎</span>}
                      </th>
                    ))}
                    <th style={{padding:"9px 12px",borderBottom:"1px solid var(--color-border-tertiary)"}}></th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row,i)=>{
                    const isEditing = editingRow===row.id
                    return (
                      <tr key={row.id||i} style={{borderBottom:"1px solid var(--color-border-tertiary)",background:isEditing?"#fffbeb":"transparent"}}>
                        {columns.map(c=>(
                          <td key={c} style={{padding:"8px 12px",color:"var(--color-text-primary)",maxWidth:240,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
                            {isEditing && isEditable(c) ? (
                              <input
                                defaultValue={row[c]??""} onChange={e=>setEditValues(v=>({...v,[c]:e.target.value}))}
                                style={{padding:"3px 6px",border:"1px solid #7c3aed",borderRadius:4,fontSize:12,width:"100%"}}/>
                            ) : (
                              typeof row[c]==="boolean" ? (row[c]?"✓":"—") :
                              typeof row[c]==="number" && c.includes("pct") ? `${(row[c]*100).toFixed(0)}%` :
                              typeof row[c]==="number" && row[c]>10000 ? row[c].toLocaleString() :
                              String(row[c]??"")
                            )}
                          </td>
                        ))}
                        <td style={{padding:"8px 12px",whiteSpace:"nowrap"}}>
                          {activeTable.editableFields && !isEditing && (
                            <button onClick={()=>{setEditingRow(row.id);setEditValues({})}} style={{background:"none",border:"none",color:"#7c3aed",cursor:"pointer",fontSize:12}}>✏</button>
                          )}
                          {isEditing && (
                            <span>
                              <button onClick={()=>handleSaveEdit(row)} style={{background:"none",border:"none",color:"#16a34a",cursor:"pointer",fontSize:12,marginRight:4}}>✓ Save</button>
                              <button onClick={()=>setEditingRow(null)} style={{background:"none",border:"none",color:"#6b7280",cursor:"pointer",fontSize:12}}>✗</button>
                            </span>
                          )}
                          {activeTable.addable && !isEditing && (
                            <button onClick={()=>handleDelete(row)} style={{background:"none",border:"none",color:"#ef4444",cursor:"pointer",fontSize:11,marginLeft:4}}>Remove</button>
                          )}
                        </td>
                      </tr>
                    )
                  })}
                  {rows.length===0 && (
                    <tr><td colSpan={columns.length+1} style={{padding:24,textAlign:"center",color:"var(--color-text-secondary)"}}>No data</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function btn(bg){ return {background:bg,color:"#fff",border:"none",padding:"8px 14px",borderRadius:6,cursor:"pointer",fontSize:12,fontWeight:500} }
