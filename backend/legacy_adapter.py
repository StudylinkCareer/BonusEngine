# =============================================================================
# legacy_adapter.py  |  StudyLink Bonus Engine v6.3
# Reads old 17/21-col báo cáo format and produces engine-ready dicts.
# =============================================================================

import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Dict, Optional, Tuple

import pandas as pd

# Local imports
try:
    from notes_parser import (
        ParsedNotes, parse_notes, infer_institution_type, infer_office,
        _GUARDIAN_AU_PATTERN
    )
except ImportError:
    from backend.notes_parser import (
        ParsedNotes, parse_notes, infer_institution_type, infer_office,
        _GUARDIAN_AU_PATTERN
    )


# ── Column positions in 17/21-col báo cáo format (0-based) ──────────────────
COL_NO          = 0
COL_NAME        = 1
COL_STUDENT_ID  = 2
COL_CONTRACT_ID = 3
COL_CONTRACT_DT = 4
COL_CLIENT_TYPE = 5
COL_COUNTRY     = 6
COL_AGENT       = 7
COL_SYSTEM_TYPE = 8
COL_STATUS      = 9
COL_VISA_DATE   = 10
COL_INSTITUTION = 11
COL_COURSE_DT   = 12
COL_COURSE_STAT = 13
COL_COUNSELLOR  = 14
COL_CO          = 15
COL_NOTES       = 16

# Bonus result columns (in báo cáo only, not closed-file)
COL_BONUS_ENR   = 17
COL_NOTE_ENR    = 18
COL_BONUS_PRI   = 20
COL_NOTE_PRI    = 21

SKIP_TOKENS = {
    "no.", "closed files", "closed files - enrolled", "enrolled",
    "closed file", "tong", "tổng", "data - updated", "data - update",
    "ngoc vien", "ngọc viên", "trong tháng", "no target",
    "tổng (bonus enrolled + bonus priority)",
    "tong (bonus enrolled",
}


@dataclass
class LegacyCase:
    no:             str  = ""
    student_name:   str  = ""
    student_id:     str  = ""
    contract_id:    str  = ""
    contract_date:  Optional[date] = None
    client_type:    str  = ""
    country:        str  = ""
    agent:          str  = ""
    system_type:    str  = ""
    app_status:     str  = ""
    visa_date:      Optional[date] = None
    institution:    str  = ""
    course_start:   Optional[date] = None
    course_status:  str  = ""
    counsellor:     str  = ""
    co:             str  = ""
    notes_raw:      str  = ""

    service_fee_type: str  = "NONE"
    package_type:     str  = "NONE"
    handover:         str  = "NO"
    handover_from:    str  = ""
    addons:           List[str] = field(default_factory=list)
    deferral:         str  = "NONE"

    institution_type: str  = "DIRECT"
    office:           str  = "HCM"
    is_addon:         bool = False

    actual_bonus_enr: int = 0
    actual_bonus_pri: int = 0
    actual_note_enr:  str = ""
    actual_note_pri:  str = ""

    customer_incentive: int = 0
    presales_agent:    str = "NONE"


def _safe_date(v) -> Optional[date]:
    if v is None: return None
    if isinstance(v, float) and pd.isna(v): return None
    if isinstance(v, (datetime, date)):
        return v.date() if isinstance(v, datetime) else v
    s = str(v).strip()
    if not s or s.lower() == "nan": return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try: return datetime.strptime(s[:19], fmt).date()
        except: pass
    return None


def _safe_str(v) -> str:
    if v is None: return ""
    if isinstance(v, float) and pd.isna(v): return ""
    s = str(v).strip()
    return "" if s.lower() == "nan" else s


def _safe_int(v) -> int:
    if v is None: return 0
    if isinstance(v, float) and pd.isna(v): return 0
    try:
        s = str(v).replace(",", "").replace(" ", "")
        if "." in s:
            s = s.split(".")[0]
        return int(s) if s else 0
    except:
        return 0


def _is_skip_row(v0: str) -> bool:
    v = v0.strip().lower()
    if not v: return True
    for tok in SKIP_TOKENS:
        if v.startswith(tok): return True
    cleaned = v.replace(".", "").replace(",", "")
    if cleaned.isdigit(): return False
    return True


def read_baocao(filepath: str, report_year: int, report_month: int,
                staff_scheme: str = "HCM_DIRECT",
                customer_incentive_default: int = 0) -> Tuple[List[LegacyCase], Dict]:
    """Read báo cáo or closed-file Excel report. Returns (cases, metadata)."""
    df = pd.read_excel(filepath, header=None, dtype=str)

    # Find header row
    hdr_row = None
    for i, row in df.iterrows():
        vals = [str(v).strip() for v in row.values]
        if "No." in vals or "No" in vals:
            hdr_row = i; break
    if hdr_row is None:
        raise ValueError(f"Header row not found in {filepath}")

    cases: List[LegacyCase] = []
    meta = {
        "filepath": filepath,
        "year": report_year,
        "month": report_month,
        "scheme": staff_scheme,
        "hdr_row": hdr_row,
        "total_rows_read": 0,
        "staff_name": "",
        "actual_total_enrolled": 0,
        "actual_total_priority": 0,
    }

    for i, row in df.iterrows():
        if i <= hdr_row: continue
        vals = [_safe_str(v) for v in row.values]
        v0 = vals[0] if vals else ""
        if _is_skip_row(v0): continue

        def get(idx: int) -> str:
            return vals[idx] if idx < len(vals) else ""

        meta["total_rows_read"] += 1

        notes_raw = get(COL_NOTES)
        parsed = parse_notes(notes_raw)

        # Also scan col 19 (Note BONUS Enrolled) for guardian add-ons
        note_enr_text = get(COL_NOTE_ENR)
        if note_enr_text and _GUARDIAN_AU_PATTERN.search(note_enr_text):
            if "GUARDIAN_AU_ADDON" not in parsed.addons:
                parsed.addons.append("GUARDIAN_AU_ADDON")

        inst_type = infer_institution_type(
            get(COL_AGENT), get(COL_INSTITUTION), get(COL_SYSTEM_TYPE)
        )
        if parsed.inst_type_hint:
            inst_type = parsed.inst_type_hint

        office = infer_office(get(COL_AGENT), get(COL_COUNSELLOR), get(COL_CO))

        case = LegacyCase(
            no             = v0,
            student_name   = get(COL_NAME),
            student_id     = get(COL_STUDENT_ID),
            contract_id    = get(COL_CONTRACT_ID),
            contract_date  = _safe_date(get(COL_CONTRACT_DT)),
            client_type    = get(COL_CLIENT_TYPE),
            country        = get(COL_COUNTRY),
            agent          = get(COL_AGENT),
            system_type    = get(COL_SYSTEM_TYPE),
            app_status     = get(COL_STATUS),
            visa_date      = _safe_date(get(COL_VISA_DATE)),
            institution    = get(COL_INSTITUTION),
            course_start   = _safe_date(get(COL_COURSE_DT)),
            course_status  = get(COL_COURSE_STAT),
            counsellor     = get(COL_COUNSELLOR),
            co             = get(COL_CO),
            notes_raw      = notes_raw,
            service_fee_type = parsed.service_fee_type,
            package_type     = parsed.package_type,
            handover         = parsed.handover,
            handover_from    = parsed.handover_from,
            addons           = parsed.addons,
            deferral         = parsed.deferral,
            institution_type = inst_type,
            office           = office,
            customer_incentive = customer_incentive_default,
            presales_agent   = "NONE",
            actual_bonus_enr = _safe_int(get(COL_BONUS_ENR)),
            actual_bonus_pri = _safe_int(get(COL_BONUS_PRI) if len(vals) > COL_BONUS_PRI
                                          else get(COL_BONUS_PRI-1)),
            actual_note_enr  = note_enr_text,
        )

        if not meta["staff_name"]:
            meta["staff_name"] = case.co or case.counsellor

        meta["actual_total_enrolled"] += case.actual_bonus_enr
        meta["actual_total_priority"] += case.actual_bonus_pri

        cases.append(case)

        # Synthetic ADDON rows for add-ons
        for addon_code in parsed.addons:
            addon_row = LegacyCase(
                no           = v0 + "_ADDON",
                contract_id  = case.contract_id,
                student_name = case.student_name,
                is_addon     = True,
                service_fee_type = addon_code,
                institution_type = "ADDON",
                office       = office,
            )
            cases.append(addon_row)

    meta["actual_total"] = (meta["actual_total_enrolled"] +
                             meta["actual_total_priority"])
    return cases, meta


def to_engine_dict(case: LegacyCase, scheme: str) -> Dict:
    """Convert a LegacyCase to the dict format for build_case_records."""

    # For enrolled cases, CONTRACT-type service fee codes (SDS, Standard, Regular)
    # represent fee at signing — not enrolment bonus. Clear so tier rate fires.
    _ENROLLED_STATUSES = {
        "closed - visa granted, then enrolled",
        "closed - enrolment",
        "closed - enrolment (only)",
        "closed - enrolled, then visa granted",
        "current - enrolled",
    }
    _CONTRACT_FEE_CODES = {
        "CAN_SDS_7TR5", "CAN_SDS_6TR5", "CAN_REGULAR_9TR5",
        "US_STANDARD_16TR", "CAN_MASTER_15TR", "CAN_PREMIUM_14TR",
        "CAN_STANDARD_9TR5", "OUT_SYSTEM_30TR", "DIFFICULT_CASE_20TR",
        "OUT_SYSTEM_14TR",
    }
    sft = case.service_fee_type
    if (case.app_status.lower() in _ENROLLED_STATUSES and
            sft.upper() in _CONTRACT_FEE_CODES):
        sft = "NONE"  # tier rate fires; signing bonus paid separately

    if case.is_addon:
        return {
            "row_type":          "ADDON",
            "contract_id":       case.contract_id,
            "addon_code":        case.service_fee_type,
            "addon_count":       1,
            "office":            case.office,
        }

    return {
        "row_type":          "BASE",
        "original_no":       case.no,
        "student_name":      case.student_name,
        "student_id":        case.student_id,
        "contract_id":       case.contract_id,
        "contract_date":     case.contract_date,
        "client_type":       case.client_type,
        "country":           case.country,
        "agent":             case.agent,
        "system_type":       case.system_type,
        "app_status":        case.app_status,
        "visa_date":         case.visa_date,
        "institution":       case.institution,
        "course_start":      case.course_start,
        "course_status":     case.course_status,
        "counsellor":        case.counsellor,
        "case_officer":      case.co,
        "notes":             case.notes_raw,
        "service_fee_type":  sft,
        "package_type":      case.package_type,
        "handover":          case.handover,
        "deferral":          case.deferral,
        "institution_type":  case.institution_type,
        "office":            case.office,
        "incentive":         case.customer_incentive,
        "presales_agent":    case.presales_agent,
    }


def build_case_records(cases_dicts: List[Dict], cfg) -> List:
    """Build CaseRecord objects from dicts."""
    from app.engine.models import CaseRecord
    records = []
    for d in cases_dicts:
        c = CaseRecord()
        for k, v in d.items():
            if hasattr(c, k):
                setattr(c, k, v)
        # Derive country flags
        cr = cfg.get_country(d.get("country", ""))
        c.country_code = cr.code
        c.is_flat_country = cr.is_flat_country
        c.is_vietnam = cr.is_vietnam
        c.client_type_code = cfg.get_client_type_code(d.get("client_type", ""))
        records.append(c)
    return records
