# =============================================================================
# schemas.py
# Pydantic models for API request/response validation.
# =============================================================================

from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel


# =============================================================================
# Auth
# =============================================================================

class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None


class UserCreate(BaseModel):
    username: str
    full_name: str
    email: str
    password: str
    staff_name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    is_admin: bool
    staff_name: Optional[str] = None

    class Config:
        from_attributes = True


# =============================================================================
# Case
# =============================================================================

class CaseBase(BaseModel):
    student_name:     Optional[str] = None
    student_id:       Optional[str] = None
    contract_id:      Optional[str] = None
    contract_date:    Optional[date] = None
    client_type:      Optional[str] = None
    country:          Optional[str] = None
    agent:            Optional[str] = None
    system_type:      Optional[str] = None
    app_status:       Optional[str] = None
    visa_date:        Optional[date] = None
    institution:      Optional[str] = None
    course_start:     Optional[date] = None
    course_status:    Optional[str] = None
    counsellor:       Optional[str] = None
    case_officer:     Optional[str] = None
    presales_agent:   Optional[str] = "NONE"
    incentive:        Optional[int] = 0
    notes:            Optional[str] = None
    service_fee_type: Optional[str] = "NONE"
    deferral:         Optional[str] = "NONE"
    package_type:     Optional[str] = "NONE"
    office_override:  Optional[str] = "HCM"
    handover:         Optional[str] = "NO"
    target_owner:     Optional[str] = None
    case_transition:  Optional[str] = "NO"
    prior_month_rate: Optional[int] = 0
    institution_type: Optional[str] = "DIRECT"
    group_agent_name: Optional[str] = None
    targets_name:     Optional[str] = None
    row_type:         Optional[str] = "BASE"
    addon_code:       Optional[str] = None
    addon_count:      Optional[int] = 0


class CaseUpdate(CaseBase):
    pass


class CaseOut(CaseBase):
    id:               int
    run_id:           int
    original_no:      Optional[str] = None
    client_type_code: Optional[str] = None
    country_code:     Optional[str] = None
    bonus_enrolled:   int = 0
    note_enrolled:    Optional[str] = None
    note_enrolled2:   Optional[str] = None
    bonus_priority:   int = 0
    note_priority:    Optional[str] = None
    note_priority2:   Optional[str] = None
    prior_advances:   int = 0
    net_payable:      int = 0
    stored_base_rate: int = 0
    is_recovery_item: bool = False
    has_warnings:     bool = False
    warn_msg:         Optional[str] = None
    is_flagged:       bool = False

    class Config:
        from_attributes = True


# =============================================================================
# Run
# =============================================================================

class RunCreate(BaseModel):
    staff_name: str
    run_month:  int
    run_year:   int


class RunOut(BaseModel):
    id:             int
    staff_name:     str
    office:         Optional[str] = None
    run_month:      int
    run_year:       int
    status:         str
    input_file:     Optional[str] = None
    total_bonus:    int = 0
    enrolled_count: int = 0
    tier:           Optional[str] = None
    target:         int = 0
    warnings:       Optional[str] = None
    errors:         Optional[str] = None
    created_at:     datetime
    calculated_at:  Optional[datetime] = None
    cases:          List[CaseOut] = []

    class Config:
        from_attributes = True


class RunSummary(BaseModel):
    id:             int
    staff_name:     str
    run_month:      int
    run_year:       int
    status:         str
    total_bonus:    int = 0
    enrolled_count: int = 0
    tier:           Optional[str] = None
    created_at:     datetime

    class Config:
        from_attributes = True


# =============================================================================
# Signoff
# =============================================================================

class SignoffCreate(BaseModel):
    action:  str
    comment: Optional[str] = None


class SignoffOut(BaseModel):
    id:        int
    run_id:    int
    action:    str
    comment:   Optional[str] = None
    signed_at: datetime
    user:      UserOut

    class Config:
        from_attributes = True


# =============================================================================
# Upload response
# =============================================================================

class UploadResponse(BaseModel):
    run_id:        int
    staff_name:    str
    case_count:    int
    flagged_count: int
    errors:        List[str]
    warnings:      List[str]
    message:       str


# =============================================================================
# Calculation response
# =============================================================================

class CalculationResult(BaseModel):
    run_id:         int
    staff_name:     str
    run_month:      int
    run_year:       int
    office:         str
    target:         int
    enrolled_count: int
    tier:           str
    total_bonus:    int
    total_priority: int
    grand_total:    int
    cases:          List[CaseOut]
