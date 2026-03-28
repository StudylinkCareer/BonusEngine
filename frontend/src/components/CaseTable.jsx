import { useState } from 'react'
import FlagBadge from './FlagBadge.jsx'
import { updateCase } from '../api/client.js'

const fmt = (n) => n ? Number(n).toLocaleString('vi-VN') : '—'

const PACKAGES = [
  'NONE', 'Standard Package (16tr)', 'Superior Package (6tr)',
  'Premium Package (9tr)', 'Standard Plus (3tr)', 'Standard Package (9tr5)',
  'Regular (9tr5)', 'SDS (7tr5)', 'Premium Canada (14tr)',
]

const SERVICE_FEES = [
  'NONE', 'VISA_ONLY', 'VISA_485', 'GUARDIAN_GRANTED', 'GUARDIAN_REFUSED',
  'DEPENDANT_GRANTED', 'DEPENDANT_REFUSED', 'GUARDIAN_AU_ADDON',
  'OUT_SYSTEM_FULL_AUS', 'MGMT_EXCEPTION', 'CANCELLED_FULL_SERVICE',
  'DIFFICULT_CASE', 'EXTRA_SCHOOL',
]

export default function CaseTable({ cases, runStatus, onCaseUpdated }) {
  const editable = runStatus === 'pending' || runStatus === 'reviewed'

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>No.</th>
            <th>Student</th>
            <th>Contract</th>
            <th>Status</th>
            <th>Country</th>
            <th>Institution</th>
            <th>Package</th>
            <th>Service Fee</th>
            <th>Inst. Type</th>
            <th>Handover</th>
            <th style={{ textAlign: 'right' }}>Bonus Enrolled</th>
            <th style={{ textAlign: 'right' }}>Bonus Priority</th>
            <th>Note</th>
            <th>Flags</th>
          </tr>
        </thead>
        <tbody>
          {cases.map(c => (
            <CaseRow
              key={c.id}
              c={c}
              editable={editable}
              onUpdated={onCaseUpdated}
            />
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CaseRow({ c, editable, onUpdated }) {
  const [saving, setSaving] = useState(false)
  const isAddon = c.row_type === 'ADDON'

  const handleChange = async (field, value) => {
    setSaving(true)
    try {
      const updated = await updateCase(c.id, { [field]: value })
      if (onUpdated) onUpdated(updated)
    } finally {
      setSaving(false)
    }
  }

  const rowStyle = {
    background: isAddon
      ? '#FFFDE7'
      : c.is_flagged
        ? '#FFFBEA'
        : undefined,
    opacity: saving ? 0.6 : 1,
  }

  return (
    <tr style={rowStyle}>
      <td style={{ color: '#666', fontSize: '11px' }}>{c.original_no}</td>
      <td>
        <div style={{ fontWeight: '500' }}>{c.student_name}</div>
        <div style={{ fontSize: '11px', color: '#666' }}>{c.student_id}</div>
      </td>
      <td style={{ fontSize: '11px', whiteSpace: 'nowrap' }}>{c.contract_id}</td>
      <td style={{ fontSize: '11px' }}>{c.app_status}</td>
      <td style={{ fontSize: '11px' }}>{c.country}</td>
      <td style={{ fontSize: '11px', maxWidth: '180px' }}>{c.institution}</td>

      {/* Package — editable dropdown */}
      <td>
        {editable ? (
          <select
            value={c.package_type || 'NONE'}
            onChange={e => handleChange('package_type', e.target.value)}
            style={{ fontSize: '11px', padding: '3px 6px', width: '100%' }}
          >
            {PACKAGES.map(p => <option key={p}>{p}</option>)}
          </select>
        ) : (
          <span style={{ fontSize: '11px' }}>{c.package_type}</span>
        )}
      </td>

      {/* Service fee — editable dropdown */}
      <td>
        {editable ? (
          <select
            value={c.service_fee_type || 'NONE'}
            onChange={e => handleChange('service_fee_type', e.target.value)}
            style={{ fontSize: '11px', padding: '3px 6px', width: '100%' }}
          >
            {SERVICE_FEES.map(s => <option key={s}>{s}</option>)}
          </select>
        ) : (
          <span style={{ fontSize: '11px' }}>{c.service_fee_type}</span>
        )}
      </td>

      <td style={{ fontSize: '11px' }}>{c.institution_type}</td>
      <td style={{ fontSize: '11px' }}>{c.handover}</td>

      <td className="num" style={{ fontWeight: c.bonus_enrolled ? '500' : undefined }}>
        {c.bonus_enrolled ? `₫${fmt(c.bonus_enrolled)}` : '—'}
      </td>
      <td className="num">
        {c.bonus_priority ? `₫${fmt(c.bonus_priority)}` : '—'}
      </td>
      <td style={{ fontSize: '11px', maxWidth: '200px', color: '#444' }}>
        {c.note_enrolled}
      </td>
      <td>
        <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
          {isAddon && <FlagBadge type="blue" label="ADDON" />}
          {c.is_flagged && <FlagBadge type="amber" label="Review" />}
          {c.is_recovery_item && <FlagBadge type="red" label="Recovery" />}
          {c.has_warnings && <FlagBadge type="amber" label="Warning" />}
        </div>
      </td>
    </tr>
  )
}
