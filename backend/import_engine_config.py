"""
import_engine_config.py
=======================
One-time (and repeatable) script to import all configuration from engine.xlsm
into PostgreSQL reference tables.

Run from the backend/ folder:
    python import_engine_config.py path/to/engine.xlsm

After this runs, the app no longer needs engine.xlsm at runtime.
All config is read from PostgreSQL via load_config_from_db().
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import openpyxl
from app.database import engine as db_engine, SessionLocal
from app.models import (
    Base, StaffName, StaffTarget, MasterAgent, CountryCode,
    ClientTypeMap, StatusRule, ServiceFeeRate, ReferenceList
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


def import_all(xlsm_path: str):
    Base.metadata.create_all(bind=db_engine)
    db = SessionLocal()

    try:
        wb = openpyxl.load_workbook(xlsm_path, data_only=True)
        print(f"Opened {xlsm_path}")
        print(f"Sheets: {wb.sheetnames}\n")

        import_staff_names(wb, db)
        import_staff_targets(wb, db)
        import_country_codes(wb, db)
        import_client_type_map(wb, db)
        import_status_rules(wb, db)
        import_service_fee_rates(wb, db)
        import_master_agents(wb, db)
        import_skip_labels(wb, db)

        db.commit()
        print("\n✅ Import complete!")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Import failed: {e}")
        raise
    finally:
        db.close()


def import_staff_names(wb, db):
    ws = wb["12_STAFF_NAMES"]

    db.query(ReferenceList).filter(ReferenceList.list_name == "staff_name_map").delete()
    db.flush()

    count = 0
    seen_canonical = set()
    seen_crm = set()

    for row in ws.iter_rows(min_row=5, values_only=True):
        crm_name = _s(row[1])
        canonical = _s(row[2])
        role_note = _s(row[4]).lower() if len(row) > 4 else ""

        if not crm_name or not canonical:
            continue
        if crm_name in seen_crm:
            continue
        seen_crm.add(crm_name)

        db.add(ReferenceList(
            list_name="staff_name_map",
            value=crm_name,
            sort_order=count,
            is_active=True
        ))

        if canonical not in seen_canonical:
            seen_canonical.add(canonical)
            existing_staff = db.query(StaffName).filter(
                StaffName.full_name == canonical
            ).first()
            if not existing_staff:
                office = "HCM"
                if "hn" in role_note or "ha noi" in role_note or "hanoi" in role_note:
                    office = "HN"
                elif "dn" in role_note or "da nang" in role_note:
                    office = "DN"
                role = "counsellor"
                if "co_sub" in role_note:
                    role = "case_officer"
                elif "presales" in role_note:
                    role = "presales"

                db.add(StaffName(
                    full_name=canonical,
                    short_name=canonical,
                    office=office,
                    role=role,
                    is_active=True
                ))

        count += 1

    db.flush()
    print(f"  Staff names: {count} CRM mappings, {len(seen_canonical)} canonical names")


def import_staff_targets(wb, db):
    ws = wb["04_STAFF_TARGETS"]

    db.query(StaffTarget).delete()
    db.flush()

    current_year = None
    count = 0

    for row in ws.iter_rows(min_row=3, values_only=True):
        a = _s(row[0]).strip("'")
        if not a:
            continue

        if a.isdigit() and len(a) == 4:
            current_year = int(a)
            continue

        if current_year is None:
            continue

        if a.lower() in ("staff member", "name"):
            continue

        staff_name = a
        office = _s(row[1]) or "HCM"
        role = _s(row[2]) or "CO"

        idx3 = _s(row[3]) if len(row) > 3 and row[3] is not None else "0"
        try:
            float(idx3.replace("—", "0").replace("–", "0"))
            month_values = list(row[3:15])
        except (ValueError, TypeError):
            month_values = list(row[4:16])

        for m in range(1, 13):
            val = _i(month_values[m-1]) if m-1 < len(month_values) else 0
            if val > 0:
                db.add(StaffTarget(
                    staff_name=staff_name,
                    office=office if office in ("HCM", "HN", "DN") else "HCM",
                    month=m,
                    year=current_year,
                    target=val
                ))
                count += 1

    db.flush()
    print(f"  Staff targets: {count} monthly target records")


def import_country_codes(wb, db):
    ws = wb["14_COUNTRY_CODES"]

    db.query(CountryCode).delete()
    db.flush()

    count = 0
    seen = set()

    for row in ws.iter_rows(min_row=4, values_only=True):
        crm = _s(row[0])
        if not crm or crm.startswith("(") or crm in seen:
            continue
        seen.add(crm)

        code = _s(row[1])

        region = "Asia"
        if code in ("AU", "NZ"):
            region = "Oceania"
        elif code in ("CA", "US", "GD"):
            region = "Americas"
        elif code in ("GB", "IE", "FR", "DE", "NL", "SE", "NO", "DK", "FI",
                      "CH", "CZ", "HU", "PL", "AT", "BE", "ES", "IT"):
            region = "Europe"

        db.add(CountryCode(
            country_name=crm,
            country_code=code,
            region=region,
            is_active=True
        ))
        count += 1

    db.flush()
    print(f"  Country codes: {count} records")


def import_client_type_map(wb, db):
    ws = wb["15_CLIENT_TYPE_MAP"]

    db.query(ClientTypeMap).delete()
    db.flush()

    count = 0
    seen = set()

    for row in ws.iter_rows(min_row=4, values_only=True):
        raw = _s(row[0])
        canonical = _s(row[1])
        if not raw or not canonical or raw.startswith("(") or raw in seen:
            continue
        seen.add(raw)

        db.add(ClientTypeMap(
            raw_value=raw,
            canonical=canonical,
            display_name=raw,
            is_active=True
        ))
        count += 1

    db.flush()
    print(f"  Client type map: {count} records")


def import_status_rules(wb, db):
    ws = wb["05_STATUS_RULES"]

    db.query(StatusRule).delete()
    db.flush()

    count = 0
    seen = set()

    for row in ws.iter_rows(min_row=3, values_only=True):
        status = _s(row[0])
        if not status or status.startswith("(") or status.startswith("05_") or status in seen:
            continue
        seen.add(status)

        counts_enrolled = _b(row[2]) if len(row) > 2 else False
        is_visa = _b(row[10]) if len(row) > 10 else False
        is_zero = _b(row[8]) if len(row) > 8 else False

        db.add(StatusRule(
            status_value=status,
            is_eligible=not is_zero,
            requires_visa=is_visa,
            requires_enrol=counts_enrolled,
            note=_s(row[1]) if len(row) > 1 else ""
        ))
        count += 1

    db.flush()
    print(f"  Status rules: {count} records")


def import_service_fee_rates(wb, db):
    ws = wb["09_SERVICE_FEE_RATES"]

    db.query(ServiceFeeRate).delete()
    db.query(ReferenceList).filter(ReferenceList.list_name == "service_fee_type").delete()
    db.flush()

    count = 0
    seen = set()

    for row in ws.iter_rows(min_row=4, values_only=True):
        code = _s(row[0])
        if not code or code.startswith("(") or "rows" in code.lower() or code in seen:
            continue
        seen.add(code)

        cat = _s(row[5]).upper() if len(row) > 5 else ""
        if not cat:
            continue

        db.add(ServiceFeeRate(
            fee_type=code,
            rate_pct=0.0,
            flat_amount=_i(row[3]) if len(row) > 3 else 0,
            note=_s(row[7]) if len(row) > 7 else "",
            is_active=_b(row[4]) if len(row) > 4 else True
        ))

        db.add(ReferenceList(
            list_name="service_fee_type",
            value=code,
            sort_order=count,
            is_active=True
        ))
        count += 1

    db.flush()
    print(f"  Service fee rates: {count} records")


def import_master_agents(wb, db):
    ws = wb["11_MASTER_AGENTS"]

    db.query(MasterAgent).delete()
    db.flush()

    count = 0
    seen = set()

    for row in ws.iter_rows(min_row=5, values_only=True):
        name = _s(row[1])
        classification = _s(row[2])
        if not name or not classification or name in seen:
            continue
        seen.add(name)

        agent_type = "DIRECT"
        if "master" in classification.lower():
            agent_type = "MASTER_AGENT"
        elif "group" in classification.lower():
            agent_type = "GROUP"

        db.add(MasterAgent(
            agent_name=name,
            agent_type=agent_type,
            office="",
            is_active=True
        ))
        count += 1

    db.flush()
    print(f"  Master agents: {count} records")


def import_skip_labels(wb, db):
    ws = wb["13_SKIP_LABELS"]

    db.query(ReferenceList).filter(ReferenceList.list_name == "skip_labels").delete()
    db.flush()

    count = 0
    seen = set()

    for row in ws.iter_rows(min_row=4, values_only=True):
        label = _s(row[0])
        if not label or label.startswith("(") or label.startswith("13_") or label in seen:
            continue
        seen.add(label)

        db.add(ReferenceList(
            list_name="skip_labels",
            value=label,
            sort_order=count,
            is_active=True
        ))
        count += 1

    db.flush()
    print(f"  Skip labels: {count} records")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_engine_config.py path/to/engine.xlsm")
        sys.exit(1)

    xlsm_path = sys.argv[1]
    if not os.path.exists(xlsm_path):
        print(f"File not found: {xlsm_path}")
        sys.exit(1)

    import_all(xlsm_path)
