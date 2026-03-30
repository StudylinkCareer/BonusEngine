# =============================================================================
# routers/reference.py
# Admin endpoints for managing all reference/lookup tables.
# =============================================================================

import io
import pandas as pd
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    StaffName, StaffTarget, MasterAgent, CountryCode,
    ClientTypeMap, StatusRule, ServiceFeeRate, ReferenceList,
    PriorityInstitution, YtdTracker, ClientWeight, ContractBonus,
    AdvancePayment
)
from ..routers.auth import get_admin_user, get_current_user
from ..models import User

router = APIRouter()


# =============================================================================
# DROPDOWN LISTS — served to the frontend upload/review forms
# =============================================================================

@router.get("/lists")
def get_all_lists(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Returns all dropdown values needed by the upload and review forms."""

    def get_list(name):
        return [r.value for r in
                db.query(ReferenceList)
                .filter(ReferenceList.list_name == name, ReferenceList.is_active == True)
                .order_by(ReferenceList.sort_order, ReferenceList.value)
                .all()]

    staff_names = [r.full_name for r in
                   db.query(StaffName)
                   .filter(StaffName.is_active == True)
                   .order_by(StaffName.full_name).all()]

    countries = [r.country_name for r in
                 db.query(CountryCode)
                 .filter(CountryCode.is_active == True)
                 .order_by(CountryCode.country_name).all()]

    client_types = sorted(set(
        [r.raw_value for r in db.query(ClientTypeMap)
         .filter(ClientTypeMap.is_active == True).all()]
    ))

    statuses = [r.value for r in
                db.query(ReferenceList)
                .filter(ReferenceList.list_name == "application_status",
                        ReferenceList.is_active == True)
                .order_by(ReferenceList.sort_order).all()]

    service_fees = [r.fee_type for r in
                    db.query(ServiceFeeRate)
                    .filter(ServiceFeeRate.is_active == True)
                    .order_by(ServiceFeeRate.fee_type).all()]

    return {
        "application_status": statuses,
        "client_type":        client_types,
        "country":            countries,
        "service_fee_type":   service_fees,
        "package_type":       get_list("package_type"),
        "presales_agent":     ["NONE"] + staff_names,
        "institution_type":   get_list("institution_type"),
        "office_override":    ["HCM", "HN", "DN"],
        "deferral":           get_list("deferral"),
        "handover":           ["YES", "NO"],
        "case_transition":    ["YES", "NO"],
        "system_type":        get_list("system_type"),
        "row_type":           ["BASE", "ADDON"],
        "addon_code":         get_list("addon_code"),
        "staff_names":        staff_names,
    }


# =============================================================================
# STAFF NAMES
# =============================================================================

@router.get("/staff-names")
def get_staff_names(db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    return db.query(StaffName).order_by(StaffName.full_name).all()

@router.post("/staff-names")
def add_staff_name(data: dict, db: Session = Depends(get_db),
                   admin: User = Depends(get_admin_user)):
    if db.query(StaffName).filter(StaffName.full_name == data["full_name"]).first():
        raise HTTPException(400, "Staff name already exists")
    row = StaffName(**{k: v for k, v in data.items()
                       if k in ("full_name","short_name","office","role","is_active")})
    db.add(row); db.commit(); db.refresh(row)
    return row

@router.put("/staff-names/{id}")
def update_staff_name(id: int, data: dict, db: Session = Depends(get_db),
                      admin: User = Depends(get_admin_user)):
    row = db.query(StaffName).filter(StaffName.id == id).first()
    if not row: raise HTTPException(404, "Not found")
    for k, v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row)
    return row

@router.delete("/staff-names/{id}")
def delete_staff_name(id: int, db: Session = Depends(get_db),
                      admin: User = Depends(get_admin_user)):
    row = db.query(StaffName).filter(StaffName.id == id).first()
    if not row: raise HTTPException(404, "Not found")
    db.delete(row); db.commit()
    return {"ok": True}


# =============================================================================
# STAFF TARGETS
# =============================================================================

@router.get("/staff-targets")
def get_staff_targets(
    month: Optional[int] = None, year: Optional[int] = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    q = db.query(StaffTarget)
    if month: q = q.filter(StaffTarget.month == month)
    if year:  q = q.filter(StaffTarget.year == year)
    return q.order_by(StaffTarget.year, StaffTarget.month, StaffTarget.staff_name).all()

@router.post("/staff-targets/upload")
async def upload_staff_targets(
    file: UploadFile = File(...),
    month: int = None, year: int = None,
    db: Session = Depends(get_db), admin: User = Depends(get_admin_user)
):
    content = await file.read()
    try: df = pd.read_excel(io.BytesIO(content))
    except Exception as e: raise HTTPException(400, f"Could not read file: {e}")

    df.columns = df.columns.str.lower()
    if not {"staff_name","target"}.issubset(set(df.columns)):
        raise HTTPException(400, "File must have columns: staff_name, target")

    valid_names = {r.full_name for r in db.query(StaffName).all()}
    warnings = [f"Unknown staff name: {n}" for n in df["staff_name"].unique()
                if n not in valid_names]

    if month and year:
        db.query(StaffTarget).filter(StaffTarget.month == month,
                                     StaffTarget.year == year).delete()

    rows_added = 0
    for _, row in df.iterrows():
        db.add(StaffTarget(
            staff_name=row["staff_name"],
            office=row.get("office", None),
            month=month or int(row.get("month", 0)),
            year=year or int(row.get("year", 0)),
            target=int(row["target"])
        ))
        rows_added += 1

    db.commit()
    return {"rows_added": rows_added, "warnings": warnings}


# =============================================================================
# MASTER AGENTS
# =============================================================================

@router.get("/master-agents")
def get_master_agents(db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    return db.query(MasterAgent).order_by(MasterAgent.agent_name).all()

@router.post("/master-agents/upload")
async def upload_master_agents(
    file: UploadFile = File(...),
    db: Session = Depends(get_db), admin: User = Depends(get_admin_user)
):
    content = await file.read()
    try: df = pd.read_excel(io.BytesIO(content))
    except Exception as e: raise HTTPException(400, f"Could not read file: {e}")
    df.columns = df.columns.str.lower()
    db.query(MasterAgent).delete()
    for _, row in df.iterrows():
        db.add(MasterAgent(
            agent_name=str(row.get("agent_name", row.get("name",""))),
            agent_type=str(row.get("agent_type","DIRECT")),
            office=str(row.get("office","")), is_active=bool(row.get("is_active",True))
        ))
    db.commit()
    return {"rows_added": len(df)}


# =============================================================================
# COUNTRY CODES
# =============================================================================

@router.get("/country-codes")
def get_country_codes(db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    return db.query(CountryCode).order_by(CountryCode.country_name).all()


# =============================================================================
# CLIENT TYPE MAP
# =============================================================================

@router.get("/client-type-map")
def get_client_type_map(db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    return db.query(ClientTypeMap).order_by(ClientTypeMap.raw_value).all()


# =============================================================================
# STATUS RULES
# =============================================================================

@router.get("/status-rules")
def get_status_rules(db: Session = Depends(get_db),
                     current_user: User = Depends(get_current_user)):
    return db.query(StatusRule).order_by(StatusRule.status_value).all()


# =============================================================================
# PRIORITY INSTITUTIONS
# =============================================================================

@router.get("/priority-instns")
def get_priority_instns(db: Session = Depends(get_db),
                        current_user: User = Depends(get_current_user)):
    return db.query(PriorityInstitution).order_by(
        PriorityInstitution.country_code, PriorityInstitution.institution_name).all()

@router.put("/priority-instns/{id}")
def update_priority_instn(id: int, data: dict, db: Session = Depends(get_db),
                          admin: User = Depends(get_admin_user)):
    row = db.query(PriorityInstitution).filter(PriorityInstitution.id == id).first()
    if not row: raise HTTPException(404, "Not found")
    for k, v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row)
    return row


# =============================================================================
# YTD TRACKER
# =============================================================================

@router.get("/ytd-tracker")
def get_ytd_tracker(
    year: Optional[int] = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    q = db.query(YtdTracker)
    if year: q = q.filter(YtdTracker.year == year)
    return q.order_by(YtdTracker.institution_name, YtdTracker.month).all()


# =============================================================================
# CLIENT WEIGHTS
# =============================================================================

@router.get("/client-weights")
def get_client_weights(db: Session = Depends(get_db),
                       current_user: User = Depends(get_current_user)):
    return db.query(ClientWeight).order_by(ClientWeight.canonical_code).all()


# =============================================================================
# CONTRACT BONUSES
# =============================================================================

@router.get("/contract-bonuses")
def get_contract_bonuses(db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    return db.query(ContractBonus).order_by(ContractBonus.package_name).all()


# =============================================================================
# ADVANCE PAYMENTS
# =============================================================================

@router.get("/advance-payments")
def get_advance_payments(
    staff_name: Optional[str] = None,
    settled: Optional[bool] = None,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    q = db.query(AdvancePayment)
    if staff_name: q = q.filter(AdvancePayment.staff_name == staff_name)
    if settled is not None: q = q.filter(AdvancePayment.is_settled == settled)
    return q.order_by(AdvancePayment.recorded_at.desc()).all()


# =============================================================================
# GENERIC REF LIST
# =============================================================================

@router.get("/ref-list/{list_name}")
def get_ref_list(list_name: str, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    return db.query(ReferenceList).filter(
        ReferenceList.list_name == list_name
    ).order_by(ReferenceList.sort_order).all()

@router.post("/ref-list/{list_name}")
def add_ref_list_value(list_name: str, data: dict, db: Session = Depends(get_db),
                       admin: User = Depends(get_admin_user)):
    if db.query(ReferenceList).filter(ReferenceList.list_name == list_name,
                                       ReferenceList.value == data["value"]).first():
        raise HTTPException(400, "Value already exists")
    row = ReferenceList(list_name=list_name, value=data["value"],
                        sort_order=data.get("sort_order", 0))
    db.add(row); db.commit()
    return row

@router.delete("/ref-list/{list_name}/{id}")
def delete_ref_list_value(list_name: str, id: int, db: Session = Depends(get_db),
                          admin: User = Depends(get_admin_user)):
    row = db.query(ReferenceList).filter(ReferenceList.list_name == list_name,
                                          ReferenceList.id == id).first()
    if not row: raise HTTPException(404, "Not found")
    db.delete(row); db.commit()
    return {"ok": True}


# =============================================================================
# DOWNLOAD ANY TABLE AS EXCEL
# =============================================================================

TABLE_MAP = {
    "staff_names":       StaffName,
    "staff_targets":     StaffTarget,
    "master_agents":     MasterAgent,
    "country_codes":     CountryCode,
    "client_type_map":   ClientTypeMap,
    "status_rules":      StatusRule,
    "service_fee_rates": ServiceFeeRate,
    "priority_instns":   PriorityInstitution,
    "ytd_tracker":       YtdTracker,
    "client_weights":    ClientWeight,
    "contract_bonuses":  ContractBonus,
    "advance_payments":  AdvancePayment,
}

@router.get("/download/{table_name}")
def download_table(table_name: str, db: Session = Depends(get_db),
                   admin: User = Depends(get_admin_user)):
    model = TABLE_MAP.get(table_name)
    if not model: raise HTTPException(404, f"Unknown table: {table_name}")

    rows = db.query(model).all()
    df = pd.DataFrame(
        [{c.name: getattr(r, c.name) for c in model.__table__.columns} for r in rows]
    ) if rows else pd.DataFrame()

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=table_name)
    output.seek(0)

    filename = f"{table_name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
