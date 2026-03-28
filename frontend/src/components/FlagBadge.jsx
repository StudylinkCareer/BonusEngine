export default function FlagBadge({ type, label }) {
  const styles = {
    amber: { background: '#FFFF8C', color: '#555',    border: '0.5px solid #cccc00' },
    red:   { background: '#FFCCCC', color: '#A32D2D', border: '0.5px solid #f09595' },
    green: { background: '#E2EFDA', color: '#3B6D11', border: '0.5px solid #97C459' },
    blue:  { background: '#BDD7EE', color: '#1E4E79', border: '0.5px solid #85B7EB' },
  }
  const s = styles[type] || styles.blue
  return (
    <span style={{
      display: 'inline-block',
      fontSize: '10px',
      fontWeight: '500',
      padding: '2px 7px',
      borderRadius: '10px',
      whiteSpace: 'nowrap',
      ...s,
    }}>
      {label}
    </span>
  )
}
