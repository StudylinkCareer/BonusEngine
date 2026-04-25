# =============================================================================
# notes_parser.py  |  StudyLink Bonus Engine v6.3
# Converts free-text Notes (col 17) from historical báo cáo files into
# structured engine fields.
# =============================================================================

import re
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ParsedNotes:
    service_fee_type: str = "NONE"
    package_type:     str = "NONE"
    handover:         str = "NO"
    handover_from:    str = ""
    addons:           List[str] = field(default_factory=list)
    inst_type_hint:   str = ""
    deferral:         str = "NONE"
    raw:              str = ""


# ── Handover patterns (regex → canonical staff name) ────────────────────────
_HANDOVER_PATTERNS = [
    (r"Hò[aà]\s+bàn\s+giao",              "VŨ Thị Hòa"),
    (r"Hoa\s+bàn\s+giao",                  "VŨ Thị Hòa"),
    (r"\bLA\s+bàn\s+giao",                 "Lê Thị Trường An"),
    (r"Trường\s+An\s+bàn\s+giao",          "Lê Thị Trường An"),
    (r"\bMy\s+bàn\s+giao",                 "Nguyễn Thị Mỹ Ly"),
    (r"Mỹ\s+Ly\s+bàn\s+giao",              "Nguyễn Thị Mỹ Ly"),
    (r"Hạ\s+bàn\s+giao",                   "Thái Thị Huỳnh Anh"),
    (r"Dung\s+bàn\s+giao",                 "Nguyễn Thị Kim Dung"),
    (r"Thành\s+bàn\s+giao",                "Thành"),
    (r"bàn\s+giao",                        ""),
]

# ── Service fee / package patterns (most specific first) ─────────────────────
# Format: (regex_pattern, service_fee_code, package_code)
_SERVICE_PATTERNS = [
    # AP/Aus packages
    (r"Standard\s+Plus\s+3tr",                "AP_STANDARD_PLUS_3TR", "NONE"),
    (r"đặt\s+cọc\s+3tr",                      "AP_STANDARD_PLUS_3TR", "NONE"),
    (r"superior\s+Package\s+8tr|superior\s+8tr|8\s*triệu|8\s*trieu",
                                              "NONE", "superior Package 8tr"),
    (r"Superior\s+Package\s+USA\s+In",        "NONE", "Superior Package USA In-Full (45tr)"),
    (r"Superior\s+Package\s+USA\s+Out",       "NONE", "Superior Package USA Out-Full (68tr)"),
    (r"Standard\s+Package\s+USA\s+Out",       "NONE", "Standard Package USA Out-Full (28tr)"),
    # CONTRACT category — fee at signing, not enrolment package.
    # legacy_adapter clears these for enrolled cases so only tier rate applies.
    (r"Standard\s+Package\s+\(?16tr\)?|standard\s+16tr",
                                              "US_STANDARD_16TR", "NONE"),
    (r"Premium\s+Canada\s+\(?14tr\)?|premium\s+canada",
                                              "CAN_PREMIUM_14TR", "NONE"),
    (r"Standard\s+Master\s+15tr|master\s+15tr",
                                              "CAN_MASTER_15TR", "NONE"),
    (r"Standard\s+regular\s+9tr5|standard\s+9tr5|regular\s+9tr5",
                                              "CAN_REGULAR_9TR5", "NONE"),
    (r"SDS\s+7tr5|sds\s+7tr5|gói\s+SDS\s+7tr5",
                                              "CAN_SDS_7TR5", "NONE"),
    (r"SDS\s+6tr5|sds\s+6tr5",                "CAN_SDS_6TR5", "NONE"),
    (r"Premium\s+Package\s+9tr|premium\s+9tr|gói\s+premium",
                                              "NONE", "Premium Package (9tr)"),
    (r"Superior\s+Package\s+6tr|superior\s+6tr|gói\s+6tr|goi\s+6tr|superior\s+package",
                                              "NONE", "Superior Package (6tr)"),
    (r"Superior\s+package",                   "NONE", "Superior Package (6tr)"),
    # Service fees (these REPLACE tier rate)
    (r"Visa\s+only|visa\s+service",           "VISA_ONLY", "NONE"),
    (r"Visa\s+485|graduate\s+visa\s+485|485",
                                              "VISA_485", "NONE"),
    (r"Visa\s+renewal|visa\s+extension|gia\s+hạn\s+visa",
                                              "VISA_RENEWAL", "NONE"),
    (r"Study\s+permit\s+renewal|gia\s+hạn\s+study",
                                              "STUDY_PERMIT_RENEWAL", "NONE"),
    (r"\bCAQ\b",                              "CAQ", "NONE"),
    (r"Guardian\s+granted",                   "GUARDIAN_GRANTED", "NONE"),
    (r"Guardian\s+refused",                   "GUARDIAN_REFUSED", "NONE"),
    (r"Dependant\s+granted|dependent\s+granted",
                                              "DEPENDANT_GRANTED", "NONE"),
    (r"Dependant\s+refused|dependent\s+refused",
                                              "DEPENDANT_REFUSED", "NONE"),
    (r"Cancelled\s+full\s+service|phí\s+đã\s+thu",
                                              "CANCELLED_FULL_SERVICE", "NONE"),
    (r"Difficult\s+case|out\s+system\s+full\s+aus",
                                              "DIFFICULT_CASE_20TR", "NONE"),
    (r"Out\s+system\s+full|out\s+system\s+30tr",
                                              "OUT_SYSTEM_30TR", "NONE"),
    (r"Out\s+system\s+14tr",                  "OUT_SYSTEM_14TR", "NONE"),
    (r"Extra\s+school|thêm\s+trường",         "EXTRA_SCHOOL", "NONE"),
    (r"Visitor|exchange",                     "VISITOR_EXCHANGE", "NONE"),
]

# ── Guardian add-on detection (col 17 OR col 19) ─────────────────────────────
_GUARDIAN_AU_PATTERN = re.compile(
    r"[Gg]iám\s+hộ\s+từ\s+[ÚUu]c|"
    r"[Gg]uardian\s+(?:from\s+)?(?:Aus|AU)|"
    r"Thu\s+phí\s+(?:dv|dịch\s+vụ).*100\s*USD.*(?:guardian|giám\s+hộ)|"
    r"(?:guardian|giám\s+hộ).*100\s*USD"
)

# ── No-commission / deferral ─────────────────────────────────────────────────
_NO_COMM_PATTERN = re.compile(r"ko\s+có\s+comm|không\s+có\s+comm|no\s+commission", re.I)


def parse_notes(notes_text: str) -> ParsedNotes:
    result = ParsedNotes(raw=notes_text or "")
    if not notes_text or notes_text.strip().lower() in ("nan", "none", ""):
        return result

    text = notes_text.strip()

    # Handover detection
    for pattern, staff_name in _HANDOVER_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            result.handover = "YES"
            result.handover_from = staff_name
            text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
            break

    # Guardian add-on
    if _GUARDIAN_AU_PATTERN.search(text):
        result.addons.append("GUARDIAN_AU_ADDON")

    # No-commission
    if _NO_COMM_PATTERN.search(text):
        result.deferral = "NO_SERVICE"
        return result

    # Service fee / package
    for pattern, svc_code, pkg_code in _SERVICE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            if svc_code != "NONE":
                result.service_fee_type = svc_code
            if pkg_code != "NONE":
                result.package_type = pkg_code
            break

    # Institution type hint from notes (master agent names)
    if re.search(r"Can-Achieve|Adventus|ApplyBoard|Apply\s*Board", text, re.I):
        result.inst_type_hint = "MASTER_AGENT"

    return result


def infer_institution_type(agent_col: str, institution_col: str,
                           system_type_col: str) -> str:
    """
    Infer InstitutionType from CRM data.
    PARTNER (* in name) takes precedence over MASTER_AGENT name detection,
    because * marks a partner case where Can-Achieve/Adventus is just the platform name.
    ** = GROUP. Vietnam programs → RMIT_VN / BUV_VN / OTHER_VN.
    """
    inst = institution_col or ""
    sys  = (system_type_col or "").lower()
    inst_lower = inst.lower()

    # Partner detection FIRST — * flag means partner case, return DIRECT.
    # _is_partner_case in calc.py applies the 400k partner rate.
    if "**" in inst:
        return "GROUP"
    if "*" in inst:
        return "DIRECT"

    # Vietnam domestic (only after partner check — Vietnam files don't have *)
    if "rmit" in inst_lower:
        return "RMIT_VN"
    if "buv" in inst_lower or "british university" in inst_lower:
        return "BUV_VN"

    # Master agent names (only when no * flag present)
    master_agent_names = ["can-achieve", "canapply", "adventus", "applyboard",
                          "apply board", "gelts", "edugo", "educo"]
    for ma in master_agent_names:
        if ma in inst_lower:
            return "MASTER_AGENT"

    # System type "Ngoài" = OUT_OF_SYSTEM
    if "ngoài" in sys or "ngoai" in sys:
        return "OUT_OF_SYSTEM"

    return "DIRECT"


def infer_office(agent: str, counsellor: str, case_officer: str) -> str:
    """Infer office from Hà Nội / Đà Nẵng / HCM signals in agent or staff names."""
    text = " ".join([agent or "", counsellor or "", case_officer or ""]).lower()
    if any(k in text for k in ("hà nội", "ha noi", "hn", "vp hn")):
        return "HN"
    if any(k in text for k in ("đà nẵng", "da nang", "dn", "vp đn", "vp dn")):
        return "DN"
    return "HCM"
