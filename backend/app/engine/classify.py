# =============================================================================
# classify.py  |  StudyLink Bonus Engine v1.0
# Auto-classifies CaseRecords from CRM reports.
# =============================================================================

from typing import Dict, List, Optional
from .constants import *
from .config import BonusConfig
from .models import CaseRecord


# ── Keyword rules ─────────────────────────────────────────────────────────────

_SERVICE_FEE_RULES = [
    # Must be checked before generic visa rules
    (["gia hạn visa", "gia han visa", "student visa renewal",
      "visa renewal", "visa extension"],              "VISA_RENEWAL"),
    (["visa renewal support", "bổ sung hồ sơ visa",
      "bo sung ho so visa"],                          "VISA_RENEWAL_SUPPORT"),
    (["visa 485", "graduate visa", "485",
      "thị thực tạm trú"],                            "VISA_485"),
    (["visa only", "visa service", "first visa"],     "VISA_ONLY"),
    (["guardian au addon", "guardian au"],            "GUARDIAN_AU_ADDON"),
    (["guardian granted"],                            "GUARDIAN_GRANTED"),
    (["guardian refused"],                            "GUARDIAN_REFUSED"),
    (["guardian", "giám hộ", "giam ho"],              "GUARDIAN_VISA"),
    (["dependant granted", "dependent granted"],      "DEPENDANT_GRANTED"),
    (["dependant refused", "dependent refused"],      "DEPENDANT_REFUSED"),
    (["study permit renewal"],                        "STUDY_PERMIT_RENEWAL"),
    (["caq"],                                         "CAQ"),
    (["extra school", "them truong"],                 "EXTRA_SCHOOL"),
    (["visitor", "exchange"],                         "VISITOR_EXCHANGE"),
    (["cancelled full service", "phi da thu",
      "ko hoàn", "ko hoan"],                          "CANCELLED_FULL_SERVICE"),
    (["difficult case", "out system full"],           "DIFFICULT_CASE"),
]

_PACKAGE_RULES = [
    # USA
    (["superior usa in", "45tr"],          "Superior Package USA In-Full (45tr)"),
    (["superior usa out", "68tr"],         "Superior Package USA Out-Full (68tr)"),
    (["standard out", "28tr"],             "Standard Package USA Out-Full (28tr)"),
    (["standard", "16tr"],                 "Standard Package (16tr)"),
    # Canada
    (["premium canada", "14tr"],           "Premium Canada (14tr)"),
    (["standard regular", "9tr5"],         "Standard Package (9tr5)"),
    (["sds", "7tr5"],                      "SDS (7tr5)"),
    # AP
    (["premium"],                          "Premium Package (9tr)"),
    (["standard plus", "3tr"],             "Standard Plus (3tr)"),
    # Superior variants — 8tr before 6tr to avoid false match
    (["superior", "8tr", "8 triệu",
      "8 trieu"],                          "superior Package 8tr"),
    (["superior", "6tr", "6 triệu",
      "6 trieu", "gói 6", "goi 6"],        "Superior Package (6tr)"),
    (["superior"],                         "Superior Package (6tr)"),
]

def _match(text: str, rules: list) -> Optional[str]:
    t = text.lower()
    for keywords, result in rules:
        if all(kw in t for kw in ([keywords] if isinstance(keywords, str) else keywords)):
            return result
        if any(kw in t for kw in ([keywords] if isinstance(keywords, str) else keywords)):
            return result
    return None

def _infer_service_fee(notes: str, client_type_code: str, app_status: str) -> Optional[str]:
    if not notes:
        if client_type_code == CT_VISA_ONLY and "visa granted" in app_status.lower():
            return "VISA_ONLY"
        return None
    # Check visa renewal before visa only (more specific)
    return _match(notes, _SERVICE_FEE_RULES)

def _infer_package(notes: str) -> Optional[str]:
    if not notes:
        return None
    # Multi-keyword rules for packages need special handling
    n = notes.lower()
    # USA
    if "superior" in n and ("45tr" in n or "usa in" in n): return "Superior Package USA In-Full (45tr)"
    if "superior" in n and ("68tr" in n or "usa out" in n): return "Superior Package USA Out-Full (68tr)"
    if ("standard" in n or "goi 3 my" in n) and "28tr" in n: return "Standard Package USA Out-Full (28tr)"
    if "16tr" in n or "goi 1 my" in n or "standard package usa" in n: return "Standard Package (16tr)"
    # Canada
    if "premium canada" in n or "14tr" in n: return "Premium Canada (14tr)"
    if "9tr5" in n or "standard regular" in n: return "Standard Package (9tr5)"
    if "sds" in n or "7tr5" in n: return "SDS (7tr5)"
    # AP — check 8tr before 6tr
    if "premium" in n and "canada" not in n: return "Premium Package (9tr)"
    if "standard plus" in n or "3tr" in n: return "Standard Plus (3tr)"
    if "superior" in n and ("8tr" in n or "8 triệu" in n or "8 trieu" in n):
        return "superior Package 8tr"
    if "superior" in n: return "Superior Package (6tr)"
    return None

def _infer_office(agent: str) -> str:
    a = (agent or "").lower()
    if "hà nội" in a or "ha noi" in a or " hn" in a:
        return OFFICE_HN
    if "đà nẵng" in a or "da nang" in a or " dn" in a or " đn" in a:
        return OFFICE_DN
    return OFFICE_HCM

def _is_handover(notes: str) -> bool:
    n = (notes or "").lower()
    return "bàn giao" in n or "ban giao" in n


def classify_cases(
    cases:              List[CaseRecord],
    cfg:                BonusConfig,
    staff_name:         str,
    year:               int,
    month:              int,
    operator_overrides: Dict[str, dict] = None,
) -> List[CaseRecord]:
    """
    Auto-classifies all cases. Operator overrides take precedence over inference.
    """
    overrides = operator_overrides or {}
    canonical_staff = cfg.resolve_staff_name(staff_name)

    for c in cases:
        if c.is_duplicate or c.row_type == ROW_ADDON:
            continue
        ov = overrides.get(c.contract_id, {})

        # Office
        c.office = ov.get("office", _infer_office(c.agent))

        # Institution type override
        if "inst_type" in ov:
            c.institution_type = ov["inst_type"]

        # Group agent name
        if c.institution_type in (INST_MASTER_AGENT, INST_GROUP):
            c.group_agent_name = ov.get("group_agent_name", "StudyLink")

        # Service fee
        if "service_fee_type" in ov:
            c.service_fee_type = ov["service_fee_type"]
        elif c.service_fee_type and c.service_fee_type.upper() not in ("NONE", ""):
            # Apr 2026: v7 input already provided a service_fee_type, don't
            # let note-based inference clobber it (e.g. note "$120 USD renewal"
            # would otherwise override the operator's explicit code).
            pass
        else:
            sf = _infer_service_fee(c.notes, c.client_type_code, c.app_status)
            if sf:
                c.service_fee_type = sf

        # Package
        if "package_type" in ov:
            c.package_type = ov["package_type"]
        elif c.service_fee_type in (SVC_NONE, ""):
            pkg = _infer_package(c.notes)
            if pkg:
                c.package_type = pkg
            elif c.notes:
                c.add_warning(f"Package not inferred from: {c.notes[:60]}")

        # Prior month rate
        if "prior_month_rate" in ov:
            c.prior_month_rate = ov["prior_month_rate"]

        # Incentive
        if "incentive" in ov:
            c.incentive = ov["incentive"]

        # Handover
        if "handover" in ov:
            c.handover = ov["handover"].upper()
        elif _is_handover(c.notes):
            c.handover = "YES"

        if "target_owner" in ov:
            c.target_owner = ov["target_owner"]

        # Targets name — V2 input may already have set this; respect that
        if "targets_name" in ov:
            c.targets_name = ov["targets_name"]
        elif c.targets_name:
            pass  # V2 input already set this value
        else:
            c.targets_name = canonical_staff

        # Deferral — V2 input may already have set this; respect that
        if "deferral" in ov:
            c.deferral = ov["deferral"]
        elif c.deferral and c.deferral.upper() not in (DEFERRAL_NONE, ""):
            pass  # V2 input already set this value
        else:
            c.deferral = DEFERRAL_NONE

        # Cross-office: if case office != staff primary office, mark for HN rate
        if c.office == OFFICE_HN and canonical_staff:
            st = cfg.staff_targets.get(canonical_staff.lower())
            if st and st.office != OFFICE_HN:
                c.add_warning(f"Cross-office: HN case in HCM file — HN rates apply")

    return cases
