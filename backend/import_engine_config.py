"""
import_engine_config.py
=======================
Imports ALL configuration from engine.xlsm into PostgreSQL.
Safe to re-run — all tables are cleared and re-imported each time.

Tables imported:
  12_STAFF_NAMES       → ref_staff_names + ref_lists[staff_name_map]
  04_STAFF_TARGETS     → ref_staff_targets
  14_COUNTRY_CODES     → ref_country_codes
  15_CLIENT_TYPE_MAP   → ref_client_type_map
  05_STATUS_RULES      → ref_status_rules + ref_lists[application_status]
  09_SERVICE_FEE_RATES → ref_service_fee_rates + ref_lists[service_fee_type]
  11_MASTER_AGENTS     → ref_master_agents
  13_SKIP_LABELS       → ref_lists[skip_labels]
  03_PRIORITY_INSTNS   → ref_priority_instns + ref_ytd_tracker (scaffold)
  08_YTD_TRACKER       → ref_ytd_tracker (existing data)
  06_CLIENT_WEIGHTS    → ref_client_weights
  07_CONTRACT_BONUS    → ref_contract_bonuses
  09_ADVANCE_TRACKER   → advance_payments

Run from backend/ folder:
    python import_engine_config.py data/config/engine.xlsm
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import openpyxl
from datetime import datetime
from app.database import engine as db_engine, SessionLocal
from app.models import (
    Base, StaffName, StaffTarget, MasterAgent, CountryCode,
    ClientTypeMap, StatusRule, ServiceFeeRate, ReferenceList,
    PriorityInstitution, YtdTracker, ClientWeight, ContractBonus,
    AdvancePayment
)


def _s(v) -> str:
    if v is None: return ""
    return str(v).replace("\xa0", " ").replace("?", "").strip()

def _i(v) -> int:
    try:
        return int(float(str(v).replace("—","0").replace("–","0").replace(",","").strip()))
    except:
        return 0

def _f(v) -> float:
    s = str(v or "0").replace("%","").strip()
    try:
        f = float(s)
        return f / 100 if f > 1 else f
    except:
        return 0.0

def _b(v) -> bool:
    return str(v or "").strip().upper() in ("Y", "YES", "TRUE", "1")

def _dt(v):
    """Parse datetime from various formats."""
    if v is None: return None
    if isinstance(v, datetime): return v
    try:
        s = str(v).strip().replace(" 00:00:00", "")
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(s, fmt)
            except:
                pass
    except:
        pass
    return None


def import_all(xlsm_path: str):
    Base.metadata.create_all(bind=db_engine)
    db = SessionLocal()

    try:
        wb = openpyxl.load_workbook(xlsm_path, data_only=True)
        print(f"Opened: {xlsm_path}")
        print(f"Sheets: {wb.sheetnames}\n")

        import_staff_names(wb, db)
        import_staff_targets(wb, db)
        import_country_codes(wb, db)
        import_client_type_map(wb, db)
        import_status_rules(wb, db)
        import_service_fee_rates(wb, db)
        import_master_agents(wb, db)
        import_skip_labels(wb, db)
        import_priority_institutions(wb, db)
        import_ytd_tracker(wb, db)
        import_client_weights(wb, db)
        import_contract_bonuses(wb, db)
        import_advance_tracker(wb, db)

        db.commit()
        print("\n✅ All tables imported successfully!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Import failed: {e}")
        import traceback; traceback.print_exc()
        raise
    finally:
        db.close()


# =============================================================================
# 12_STAFF_NAMES
# =============================================================================
def import_staff_names(wb, db):
    ws = wb["12_STAFF_NAMES"]
    db.query(ReferenceList).filter(ReferenceList.list_name == "staff_name_map").delete()
    db.flush()

    count = 0
    seen_canonical = set()
    seen_crm = set()

    for row in ws.iter_rows(min_row=5, values_only=True):
        crm_name  = _s(row[1])
        canonical = _s(row[2])
        role_note = _s(row[4]).lower() if len(row) > 4 else ""

        if not crm_name or not canonical or crm_name in seen_crm:
            continue
        seen_crm.add(crm_name)

        db.add(ReferenceList(list_name="staff_name_map", value=crm_name,
                             sort_order=count, is_active=True))

        if canonical not in seen_canonical:
            seen_canonical.add(canonical)
            if not db.query(StaffName).filter(StaffName.full_name == canonical).first():
                office = "HCM"
                if "hn" in role_note or "ha noi" in role_note: office = "HN"
                elif "dn" in role_note or "da nang" in role_note: office = "DN"
                role = "counsellor"
                if "co_sub" in role_note: role = "case_officer"
                elif "presales" in role_note: role = "presales"
                db.add(StaffName(full_name=canonical, short_name=canonical,
                                 office=office, role=role, is_active=True))
        count += 1

    db.flush()
    print(f"  12_STAFF_NAMES:       {count} CRM mappings, {len(seen_canonical)} canonical names")


# =============================================================================
# 04_STAFF_TARGETS
# =============================================================================
def import_staff_targets(wb, db):
    ws = wb["04_STAFF_TARGETS"]
    db.query(StaffTarget).delete()
    db.flush()

    current_year = None
    count = 0

    for row in ws.iter_rows(min_row=3, values_only=True):
        a = _s(row[0]).strip("'")
        if not a: continue
        if a.isdigit() and len(a) == 4:
            current_year = int(a); continue
        if current_year is None or a.lower() in ("staff member", "name"): continue

        idx3 = _s(row[3]) if len(row) > 3 and row[3] is not None else "0"
        try:
            float(idx3.replace("—", "0").replace("–", "0"))
            months = list(row[3:15])
        except (ValueError, TypeError):
            months = list(row[4:16])

        office = _s(row[1]) or "HCM"
        for m in range(1, 13):
            val = _i(months[m-1]) if m-1 < len(months) else 0
            if val > 0:
                db.add(StaffTarget(staff_name=a,
                                   office=office if office in ("HCM","HN","DN") else "HCM",
                                   month=m, year=current_year, target=val))
                count += 1

    db.flush()
    print(f"  04_STAFF_TARGETS:     {count} monthly target records")


# =============================================================================
# 14_COUNTRY_CODES
# =============================================================================
def import_country_codes(wb, db):
    ws = wb["14_COUNTRY_CODES"]
    db.query(CountryCode).delete()
    db.flush()

    count = 0
    seen = set()
    for row in ws.iter_rows(min_row=4, values_only=True):
        crm = _s(row[0])
        if not crm or crm.startswith("(") or crm in seen: continue
        seen.add(crm)
        code = _s(row[1])
        region = "Asia"
        if code in ("AU","NZ"): region = "Oceania"
        elif code in ("CA","US","GD"): region = "Americas"
        elif code in ("GB","IE","FR","DE","NL","SE","NO","DK","FI",
                      "CH","CZ","HU","PL","AT","BE","ES","IT"): region = "Europe"
        db.add(CountryCode(country_name=crm, country_code=code,
                           region=region, is_active=True))
        count += 1

    db.flush()
    print(f"  14_COUNTRY_CODES:     {count} records")


# =============================================================================
# 15_CLIENT_TYPE_MAP
# =============================================================================
def import_client_type_map(wb, db):
    ws = wb["15_CLIENT_TYPE_MAP"]
    db.query(ClientTypeMap).delete()
    db.flush()

    count = 0
    seen = set()
    for row in ws.iter_rows(min_row=4, values_only=True):
        raw = _s(row[0]); canonical = _s(row[1])
        if not raw or not canonical or raw.startswith("(") or raw in seen: continue
        seen.add(raw)
        db.add(ClientTypeMap(raw_value=raw, canonical=canonical,
                             display_name=raw, is_active=True))
        count += 1

    db.flush()
    print(f"  15_CLIENT_TYPE_MAP:   {count} records")


# =============================================================================
# 05_STATUS_RULES
# =============================================================================
def import_status_rules(wb, db):
    ws = wb["05_STATUS_RULES"]
    db.query(StatusRule).delete()
    db.query(ReferenceList).filter(ReferenceList.list_name == "application_status").delete()
    db.flush()

    # Ordered display list matching the input template
    status_order = [
        "Closed - Visa granted, then enrolled",
        "Closed - Visa granted (visa only)",
        "Closed - Visa granted then cancelled",
        "Closed - Visa refused",
        "Closed - Visa refused then granted",
        "Closed - Enrolment (only)",
        "Closed - Enrolled then cancelled",
        "Closed - Enrolled, then Visa granted",
        "Closed - Cancelled",
        "Current - Enrolled",
        "Current - Visa refused",
        "Pending - Visa refused",
        "Closed - Institution refused",
        "Closed - Visa granted",
        "Closed - Enrolled then visa refused",
        "Closed - Enrolment",
    ]

    count = 0
    seen = set()
    for row in ws.iter_rows(min_row=3, values_only=True):
        status = _s(row[0])
        if not status or status in seen: continue
        if not any(status.startswith(p) for p in ("Closed","Current","Pending")): continue
        seen.add(status)
        db.add(StatusRule(
            status_value=status,
            is_eligible=not (_b(row[8]) if len(row) > 8 else False),
            requires_visa=_b(row[10]) if len(row) > 10 else False,
            requires_enrol=_b(row[2]) if len(row) > 2 else False,
            note=_s(row[1]) if len(row) > 1 else ""
        ))
        count += 1

    for i, status in enumerate(status_order):
        db.add(ReferenceList(list_name="application_status",
                             value=status, sort_order=i, is_active=True))

    db.flush()
    print(f"  05_STATUS_RULES:      {count} rules + {len(status_order)} dropdown values")


# =============================================================================
# 09_SERVICE_FEE_RATES
# =============================================================================
def import_service_fee_rates(wb, db):
    ws = wb["09_SERVICE_FEE_RATES"]
    db.query(ServiceFeeRate).delete()
    db.query(ReferenceList).filter(ReferenceList.list_name == "service_fee_type").delete()
    db.flush()

    count = 0
    seen = set()
    for row in ws.iter_rows(min_row=4, values_only=True):
        code = _s(row[0])
        if not code or code.startswith("(") or "rows" in code.lower() or code in seen: continue
        seen.add(code)
        cat = _s(row[5]).upper() if len(row) > 5 else ""
        if not cat: continue
        db.add(ServiceFeeRate(fee_type=code, rate_pct=0.0,
                              flat_amount=_i(row[3]) if len(row) > 3 else 0,
                              note=_s(row[7]) if len(row) > 7 else "",
                              is_active=_b(row[4]) if len(row) > 4 else True))
        db.add(ReferenceList(list_name="service_fee_type",
                             value=code, sort_order=count, is_active=True))
        count += 1

    db.flush()
    print(f"  09_SERVICE_FEE_RATES: {count} records")


# =============================================================================
# 11_MASTER_AGENTS
# =============================================================================
def import_master_agents(wb, db):
    ws = wb["11_MASTER_AGENTS"]
    db.query(MasterAgent).delete()
    db.flush()

    count = 0
    seen = set()
    for row in ws.iter_rows(min_row=5, values_only=True):
        name = _s(row[1]); cls = _s(row[2])
        if not name or not cls or name in seen: continue
        seen.add(name)
        agent_type = "MASTER_AGENT" if "master" in cls.lower() else \
                     "GROUP" if "group" in cls.lower() else "DIRECT"
        db.add(MasterAgent(agent_name=name, agent_type=agent_type,
                           office="", is_active=True))
        count += 1

    db.flush()
    print(f"  11_MASTER_AGENTS:     {count} records")


# =============================================================================
# 13_SKIP_LABELS
# =============================================================================
def import_skip_labels(wb, db):
    ws = wb["13_SKIP_LABELS"]
    db.query(ReferenceList).filter(ReferenceList.list_name == "skip_labels").delete()
    db.flush()

    count = 0
    seen = set()
    for row in ws.iter_rows(min_row=4, values_only=True):
        label = _s(row[0])
        if not label or label.startswith("(") or label.startswith("13_") or label in seen: continue
        seen.add(label)
        db.add(ReferenceList(list_name="skip_labels", value=label,
                             sort_order=count, is_active=True))
        count += 1

    db.flush()
    print(f"  13_SKIP_LABELS:       {count} records")


# =============================================================================
# 03_PRIORITY_INSTNS
# =============================================================================
def import_priority_institutions(wb, db):
    ws = wb["03_PRIORITY_INSTNS"]
    db.query(PriorityInstitution).delete()
    db.flush()

    count = 0
    seen = set()
    for row in ws.iter_rows(min_row=3, values_only=True):
        country = _s(row[0]); name = _s(row[1])
        if not name or not country or name in seen: continue
        if name.startswith("(") or name.startswith("03_"): continue
        seen.add(name)
        db.add(PriorityInstitution(
            country_code=country,
            institution_name=name,
            annual_target=_i(row[2]),
            bonus_pct=_f(row[3]) if row[3] else 0.0,
            direct_target=_i(row[4]),
            sub_target=_i(row[5]) if len(row) > 5 else 0,
            is_active=True
        ))
        count += 1

    db.flush()
    print(f"  03_PRIORITY_INSTNS:   {count} institutions")


# =============================================================================
# 08_YTD_TRACKER
# =============================================================================
def import_ytd_tracker(wb, db):
    ws = wb["08_YTD_TRACKER"]
    db.query(YtdTracker).delete()
    db.flush()

    # Get current year from data (assume current tracking year)
    import datetime as dt
    current_year = dt.datetime.now().year

    count = 0
    for row in ws.iter_rows(min_row=3, values_only=True):
        inst_name = _s(row[0])
        if not inst_name or inst_name.startswith("("): continue

        # Columns: institution | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | YTD
        for m in range(1, 13):
            val = _i(row[m]) if len(row) > m and row[m] is not None else 0
            if val > 0:
                db.add(YtdTracker(
                    institution_name=inst_name,
                    year=current_year,
                    month=m,
                    enrolment_count=val
                ))
                count += 1

    db.flush()
    print(f"  08_YTD_TRACKER:       {count} monthly enrolment records")


# =============================================================================
# 06_CLIENT_WEIGHTS
# =============================================================================
def import_client_weights(wb, db):
    ws = wb["06_CLIENT_WEIGHTS"]
    db.query(ClientWeight).delete()
    db.flush()

    count = 0
    seen = set()
    for row in ws.iter_rows(min_row=3, values_only=True):
        display = _s(row[0]); canonical = _s(row[1])
        if not canonical or canonical in seen or "ENGINE" in canonical: continue
        seen.add(canonical)
        db.add(ClientWeight(
            canonical_code=canonical,
            display_name=display,
            weight_direct=_f(row[2]) if row[2] else 0.0,
            weight_referred=_f(row[3]) if row[3] else 0.0,
            weight_master=_f(row[4]) if row[4] else 0.0,
            weight_outsys=_f(row[5]) if len(row) > 5 and row[5] else 0.0,
            weight_outsys_usa=_f(row[6]) if len(row) > 6 and row[6] else 0.0,
            note=_s(row[7]) if len(row) > 7 else "",
            is_active=True
        ))
        count += 1

    db.flush()
    print(f"  06_CLIENT_WEIGHTS:    {count} records")


# =============================================================================
# 07_CONTRACT_BONUS
# =============================================================================
def import_contract_bonuses(wb, db):
    ws = wb["07_CONTRACT_BONUS"]
    db.query(ContractBonus).delete()
    db.flush()

    count = 0
    seen = set()
    for row in ws.iter_rows(min_row=3, values_only=True):
        name = _s(row[0])
        if not name or name in seen or name.startswith("(") or name.startswith("CONTRACT"): continue
        seen.add(name)
        db.add(ContractBonus(
            package_name=name,
            service_fee_vnd=_s(row[1]),
            coun_bonus=_s(row[2]),
            co_bonus=_s(row[3]),
            timing=_s(row[4]) if len(row) > 4 else "",
            note=_s(row[5]) if len(row) > 5 else "",
            is_active=True
        ))
        count += 1

    db.flush()
    print(f"  07_CONTRACT_BONUS:    {count} records")


# =============================================================================
# 09_ADVANCE_TRACKER
# =============================================================================
def import_advance_tracker(wb, db):
    ws = wb["09_ADVANCE_TRACKER"]
    db.query(AdvancePayment).delete()
    db.flush()

    count = 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        contract_id = _s(row[0])
        if not contract_id or not contract_id.startswith("SLC"): continue

        student_name  = _s(row[1])
        staff_name    = _s(row[2])
        period_dt     = _dt(row[3])
        advance_paid  = _i(row[4])
        status        = _s(row[5])
        full_bonus    = _i(row[6])
        recorded_dt   = _dt(row[7])

        period_month = period_dt.month if period_dt else None
        period_year  = period_dt.year  if period_dt else None

        db.add(AdvancePayment(
            contract_id=contract_id,
            student_name=student_name,
            staff_name=staff_name,
            period_month=period_month,
            period_year=period_year,
            advance_paid=advance_paid,
            status_at_payment=status,
            full_bonus_at_tier=full_bonus,
            is_settled=False,
            recorded_at=recorded_dt or datetime.utcnow()
        ))
        count += 1

    db.flush()
    print(f"  09_ADVANCE_TRACKER:   {count} advance payment records")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_engine_config.py path/to/engine.xlsm")
        sys.exit(1)
    xlsm_path = sys.argv[1]
    if not os.path.exists(xlsm_path):
        print(f"File not found: {xlsm_path}")
        sys.exit(1)
    import_all(xlsm_path)
