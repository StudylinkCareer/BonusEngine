# =============================================================================
# input.py
# Equivalent of modInput.bas
# Parses CRM Excel reports into CaseRecord lists.
# Handles both the native CRM format and the v7 template input format.
# =============================================================================

import re
from datetime import datetime, date
from typing import List, Tuple, Optional
import openpyxl

from .constants import (
    COL_NO, COL_NAME, COL_STUDENT_ID, COL_CONTRACT_ID, COL_CONTRACT_DATE,
    COL_CLIENT_TYPE, COL_COUNTRY, COL_AGENT, COL_SYSTEM, COL_STATUS,
    COL_VISA_DATE, COL_INSTITUTION, COL_COURSE_START, COL_COURSE_STATUS,
    COL_COUNSELLOR, COL_CO, COL_PRESALES_AGENT, COL_INCENTIVE, COL_NOTES,
    COL_SERVICE_FEE, COL_DEFERRAL, COL_PACKAGE_TYPE, COL_OFFICE,
    COL_HANDOVER, COL_TARGET_OWNER, COL_CASE_TRANS, COL_PRIOR_RATE,
    COL_INST_TYPE, COL_GROUP_AGENT, COL_TARGETS_NAME,
    COL_ROW_TYPE, COL_ADDON_CODE, COL_ADDON_COUNT,
    ROW_TYPE_BASE, ROW_TYPE_ADDON, ADDON_STATUS,
    PRESALES_NONE, OFFICE_HCM, OFFICE_HN, OFFICE_DN, OFFICE_DEFAULT,
    INST_TYPE_DIRECT, INST_TYPE_MASTER_AGENT, INST_TYPE_GROUP,
    INST_TYPE_OUT_OF_SYS, INST_TYPE_RMIT_VN, INST_TYPE_BUV_VN,
    INST_TYPE_OTHER_VN,
)
from .calc import CaseRecord
from .config import BonusConfig

# Row labels that should be skipped during parsing
SKIP_LABELS_FALLBACK = {
    "no.", "closed files", "closed files - enrolled", "enrolled",
    "closed file", "tong", "tổng", "tong (bonus", "tổng (bonus",
    "data - updated", "ngoc vien", "ngọc viên", "closed files - visa",
    "closed files - other",
}


# =============================================================================
# Safe cell readers
# =============================================================================

def _str(cell) -> str:
    v = cell.value if hasattr(cell, 'value') else cell
    if v is None:
        return ""
    return str(v).strip()


def _date(cell) -> Optional[date]:
    v = cell.value if hasattr(cell, 'value') else cell
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    s = str(v).strip().replace(' 00:00:00', '')
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _int(cell) -> int:
    v = cell.value if hasattr(cell, 'value') else cell
    if v is None:
        return 0
    s = str(v).replace(',', '').replace(' ', '').strip()
    if s.upper() in ('NO', 'N/A', ''):
        return 0
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return 0


def _is_skip_label(value: str, cfg: Optional[BonusConfig] = None) -> bool:
    """Returns True if the row label should be skipped."""
    v = value.strip().lower()
    if not v:
        return True
    # Check config-driven skip labels first
    if cfg and cfg.is_skip_label(value):
        return True
    # Fallback hardcoded labels
    for label in SKIP_LABELS_FALLBACK:
        if v == label or v.startswith(label):
            return True
    return False


# =============================================================================
# Deduplication
# =============================================================================

def _get_status_rank(status: str, cfg: BonusConfig) -> int:
    rule = cfg.get_status_rule(status)
    return rule.deduplication_rank


def _deduplicate(cases: List[CaseRecord], cfg: BonusConfig) -> Tuple[List[CaseRecord], List[str]]:
    """
    Removes lower-ranked duplicate ContractIDs.
    Higher deduplication_rank wins.
    Returns (deduped_cases, warnings).
    """
    warnings = []
    flagged = [False] * len(cases)

    for i in range(len(cases)):
        if flagged[i] or cases[i].row_type == ROW_TYPE_ADDON:
            continue
        for j in range(i + 1, len(cases)):
            if flagged[j] or cases[j].row_type == ROW_TYPE_ADDON:
                continue
            if (cases[i].contract_id and
                    cases[i].contract_id == cases[j].contract_id):
                rank_i = _get_status_rank(cases[i].app_status, cfg)
                rank_j = _get_status_rank(cases[j].app_status, cfg)
                if rank_j > rank_i:
                    flagged[i] = True
                    msg = (f"Duplicate contract {cases[i].contract_id} -- "
                           f"retained: {cases[j].app_status}, "
                           f"removed: {cases[i].app_status}")
                    warnings.append(msg)
                else:
                    flagged[j] = True
                    msg = (f"Duplicate contract {cases[i].contract_id} -- "
                           f"retained: {cases[i].app_status}, "
                           f"removed: {cases[j].app_status}")
                    warnings.append(msg)

    deduped = [c for i, c in enumerate(cases) if not flagged[i]]
    return deduped, warnings


# =============================================================================
# Row validation
# =============================================================================

def validate_row(cs: CaseRecord, cfg: BonusConfig) -> List[str]:
    """
    Validates mandatory fields for a BASE row.
    Returns list of error strings. Empty list = valid.
    Mirrors ValidateRow() in modInput.bas.
    """
    errors = []

    def req(val, col_num, col_name, hint=""):
        if not val or val.strip() == "":
            errors.append(f"  Col {col_num} ({col_name}): blank.{' ' + hint if hint else ''}")

    req(cs.student_name,   2,  "Student Name")
    req(cs.contract_id,    4,  "Contract ID")
    req(cs.client_type,    6,  "Client Type")
    req(cs.country,        7,  "Country")
    req(cs.app_status,     10, "Application Status")
    req(cs.institution,    12, "Institution Name")
    req(cs.counsellor,     15, "Counsellor Name")
    req(cs.case_officer,   16, "Case Officer Name")

    # Client type code must resolve
    if cs.client_type and not cs.client_type_code:
        errors.append(
            f"  Col 6 (Client Type): '{cs.client_type}' not found in 15_CLIENT_TYPE_MAP. "
            f"Check spelling."
        )

    # Mandatory operator fields
    if not cs.service_fee_type:
        errors.append("  Col 20 (Service Fee Type): blank. Enter NONE if no service fee.")
    if not cs.deferral:
        errors.append("  Col 21 (Deferral): blank. Enter NONE if no deferral.")
    if not cs.package_type:
        errors.append("  Col 22 (Package Type): blank. Enter NONE if no package.")
    if not cs.handover:
        errors.append("  Col 24 (Handover): blank. Enter YES or NO.")
    if not cs.case_transition:
        errors.append("  Col 26 (Case Transition): blank. Enter YES or NO.")
    if not cs.institution_type:
        errors.append("  Col 28 (Institution Type): blank. Enter DIRECT if standard case.")
    if not cs.targets_name:
        errors.append(
            "  Col 30 (Targets Name): blank. Enter the name of the staff member "
            "whose bonus this file calculates. Must match 04_STAFF_TARGETS exactly."
        )

    # Conditional mandatory fields
    if cs.app_status:
        sr = cfg.get_status_rule(cs.app_status)
        if sr.is_visa_granted and not cs.visa_date:
            errors.append(f"  Col 11 (Visa Date): required for status '{cs.app_status}'")
        if sr.counts_as_enrolled and not cs.course_start:
            errors.append(f"  Col 13 (Course Start): required for status '{cs.app_status}'")
        if sr.is_carry_over and cs.prior_month_rate == 0:
            errors.append(
                "  Col 27 (Prior Month Rate): required for carry-over status. "
                "Auto-lookup found no prior rate. Enter manually."
            )

    # MGMT_EXCEPTION requires amount
    if cs.service_fee_type.upper() == "MGMT_EXCEPTION" and cs.prior_month_rate == 0:
        errors.append(
            "  Col 27 (Management Override Amount): required when col 20 = MGMT_EXCEPTION. "
            "Enter the management-approved bonus amount."
        )

    # Handover requires target owner
    if cs.handover.upper() == "YES" and not cs.target_owner:
        errors.append("  Col 25 (Target Owner): required when Handover = YES.")

    # MASTER_AGENT/GROUP require group agent name
    if cs.institution_type in (INST_TYPE_MASTER_AGENT, INST_TYPE_GROUP):
        if not cs.group_agent_name:
            errors.append(
                f"  Col 29 (Group/Agent Name): required when Institution Type = "
                f"{cs.institution_type}"
            )

    return errors


# =============================================================================
# Office detection from agent field
# =============================================================================

def detect_office_from_agent(agent: str) -> str:
    """Infers office from agent name. Advisory only — col 23 override takes precedence."""
    if not agent:
        return OFFICE_DEFAULT
    a = agent.lower()
    if "hà nội" in a or "ha noi" in a or "vp hn" in a:
        return OFFICE_HN
    if "đà nẵng" in a or "da nang" in a or "vp dn" in a or "vp đn" in a:
        return OFFICE_DN
    return OFFICE_DEFAULT


# =============================================================================
# Main parser — v7 template input format
# =============================================================================

def parse_input_file(
    file_path: str,
    cfg: BonusConfig,
) -> Tuple[List[CaseRecord], str, List[str], List[str]]:
    """
    Parses a v7 template input Excel file.
    Returns (cases, staff_name, errors, warnings).
    errors = blocking validation errors (engine cannot run)
    warnings = non-blocking notices
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.worksheets[0]

    cases: List[CaseRecord] = []
    addon_rows: List[CaseRecord] = []
    errors: List[str] = []
    warnings: List[str] = []
    staff_name = ""

    for row in ws.iter_rows(min_row=4):
        no_val = _str(row[0]) if row else ""
        if not no_val:
            continue
        if _is_skip_label(no_val, cfg):
            continue

        row_type = _str(row[COL_ROW_TYPE - 1]).upper() if len(row) >= COL_ROW_TYPE else ""
        if not row_type:
            row_type = ROW_TYPE_BASE

        # ── ADDON rows ────────────────────────────────────────────────────────
        if row_type == ROW_TYPE_ADDON:
            cs = CaseRecord()
            cs.original_no  = no_val
            cs.row_type     = ROW_TYPE_ADDON
            cs.app_status   = ADDON_STATUS
            cs.contract_id  = _str(row[COL_CONTRACT_ID - 1])
            cs.addon_code   = _str(row[COL_ADDON_CODE - 1]).upper() if len(row) >= COL_ADDON_CODE else ""
            cs.addon_count  = _int(row[COL_ADDON_COUNT - 1]) if len(row) >= COL_ADDON_COUNT else 0

            if not cs.contract_id:
                errors.append(f"ADDON row #{no_val}: Col 4 (Contract ID) is blank.")
            if not cs.addon_code:
                errors.append(f"ADDON row #{no_val} ({cs.contract_id}): Col 32 (Add-on Code) is blank.")
            if cs.addon_count <= 0:
                errors.append(f"ADDON row #{no_val} ({cs.contract_id}): Col 33 (Add-on Count) must be > 0.")

            addon_rows.append(cs)
            continue

        # ── BASE rows ─────────────────────────────────────────────────────────
        if not no_val.replace('.', '').isdigit():
            continue  # Skip non-numeric rows that aren't ADDON

        def col(n):
            idx = n - 1
            return row[idx] if idx < len(row) else type('', (), {'value': None})()

        cs = CaseRecord()
        cs.original_no    = no_val
        cs.row_type       = ROW_TYPE_BASE
        cs.student_name   = _str(col(COL_NAME))
        cs.student_id     = _str(col(COL_STUDENT_ID))
        cs.contract_id    = _str(col(COL_CONTRACT_ID))
        cs.contract_date  = _date(col(COL_CONTRACT_DATE))
        cs.client_type    = _str(col(COL_CLIENT_TYPE))
        cs.country        = _str(col(COL_COUNTRY))
        cs.agent          = _str(col(COL_AGENT))
        cs.system_type    = _str(col(COL_SYSTEM))
        cs.app_status     = _str(col(COL_STATUS))
        cs.visa_date      = _date(col(COL_VISA_DATE))
        cs.institution    = _str(col(COL_INSTITUTION))
        cs.course_start   = _date(col(COL_COURSE_START))
        cs.course_status  = _str(col(COL_COURSE_STATUS))
        cs.counsellor     = _str(col(COL_COUNSELLOR))
        cs.case_officer   = _str(col(COL_CO))

        # Col 17: Pre-sales agent
        ps = _str(col(COL_PRESALES_AGENT)).upper()
        cs.presales_agent = ps if ps else PRESALES_NONE

        # Col 18-19
        cs.incentive = _int(col(COL_INCENTIVE))
        cs.notes     = _str(col(COL_NOTES))

        # Col 20-22: service / deferral / package
        cs.service_fee_type = _str(col(COL_SERVICE_FEE)).upper() or "NONE"
        cs.deferral         = _str(col(COL_DEFERRAL)).upper() or "NONE"
        cs.package_type     = _str(col(COL_PACKAGE_TYPE)) or "NONE"

        # Col 23-27: routing
        office = _str(col(COL_OFFICE)).upper()
        cs.office_override  = office if office in (OFFICE_HCM, OFFICE_HN, OFFICE_DN) else OFFICE_DEFAULT
        cs.handover         = _str(col(COL_HANDOVER)).upper() or "NO"
        cs.target_owner     = _str(col(COL_TARGET_OWNER))
        cs.case_transition  = _str(col(COL_CASE_TRANS)).upper() or "NO"
        cs.prior_month_rate = _int(col(COL_PRIOR_RATE))

        # Col 28-30: institution classification
        cs.institution_type  = _str(col(COL_INST_TYPE)).upper() or INST_TYPE_DIRECT
        cs.group_agent_name  = _str(col(COL_GROUP_AGENT))
        cs.targets_name      = _str(col(COL_TARGETS_NAME))

        # Derive office source
        cs.office_source = cs.office_override or detect_office_from_agent(cs.agent)

        # Normalise country and client type codes
        country_rule        = cfg.get_country_code(cs.country)
        cs.country_code     = country_rule.canonical_code
        cs.client_type_code = cfg.get_client_type_code(cs.client_type)

        # Resolve staff name
        if not staff_name and cs.targets_name:
            staff_name = cfg.resolve_staff_name(cs.targets_name)

        # Auto-lookup carry-over rate if missing (will be handled by engine later)

        # Validate
        row_errors = validate_row(cs, cfg)
        if row_errors:
            errors.append(
                f"Case #{cs.original_no} ({cs.student_name}):\n" +
                "\n".join(row_errors)
            )

        cases.append(cs)

    # Append ADDON rows after deduplication
    deduped, dup_warnings = _deduplicate(cases, cfg)
    warnings.extend(dup_warnings)

    # Cross-reference ADDON rows to BASE rows
    base_contracts = {c.contract_id for c in deduped}
    for addon in addon_rows:
        if addon.contract_id not in base_contracts:
            errors.append(
                f"ADDON row #{addon.original_no}: Contract ID '{addon.contract_id}' "
                f"has no matching BASE row."
            )
        else:
            deduped.append(addon)

    return deduped, staff_name, errors, warnings


# =============================================================================
# Native CRM report parser (the "Báo cáo" format)
# =============================================================================

def parse_crm_report(
    file_path: str,
    cfg: BonusConfig,
) -> Tuple[List[dict], str, List[str]]:
    """
    Parses a native CRM closed-file report (Báo cáo format).
    Returns (raw_rows, staff_name, warnings) where raw_rows are dicts
    that can be used to pre-populate an input file for review.

    Column layout (CRM native, detected dynamically):
    No. | Student Name | Student ID | Contract ID | Contract Date |
    Client Type | Country | Refer Agent | System Type | Status |
    Visa Date | Institution | Course Start | Course Status |
    Counsellor | Case Officer | Notes
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.worksheets[0]

    # Detect header row (contains "Contract ID" or "No.")
    header_row_idx = None
    col_map = {}

    for i, row in enumerate(ws.iter_rows(max_row=10)):
        headers = [_str(c).lower().strip() for c in row]
        if "contract id" in headers or "no." in headers:
            header_row_idx = i
            for j, h in enumerate(headers):
                col_map[h] = j
            break

    if header_row_idx is None:
        return [], "", ["Could not detect header row in CRM report"]

    raw_rows = []
    staff_name = ""
    warnings = []

    HEADER = header_row_idx + 1  # 0-indexed, skip to data
    for row in ws.iter_rows(min_row=HEADER + 1):
        no_val = _str(row[col_map.get("no.", 0)]) if col_map else _str(row[0])
        if not no_val or _is_skip_label(no_val):
            continue
        if not no_val.replace('.', '').isdigit():
            continue

        def get(key: str) -> str:
            idx = col_map.get(key)
            if idx is None:
                return ""
            return _str(row[idx]) if idx < len(row) else ""

        def get_date(key: str):
            idx = col_map.get(key)
            if idx is None:
                return None
            return _date(row[idx]) if idx < len(row) else None

        counsellor  = get("counsellor name")
        case_officer = get("case officer name")
        notes       = get("notes")

        # Detect staff name from first non-empty row
        if not staff_name:
            name_candidate = counsellor or case_officer
            if name_candidate:
                staff_name = cfg.resolve_staff_name(name_candidate)

        # Infer institution type from name markers
        institution = get("institution name")
        if "**" in institution:
            inst_type = INST_TYPE_GROUP
        elif "*" in institution:
            inst_type = INST_TYPE_MASTER_AGENT
        else:
            system = get("system type")
            if "ngoài" in system.lower() or "ngoai" in system.lower():
                inst_type = INST_TYPE_OUT_OF_SYS
            elif "rmit" in institution.lower():
                inst_type = INST_TYPE_RMIT_VN
            else:
                inst_type = INST_TYPE_DIRECT

        # Infer package from notes
        package = _infer_package_from_notes(notes)

        raw_rows.append({
            "no":           no_val,
            "student_name": get("student name"),
            "student_id":   get("student id"),
            "contract_id":  get("contract id"),
            "contract_date": get_date("contract signed date") or get_date("contract date"),
            "client_type":  get("client type"),
            "country":      get("country of study") or get("country"),
            "agent":        get("refer source agent") or get("refer agent"),
            "system_type":  get("system type"),
            "app_status":   get("application report status") or get("application status"),
            "visa_date":    get_date("visa received date") or get_date("visa date"),
            "institution":  institution,
            "course_start": get_date("course start date") or get_date("course start"),
            "course_status": get("course status"),
            "counsellor":   counsellor,
            "case_officer": case_officer,
            "notes":        notes,
            "institution_type": inst_type,
            "group_agent":  "StudyLink" if inst_type in (INST_TYPE_MASTER_AGENT, INST_TYPE_GROUP) else "",
            "package_type": package,
        })

    return raw_rows, staff_name, warnings


def _infer_package_from_notes(notes: str) -> str:
    """Infers package code from CRM notes field."""
    n = notes.lower()
    if "premium canada" in n:
        return "Premium Canada (14tr)"
    if "premium" in n:
        return "Premium Package (9tr)"
    if "standard package" in n and "16" in n:
        return "Standard Package (16tr)"
    if "standard package" in n and "9" in n:
        return "Standard Package (9tr5)"
    if "standard plus" in n:
        return "Standard Plus (3tr)"
    if "superior" in n and ("6" in n or "triệu" in n or "trieu" in n):
        return "Superior Package (6tr)"
    if "regular" in n and "9" in n:
        return "Regular (9tr5)"
    if "sds" in n:
        return "SDS (7tr5)"
    return ""  # Unknown — operator must enter
