import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { getRun, getCases, signOff, calculate } from '../api/client.js'
import CaseTable from '../components/CaseTable.jsx'
import FlagBadge from '../components/FlagBadge.jsx'

export default function Review() {
  const { id } = useParams()
  const navigate = useNavigate()

  const [run, setRun]       = useState(null)
  const [cases, setCases]   = useState([])
  const [loading, setLoading] = useState(true)
  const [calculating, setCalculating] = useState(false)
  const [error, setError]   = useState(null)

  useEffect(() => {
    Promise.all([getRun(id), getCases(id)])
      .then(([r, c]) => { setRun(r); setCases(c) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [id])

  const handleCaseUpdated = (updated) => {
    setCases(prev => prev.map(c => c.id === updated.id ? updated : c))
  }

  const handleSignOff = async () => {
    await signOff(id, 'signed_off', '')
    setRun(r => ({ ...r, status: 'signed_off' }))
  }

  const handleCalculate = async () => {
    setCalculating(true)
    setError(null)
    try {
      const result = await calculate(id)
      navigate(`/results/${id}`, { state: { result } })
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setCalculating(false)
    }
  }

  if (loading) return <p style={{ color: '#666' }}>Loading...</p>
  if (!run)    return <p style={{ color: '#A32D2D' }}>{error || 'Run not found'}</p>

  const flaggedCount = cases.filter(c => c.is_flagged).length
  const canCalculate = run.status === 'reviewed' || run.status === 'signed_off'

  return (
    <div>
      {/* Header */}
      <div className="flex-between" style={{ marginBottom: '20px' }}>
        <div>
          <h2 style={{ color: '#1E4E79', marginBottom: '4px' }}>
            Review — {run.staff_name}
          </h2>
          <p style={{ color: '#666', fontSize: '13px' }}>
            {monthName(run.run_month)} {run.run_year} &nbsp;|&nbsp;
            {cases.length} cases &nbsp;|&nbsp;
            <span className={`badge badge-${run.status}`}>{run.status}</span>
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          {flaggedCount > 0 && (
            <FlagBadge type="amber" label={`${flaggedCount} need review`} />
          )}
          {run.status === 'reviewed' && (
            <button onClick={handleSignOff}>Sign off</button>
          )}
          <button
            className="primary"
            onClick={handleCalculate}
            disabled={!canCalculate || calculating}
          >
            {calculating ? 'Calculating...' : 'Calculate bonuses →'}
          </button>
        </div>
      </div>

      {/* Warnings */}
      {run.warnings && (
        <div className="card" style={{ borderColor: '#FFCC00', background: '#FFFDE7', marginBottom: '16px' }}>
          <p style={{ fontSize: '12px', color: '#555' }}>
            ⚠ {run.warnings}
          </p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="card" style={{ borderColor: '#f09595', background: '#FCEBEB', marginBottom: '16px' }}>
          <p style={{ color: '#A32D2D', fontSize: '13px' }}>{error}</p>
        </div>
      )}

      {/* Flagged cases first */}
      {flaggedCount > 0 && (
        <div style={{ marginBottom: '8px' }}>
          <p style={{ fontSize: '12px', color: '#7a5c00', marginBottom: '8px' }}>
            ⚠ {flaggedCount} case(s) flagged amber — review package type and service fee before calculating.
          </p>
        </div>
      )}

      {/* Case table */}
      <CaseTable
        cases={cases}
        runStatus={run.status}
        onCaseUpdated={handleCaseUpdated}
      />
    </div>
  )
}

function monthName(m) {
  return ['','January','February','March','April','May','June',
          'July','August','September','October','November','December'][m] || m
}
