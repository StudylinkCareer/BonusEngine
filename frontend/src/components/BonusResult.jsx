const fmt = (n) => (n ?? 0).toLocaleString('vi-VN')

export default function BonusResult({ result }) {
  if (!result) return null

  const tierColor = {
    OVER:       '#276221',
    MEET_HIGH:  '#1E4E79',
    MEET_LOW:   '#2E75B6',
    MEET:       '#2E75B6',
    UNDER:      '#A32D2D',
  }[result.tier] || '#222'

  return (
    <div>
      {/* Summary cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '24px' }}>
        <MetricCard label="Staff" value={result.staff_name} />
        <MetricCard label="Period" value={`${monthName(result.run_month)} ${result.run_year}`} />
        <MetricCard label="Target" value={result.target} />
        <MetricCard label="Enrolled" value={result.enrolled_count} />
        <MetricCard label="Tier" value={result.tier?.replace('_', ' ')} color={tierColor} />
        <MetricCard label="Bonus Enrolled" value={`₫${fmt(result.total_bonus)}`} />
        <MetricCard label="Priority Bonus" value={`₫${fmt(result.total_priority)}`} />
        <MetricCard label="Grand Total" value={`₫${fmt(result.grand_total)}`} bold />
      </div>
    </div>
  )
}

function MetricCard({ label, value, color, bold }) {
  return (
    <div style={{
      background: '#f5f7fa',
      borderRadius: '8px',
      padding: '12px 14px',
    }}>
      <div style={{ fontSize: '11px', color: '#666', marginBottom: '4px' }}>{label}</div>
      <div style={{
        fontSize: '15px',
        fontWeight: bold ? '600' : '500',
        color: color || '#222',
      }}>
        {value}
      </div>
    </div>
  )
}

function monthName(m) {
  return ['', 'January','February','March','April','May','June',
          'July','August','September','October','November','December'][m] || m
}
