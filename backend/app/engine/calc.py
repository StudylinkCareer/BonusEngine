# =============================================================================
# calc.py  |  StudyLink Bonus Engine v1.0
# Replaces: modCalc.bas
# =============================================================================

from typing import List, Tuple
from .constants import *
from .config import BonusConfig, StatusRule
from .models import CaseRecord


def determine_tier(enrolled: int, target: int, inherited_tier: str = "") -> str:
    """
    TARGET=0 FIX: any enrolment with zero target → OVER.
    Cross-office: pass inherited_tier from primary office section.
    """
    if target == 0:
        if inherited_tier:
            return inherited_tier
        return TIER_OVER if enrolled > 0 else TIER_UNDER
    if enrolled > target:  return TIER_OVER
    if enrolled == target: return TIER_MEET
    return TIER_UNDER


def resolve_meet_tier(incentive: int) -> str:
    return TIER_MEET_HIGH if incentive >= INCENTIVE_THRESHOLD else TIER_MEET_LOW


def count_enrolled_for_tier(cases: List[CaseRecord], scheme: str,
                             cfg: BonusConfig) -> int:
    weighted = 0.0
    for c in cases:
        if c.row_type == ROW_ADDON or c.is_duplicate or c.exclude_from_calc:
            continue
        if c.deferral.upper() in DEFERRAL_ZERO_VALUES:
            continue
        sr = cfg.get_status_rule(c.app_status)
        if sr.is_carry_over or sr.is_zero_bonus or not sr.counts_as_enrolled:
            continue
        if sr.fees_paid_non_enrolled:
            if c.institution_type in (INST_MASTER_AGENT, INST_GROUP, INST_OUT_OF_SYS):
                continue
        # Agent-referred 0.7 weight applies to CO_DIRECT cases referred via external agent
        # It does NOT apply to CO_SUB scheme — Truong An's sub-agent partners are her primary
        # referral source, so all CO_SUB enrolled cases count as weight=1.0
        if c.is_agent_referred and c.institution_type == INST_DIRECT and scheme != SCHEME_CO_SUB:
            w = 0.7
        else:
            w = cfg.get_kpi_weight(c.client_type_code, c.institution_type, scheme)
        weighted += w
    return int(weighted)


def _get_rates(cfg: BonusConfig, scheme: str) -> dict:
    return cfg.base_rates.get(scheme, cfg.base_rates.get(SCHEME_HCM_DIRECT, {}))


def calc_single_case(c: CaseRecord, tier: str, target: int, enrolled: int,
                     scheme: str, cfg: BonusConfig, month: int, year: int,
                     is_counsellor: bool = False) -> None:
    """Calculates bonus for one case. Modifies c in place."""
    c.bonus_enrolled = 0; c.bonus_priority = 0
    c.note_enrolled = ""; c.note_enrolled2 = ""
    c.note_priority = ""; c.note_priority2 = ""; c.base_rate = 0

    if c.row_type == ROW_ADDON or c.is_duplicate: return
    if c.exclude_from_calc:
        c.note_enrolled = "EXCLUDED: cross-office case not in this period"; return

    sr    = cfg.get_status_rule(c.app_status)
    rates = _get_rates(cfg, scheme)

    # ── STEP 2.5: Deferral ────────────────────────────────────────────────────
    if c.deferral.upper() in DEFERRAL_ZERO_VALUES:
        c.note_enrolled = f"Zero bonus: {c.deferral}"; return

    # ── STEP 2.8a: MGMT_EXCEPTION ─────────────────────────────────────────────
    if c.service_fee_type.upper() == MGMT_EXCEPTION:
        c.bonus_enrolled = c.prior_month_rate
        c.base_rate      = c.prior_month_rate
        c.note_enrolled  = f"Management override: {c.prior_month_rate:,.0f}"; return

    # ── STEP 2.8b: Service fee (exits — no tier stacking) ─────────────────────
    if c.service_fee_type and c.service_fee_type.upper() not in (SVC_NONE, ""):
        sf = (cfg.get_service_fee(c.service_fee_type, SVC_SERVICE_FEE) or
              cfg.get_service_fee(c.service_fee_type, SVC_CONTRACT))
        if sf:
            amount = sf.coun_bonus if is_counsellor else sf.co_bonus
            # Apply 50% split if this is a handover case (partial service)
            if c.handover.upper() == "YES":
                amount = amount // 2
                c.note_enrolled = f"{c.service_fee_type}: {sf.co_bonus if not is_counsellor else sf.coun_bonus:,.0f} × 50% (handover) = {amount:,.0f}"
            else:
                c.note_enrolled = f"{c.service_fee_type}: {amount:,.0f}"
            c.bonus_enrolled = amount
            c.base_rate      = amount
            # CONTRACT category can stack package
            if sf.category == SVC_CONTRACT:
                _apply_package(c, is_counsellor, cfg, sr)
            return
        else:
            c.note_enrolled = f"Service fee '{c.service_fee_type}' not found → 0"; return

    # ── STEP 3: Zero-bonus status ──────────────────────────────────────────────
    if sr.is_zero_bonus:
        c.note_enrolled = f"Status: {c.app_status} → 0"; return

    # ── STEP 3.5: Fees-paid non-enrolled ─────────────────────────────────────
    if sr.fees_paid_non_enrolled:
        if c.institution_type in (INST_GROUP, INST_OUT_OF_SYS):
            r = rates.get("out_sys_co", 400000)
            c.bonus_enrolled = r; c.base_rate = r
            c.note_enrolled  = f"Fees paid ({c.institution_type}): {r:,.0f}"; return
        # DIRECT and MASTER_AGENT: 0
        c.note_enrolled = f"{c.app_status} → 0 (fees paid, direct/MA)"; return

    # ── STEP 4: Carry-over ────────────────────────────────────────────────────
    if sr.is_carry_over:
        if c.prior_month_rate <= 0 and scheme == SCHEME_CO_SUB:
            # Auto-derive: for CO_SUB, prior rate = tier rate from enrolled month
            resolved_prior = tier if tier != TIER_MEET else resolve_meet_tier(c.incentive)
            c.prior_month_rate = rates.get(resolved_prior, rates.get(TIER_UNDER, 700_000))
        if c.prior_month_rate <= 0:
            c.note_enrolled = "CARRY-OVER: prior month rate missing (col 27)"; return
        c.base_rate = c.prior_month_rate
        # Apply split percentage to prior rate (50% for CO_SUB carry-overs)
        split = sr.co_sub_pct if scheme == SCHEME_CO_SUB else sr.co_direct_pct
        c.bonus_enrolled = int(c.prior_month_rate * split) if split > 0 else c.prior_month_rate
        c.note_enrolled  = (f"Carry-over: {c.prior_month_rate:,.0f} × "
                            f"{int(split*100)}% = {c.bonus_enrolled:,.0f}")
        _apply_package(c, is_counsellor, cfg, sr)
        _apply_advance_offset(c, sr); return

    # ── STEP 5: CountsAsEnrolled ──────────────────────────────────────────────
    # IMPORTANT: is_current_enrolled cases have counts_as_enrolled=False in the
    # status table (they count as 50% KPI weight, not a full enrolment), but they
    # DO earn a bonus (50% of base rate + 50% of package). Must not exit here.
    if not sr.counts_as_enrolled and not sr.is_current_enrolled:
        c.note_enrolled = f"Status: {c.app_status} → 0"; return

    # ── STEP 7: Base rate ─────────────────────────────────────────────────────
    resolved_tier = tier if tier != TIER_MEET else resolve_meet_tier(c.incentive)

    if c.is_flat_country:
        base = rates.get("out_sys_co", 500000)
        c.note_enrolled = f"Flat-rate country: {base:,.0f}"
    elif c.is_vietnam:
        # CO_SUB has different VN rates than CO Direct
        if scheme == SCHEME_CO_SUB:
            if c.institution_type in (INST_RMIT_VN, INST_BUV_VN):
                # CO_SUB RMIT VN rate = 600k (row 24 section B)
                base = rates.get("rmit_vn", 600_000)
                c.note_enrolled = f"RMIT/BUV VN (CO_SUB): {base:,.0f}"
            else:
                # CO_SUB Other VN / QTS etc = 600k per manual evidence
                base = rates.get("rmit_vn", 600_000)   # same rate confirmed in manual
                c.note_enrolled = f"Vietnam domestic (CO_SUB): {base:,.0f}"
        else:
            if c.institution_type == INST_RMIT_VN:
                base = 1_000_000; c.note_enrolled = f"RMIT VN: {base:,.0f}"
            elif c.institution_type == INST_BUV_VN:
                base = 600_000;   c.note_enrolled = f"BUV VN: {base:,.0f}"
            else:
                base = 500_000;   c.note_enrolled = f"Vietnam domestic: {base:,.0f}"
    elif c.institution_type == INST_MASTER_AGENT:
        rate_key = f"coun_{resolved_tier}" if is_counsellor else resolved_tier
        base = rates.get(rate_key, rates.get(resolved_tier, rates.get(TIER_UNDER, 800_000)))
        c.note_enrolled = f"MASTER_AGENT tier {resolved_tier}: {base:,.0f}"
    else:
        rate_key = f"coun_{resolved_tier}" if is_counsellor else resolved_tier
        base = rates.get(rate_key, rates.get(resolved_tier, rates.get(TIER_UNDER, 800_000)))
        tier_desc = {
            TIER_OVER:      f"Over target — {base:,.0f}",
            TIER_MEET_HIGH: f"Meet target (incentive ≥5M) — {base:,.0f}",
            TIER_MEET_LOW:  f"Meet target (incentive <5M) — {base:,.0f}",
            TIER_UNDER:     f"Under target — {base:,.0f}",
        }.get(resolved_tier, f"{resolved_tier}: {base:,.0f}")
        c.note_enrolled2 = (
            f"Thang {month:02d}/{year}, chi tieu {target} Enrolled. "
            f"Dat {enrolled} Enrolled nen nhan bonus muc {tier_desc}"
        )

    c.base_rate = base

    # ── STEP 8: Split percentage ──────────────────────────────────────────────
    if sr.is_current_enrolled:
        split = 1.0 if is_counsellor else 0.5
        sfx = " | 100% da nhap hoc" if is_counsellor else " | 50% chua co visa"
        c.note_enrolled = (c.note_enrolled + sfx).strip(" | ")
    elif is_counsellor:
        split = sr.coun_pct
    elif scheme == SCHEME_CO_SUB:
        split = sr.co_sub_pct
    else:
        split = sr.co_direct_pct

    c.bonus_enrolled = int(base * split)

    # ── STEP 8A: Pre-sales split ──────────────────────────────────────────────
    if is_counsellor and c.presales_agent not in (PRESALES_NONE, "", "NONE"):
        c.bonus_enrolled = c.bonus_enrolled // 2
        c.note_enrolled  = (c.note_enrolled +
                            f" | Pre-sales 50/50 with {c.presales_agent}").strip(" | ")

    # ── STEP 9: Package + priority ────────────────────────────────────────────
    if c.contract_id in ('SLC-13414','SLC-13348','SLC-13588'):
        print(f"  DEBUG {c.contract_id}: before_package={c.bonus_enrolled:,}")
    _apply_package(c, is_counsellor, cfg, sr)
    if c.contract_id in ('SLC-13414','SLC-13348','SLC-13588'):
        print(f"  DEBUG {c.contract_id}: after_package={c.bonus_enrolled:,} pkg={c.package_type}")
    _apply_priority(c, cfg)
    if c.contract_id in ('SLC-13414','SLC-13348','SLC-13588'):
        print(f"  DEBUG {c.contract_id}: after_priority={c.bonus_enrolled:,}")
    _apply_advance_offset(c, sr)


def _apply_package(c: CaseRecord, is_counsellor: bool,
                   cfg: BonusConfig, sr: StatusRule) -> None:
    """Applies package bonus. For current-enrolled, applies 50% split."""
    if c.package_type and c.package_type.upper() not in (PKG_NONE, ""):
        pf = cfg.get_service_fee(c.package_type, SVC_PACKAGE)
        if pf:
            amt = pf.coun_bonus if is_counsellor else pf.co_bonus
            if amt > 0:
                # Current-enrolled: package bonus also split 50%
                if sr.is_current_enrolled:
                    amt = amt // 2
                c.bonus_enrolled += amt
                c.note_enrolled = (
                    c.note_enrolled + f" | Package {c.package_type}: +{amt:,.0f}"
                ).strip(" | ")


def _apply_priority(c: CaseRecord, cfg: BonusConfig) -> None:
    if c.bonus_enrolled <= 0: return
    inst_lower = c.institution.lower()
    for p in cfg.priority_instns:
        if p.name.lower() in inst_lower or inst_lower in p.name.lower():
            af     = 1.0 if p.achieved_ytd >= p.annual_target else 0.5
            af_pct = int(af * 100)
            c.bonus_priority = int(c.bonus_enrolled * p.bonus_pct * af)
            c.note_priority  = f"Them {p.bonus_pct*100:.0f}% bonus cho {p.name}"
            c.note_priority2 = (
                f"Chi tieu {p.annual_target}, Dat {p.achieved_ytd} → {af_pct}%"
            )
            break


def _apply_advance_offset(c: CaseRecord, sr: StatusRule) -> None:
    if c.prior_advances > 0 and not sr.is_current_enrolled:
        gross = c.bonus_enrolled
        c.net_payable    = c.bonus_enrolled - c.prior_advances
        c.bonus_enrolled = c.net_payable
        if c.net_payable < 0:
            c.is_recovery    = True
            c.note_enrolled2 = (
                f"RECOVERY: Gross {gross:,.0f} - Advance {c.prior_advances:,.0f} "
                f"= NET {c.net_payable:,.0f}"
            )
    elif sr.is_current_enrolled:
        c.net_payable = c.bonus_enrolled


def _process_addon_rows(cases: List[CaseRecord], cfg: BonusConfig) -> None:
    base_map = {c.contract_id: c for c in cases if c.row_type == ROW_BASE}
    for addon in cases:
        if addon.row_type != ROW_ADDON: continue
        if not addon.addon_code or addon.addon_count <= 0: continue
        rule = cfg.get_service_fee(addon.addon_code, SVC_ADDON)
        if not rule:
            addon.note_enrolled = f"ADDON '{addon.addon_code}' not found"; continue
        unit = rule.co_bonus
        total = unit * addon.addon_count
        addon.bonus_enrolled = total
        addon.note_enrolled  = f"Add-on: {addon.addon_code} × {addon.addon_count} @ {unit:,.0f} = {total:,.0f}"
        base = base_map.get(addon.contract_id)
        if base:
            base.bonus_enrolled += total
            base.note_enrolled   = (base.note_enrolled + f" | ADDON +{total:,.0f}").strip(" | ")


def calculate_bonuses(cases: List[CaseRecord], staff_name: str,
                      year: int, month: int, cfg: BonusConfig,
                      is_counsellor: bool = False,
                      inherited_tier: str = "",
                      office: str = OFFICE_HCM,
                      enrolled_override: int = -1,
                      ) -> Tuple[List[CaseRecord], str, int, int]:
    """
    Main entry point. Calculates bonuses for all cases.
    Handles cross-office cases by applying HN/DN rates where needed.

    enrolled_override: when >= 0, overrides the counted enrolled total.
    Use when cross-office enrolments from other branch reports contribute
    to this staff member's tier (e.g. Aug 2025 HCM+DN combined = 2).
    """
    target, scheme = cfg.get_staff_target(staff_name, year, month)
    enrolled_count  = count_enrolled_for_tier(cases, scheme, cfg)
    if enrolled_override >= 0:
        enrolled_count = enrolled_override
    tier            = determine_tier(enrolled_count, target, inherited_tier)

    for c in cases:
        if c.row_type == ROW_ADDON: continue
        # Cross-office: HN/DN office uses HN rate table — BUT only for CO_DIRECT schemes.
        # CO_SUB scheme is fixed regardless of sub-agent partner location.
        case_scheme = (SCHEME_HN_DIRECT
                       if c.office in (OFFICE_HN, OFFICE_DN)
                       and scheme not in (SCHEME_HN_DIRECT, SCHEME_CO_SUB)
                       else scheme)
        calc_single_case(c, tier, target, enrolled_count,
                         case_scheme, cfg, month, year, is_counsellor)

    _process_addon_rows(cases, cfg)

    tier_display = resolve_meet_tier(0) if tier == TIER_MEET else tier
    return cases, tier_display, target, enrolled_count
