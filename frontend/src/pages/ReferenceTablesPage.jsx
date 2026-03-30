// frontend/src/pages/ReferenceTablesPage.jsx
// Admin-only page for managing all reference/lookup tables

import { useState, useEffect } from "react"
import api from "../api/client.js"

const TABLES = [
  // Staff
  { key: "staff-names",      label: "12 — Staff Names",          uploadable: false, download: true,  addable: true,  endpoint: "/reference/staff-names" },
  { key: "staff-targets",    label: "04 — Staff Targets",        uploadable: true,  download: true,  addable: false, endpoint: "/reference/staff-targets" },
  // Institutions
  { key: "priority-instns",  label: "03 — Priority Institutions",uploadable: false, download: true,  addable: false, endpoint: "/reference/priority-instns" },
  { key: "master-agents",    label: "11 — Master Agents",        uploadable: true,  download: true,  addable: false, endpoint: "/reference/master-agents" },
  // Countries & Client Types
  { key: "country-codes",    label: "14 — Country Codes",        uploadable: false, download: true,  addable: false, endpoint: "/reference/country-codes" },
  { key: "client-type-map",  label: "15 — Client Type Map",      uploadable: false, download: true,  addable: false, endpoint: "/reference/client-type-map" },
  { key: "client-weights",   label: "06 — Client Weights",       uploadable: false, download: true,  addable: false, endpoint: "/reference/client-weights" },
  // Rules & Rates
  { key: "status-rules",     label: "05 — Status Rules",         uploadable: false, download: true,  addable: false, endpoint: "/reference/status-rules" },
  { key: "service-fee-rates",label: "09 — Service Fee Rates",    uploadable: false, download: true,  addable: false, endpoint: "/reference/service-fee-rates",  dlKey: "service_fee_rates" },
  { key: "contract-bonuses", label: "07 — Contract Bonuses",     uploadable: false, download: true,  addable: false, endpoint: "/reference/contract-bonuses",   dlKey: "contract_bonuses" },
  // Trackers
  { key: "ytd-tracker",      label: "08 — YTD Tracker",          uploadable: false, download: true,  addable: false, endpoint: "/reference/ytd-tracker",        dlKey: "ytd_tracker" },
  { key: "advance-payments", label: "09 — Advance Payments",     uploadable: false, download: true,  addable: false, endpoint: "/reference/advance-payments",   dlKey: "advance_payments" },
  // Dropdown Lists
  { key: "application_status",label:"Application Status List",   uploadable: false, download: false, addable: true,  listName: "application_status" },
  { key: "package_type",     label: "Package Type List",          uploadable: false, download: false, addable: true,  listName: "package_type" },
  { key: "service_fee_type", label: "Service Fee Type List",      uploadable: false, download: false, addable: true,  listName: "service_fee_type" },
  { key: "addon_code",       label: "Add-on Code List",           uploadable: false, download: false, addable: true,  listName: "addon_code" },
  { key: "deferral",         label: "Deferral List",              uploadable: false, download: false, addable: true,  listName: "deferral" },
  { key: "institution_type", label: "Institution Type List",      uploadable: false, download: false, addable: true,  listName: "institution_type" },
]

const SECTIONS = [
  { label: "STAFF",           keys: ["staff-names","staff-targets"] },
  { label: "INSTITUTIONS",    keys: ["priority-instns","master-agents"] },
  { label: "COUNTRIES & TYPES", keys: ["country-codes","client-type-map","client-weights"] },
  { label: "RULES & RATES",   keys: ["status-rules","service-fee-rates","contract-bonuses"] },
  { label: "TRACKERS",        keys: ["ytd-tracker","advance-payments"] },
  { label: "DROPDOWN LISTS",  keys: ["application_status","package_type","service_fee_type","addon_code","deferral","institution_type"] },
]

export default function ReferenceTablesPage() {
  const [activeTable, setActiveTable] = useState(TABLES[0])
  const [rows, setRows]               = useState([])
  const [loading, setLoading]         = useState(false)
  const [message, setMessage]         = useState(null)
  const [uploadFile, setUploadFile]   = useState(null)
  const [newValue, setNewValue]       = useState("")

  useEffect(() => { loadTable() }, [activeTable])

  async function loadTable() {
    setLoading(true); setRows([]); setMessage(null)
    try {
      const endpoint = activeTable.listName
        ? `/reference/ref-list/${activeTable.listName}`
        : activeTable.endpoint
      const res = await api.get(endpoint)
      setRows(res.data)
    } catch (e) {
      setMessage({ type: "error", text: "Failed to load table." })
    }
    setLoading(false)
  }

  async function handleDownload() {
    try {
      const dlKey = activeTable.dlKey || activeTable.key.replace(/-/g, "_")
      const res = await api.get(`/reference/download/${dlKey}`, { responseType: "blob" })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement("a")
      a.href = url
      a.download = `${activeTable.key}_${new Date().toISOString().slice(0,10)}.xlsx`
      a.click(); URL.revokeObjectURL(url)
    } catch (e) {
      setMessage({ type: "error", text: "Download failed." })
    }
  }

  async function handleUpload() {
    if (!uploadFile) return
    const form = new FormData()
    form.append("file", uploadFile)
    try {
      const res = await api.post(`/reference/${activeTable.key}/upload`, form)
      setMessage({ type: "success", text: `Uploaded: ${res.data.rows_added} rows. ${res.data.warnings?.join(", ") || ""}` })
      loadTable()
    } catch (e) {
      setMessage({ type: "error", text: e.response?.data?.detail || "Upload failed." })
    }
    setUploadFile(null)
  }

  async function handleAddValue() {
    if (!newValue.trim()) return
    try {
      if (activeTable.key === "staff-names") {
        await api.post(`/reference/staff-names`, { full_name: newValue.trim(), is_active: true })
      } else {
        await api.post(`/reference/ref-list/${activeTable.listName}`, { value: newValue.trim() })
      }
      setNewValue("")
      setMessage({ type: "success", text: "Value added." })
      loadTable()
    } catch (e) {
      setMessage({ type: "error", text: e.response?.data?.detail || "Failed to add value." })
    }
  }

  async function handleDelete(row) {
    const endpoint = activeTable.listName
      ? `/reference/ref-list/${activeTable.listName}/${row.id}`
      : `/reference/${activeTable.key}/${row.id}`
    try {
      await api.delete(endpoint)
      setMessage({ type: "success", text: "Deleted." })
      loadTable()
    } catch (e) {
      setMessage({ type: "error", text: "Delete failed." })
    }
  }

  const columns = rows.length > 0
    ? Object.keys(rows[0]).filter(k => !["id","updated_at","recorded_at"].includes(k))
    : []

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "Arial, sans-serif" }}>

      {/* Sidebar */}
      <div style={{ width: 260, background: "#1a2035", color: "#fff", padding: "16px 0", overflowY: "auto", flexShrink: 0 }}>
        <div style={{ padding: "0 16px 12px", fontWeight: "bold", fontSize: 11, color: "#f5a623", letterSpacing: 1 }}>
          REFERENCE TABLES
        </div>
        {SECTIONS.map(section => (
          <div key={section.label}>
            <div style={{ padding: "8px 16px 4px", fontSize: 10, color: "#556", letterSpacing: 1, fontWeight: 600 }}>
              {section.label}
            </div>
            {section.keys.map(key => {
              const t = TABLES.find(t => t.key === key)
              if (!t) return null
              const active = activeTable.key === key
              return (
                <div key={key}
                  onClick={() => { setActiveTable(t); setMessage(null) }}
                  style={{
                    padding: "7px 16px", cursor: "pointer", fontSize: 12,
                    background: active ? "#2d3f6b" : "transparent",
                    color: active ? "#fff" : "#99a",
                    borderLeft: active ? "3px solid #f5a623" : "3px solid transparent",
                  }}>
                  {t.label}
                </div>
              )
            })}
          </div>
        ))}
      </div>

      {/* Main content */}
      <div style={{ flex: 1, padding: 24, overflowY: "auto", background: "#f4f6fa" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
          <h2 style={{ margin: 0, fontSize: 18, color: "#1a2035" }}>{activeTable.label}</h2>
          <div style={{ display: "flex", gap: 8 }}>
            {activeTable.download && (
              <button onClick={handleDownload} style={btnStyle("#2563eb")}>⬇ Download Excel</button>
            )}
            {activeTable.uploadable && (
              <label style={btnStyle("#16a34a")}>
                ⬆ Upload Excel
                <input type="file" accept=".xlsx" style={{ display: "none" }}
                  onChange={e => setUploadFile(e.target.files[0])} />
              </label>
            )}
          </div>
        </div>

        {uploadFile && (
          <div style={{ background: "#fff3cd", padding: 12, borderRadius: 8, marginBottom: 12, display: "flex", gap: 12, alignItems: "center" }}>
            <span>Ready to upload: <strong>{uploadFile.name}</strong></span>
            <button onClick={handleUpload} style={btnStyle("#16a34a")}>Confirm Upload</button>
            <button onClick={() => setUploadFile(null)} style={btnStyle("#6b7280")}>Cancel</button>
          </div>
        )}

        {message && (
          <div style={{
            padding: 12, borderRadius: 8, marginBottom: 12,
            background: message.type === "error" ? "#fee2e2" : "#d1fae5",
            color: message.type === "error" ? "#b91c1c" : "#065f46", fontSize: 13
          }}>
            {message.text}
          </div>
        )}

        {activeTable.addable && (
          <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
            <input value={newValue} onChange={e => setNewValue(e.target.value)}
              placeholder={activeTable.key === "staff-names" ? "Full name (Vietnamese OK)" : "New value..."}
              style={{ flex: 1, padding: "8px 12px", borderRadius: 6, border: "1px solid #ddd", fontSize: 13 }} />
            <button onClick={handleAddValue} style={btnStyle("#7c3aed")}>+ Add</button>
          </div>
        )}

        {/* Stats bar */}
        {rows.length > 0 && (
          <div style={{ fontSize: 12, color: "#6b7280", marginBottom: 8 }}>
            {rows.length} records
          </div>
        )}

        {loading ? (
          <div style={{ color: "#888", fontSize: 13 }}>Loading...</div>
        ) : (
          <div style={{ background: "#fff", borderRadius: 10, overflow: "hidden", boxShadow: "0 1px 4px rgba(0,0,0,0.08)" }}>
            <div style={{ overflowX: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                <thead>
                  <tr style={{ background: "#f1f5f9" }}>
                    {columns.map(c => (
                      <th key={c} style={{ padding: "9px 12px", textAlign: "left", fontWeight: 600, color: "#374151", borderBottom: "1px solid #e5e7eb", whiteSpace: "nowrap" }}>
                        {c.replace(/_/g, " ").toUpperCase()}
                      </th>
                    ))}
                    {activeTable.addable && <th style={{ padding: "9px 12px", borderBottom: "1px solid #e5e7eb" }}></th>}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr key={row.id || i} style={{ borderBottom: "1px solid #f3f4f6" }}>
                      {columns.map(c => (
                        <td key={c} style={{ padding: "8px 12px", color: "#1f2937", maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {String(row[c] ?? "")}
                        </td>
                      ))}
                      {activeTable.addable && (
                        <td style={{ padding: "8px 12px" }}>
                          <button onClick={() => handleDelete(row)}
                            style={{ background: "none", border: "none", color: "#ef4444", cursor: "pointer", fontSize: 11 }}>
                            Remove
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                  {rows.length === 0 && (
                    <tr>
                      <td colSpan={columns.length + 1} style={{ padding: 24, textAlign: "center", color: "#9ca3af" }}>
                        No data
                      </td>
                    </tr>
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

function btnStyle(bg) {
  return { background: bg, color: "#fff", border: "none", padding: "8px 14px", borderRadius: 6, cursor: "pointer", fontSize: 12, fontWeight: 500 }
}
