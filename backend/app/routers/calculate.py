# =============================================================================
# routers/calculate.py
# Calculation trigger and sign-off endpoints.
# =============================================================================

import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Run, Case, Signoff, User
from ..schemas import CalculationResult, CaseOut, SignoffCreate, SignoffOut
from ..routers.auth import get_current_user
from ..engine.config import load_config

from ..engine.calc import calculate_bonuses
from ..engine.models import CaseRecord
from ..engine.constants import ROW_BASE as ROW_TYPE_BASE

from ..engine.constants import OFFICE_HCM, OFFICE_HN, OFFICE_DN, OFFICE_DEFAULT

router = APIRouter()

ENGINE_WORKBOOK = os.environ.get("ENGINE_WORKBOOK_PATH", "data/config/engine.xlsm")


def _db_case_to_record(case: Case) -> CaseRecord:
    """Converts a database Case model to a CaseRecord for the engine."""
    cs = CaseRecord()
    cs.original_no      = case.original_no or ""
    cs.student_name     = case.student_name or ""
    cs.student_id       = case.student_id or ""
    cs.contract_id      = case.contract_id or ""
    cs.contract_date    = case.contract_date
    cs.client_type      = case.client_type or ""
    cs.client_type_code = case.client_type_code or ""
    cs.country          = case.country or ""
    cs.country_code     = case.country_code or ""
    cs.agent            = case.agent or ""
    cs.system_type      = case.system_type or ""
    cs.app_status       = case.app_status or ""
    cs.visa_date        = case.visa_date
    cs.institution      = case.institution or ""
    cs.course_start     = case.course_start
    cs.course_status    = case.course_status or ""
    cs.counsellor       = case.counsellor or ""
    cs.case_officer     = case.case_officer or ""
    cs.presales_agent   = case.presales_agent or "NONE"
    cs.incentive        = case.incentive or 0
    cs.notes            = case.notes or ""
    cs.service_fee_type = case.service_fee_type or "NONE"
    cs.deferral         = case.deferral or "NONE"
    cs.package_type     = case.package_type or "NONE"
    cs.office_override  = case.office_override or OFFICE_DEFAULT
    cs.handover         = case.handover or "NO"
    cs.target_owner     = case.target_owner or ""
    cs.case_transition  = case.case_transition or "NO"
    cs.prior_month_rate = case.prior_month_rate or 0
    cs.institution_type = case.institution_type or "DIRECT"
    cs.group_agent_name = case.group_agent_name or ""
    cs.targets_name     = case.targets_name or ""
    cs.row_type         = case.row_type or "BASE"
    cs.addon_code       = case.addon_code or ""
    cs.addon_count      = case.addon_count or 0
    cs.prior_advances_paid = case.prior_advances or 0
    cs.office_source    = case.office_override or OFFICE_DEFAULT
    return cs


def _write_results_back(db: Session, run_id: int, calculated_cases: list[CaseRecord]):
    """Writes calculated bonus results back to the database."""
    cases_db = {c.original_no: c for c in
                db.query(Case).filter(Case.run_id == run_id).all()}

    for cs in calculated_cases:
        case_db = cases_db.get(cs.original_no)
        if not case_db:
            continue
        case_db.bonus_enrolled   = cs.bonus_enrolled
        case_db.note_enrolled    = cs.note_enrolled
        case_db.note_enrolled2   = cs.note_enrolled2
        case_db.bonus_priority   = cs.bonus_priority
        case_db.note_priority    = cs.note_priority
        case_db.note_priority2   = cs.note_priority2
        case_db.prior_advances   = cs.prior_advances_paid
        case_db.net_payable      = cs.net_payable
        case_db.stored_base_rate = cs.stored_base_rate
        case_db.is_recovery_item = cs.is_recovery_item

    db.commit()


@router.post("/run/{run_id}", response_model=CalculationResult)
def run_calculation(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Triggers the bonus calculation for a run.
    Run must be in 'signed_off' or 'reviewed' status.
    """
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in ("reviewed", "signed_off"):
        raise HTTPException(
            status_code=400,
            detail=f"Run must be reviewed or signed off before calculation. "
                   f"Current status: {run.status}"
        )

    if not os.path.exists(ENGINE_WORKBOOK):
        raise HTTPException(status_code=500, detail="Engine workbook not configured")

    cfg = load_config(ENGINE_WORKBOOK, run.run_year)

    # Get staff config
    staff_cfg = cfg.get_staff_config(run.staff_name, run.office or OFFICE_HCM)
    if not staff_cfg:
        raise HTTPException(
            status_code=400,
            detail=f"Staff '{run.staff_name}' not found in 04_STAFF_TARGETS "
                   f"for year {run.run_year}. Check 12_STAFF_NAMES mapping."
        )

    # Load cases from DB and convert to CaseRecord
    db_cases = db.query(Case).filter(Case.run_id == run_id).all()
    case_records = [_db_case_to_record(c) for c in db_cases]

    # Run calculation
    calculated = calculate_bonuses(
        cases=case_records,
        cfg_staff=staff_cfg,
        run_month=run.run_month,
        run_year=run.run_year,
        cfg=cfg,
    )

    # Write results back to DB
    _write_results_back(db, run_id, calculated)

    # Update run totals
    base_cases = [c for c in calculated if c.row_type != "ADDON"]
    total_bonus    = sum(c.bonus_enrolled for c in base_cases)
    total_priority = sum(c.bonus_priority for c in base_cases)
    enrolled_count = sum(1 for c in base_cases if c.bonus_enrolled > 0 and not
                        cfg.get_status_rule(c.app_status).is_carry_over)

    from ..engine.calc import determine_tier, count_enrolled_for_tier
    tier_enrolled = count_enrolled_for_tier(case_records, staff_cfg, cfg)
    target = staff_cfg.targets.get(run.run_month, 0)
    tier = determine_tier(tier_enrolled, target)

    run.total_bonus    = total_bonus + total_priority
    run.enrolled_count = enrolled_count
    run.tier           = tier
    run.target         = target
    run.status         = "calculated"
    run.calculated_at  = datetime.utcnow()
    db.commit()

    # Build response
    fresh_cases = db.query(Case).filter(Case.run_id == run_id).all()
    return CalculationResult(
        run_id=run_id,
        staff_name=run.staff_name,
        run_month=run.run_month,
        run_year=run.run_year,
        office=run.office or OFFICE_HCM,
        target=target,
        enrolled_count=tier_enrolled,
        tier=tier,
        total_bonus=total_bonus,
        total_priority=total_priority,
        grand_total=total_bonus + total_priority,
        cases=fresh_cases,
    )


@router.post("/run/{run_id}/signoff", response_model=SignoffOut)
def sign_off(
    run_id: int,
    signoff_in: SignoffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Records a sign-off action on a run."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    signoff = Signoff(
        run_id=run_id,
        user_id=current_user.id,
        action=signoff_in.action,
        comment=signoff_in.comment,
    )
    db.add(signoff)

    # Update run status
    status_map = {
        "reviewed":   "reviewed",
        "signed_off": "signed_off",
        "approved":   "approved",
        "rejected":   "pending",
    }
    if signoff_in.action in status_map:
        run.status = status_map[signoff_in.action]

    db.commit()
    db.refresh(signoff)
    return signoff
