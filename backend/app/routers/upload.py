# =============================================================================
# routers/upload.py
# File upload endpoint — ingests CRM Excel reports and creates a Run.
# =============================================================================

import os
import tempfile
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Run, Case, User
from ..schemas import UploadResponse
from ..routers.auth import get_current_user
from ..engine.input import parse_crm_report
from ..engine.config import load_config

router = APIRouter()

ENGINE_WORKBOOK = os.environ.get("ENGINE_WORKBOOK_PATH", "data/config/engine.xlsm")


def _get_config(run_year: int):
    if not os.path.exists(ENGINE_WORKBOOK):
        raise HTTPException(
            status_code=500,
            detail=f"Engine workbook not found at {ENGINE_WORKBOOK}. "
                   f"Upload it via the admin config page."
        )
    return load_config(ENGINE_WORKBOOK, run_year)


@router.post("/crm", response_model=UploadResponse)
async def upload_crm_report(
    file: UploadFile = File(...),
    run_month: int = Form(...),
    run_year: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a native CRM closed-file report (Báo cáo format).
    Parses it, creates a Run and Case rows for operator review.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) accepted")

    cfg = _get_config(run_year)

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        raw_rows, staff_name, warnings = parse_crm_report(tmp_path, cfg)
    finally:
        os.unlink(tmp_path)

    if not raw_rows:
        raise HTTPException(status_code=400, detail="No case rows found in uploaded file")

    # Create Run
    run = Run(
        staff_name=staff_name or "Unknown",
        run_month=run_month,
        run_year=run_year,
        status="pending",
        input_file=file.filename,
        created_by=current_user.id,
        warnings=str(warnings) if warnings else None,
    )
    db.add(run)
    db.flush()

    # Create Case rows from raw CRM data
    flagged = 0
    for r in raw_rows:
        is_flagged = not r.get("package_type")  # Amber if package unknown
        case = Case(
            run_id=run.id,
            original_no=r.get("no"),
            student_name=r.get("student_name"),
            student_id=r.get("student_id"),
            contract_id=r.get("contract_id"),
            contract_date=r.get("contract_date"),
            client_type=r.get("client_type"),
            country=r.get("country"),
            agent=r.get("agent"),
            system_type=r.get("system_type"),
            app_status=r.get("app_status"),
            visa_date=r.get("visa_date"),
            institution=r.get("institution"),
            course_start=r.get("course_start"),
            course_status=r.get("course_status"),
            counsellor=r.get("counsellor"),
            case_officer=r.get("case_officer"),
            notes=r.get("notes"),
            institution_type=r.get("institution_type", "DIRECT"),
            group_agent_name=r.get("group_agent", ""),
            package_type=r.get("package_type") or "NONE",
            targets_name=staff_name,
            is_flagged=is_flagged,
        )
        if is_flagged:
            flagged += 1
        db.add(case)

    db.commit()
    db.refresh(run)

    return UploadResponse(
        run_id=run.id,
        staff_name=run.staff_name,
        case_count=len(raw_rows),
        flagged_count=flagged,
        errors=[],
        warnings=warnings,
        message=f"Uploaded {len(raw_rows)} cases for review. "
                f"{flagged} cases need attention before calculation.",
    )


@router.post("/template", response_model=UploadResponse)
async def upload_template_file(
    file: UploadFile = File(...),
    run_month: int = Form(...),
    run_year: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a completed v7 template input file.
    Validates all mandatory fields and creates a Run ready for calculation.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) accepted")

    cfg = _get_config(run_year)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        cases_parsed, staff_name, errors, warnings = parse_input_file(tmp_path, cfg)
    finally:
        os.unlink(tmp_path)

    if errors:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Validation errors found. Correct and re-upload.",
                "errors": errors,
            }
        )

    run = Run(
        staff_name=staff_name or "Unknown",
        run_month=run_month,
        run_year=run_year,
        status="reviewed",  # Template files are pre-validated
        input_file=file.filename,
        created_by=current_user.id,
        warnings=str(warnings) if warnings else None,
    )
    db.add(run)
    db.flush()

    flagged = 0
    for cs in cases_parsed:
        is_flagged = cs.package_type in ("", "NONE") or bool(cs.warn_msg)
        case = Case(
            run_id=run.id,
            original_no=cs.original_no,
            student_name=cs.student_name,
            student_id=cs.student_id,
            contract_id=cs.contract_id,
            contract_date=cs.contract_date,
            client_type=cs.client_type,
            client_type_code=cs.client_type_code,
            country=cs.country,
            country_code=cs.country_code,
            agent=cs.agent,
            system_type=cs.system_type,
            app_status=cs.app_status,
            visa_date=cs.visa_date,
            institution=cs.institution,
            course_start=cs.course_start,
            course_status=cs.course_status,
            counsellor=cs.counsellor,
            case_officer=cs.case_officer,
            presales_agent=cs.presales_agent,
            incentive=cs.incentive,
            notes=cs.notes,
            service_fee_type=cs.service_fee_type,
            deferral=cs.deferral,
            package_type=cs.package_type,
            office_override=cs.office_override,
            handover=cs.handover,
            target_owner=cs.target_owner,
            case_transition=cs.case_transition,
            prior_month_rate=cs.prior_month_rate,
            institution_type=cs.institution_type,
            group_agent_name=cs.group_agent_name,
            targets_name=cs.targets_name,
            row_type=cs.row_type,
            addon_code=cs.addon_code,
            addon_count=cs.addon_count,
            is_flagged=is_flagged,
            has_warnings=bool(cs.warn_msg),
            warn_msg=cs.warn_msg,
        )
        if is_flagged:
            flagged += 1
        db.add(case)

    db.commit()

    return UploadResponse(
        run_id=run.id,
        staff_name=run.staff_name,
        case_count=len(cases_parsed),
        flagged_count=flagged,
        errors=[],
        warnings=warnings,
        message=f"Uploaded and validated {len(cases_parsed)} cases. Ready for review.",
    )
