# =============================================================================
# services/recalc.py  |  Report recalculation
# =============================================================================
# Re-runs the engine against persisted cases (BonusReportCase) and writes
# the new bonus values back. Used after operators edit classification fields
# during the review phase.
#
# Input: a BonusReport that already exists in the DB with cases attached.
# Output: same cases with bonus_enrolled / bonus_priority / notes updated;
#         report totals (engine_total, tier, target, enrolled) updated.
#
# This intentionally skips the classify_cases step. Classification happens
# at upload time. After upload, operator edits to classification fields
# (institution_type, package_type, service_fee_type, office, etc.) are the
# authoritative values — re-running the auto-classifier would overwrite
# those edits.
# =============================================================================

from datetime import datetime
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

from ..models import BonusReport, BonusReportCase, BonusFieldChange, User
from ..engine.config import load_config
from ..engine.calc import calculate_bonuses
from ..engine.models import CaseRecord
from ..engine.constants import (
    SCHEME_HN_DIRECT, SCHEME_CO_SUB, OFFICE_HN, OFFICE_DN,
)


def _db_case_to_record(case: BonusReportCase) -> CaseRecord:
    """Convert a persisted BonusReportCase back into an in-memory CaseRecord.

    Mirrors the inverse of the persistence step in routers/reports.py
    upload_report. Any classification edits the operator made are picked
    up here because they live on the BonusReportCase row.
    """
    cs = CaseRecord()
    cs.contract_id      = case.contract_id or ""
    cs.student_name     = case.student_name or ""
    cs.student_id       = case.student_id or ""
    cs.app_status       = case.app_status or ""
    cs.client_type      = case.client_type or ""
    cs.country          = case.country or ""
    cs.institution      = case.institution or ""
    cs.agent            = case.refer_agent or ""
    cs.notes            = case.notes or ""
    cs.institution_type = case.institution_type or "DIRECT"
    cs.service_fee_type = case.service_fee_type or "NONE"
    cs.package_type     = case.package_type or "NONE"
    cs.is_vietnam       = bool(case.is_vietnam)
    cs.is_agent_referred = bool(case.is_agent_referred)
    cs.office           = case.office or ""
    cs.row_type         = case.row_type or "BASE"
    cs.deferral         = case.deferral or "NONE"
    cs.handover         = case.handover or "NO"
    cs.target_owner     = case.target_owner or ""
    cs.targets_name     = case.targets_name or ""
    cs.presales_agent   = case.presales_agent or "NONE"
    cs.incentive        = case.incentive or 0
    cs.group_agent_name = case.group_agent_name or ""
    cs.case_transition  = case.case_transition or "NO"
    # prior_month_rate stored as String(20) on the DB — convert defensively
    try:
        cs.prior_month_rate = int(case.prior_month_rate) if case.prior_month_rate else 0
    except (ValueError, TypeError):
        cs.prior_month_rate = 0
    cs.priority_factor  = float(case.priority_factor or 0.0)
    # Date fields stored as ISO strings on the DB
    cs.course_start = _parse_date(case.course_start)
    cs.visa_date    = _parse_date(case.visa_date)
    return cs


def _parse_date(val) -> Optional[datetime]:
    if not val: return None
    if hasattr(val, 'isoformat'): return val  # already a date
    try:
        from datetime import date
        return date.fromisoformat(str(val)[:10])
    except (ValueError, TypeError):
        return None


def recalculate_report(db: Session, report: BonusReport,
                       triggered_by: User) -> dict:
    """Re-run the engine over all cases in a report, write results back.

    Returns:
      {
        "report_id": str,
        "tier": str,
        "target": int,
        "enrolled": int,
        "engine_total": int,
        "cases_updated": int,
        "diffs": [ ... per-case before/after where bonus changed ... ],
      }

    Side effects:
      - Updates each BonusReportCase.bonus_enrolled / bonus_priority / notes
      - Updates report.engine_total, tier, target, enrolled, base_rate
      - Creates BonusFieldChange entries for cases whose bonus moved
      - Updates report.updated_at
    """
    cfg = load_config(db)

    # Load and convert all cases
    db_cases = (db.query(BonusReportCase)
                .filter(BonusReportCase.report_id == report.id)
                .all())
    if not db_cases:
        return {"report_id": report.id, "tier": None, "target": 0,
                "enrolled": 0, "engine_total": 0, "cases_updated": 0,
                "diffs": []}

    # Snapshot current bonus values for diff computation
    before = {c.id: (c.bonus_enrolled or 0, c.bonus_priority or 0)
              for c in db_cases}

    case_records = [_db_case_to_record(c) for c in db_cases]

    # Run the engine
    calculated, tier, target, enrolled = calculate_bonuses(
        case_records, report.staff_name, report.year, report.month,
        cfg, office=report.office,
    )

    # Index calculated cases by contract_id for write-back
    calc_by_cid = {c.contract_id: c for c in calculated}

    cases_updated = 0
    diffs = []
    for db_case in db_cases:
        calc = calc_by_cid.get(db_case.contract_id)
        if not calc:
            continue
        old_enr, old_pri = before[db_case.id]
        new_enr = calc.bonus_enrolled or 0
        new_pri = calc.bonus_priority or 0

        db_case.bonus_enrolled  = new_enr
        db_case.bonus_priority  = new_pri
        db_case.note_enrolled   = calc.note_enrolled
        db_case.note_enrolled_2 = calc.note_enrolled2
        db_case.note_priority   = calc.note_priority
        db_case.note_priority_2 = calc.note_priority2

        if old_enr != new_enr or old_pri != new_pri:
            cases_updated += 1
            diffs.append({
                "case_id":     db_case.id,
                "contract_id": db_case.contract_id,
                "old_enrolled": old_enr, "new_enrolled": new_enr,
                "old_priority": old_pri, "new_priority": new_pri,
                "old_total":    old_enr + old_pri,
                "new_total":    new_enr + new_pri,
            })
            # Audit trail entry
            db.add(BonusFieldChange(
                report_id   = report.id,
                case_id     = db_case.id,
                field_name  = "_recalc",
                field_label = "Recalculation",
                old_value   = str(old_enr + old_pri),
                new_value   = str(new_enr + new_pri),
                comment     = f"Engine recalculation. "
                              f"Enrolled: {old_enr:,} → {new_enr:,}, "
                              f"Priority: {old_pri:,} → {new_pri:,}",
                changed_by  = triggered_by.full_name or triggered_by.username,
            ))

    # Update report-level totals
    base_cases = [c for c in calculated if c.row_type != "ADDON"]
    new_engine_total = sum((c.bonus_enrolled or 0) + (c.bonus_priority or 0)
                           for c in base_cases)
    report.engine_total = new_engine_total
    report.tier         = tier
    report.target       = target
    report.enrolled     = enrolled
    report.gap          = new_engine_total - (report.manual_total or 0)
    report.updated_at   = datetime.utcnow()

    db.commit()

    return {
        "report_id":     report.id,
        "tier":          tier,
        "target":        target,
        "enrolled":      enrolled,
        "engine_total":  new_engine_total,
        "manual_total":  report.manual_total or 0,
        "gap":           report.gap,
        "cases_updated": cases_updated,
        "diffs":         diffs,
    }
