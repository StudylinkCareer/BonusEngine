import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { getRuns } from '../api/client.jsx'

const fmt = (n) => n ? Number(n).toLocaleString('vi-VN') : '—'

const MONTHS = ['','January','February','March','April','May','June',
                'July','August','September','October','November','December']

export default function History() {
  const navigate = useNavigate()
  const [runs, setRuns]       = useState([])
  const [loading, setLoading] = useState(true)
  const [year, setYear]       = useState(new Date().getFullYear())

  useEffect(() => {
    getRuns({ run_year: year })
      .then(setRuns)
      .finally(() => setLoading(false))
  }, [year])

  const statusNav = (run) => {
    if (run.status === 'calculated' || run.status === 'approved') {
      navigate(`/results/${run.id}`)
    } else {
      navigate(`/review/${run.id}`)
    }
  }

  return (
    <div>
      <div className="flex-between" style={{ marginBottom: '20px' }}>
        <h2 style={{ color: '#1E4E79' }}>Run History</h2>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <select value={year} onChange={e => setYear(Number(e.target.value))}>
            {[2024, 2025, 2026].map(y => <option key={y}>{y}</option>)}
          </select>
          <button className="primary" onClick={() => navigate('/upload')}>
            + New upload
          </button>
        </div>
      </div>

      {loading ? (
        <p style={{ color: '#666' }}>Loading...</p>
      ) : runs.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: '40px' }}>
          <p style={{ color: '#666' }}>No runs found for {year}.</p>
          <button
            className="primary"
            style={{ marginTop: '16px' }}
            onClick={() => navigate('/upload')}
          >
            Upload first report
          </button>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Staff</th>
                <th>Period</th>
                <th>Status</th>
                <th>Target</th>
                <th>Enrolled</th>
                <th>Tier</th>
                <th style={{ textAlign: 'right' }}>Total Bonus</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {runs.map(run => (
                <tr key={run.id} style={{ cursor: 'pointer' }} onClick={() => statusNav(run)}>
                  <td style={{ fontWeight: '500' }}>{run.staff_name}</td>
                  <td style={{ whiteSpace: 'nowrap' }}>
                    {MONTHS[run.run_month]} {run.run_year}
                  </td>
                  <td>
                    <span className={`badge badge-${run.status}`}>
                      {run.status}
                    </span>
                  </td>
                  <td className="num">{run.target ?? '—'}</td>
                  <td className="num">{run.enrolled_count ?? '—'}</td>
                  <td>
                    {run.tier && (
                      <span style={{
                        fontSize: '11px', fontWeight: '500',
                        color: {
                          OVER: '#276221', MEET_HIGH: '#1E4E79',
                          MEET_LOW: '#2E75B6', MEET: '#2E75B6',
                          UNDER: '#A32D2D',
                        }[run.tier] || '#222'
                      }}>
                        {run.tier?.replace('_', ' ')}
                      </span>
                    )}
                  </td>
                  <td className="num" style={{ fontWeight: '500' }}>
                    {run.total_bonus ? `₫${fmt(run.total_bonus)}` : '—'}
                  </td>
                  <td style={{ fontSize: '11px', color: '#666' }}>
                    {new Date(run.created_at).toLocaleDateString('en-GB')}
                  </td>
                  <td>
                    <button
                      style={{ fontSize: '11px', padding: '3px 10px' }}
                      onClick={e => { e.stopPropagation(); statusNav(run) }}
                    >
                      {run.status === 'calculated' || run.status === 'approved'
                        ? 'View results'
                        : 'Review →'}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
