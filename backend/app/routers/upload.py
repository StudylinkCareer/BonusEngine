# =============================================================================
# routers/upload.py
# File upload endpoint — ingests CRM Excel reports and creates a Run.
# Config is loaded from PostgreSQL — no engine.xlsm required at runtime.
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


@router.post("/crm", response_model=UploadResponse)
async def upload_crm_report(
    file: UploadFile = File(...),
    staff_name: str = Form(...),
    run_month: int = Form(...),
    run_year: int = Form(...),
    office: str = Form(default="HCM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a native CRM closed-file report (Báo cáo format).
    Parses it, creates a Run and Case rows for operator review.
    Config is loaded from PostgreSQL reference tables.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) accepted")

    # Load config from PostgreSQL — no xlsm file needed
    cfg = load_config(db)

    # Save to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        cases, warnings = parse_crm_report(tmp_path, cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {str(e)}")
    finally:
        os.unlink(tmp_path)

    print(f"[UPLOAD DEBUG] Cases parsed: {len(cases)}, Warnings: {len(warnings)}")

    if not cases:
        raise HTTPException(
            status_code=400,
            detail="No case rows found in uploaded file. "
                   "Check that the file is a CRM closed-file report with the correct format."
        )

    # Create Run
    run = Run(
        staff_name=staff_name,
        office=office,
        run_month=run_month,
        run_year=run_year,
        status="pending",
        input_file=file.filename,
        created_by=current_user.id,
        warnings=str(warnings) if warnings else None,
    )
    db.add(run)
    db.flush()

    # Create Case rows from parsed CRM data
    flagged = 0
    for c in cases:
        is_flagged = c.is_duplicate or bool(c.warn_flags)
        case = Case(
            run_id=run.id,
            original_no=c.original_no,
            student_name=c.student_name,
            student_id=c.student_id,
            contract_id=c.contract_id,
            contract_date=c.contract_date,
            client_type=c.client_type,
            client_type_code=c.client_type_code,
            country=c.country,
            country_code=c.country_code,
            agent=c.agent,
            system_type=c.system_type,
            app_status=c.app_status,
            visa_date=c.visa_date,
            institution=c.institution,
            course_start=c.course_start,
            course_status=c.course_status,
            counsellor=c.counsellor,
            case_officer=c.case_officer,
            notes=c.notes,
            institution_type=c.institution_type,
            group_agent_name=getattr(c, 'group_agent', ''),
            package_type="NONE",
            targets_name=staff_name,
            is_flagged=is_flagged,
            has_warnings=bool(c.warn_flags),
            warn_msg=", ".join(c.warn_flags) if c.warn_flags else None,
        )
        if is_flagged:
            flagged += 1
        db.add(case)

    db.commit()
    db.refresh(run)

    print(f"[UPLOAD DEBUG] Cases saved to DB: {len(cases)}")

    return UploadResponse(
        run_id=run.id,
        staff_name=run.staff_name,
        case_count=len(cases),
        flagged_count=flagged,
        errors=[],
        warnings=warnings,
        message=f"Uploaded {len(cases)} cases for {staff_name}. "
                f"{flagged} cases need attention before calculation.",
    )


@router.post("/template", response_model=UploadResponse)
async def upload_template_file(
    file: UploadFile = File(...),
    staff_name: str = Form(...),
    run_month: int = Form(...),
    run_year: int = Form(...),
    office: str = Form(default="HCM"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a completed v7 template input file.
    Validates all mandatory fields and creates a Run ready for calculation.
    Config is loaded from PostgreSQL reference tables.
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Only Excel files (.xlsx, .xls) accepted")

    cfg = load_config(db)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        from ..engine.input import parse_input_file
        cases_parsed, errors, warnings = parse_input_file(tmp_path, cfg)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {str(e)}")
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
        staff_name=staff_name,
        office=office,
        run_month=run_month,
        run_year=run_year,
        status="reviewed",
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
            targets_name=staff_name,
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
