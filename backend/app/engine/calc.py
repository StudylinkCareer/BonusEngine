# =============================================================================
# calc.py
# Equivalent of modCalc.bas
# Core bonus calculation engine.
# =============================================================================

from dataclasses import dataclass, field
from typing import List, Optional
import math

from .constants import (
    SCHEME_CO_SUB, SCHEME_HCM_DIRECT, SCHEME_HN_DIRECT,
    TIER_UNDER, TIER_MEET, TIER_OVER, TIER_MEET_HIGH, TIER_MEET_LOW,
    INST_TYPE_MASTER_AGENT, INST_TYPE_GROUP, INST_TYPE_OUT_OF_SYS,
    INST_TYPE_RMIT_VN, INST_TYPE_BUV_VN, INST_TYPE_OTHER_VN,
    CLIENT_TYPE_SUMMER_STUDY, CLIENT_TYPE_VIETNAM_DOMESTIC,
    DEFERRAL_FEE_TRANSFERRED, DEFERRAL_DEFERRED,
    DEFERRAL_FEE_WAIVED, DEFERRAL_NO_SERVICE,
    PRESALES_NONE, ROW_TYPE_ADDON, ROW_TYPE_BASE,
    INCENTIVE_THRESHOLD, OFFICE_HCM, OFFICE_HN, OFFICE_DN,
)
from .config import BonusConfig, StaffConfig, StatusRule


# =============================================================================
# CaseRecord — equivalent to modInput.CaseRecord Type
# =============================================================================

@dataclass
class CaseRecord:
    # CRM core data (cols 1-16)
    original_no: str = ""
    student_name: str = ""
    student_id: str = ""
    contract_id: str = ""
    contract_date: Optional[object] = None
    client_type: str = ""
    country: str = ""
    agent: str = ""
    system_type: str = ""
    app_status: str = ""
    visa_date: Optional[object] = None
    institution: str = ""
    course_start: Optional[object] = None
    course_status: str = ""
    counsellor: str = ""
    case_officer: str = ""

    # Operator fields (cols 17-33)
    presales_agent: str = PRESALES_NONE
    incentive: int = 0
    notes: str = ""
    service_fee_type: str = "NONE"
    deferral: str = "NONE"
    package_type: str = "NONE"
    office_override: str = OFFICE_HCM
    handover: str = "NO"
    target_owner: str = ""
    case_transition: str = "NO"
    prior_month_rate: int = 0
    institution_type: str = "DIRECT"
    group_agent_name: str = ""
    targets_name: str = ""
    row_type: str = ROW_TYPE_BASE
    addon_code: str = ""
    addon_count: int = 0

    # Derived fields (set during parsing)
    client_type_code: str = ""
    country_code: str = ""
    office_source: str = OFFICE_HCM
    exclude_from_calc: bool = False
    warn_msg: str = ""

    # Output fields (set during calculation)
    bonus_enrolled: int = 0
    note_enrolled: str = ""
    note_enrolled2: str = ""
    bonus_priority: int = 0
    note_priority: str = ""
    note_priority2: str = ""
    prior_advances_paid: int = 0
    net_payable: int = 0
    stored_base_rate: int = 0
    is_recovery_item: bool = False
    advance_note: str = ""


# =============================================================================
# Tier determination — with target=0 fix
# =============================================================================

def determine_tier(enrolled_count: int, target: int, inherited_tier: str = "") -> str:
    """
    Determines bonus tier from enrolled count and target.

    TARGET = 0 FIX (Bug identified Jan 2025 — Gia Man):
    When target = 0, ANY enrolment exceeds it → OVER.
    Previous VBA code defaulted to UNDER when target = 0,
    which was wrong. Policy is clear: exceeding zero = OVER.

    Cross-office cases pass inherited_tier from the primary office section.
    """
    if target == 0:
        if inherited_tier:
            return inherited_tier          # Cross-office: inherit from primary
        if enrolled_count > 0:
            return TIER_OVER               # Any enrolment exceeds zero target
        return TIER_UNDER                  # No enrolments, zero target

    if enrolled_count > target:
        return TIER_OVER
    elif enrolled_count == target:
        return TIER_MEET                   # Resolved to MEET_HIGH/LOW later
    else:
        return TIER_UNDER


def resolve_meet_tier(tier: str, incentive: int) -> str:
    """Resolves TIER_MEET to MEET_HIGH or MEET_LOW based on incentive."""
    if tier == TIER_MEET:
        if incentive >= INCENTIVE_THRESHOLD:
            return TIER_MEET_HIGH
        return TIER_MEET_LOW
    return tier


# =============================================================================
# Deferral check
# =============================================================================

def is_deferral_zero(deferral: str) -> bool:
    d = deferral.strip().upper()
    return d in (
        DEFERRAL_FEE_TRANSFERRED,
        DEFERRAL_DEFERRED,
        DEFERRAL_FEE_WAIVED,
        DEFERRAL_NO_SERVICE,
    )


# =============================================================================
# Special fixed rate detection
# =============================================================================

def is_special_fixed_rate(cs: CaseRecord, cfg: BonusConfig) -> bool:
    """Returns True if this case uses a fixed rate rather than tier-based rate."""
    if cfg.is_vietnam_country(cs.country_code):
        return True
    if cs.client_type_code == CLIENT_TYPE_SUMMER_STUDY:
        return True
    return False


def get_special_fixed_rate(cs: CaseRecord, scheme: str, cfg: BonusConfig) -> int:
    """Returns the fixed rate for Vietnam domestic or summer study cases."""
    if cfg.is_vietnam_country(cs.country_code):
        is_rmit = cs.institution_type == INST_TYPE_RMIT_VN
        is_buv  = cs.institution_type == INST_TYPE_BUV_VN
        if scheme == SCHEME_HN_DIRECT:
            if is_rmit:
                return cfg.rate_hn_rmit_vn
            if is_buv:
                return cfg.rate_co_sub_buv_vn
            return cfg.rate_hn_other_vn
        elif scheme == SCHEME_CO_SUB:
            if is_rmit:
                return cfg.rate_co_sub_vn_enrol
            if is_buv:
                return cfg.rate_co_sub_buv_vn
            return cfg.rate_co_sub_other_vn
        else:  # HCM Direct
            if is_rmit:
                return cfg.rate_rmit_vn
            if is_buv:
                return cfg.rate_co_sub_buv_vn
            return cfg.rate_other_vn

    if cs.client_type_code == CLIENT_TYPE_SUMMER_STUDY:
        if scheme == SCHEME_CO_SUB:
            return cfg.rate_co_sub_summer
        elif scheme == SCHEME_HN_DIRECT:
            return cfg.rate_hn_summer
        return cfg.rate_summer

    return cfg.rate_other_vn  # Fallback


def get_special_fixed_rate_note(cs: CaseRecord, scheme: str) -> str:
    scheme_label = {
        SCHEME_HN_DIRECT: " (HN/DN rate)",
        SCHEME_CO_SUB:    " (CO Sub rate)",
    }.get(scheme, " (HCM rate)")

    if cs.institution_type == INST_TYPE_RMIT_VN:
        return f"Nhan bonus muc RMIT VN{scheme_label}"
    elif cs.institution_type == INST_TYPE_BUV_VN:
        return f"Nhan bonus muc BUV VN{scheme_label}"
    elif cs.client_type_code == CLIENT_TYPE_SUMMER_STUDY:
        return f"Summer study - fixed rate{scheme_label}"
    return f"Vietnam domestic program - fixed rate{scheme_label}"


# =============================================================================
# KPI weight for tier counting
# =============================================================================

def count_enrolled_for_tier(
    cases: List[CaseRecord],
    cfg_staff: StaffConfig,
    cfg: BonusConfig,
) -> int:
    """
    Returns weighted enrolment count for tier determination.
    Mirrors CountEnrolledForTier in modCalc.bas.
    """
    weighted = 0.0
    for cs in cases:
        if cs.row_type == ROW_TYPE_ADDON:
            continue
        if cs.exclude_from_calc:
            continue
        if is_deferral_zero(cs.deferral):
            continue

        sr = cfg.get_status_rule(cs.app_status)
        if sr.is_carry_over:
            continue
        if sr.fees_paid_non_enrolled:
            if cs.institution_type in (INST_TYPE_MASTER_AGENT, INST_TYPE_GROUP, INST_TYPE_OUT_OF_SYS):
                continue
        if sr.is_zero_bonus:
            continue
        if not sr.counts_as_enrolled:
            continue

        w = cfg.get_kpi_weight(cs.client_type_code, cfg_staff.scheme, cs.institution_type)
        weighted += w

    return int(weighted)  # Round down


# =============================================================================
# Service fee bonus lookup
# =============================================================================

def get_service_fee_bonus(
    service_code: str,
    is_counsellor: bool,
    cfg: BonusConfig,
    category: str = "",
) -> tuple[int, str]:
    """Returns (bonus_amount, note). Amount is 0 if not found."""
    if not service_code or service_code.upper() == "NONE":
        return 0, ""
    rule = cfg.get_service_fee(service_code, category)
    if not rule:
        return 0, f"Service code '{service_code}' not found in 09_SERVICE_FEE_RATES"
    if not rule.active:
        return 0, f"Service code '{service_code}' is inactive"
    amount = rule.counsellor_bonus if is_counsellor else rule.co_bonus
    note = rule.description or service_code
    return amount, note


# =============================================================================
# Package bonus
# =============================================================================

def get_package_bonus(cs: CaseRecord, is_counsellor: bool, cfg: BonusConfig) -> tuple[int, str]:
    """Returns (package_bonus, note)."""
    sr = cfg.get_status_rule(cs.app_status)
    if sr.is_zero_bonus:
        return 0, ""

    guardian_bonus = 0
    guardian_note  = ""
    if cs.service_fee_type.strip().upper() == "GUARDIAN_AU_ADDON":
        amt, note = get_service_fee_bonus("GUARDIAN_AU_ADDON", is_counsellor, cfg, "CONTRACT")
        if amt > 0:
            guardian_bonus = amt
            guardian_note  = f"Guardian AU add-on: {amt:,.0f}"

    pkg_code = cs.package_type.strip()
    if pkg_code.upper() in ("NONE", ""):
        return guardian_bonus, guardian_note

    pkg_bonus, pkg_note = get_service_fee_bonus(pkg_code, is_counsellor, cfg, "PACKAGE")

    notes = " | ".join(n for n in [guardian_note, pkg_note] if n)
    return guardian_bonus + pkg_bonus, notes


# =============================================================================
# Priority institution bonus
# =============================================================================

def get_priority_match(institution: str, cfg: BonusConfig) -> Optional[object]:
    """Returns matching PriorityInstitution or None."""
    inst_lower = institution.lower()
    for p in cfg.priority_instns:
        if p.name.lower() in inst_lower or inst_lower in p.name.lower():
            return p
    return None


# =============================================================================
# Single case calculation
# =============================================================================

def calculate_single_case(
    cs: CaseRecord,
    cfg_staff: StaffConfig,
    tier: str,
    target: int,
    actual_enrolled: int,
    run_month: int,
    run_year: int,
    cfg: BonusConfig,
):
    """
    Calculates bonus for a single case. Modifies cs in place.
    Mirrors CalculateSingleCase in modCalc.bas.
    All steps follow the same sequence as the VBA.
    """
    cs.bonus_enrolled  = 0
    cs.bonus_priority  = 0
    cs.note_enrolled   = ""
    cs.note_enrolled2  = ""
    cs.note_priority   = ""
    cs.note_priority2  = ""
    cs.stored_base_rate = 0

    # ADDON rows handled separately in Step 9A
    if cs.row_type == ROW_TYPE_ADDON:
        return

    sr = cfg.get_status_rule(cs.app_status)
    is_counsellor = cfg_staff.role.upper() in ("COUNSELLOR", "DIRECT")

    # Cross-office exclusion
    if cs.exclude_from_calc:
        cs.note_enrolled = "EXCLUDED: cross-office case not included in this period."
        return

    # STEP 2.5: Deferral
    if is_deferral_zero(cs.deferral):
        cs.note_enrolled = f"Zero bonus: {cs.deferral} (col 21 deferral)"
        return

    # STEP 2.8: MGMT_EXCEPTION
    if cs.service_fee_type.strip().upper() == "MGMT_EXCEPTION":
        cs.bonus_enrolled   = cs.prior_month_rate
        cs.stored_base_rate = cs.prior_month_rate
        cs.note_enrolled    = f"Management approved exception -- manual override: {cs.prior_month_rate:,.0f}"
        cs.note_enrolled2   = "Col 20 = MGMT_EXCEPTION: amount from col 27 (management approval required)."
        return

    # STEP 2.8: Service fee type
    if cs.service_fee_type and cs.service_fee_type.upper() not in ("NONE", ""):
        sf_bonus, sf_note = get_service_fee_bonus(
            cs.service_fee_type, is_counsellor, cfg, "SERVICE_FEE"
        )
        if sf_bonus > 0:
            cs.bonus_enrolled   = sf_bonus
            cs.stored_base_rate = sf_bonus
            cs.note_enrolled    = sf_note
            return
        if sf_note:
            cs.note_enrolled = f"{sf_note} -> 0"
            return

    # STEP 3: Zero-bonus status
    if sr.is_zero_bonus:
        cs.note_enrolled = f"Status: {cs.app_status} -> 0"
        return

    # STEP 3.5: Fees-paid non-enrolled (GROUP/OOS only, not MASTER_AGENT)
    if sr.fees_paid_non_enrolled:
        if cs.institution_type in (INST_TYPE_GROUP, INST_TYPE_OUT_OF_SYS):
            base_rate = cfg.get_base_rate(cfg_staff.scheme, TIER_UNDER)
            cs.bonus_enrolled   = base_rate
            cs.stored_base_rate = base_rate
            cs.note_enrolled    = f"Fees paid (non-enrolled) -- {cs.app_status}: {base_rate:,.0f}"
            return
        # MASTER_AGENT and DIRECT fall through to zero
        cs.note_enrolled = f"Status: {cs.app_status} -> 0"
        return

    # STEP 4: Carry-over
    if sr.is_carry_over:
        if cs.prior_month_rate <= 0:
            cs.note_enrolled = "CARRY-OVER: prior month rate missing (col 27). Cannot calculate."
            return
        cs.bonus_enrolled   = cs.prior_month_rate
        cs.stored_base_rate = cs.prior_month_rate
        cs.note_enrolled    = f"Carry-over: prior month base rate {cs.prior_month_rate:,.0f}"
        # Fall through to package and priority steps
        _apply_package_and_priority(cs, is_counsellor, cfg, run_month, run_year)
        _apply_advance_offset(cs, sr)
        return

    # STEP 5: CountsAsEnrolled check
    if not sr.counts_as_enrolled:
        cs.note_enrolled = f"Status: {cs.app_status} -> 0"
        return

    # STEP 5 continued: Vietnam domestic/summer cancelled = 0
    if is_special_fixed_rate(cs, cfg) and sr.is_zero_bonus:
        cs.note_enrolled = f"Status: {cs.app_status} -> 0"
        return

    # Resolve MEET tier to MEET_HIGH/LOW
    resolved_tier = resolve_meet_tier(tier, cs.incentive)

    # STEP 6: Partner case
    if cs.agent and cs.agent.upper() != "NONE" and cs.institution_type == "DIRECT":
        # Partner referral — flag but continue at full tier rate
        pass

    # STEP 7A: MASTER_AGENT — tier-based rate
    base_rate  = 0
    is_flat    = cfg.is_flat_country(cs.country_code)
    is_current = sr.is_current_enrolled

    if cs.institution_type == INST_TYPE_MASTER_AGENT:
        base_rate = cfg.get_base_rate(cfg_staff.scheme, resolved_tier)
        cs.stored_base_rate = base_rate
        cs.note_enrolled    = f"MASTER_AGENT referral -- tier rate: {base_rate:,.0f}"
        # Fall through to split percentage block

    # STEP 7B: Flat-rate country and tier base rate
    elif is_flat:
        if is_counsellor:
            base_rate = (cfg.rate_hn_flat_coun
                         if cfg_staff.scheme == SCHEME_HN_DIRECT
                         else cfg.rate_flat_coun)
        else:
            base_rate = (cfg.rate_hn_flat_co
                         if cfg_staff.scheme == SCHEME_HN_DIRECT
                         else cfg.rate_flat_co)
        cs.stored_base_rate = base_rate
        cs.note_enrolled    = f"Flat-rate country (MY/TH/PH) - flat rate: {base_rate:,.0f}"

    # STEP 7B continued: Special fixed rate (Vietnam/Summer)
    elif is_special_fixed_rate(cs, cfg):
        base_rate = get_special_fixed_rate(cs, cfg_staff.scheme, cfg)
        cs.stored_base_rate = base_rate
        cs.note_enrolled    = get_special_fixed_rate_note(cs, cfg_staff.scheme)

    # STEP 7B continued: Standard tier rate
    else:
        if is_counsellor:
            base_rate = cfg.get_base_rate_coun(cfg_staff.scheme, resolved_tier)
        else:
            base_rate = cfg.get_base_rate(cfg_staff.scheme, resolved_tier)
        cs.stored_base_rate = base_rate

    # -- Split percentage based on role and status ----------------------------
    if is_counsellor:
        split_pct = 1.0 if is_current else sr.split_coun_pct
    elif cfg_staff.scheme == SCHEME_CO_SUB:
        split_pct = 0.5 if is_current else sr.split_co_sub_pct
    else:
        split_pct = 0.5 if is_current else sr.split_co_direct_pct

    bonus_enr = int(base_rate * split_pct)
    cs.bonus_enrolled = bonus_enr

    # -- Tier note
    tier_label = {
        TIER_OVER:      f"Over target (all cases) -- {base_rate:,.0f}",
        TIER_MEET_HIGH: f"Meet target (incentive >={INCENTIVE_THRESHOLD:,.0f}) -- {base_rate:,.0f}",
        TIER_MEET_LOW:  f"Meet target (incentive <{INCENTIVE_THRESHOLD:,.0f}) -- {base_rate:,.0f}",
        TIER_MEET:      f"Meet target -- {base_rate:,.0f}",
        TIER_UNDER:     f"Under target -- {base_rate:,.0f}",
    }.get(resolved_tier, resolved_tier)

    if not is_flat and not is_special_fixed_rate(cs, cfg):
        cs.note_enrolled2 = (
            f"Thang {run_month:02d}/{run_year}, "
            f"chi tieu {target} Enrolled. "
            f"Dat {actual_enrolled} Enrolled "
            f"nen nhan bonus muc {tier_label}"
        )

    # STEP 8: Current-enrolled note
    if is_current:
        if is_counsellor:
            cs.note_enrolled = cs.note_enrolled.strip() + " | Nhan 100% bonus vi hs da nhap hoc"
        else:
            cs.note_enrolled = cs.note_enrolled.strip() + " | Nhan 50% bonus vi hs chua co visa va chua dong file"

    # STEP 8A: Pre-sales split (counsellor only)
    if is_counsellor and cs.presales_agent not in (PRESALES_NONE, "", "NONE"):
        cs.bonus_enrolled = bonus_enr // 2
        cs.note_enrolled  = (cs.note_enrolled.strip() +
                             f" | Pre-sales split 50/50 with {cs.presales_agent}")

    # STEP 9: Package bonus
    _apply_package_and_priority(cs, is_counsellor, cfg, run_month, run_year)

    # STEP 10: Advance offset
    _apply_advance_offset(cs, sr)


def _apply_package_and_priority(
    cs: CaseRecord,
    is_counsellor: bool,
    cfg: BonusConfig,
    run_month: int,
    run_year: int,
):
    """Steps 9 and 10 — package bonus and priority institution bonus."""
    # STEP 9: Package
    pkg_bonus, pkg_note = get_package_bonus(cs, is_counsellor, cfg)
    if pkg_bonus > 0:
        cs.bonus_enrolled += pkg_bonus
        if pkg_note:
            cs.note_enrolled = (cs.note_enrolled.strip() + " | " + pkg_note).lstrip(" | ")

    # STEP 10: Priority
    if cs.bonus_enrolled > 0:
        pri = get_priority_match(cs.institution, cfg)
        if pri:
            af = 1.0 if pri.achieved_ytd >= pri.annual_target else 0.5
            af_pct = int(af * 100)
            cs.bonus_priority = int(cs.bonus_enrolled * pri.bonus_pct * af)
            cs.note_priority  = f"Them {pri.bonus_pct*100:.0f}% bonus cho Truong {pri.name}"
            cs.note_priority2 = (
                f"Chi tieu cua Truong {pri.name} la {pri.annual_target}, "
                f"Dat {pri.achieved_ytd} nen nhan {af_pct}% bonus Priority."
            )


def _apply_advance_offset(cs: CaseRecord, sr: StatusRule):
    """Applies prior advance offset and sets net_payable."""
    if cs.prior_advances_paid > 0 and not sr.is_current_enrolled:
        gross = cs.bonus_enrolled
        cs.net_payable    = cs.bonus_enrolled - cs.prior_advances_paid
        cs.bonus_enrolled = cs.net_payable
        if cs.net_payable < 0:
            cs.is_recovery_item = True
            cs.advance_note = (
                f"RECOVERY: Gross bonus {gross:,.0f} "
                f"- Prior advances {cs.prior_advances_paid:,.0f} "
                f"= NET {cs.net_payable:,.0f} (over-paid, recovery required)"
            )
        else:
            cs.advance_note = (
                f"Net payable: {gross:,.0f} "
                f"- {cs.prior_advances_paid:,.0f} (prior advance) "
                f"= {cs.net_payable:,.0f}"
            )
        if cs.advance_note:
            cs.note_enrolled2 = (
                (cs.note_enrolled2 + "\n" if cs.note_enrolled2 else "") +
                cs.advance_note
            )
    elif sr.is_current_enrolled:
        cs.net_payable = cs.bonus_enrolled


# =============================================================================
# Main entry point — calculate all cases for one staff/office/month
# =============================================================================

def calculate_bonuses(
    cases: List[CaseRecord],
    cfg_staff: StaffConfig,
    run_month: int,
    run_year: int,
    cfg: BonusConfig,
    inherited_tier: str = "",
) -> List[CaseRecord]:
    """
    Calculates bonuses for all cases in one office section.
    Mirrors CalculateBonuses in modCalc.bas.

    Returns the same list with bonus fields populated.
    """
    # STEP 1: Determine tier
    enrolled_count = count_enrolled_for_tier(cases, cfg_staff, cfg)
    target = cfg_staff.targets.get(run_month, 0)
    tier = determine_tier(enrolled_count, target, inherited_tier)

    # STEP 2-9: Calculate BASE rows
    for cs in cases:
        if cs.row_type != ROW_TYPE_ADDON:
            calculate_single_case(
                cs, cfg_staff, tier, target,
                enrolled_count, run_month, run_year, cfg
            )

    # STEP 9A: Process ADDON rows
    _process_addon_rows(cases, cfg)

    return cases


def _process_addon_rows(cases: List[CaseRecord], cfg: BonusConfig):
    """
    Processes ADDON rows after all BASE calculations.
    Mirrors Step 9A in CalculateBonuses (modCalc.bas v6.2).
    """
    for addon in cases:
        if addon.row_type != ROW_TYPE_ADDON:
            continue
        if not addon.addon_code or addon.addon_count <= 0:
            continue

        rule = cfg.get_service_fee(addon.addon_code, "ADDON")
        if not rule or rule.co_bonus <= 0:
            addon.note_enrolled = (
                f"ADDON: code '{addon.addon_code}' not found or zero rate "
                f"in 09_SERVICE_FEE_RATES (ADDON category)"
            )
            continue

        unit_rate  = rule.co_bonus
        addon_total = unit_rate * addon.addon_count

        # Add to matching BASE row
        for base in cases:
            if base.row_type != ROW_TYPE_ADDON and base.contract_id == addon.contract_id:
                base.bonus_enrolled += addon_total
                extra = f"Add-on: {addon.addon_code} x{addon.addon_count} = {addon_total:,.0f}"
                base.note_enrolled = (base.note_enrolled.strip() + " | " + extra).lstrip(" | ")
                break

        addon.bonus_enrolled = addon_total
        addon.note_enrolled  = (
            f"Add-on: {addon.addon_code} x{addon.addon_count} "
            f"@ {unit_rate:,.0f} = {addon_total:,.0f}"
        )
