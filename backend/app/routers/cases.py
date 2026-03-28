# =============================================================================
# routers/cases.py
# Case review and editing endpoints.
# =============================================================================

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Case, Run, User
from ..schemas import CaseOut, CaseUpdate
from ..routers.auth import get_current_user

router = APIRouter()


@router.get("/run/{run_id}", response_model=List[CaseOut])
def get_cases(
    run_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Returns all cases for a given run."""
    run = db.query(Run).filter(Run.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return db.query(Case).filter(Case.run_id == run_id).all()


@router.patch("/{case_id}", response_model=CaseOut)
def update_case(
    case_id: int,
    updates: CaseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update operator-editable fields on a case during review.
    Only allowed while run status is pending or reviewed.
    """
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    run = db.query(Run).filter(Run.id == case.run_id).first()
    if run.status not in ("pending", "reviewed"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot edit cases — run status is '{run.status}'"
        )

    # Apply updates (only non-None fields)
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(case, field):
            setattr(case, field, value)

    # Clear flagged status if package is now set
    if case.package_type and case.package_type != "NONE":
        case.is_flagged = False

    db.commit()
    db.refresh(case)
    return case


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    case_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    case = db.query(Case).filter(Case.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case
