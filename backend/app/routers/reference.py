# =============================================================================
# routers/reference.py
# Admin endpoints for all reference/lookup tables.
# =============================================================================

import io, json
from datetime import date
from typing import Optional
import pandas as pd

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import (
    StaffName, StaffTarget, MasterAgent, CountryCode, ClientTypeMap,
    StatusRule, ServiceFeeRate, ReferenceList, PriorityInstitution,
    YtdTracker, ClientWeight, ContractBonus, AdvancePayment,
    BaseRate, IncentiveTier, SpecialRate, CountryRate,
    PartnerInstitution, AdvanceRule,
)
from ..routers.auth import get_admin_user, get_current_user
from ..models import User

router = APIRouter()


# =============================================================================
# DROPDOWN LISTS — served to upload and review forms
# =============================================================================

@router.get("/lists")
def get_all_lists(db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    def get_list(name):
        return [r.value for r in
                db.query(ReferenceList)
                .filter(ReferenceList.list_name==name, ReferenceList.is_active==True)
                .order_by(ReferenceList.sort_order, ReferenceList.value).all()]

    staff_names = [r.full_name for r in
                   db.query(StaffName).filter(StaffName.is_active==True)
                   .order_by(StaffName.full_name).all()]

    countries = [r.country_name for r in
                 db.query(CountryCode).filter(CountryCode.is_active==True)
                 .order_by(CountryCode.country_name).all()]

    client_types = sorted(set(
        [r.raw_value for r in db.query(ClientTypeMap).filter(ClientTypeMap.is_active==True).all()]
    ))

    statuses = [r.value for r in
                db.query(ReferenceList)
                .filter(ReferenceList.list_name=="application_status", ReferenceList.is_active==True)
                .order_by(ReferenceList.sort_order).all()]

    service_fees = [r.service_code for r in
                    db.query(ServiceFeeRate).filter(ServiceFeeRate.is_active==True)
                    .order_by(ServiceFeeRate.service_code).all()]

    offices = ["HCM", "HN", "DN"]

    return {
        "application_status": statuses,
        "client_type":        client_types,
        "country":            countries,
        "service_fee_type":   service_fees,
        "package_type":       get_list("package_type"),
        "presales_agent":     ["NONE"] + staff_names,
        "institution_type":   get_list("institution_type"),
        "office_override":    offices,
        "deferral":           get_list("deferral"),
        "handover":           ["YES", "NO"],
        "case_transition":    ["YES", "NO"],
        "system_type":        get_list("system_type"),
        "row_type":           ["BASE", "ADDON"],
        "addon_code":         get_list("addon_code"),
        "staff_names":        staff_names,
        "offices":            offices,
    }


# =============================================================================
# Per-type reference list — used by Review Board cell dropdowns.
# Returns { canonical: [{ value, display }, ...] } so the frontend can render
# an enforced dropdown when an editable cell has ref:'<type>' metadata.
# =============================================================================

@router.get("/list/{ref_type}")
def get_one_list(ref_type: str, db: Session = Depends(get_db),
                 current_user: User = Depends(get_current_user)):
    """Return a single reference list in the shape the Review Board expects.

    Reads from the same tables as /reference/lists but returns one type at a
    time and wraps it in {canonical: [{value, display}, ...]} so the frontend
    dropdown can render directly without re-shaping.

    For service_fee_type the display includes the bonus amount where known
    so operators can pick the right code (e.g., "STUDENT_VISA_RENEWAL — 400k").
    """
    def _from_reference_list(name):
        rows = (db.query(ReferenceList)
                .filter(ReferenceList.list_name == name,
                        ReferenceList.is_active == True)
                .order_by(ReferenceList.sort_order, ReferenceList.value)
                .all())
        return [{"value": r.value, "display": r.value} for r in rows]

    if ref_type == "institution_type":
        opts = _from_reference_list("institution_type")
        # Hardcoded fallback if the table is empty — matches engine constants
        if not opts:
            opts = [{"value": v, "display": v} for v in
                    ("DIRECT", "MASTER_AGENT", "GROUP", "OUT_OF_SYSTEM",
                     "RMIT_VN", "BUV_VN", "OTHER_VN")]
        return {"canonical": opts}

    if ref_type == "service_fee_type":
        rows = (db.query(ServiceFeeRate)
                .filter(ServiceFeeRate.is_active == True)
                .order_by(ServiceFeeRate.service_code).all())
        opts = []
        for r in rows:
            amt = getattr(r, "co_amount", None) or 0
            label = (f"{r.service_code} — {amt/1000:.0f}k"
                     if amt else r.service_code)
            opts.append({"value": r.service_code, "display": label})
        # Always include NONE as the no-fee option
        opts.insert(0, {"value": "NONE", "display": "NONE"})
        return {"canonical": opts}

    if ref_type == "package_type":
        opts = _from_reference_list("package_type")
        if not opts:
            opts = [{"value": "NONE", "display": "NONE"}]
        elif not any(o["value"] == "NONE" for o in opts):
            opts.insert(0, {"value": "NONE", "display": "NONE"})
        return {"canonical": opts}

    if ref_type == "deferral":
        opts = _from_reference_list("deferral")
        if not opts:
            opts = [{"value": v, "display": v} for v in
                    ("NONE", "FEE_TRANSFERRED", "DEFERRED",
                     "FEE_WAIVED", "NO_SERVICE")]
        return {"canonical": opts}

    if ref_type == "office":
        return {"canonical": [{"value": v, "display": v}
                              for v in ("HCM", "HN", "DN", "MEL")]}

    if ref_type == "row_type":
        return {"canonical": [{"value": v, "display": v}
                              for v in ("BASE", "ADDON")]}

    if ref_type == "scheme":
        return {"canonical": [{"value": v, "display": v} for v in (
            "CO_DIR", "CO_SUB", "CO_VP",
            "COUNS_DIR", "COUNS_SUB", "COUNS_VP",
        )]}

    if ref_type == "handover" or ref_type == "case_transition":
        return {"canonical": [{"value": v, "display": v}
                              for v in ("YES", "NO")]}

    if ref_type == "country":
        rows = (db.query(CountryCode)
                .filter(CountryCode.is_active == True)
                .order_by(CountryCode.country_name).all())
        return {"canonical": [{"value": r.country_name,
                               "display": r.country_name} for r in rows]}

    if ref_type == "client_type":
        rows = (db.query(ClientTypeMap)
                .filter(ClientTypeMap.is_active == True).all())
        seen = set()
        opts = []
        for r in rows:
            if r.raw_value in seen: continue
            seen.add(r.raw_value)
            opts.append({"value": r.raw_value, "display": r.raw_value})
        return {"canonical": sorted(opts, key=lambda o: o["value"])}

    if ref_type == "app_status":
        rows = (db.query(ReferenceList)
                .filter(ReferenceList.list_name == "application_status",
                        ReferenceList.is_active == True)
                .order_by(ReferenceList.sort_order).all())
        return {"canonical": [{"value": r.value, "display": r.value}
                              for r in rows]}

    if ref_type == "system_type":
        opts = _from_reference_list("system_type")
        if not opts:
            opts = [{"value": v, "display": v} for v in
                    ("Trong hệ thống", "Ngoài hệ thống")]
        return {"canonical": opts}

    if ref_type == "presales_agent":
        names = [r.full_name for r in
                 db.query(StaffName).filter(StaffName.is_active == True)
                 .order_by(StaffName.full_name).all()]
        return {"canonical": [{"value": "NONE", "display": "NONE"}] +
                             [{"value": n, "display": n} for n in names]}

    # Generic fallback — try the catch-all reference_list table by name.
    opts = _from_reference_list(ref_type)
    if opts:
        return {"canonical": opts}

    raise HTTPException(404, f"Unknown reference type: {ref_type}")


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
    if db.query(StaffName).filter(StaffName.full_name==data["full_name"]).first():
        raise HTTPException(400, "Staff name already exists")
    allowed = ("full_name","short_name","office","role","scheme","is_active","start_date","end_date")
    row = StaffName(**{k: v for k,v in data.items() if k in allowed})
    db.add(row); db.commit(); db.refresh(row)
    return row

@router.put("/staff-names/{id}")
def update_staff_name(id: int, data: dict, db: Session = Depends(get_db),
                      admin: User = Depends(get_admin_user)):
    row = db.query(StaffName).filter(StaffName.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    for k,v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row); return row

@router.delete("/staff-names/{id}")
def delete_staff_name(id: int, db: Session = Depends(get_db),
                      admin: User = Depends(get_admin_user)):
    row = db.query(StaffName).filter(StaffName.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    db.delete(row); db.commit(); return {"ok": True}


# =============================================================================
# STAFF TARGETS
# =============================================================================

@router.get("/staff-targets")
def get_staff_targets(month: Optional[int]=None, year: Optional[int]=None,
                      db: Session=Depends(get_db),
                      current_user: User=Depends(get_current_user)):
    q = db.query(StaffTarget)
    if month: q = q.filter(StaffTarget.month==month)
    if year:  q = q.filter(StaffTarget.year==year)
    return q.order_by(StaffTarget.year, StaffTarget.month, StaffTarget.staff_name).all()

@router.post("/staff-targets/upload")
async def upload_staff_targets(
    file: UploadFile = File(...),
    replace_years: str = "",
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    """
    Upload a staff targets Excel file using the 04_STAFF_TARGETS template format
    (year-section layout with Office / Role / Partner columns and Jan–Dec month columns).

    replace_years: optional comma-separated years to replace e.g. "2025,2026".
    If blank, all years found in the file are replaced.

    Multi-office rows (e.g. Hoàng Yến HCM + HN) are stored as separate DB rows;
    the engine sums them automatically for tier calculation.
    """
    import tempfile, os, re

    content = await file.read()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
        tmp.write(content); tmp_path = tmp.name

    try:
        from ..engine.parse_staff_targets import parse_targets_excel
        records, parse_warnings = parse_targets_excel(tmp_path)
    except ImportError:
        # Fallback: simple flat format (staff_name, month, year, target columns)
        try:
            df = pd.read_excel(io.BytesIO(content))
            df.columns = df.columns.str.lower()
            records = []
            for _, row in df.iterrows():
                for m in range(1, 13):
                    records.append({
                        "staff_name": str(row.get("staff_name","")),
                        "office":     str(row.get("office","")) if pd.notna(row.get("office","")) else "",
                        "year":       int(row.get("year", 0)),
                        "month":      m,
                        "target":     int(row.get(str(m), 0)),
                    })
            parse_warnings = []
        except Exception as e:
            raise HTTPException(400, f"Could not parse file: {e}")
    except Exception as e:
        raise HTTPException(400, f"Could not parse file: {e}")
    finally:
        os.unlink(tmp_path)

    if not records:
        raise HTTPException(400, f"No target records found. Warnings: {parse_warnings}")

    years_in_file = sorted(set(r["year"] for r in records if r.get("year")))
    if replace_years:
        try:
            years_to_replace = [int(y.strip()) for y in replace_years.split(",")]
        except:
            raise HTTPException(400, "replace_years must be comma-separated integers e.g. '2025,2026'")
    else:
        years_to_replace = years_in_file

    deleted = db.query(StaffTarget).filter(
        StaffTarget.year.in_(years_to_replace)
    ).delete(synchronize_session=False)

    valid_names = {r.full_name for r in db.query(StaffName).all()}
    name_warnings = []
    rows_added = 0

    for rec in records:
        if rec.get("year") not in years_to_replace:
            continue
        name = rec.get("staff_name","").strip()
        if not name:
            continue
        if name not in valid_names:
            w = f"'{name}' not in staff names table — imported anyway"
            if w not in name_warnings:
                name_warnings.append(w)
        db.add(StaffTarget(
            staff_name = name,
            office     = rec.get("office") or None,
            month      = rec.get("month", 0),
            year       = rec.get("year", 0),
            target     = rec.get("target", 0),
        ))
        rows_added += 1

    db.commit()
    return {
        "rows_deleted":   deleted,
        "rows_added":     rows_added,
        "years_replaced": years_to_replace,
        "years_in_file":  years_in_file,
        "warnings":       parse_warnings + name_warnings,
    }


# =============================================================================
# BASE RATES
# =============================================================================

@router.get("/base-rates")
def get_base_rates(scheme: Optional[str]=None, db: Session=Depends(get_db),
                   current_user: User=Depends(get_current_user)):
    q = db.query(BaseRate).filter(BaseRate.is_active==True)
    if scheme: q = q.filter(BaseRate.scheme==scheme)
    return q.order_by(BaseRate.scheme, BaseRate.tier, BaseRate.role).all()

@router.put("/base-rates/{id}")
def update_base_rate(id: int, data: dict, db: Session=Depends(get_db),
                     admin: User=Depends(get_admin_user)):
    row = db.query(BaseRate).filter(BaseRate.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    for k,v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row); return row

@router.post("/base-rates")
def add_base_rate(data: dict, db: Session=Depends(get_db),
                  admin: User=Depends(get_admin_user)):
    row = BaseRate(**data)
    db.add(row); db.commit(); db.refresh(row); return row


# =============================================================================
# INCENTIVE TIERS
# =============================================================================

@router.get("/incentive-tiers")
def get_incentive_tiers(db: Session=Depends(get_db),
                        current_user: User=Depends(get_current_user)):
    return db.query(IncentiveTier).order_by(IncentiveTier.start_date.desc()).all()

@router.put("/incentive-tiers/{id}")
def update_incentive_tier(id: int, data: dict, db: Session=Depends(get_db),
                          admin: User=Depends(get_admin_user)):
    row = db.query(IncentiveTier).filter(IncentiveTier.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    for k,v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row); return row

@router.post("/incentive-tiers")
def add_incentive_tier(data: dict, db: Session=Depends(get_db),
                       admin: User=Depends(get_admin_user)):
    row = IncentiveTier(**data)
    db.add(row); db.commit(); db.refresh(row); return row


# =============================================================================
# SPECIAL RATES
# =============================================================================

@router.get("/special-rates")
def get_special_rates(db: Session=Depends(get_db),
                      current_user: User=Depends(get_current_user)):
    return db.query(SpecialRate).filter(SpecialRate.is_active==True)\
             .order_by(SpecialRate.scheme, SpecialRate.rate_code).all()

@router.put("/special-rates/{id}")
def update_special_rate(id: int, data: dict, db: Session=Depends(get_db),
                        admin: User=Depends(get_admin_user)):
    row = db.query(SpecialRate).filter(SpecialRate.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    for k,v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row); return row


# =============================================================================
# COUNTRY RATES
# =============================================================================

@router.get("/country-rates")
def get_country_rates(db: Session=Depends(get_db),
                      current_user: User=Depends(get_current_user)):
    return db.query(CountryRate).filter(CountryRate.is_active==True)\
             .order_by(CountryRate.country_name, CountryRate.scheme).all()

@router.put("/country-rates/{id}")
def update_country_rate(id: int, data: dict, db: Session=Depends(get_db),
                        admin: User=Depends(get_admin_user)):
    row = db.query(CountryRate).filter(CountryRate.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    for k,v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row); return row


# =============================================================================
# PARTNER INSTITUTIONS
# =============================================================================

@router.get("/partner-instns")
def get_partner_instns(db: Session=Depends(get_db),
                       current_user: User=Depends(get_current_user)):
    return db.query(PartnerInstitution).filter(PartnerInstitution.is_active==True)\
             .order_by(PartnerInstitution.partner_level).all()

@router.put("/partner-instns/{id}")
def update_partner_instn(id: int, data: dict, db: Session=Depends(get_db),
                         admin: User=Depends(get_admin_user)):
    row = db.query(PartnerInstitution).filter(PartnerInstitution.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    for k,v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row); return row


# =============================================================================
# ADVANCE RULES
# =============================================================================

@router.get("/advance-rules")
def get_advance_rules(db: Session=Depends(get_db),
                      current_user: User=Depends(get_current_user)):
    return db.query(AdvanceRule).filter(AdvanceRule.is_active==True)\
             .order_by(AdvanceRule.sort_order).all()

@router.put("/advance-rules/{id}")
def update_advance_rule(id: int, data: dict, db: Session=Depends(get_db),
                        admin: User=Depends(get_admin_user)):
    row = db.query(AdvanceRule).filter(AdvanceRule.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    for k,v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row); return row

@router.post("/advance-rules")
def add_advance_rule(data: dict, db: Session=Depends(get_db),
                     admin: User=Depends(get_admin_user)):
    row = AdvanceRule(**data)
    db.add(row); db.commit(); db.refresh(row); return row


# =============================================================================
# MASTER AGENTS
# =============================================================================

@router.get("/master-agents")
def get_master_agents(db: Session=Depends(get_db),
                      current_user: User=Depends(get_current_user)):
    return db.query(MasterAgent).order_by(MasterAgent.agent_name).all()

@router.post("/master-agents/upload")
async def upload_master_agents(file: UploadFile=File(...),
                                db: Session=Depends(get_db),
                                admin: User=Depends(get_admin_user)):
    content = await file.read()
    try: df = pd.read_excel(io.BytesIO(content))
    except Exception as e: raise HTTPException(400, f"Could not read file: {e}")
    df.columns = df.columns.str.lower()
    db.query(MasterAgent).delete()
    for _, row in df.iterrows():
        db.add(MasterAgent(agent_name=str(row.get("agent_name",row.get("name",""))),
                           agent_type=str(row.get("agent_type","DIRECT")),
                           office=str(row.get("office","")), is_active=True))
    db.commit()
    return {"rows_added": len(df)}


# =============================================================================
# COUNTRY CODES / CLIENT TYPE MAP / STATUS RULES
# =============================================================================

@router.get("/country-codes")
def get_country_codes(db: Session=Depends(get_db),
                      current_user: User=Depends(get_current_user)):
    return db.query(CountryCode).order_by(CountryCode.country_name).all()

@router.get("/client-type-map")
def get_client_type_map(db: Session=Depends(get_db),
                        current_user: User=Depends(get_current_user)):
    return db.query(ClientTypeMap).order_by(ClientTypeMap.raw_value).all()

@router.get("/status-rules")
def get_status_rules(db: Session=Depends(get_db),
                     current_user: User=Depends(get_current_user)):
    return db.query(StatusRule).order_by(StatusRule.status_value).all()

@router.put("/status-rules/{id}")
def update_status_rule(id: int, data: dict, db: Session=Depends(get_db),
                       admin: User=Depends(get_admin_user)):
    row = db.query(StatusRule).filter(StatusRule.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    for k,v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row); return row

@router.post("/status-rules")
def add_status_rule(data: dict, db: Session=Depends(get_db),
                    admin: User=Depends(get_admin_user)):
    row = StatusRule(**data)
    db.add(row); db.commit(); db.refresh(row); return row


# =============================================================================
# SERVICE FEE RATES
# =============================================================================

@router.get("/service-fee-rates")
def get_service_fee_rates(db: Session=Depends(get_db),
                          current_user: User=Depends(get_current_user)):
    return db.query(ServiceFeeRate).filter(ServiceFeeRate.is_active==True)\
             .order_by(ServiceFeeRate.service_code).all()

@router.put("/service-fee-rates/{id}")
def update_service_fee_rate(id: int, data: dict, db: Session=Depends(get_db),
                             admin: User=Depends(get_admin_user)):
    row = db.query(ServiceFeeRate).filter(ServiceFeeRate.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    for k,v in data.items(): setattr(row, k, v)
    db.commit(); db.refresh(row); return row


# =============================================================================
# PRIORITY INSTITUTIONS / YTD TRACKER / ADVANCE PAYMENTS / CLIENT WEIGHTS
# =============================================================================

@router.get("/priority-instns")
def get_priority_instns(db: Session=Depends(get_db),
                        current_user: User=Depends(get_current_user)):
    return db.query(PriorityInstitution).order_by(
        PriorityInstitution.country_code, PriorityInstitution.institution_name).all()

@router.get("/ytd-tracker")
def get_ytd_tracker(year: Optional[int]=None, db: Session=Depends(get_db),
                    current_user: User=Depends(get_current_user)):
    q = db.query(YtdTracker)
    if year: q = q.filter(YtdTracker.year==year)
    return q.order_by(YtdTracker.institution_name, YtdTracker.year, YtdTracker.month).all()

@router.get("/advance-payments")
def get_advance_payments(staff_name: Optional[str]=None,
                          settled: Optional[bool]=None,
                          db: Session=Depends(get_db),
                          current_user: User=Depends(get_current_user)):
    q = db.query(AdvancePayment)
    if staff_name: q = q.filter(AdvancePayment.staff_name==staff_name)
    if settled is not None: q = q.filter(AdvancePayment.is_settled==settled)
    return q.order_by(AdvancePayment.recorded_at.desc()).all()

@router.get("/client-weights")
def get_client_weights(db: Session=Depends(get_db),
                       current_user: User=Depends(get_current_user)):
    return db.query(ClientWeight).order_by(ClientWeight.canonical_code).all()

@router.get("/contract-bonuses")
def get_contract_bonuses(db: Session=Depends(get_db),
                         current_user: User=Depends(get_current_user)):
    return db.query(ContractBonus).order_by(ContractBonus.package_name).all()


# =============================================================================
# GENERIC REF LIST
# =============================================================================

@router.get("/ref-list/{list_name}")
def get_ref_list(list_name: str, db: Session=Depends(get_db),
                 current_user: User=Depends(get_current_user)):
    return db.query(ReferenceList).filter(
        ReferenceList.list_name==list_name
    ).order_by(ReferenceList.sort_order).all()

@router.post("/ref-list/{list_name}")
def add_ref_list_value(list_name: str, data: dict, db: Session=Depends(get_db),
                       admin: User=Depends(get_admin_user)):
    if db.query(ReferenceList).filter(ReferenceList.list_name==list_name,
                                       ReferenceList.value==data["value"]).first():
        raise HTTPException(400, "Value already exists")
    row = ReferenceList(list_name=list_name, value=data["value"],
                        sort_order=data.get("sort_order",0))
    db.add(row); db.commit(); return row

@router.delete("/ref-list/{list_name}/{id}")
def delete_ref_list_value(list_name: str, id: int, db: Session=Depends(get_db),
                          admin: User=Depends(get_admin_user)):
    row = db.query(ReferenceList).filter(ReferenceList.list_name==list_name,
                                          ReferenceList.id==id).first()
    if not row: raise HTTPException(404, "Not found")
    db.delete(row); db.commit(); return {"ok": True}


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
    "base_rates":        BaseRate,
    "incentive_tiers":   IncentiveTier,
    "special_rates":     SpecialRate,
    "country_rates":     CountryRate,
    "partner_instns":    PartnerInstitution,
    "advance_rules":     AdvanceRule,
}

@router.get("/download/{table_name}")
def download_table(table_name: str, db: Session=Depends(get_db),
                   admin: User=Depends(get_admin_user)):
    model = TABLE_MAP.get(table_name)
    if not model: raise HTTPException(404, f"Unknown table: {table_name}")
    rows = db.query(model).all()
    df = pd.DataFrame(
        [{c.name: getattr(r,c.name) for c in model.__table__.columns} for r in rows]
    ) if rows else pd.DataFrame()
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=table_name)
    output.seek(0)
    from datetime import datetime as dt
    filename = f"{table_name}_{dt.now().strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
