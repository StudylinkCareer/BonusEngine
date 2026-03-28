// =============================================================================
// Results.jsx
// =============================================================================
import { useState, useEffect } from 'react'
import { useParams, useLocation, useNavigate } from 'react-router-dom'
import { getRun, exportRun } from '../api/client.js'
import BonusResult from '../components/BonusResult.jsx'
import CaseTable from '../components/CaseTable.jsx'

export default function Results() {
  const { id } = useParams()
  const { state } = useLocation()
  const navigate = useNavigate()

  const [run, setRun]         = useState(null)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)

  useEffect(() => {
    getRun(id)
      .then(setRun)
      .finally(() => setLoading(false))
  }, [id])

  const handleExport = async () => {
    setExporting(true)
    try {
      const blob = await exportRun(id)
      const url  = URL.createObjectURL(blob)
      const a    = document.createElement('a')
      a.href     = url
      a.download = `BonusReport_${run.staff_name.replace(/ /g,'_')}_${run.run_month}${run.run_year}.xlsx`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  if (loading) return <p style={{ color: '#666' }}>Loading...</p>
  if (!run)    return <p style={{ color: '#A32D2D' }}>Run not found</p>

  const result = state?.result || run

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: '20px' }}>
        <h2 style={{ color: '#1E4E79' }}>
          Results — {run.staff_name} &nbsp;
          <span style={{ fontSize: '14px', color: '#666', fontWeight: '400' }}>
            {monthName(run.run_month)} {run.run_year}
          </span>
        </h2>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button onClick={() => navigate(`/review/${id}`)}>← Back to review</button>
          <button className="primary" onClick={handleExport} disabled={exporting}>
            {exporting ? 'Exporting...' : '↓ Export Excel'}
          </button>
        </div>
      </div>

      <BonusResult result={result} />

      <div style={{ marginTop: '24px' }}>
        <h3 style={{ color: '#1E4E79', marginBottom: '12px', fontSize: '14px' }}>Case Detail</h3>
        <CaseTable cases={run.cases || []} runStatus={run.status} />
      </div>
    </div>
  )
}

function monthName(m) {
  return ['','January','February','March','April','May','June',
          'July','August','September','October','November','December'][m] || m
}
