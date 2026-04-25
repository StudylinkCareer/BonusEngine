# =============================================================================
# calc.py  |  StudyLink Bonus Engine v6.3
# Reconstructed with 9 documented fixes applied:
#   1. _get_rates: flat dict (tier→CO, coun_tier→COUN, out_sys_co, ...)
#   2. get_service_fee: 2-arg signature (in config.py)
#   3. Step 2.8b: CONTRACT zero-amount fees fall through for fees_paid
#   4. Step 3.5: fees_paid detection checks service_fee_type AND package_type
#   5. Step 3.5: DIRECT cancelled with fee collected → 400k
#   6. Step 6: partner case (** or * in institution) → 400k
#   7. Step 7/8: base_rate set AFTER split, BEFORE package
#   8. Carry-over: always 50% of prior month rate
#   9. Priority: uses c.base_rate (pre-package), not c.bonus_enrolled
#
# Plus: keyword-based package resolution from today's session — _apply_package
# calls cfg.resolve_service_code() before get_service_fee() so display strings
# like "Standard Package (16tr)" map to canonical codes like USA_STANDARD_16TR.
# =============================================================================

from typing import List, Tuple
from .constants import *
from .config import BonusConfig, StatusRule
from .models import CaseRecord


def determine_tier(enrolled: int, target: int, inherited_tier: str = "") -> str:
    if target == 0:
        if inherited_tier:
            return inherited_tier
        return TIER_OVER if enrolled > 0 else TIER_UNDER
    if enrolled > target:  return TIER_OVER
    if enrolled == target: return TIER_MEET
    return TIER_UNDER


def resolve_meet_tier(incentive: int, cfg: "BonusConfig" = None) -> str:
    threshold = cfg.incentive_threshold if cfg else INCENTIVE_THRESHOLD
    return TIER_MEET_HIGH if incentive >= threshold else TIER_MEET_LOW


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
        if c.is_agent_referred and c.institution_type == INST_DIRECT and scheme != SCHEME_CO_SUB:
            w = 0.7
        else:
            w = cfg.get_kpi_weight(c.client_type_code, c.institution_type, scheme)
        weighted += w
    return int(weighted)


def _get_rates(cfg: BonusConfig, scheme: str) -> dict:
    """
    v6.3 FIX #1: Returns FLAT dict suitable for calc.py lookups.
    Input structure:  {tier: {CO: amt, COUN: amt}, "out_sys_co": amt, ...}
    Output structure: {tier: CO_amt, "coun_<tier>": COUN_amt, "out_sys_co": amt, ...}
    """
    raw = cfg.base_rates.get(scheme, cfg.base_rates.get(SCHEME_HCM_DIRECT, {}))
    flat = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            # tier dict — split into CO and COUN entries
            if "CO" in v:
                flat[k] = v["CO"]
            if "COUN" in v:
                flat[f"coun_{k}"] = v["COUN"]
        else:
            # already flat (out_sys_co, rmit_vn, etc.)
            flat[k] = v
    return flat


def _is_partner_case(institution: str) -> bool:
    """
    v6.3 FIX #6: detect * flag in institution name → partner case.
    The * indicates a partner-platform enrolment.
    """
    if not institution:
        return False
    return "*" in institution


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

    # ── STEP 2.8b: Service fee (v6.3 FIX #3: CONTRACT zero falls through) ────
    if c.service_fee_type and c.service_fee_type.upper() not in (SVC_NONE, ""):
        sf = (cfg.get_service_fee(c.service_fee_type, SVC_SERVICE_FEE) or
              cfg.get_service_fee(c.service_fee_type, SVC_CONTRACT))
        if sf:
            amount = sf.coun_bonus if is_counsellor else sf.co_bonus
            # CONTRACT fee with zero amount on fees_paid status → fall through to Step 3.5
            if amount == 0 and sf.category == SVC_CONTRACT and sr.fees_paid_non_enrolled:
                pass  # Step 3.5 will apply 400k fees-paid rate
            else:
                if c.handover.upper() == "YES":
                    amount = amount // 2
                    c.note_enrolled = f"{c.service_fee_type}: × 50% (handover) = {amount:,.0f}"
                else:
                    c.note_enrolled = f"{c.service_fee_type}: {amount:,.0f}"
                c.bonus_enrolled = amount
                c.base_rate      = amount
                if sf.category == SVC_CONTRACT:
                    _apply_package(c, is_counsellor, cfg, sr)
                return
        else:
            c.note_enrolled = f"Service fee '{c.service_fee_type}' not found → 0"; return

    # ── STEP 3: Zero-bonus status ──────────────────────────────────────────────
    if sr.is_zero_bonus:
        c.note_enrolled = f"Status: {c.app_status} → 0"; return

    # ── STEP 3.5: Fees-paid (v6.3 FIX #4 + #5) ────────────────────────────────
    if sr.fees_paid_non_enrolled:
        no_fee_codes = {"NONE", "", "AP_STANDARD_PLUS_3TR", "NO_COMM"}
        # FIX #4: check BOTH service_fee_type AND package_type for fee evidence
        has_svc_fee = bool(c.service_fee_type and
                           c.service_fee_type.upper() not in no_fee_codes)
        has_pkg     = bool(c.package_type and
                           c.package_type.upper() not in no_fee_codes)
        has_fee     = has_svc_fee or has_pkg

        if c.institution_type in (INST_GROUP, INST_OUT_OF_SYS) or has_fee:
            r = (rates.get("out_sys_coun", 600_000) if is_counsellor
                 else rates.get("out_sys_co", 400_000))
            c.bonus_enrolled = r; c.base_rate = r
            tag = ("(fee collected)" if (has_fee and c.institution_type == INST_DIRECT)
                   else f"({c.institution_type})")
            c.note_enrolled = f"Fees paid {tag}: {r:,.0f}"; return
        # DIRECT + no fee, MASTER_AGENT: truly zero
        c.note_enrolled = f"{c.app_status} → 0 (no fee collected)"; return

    # ── STEP 4: Carry-over (v6.3 FIX #8: always 50%) ─────────────────────────
    if sr.is_carry_over:
        if c.prior_month_rate <= 0 and scheme == SCHEME_CO_SUB:
            resolved_prior = tier if tier != TIER_MEET else resolve_meet_tier(c.incentive, cfg)
            c.prior_month_rate = rates.get(resolved_prior, rates.get(TIER_UNDER, 700_000))
        if c.prior_month_rate <= 0:
            c.note_enrolled = "CARRY-OVER: prior month rate missing (col 27)"; return
        c.base_rate = c.prior_month_rate
        # FIX #8: always 50% (VBA: priorRate // 2)
        c.bonus_enrolled = c.prior_month_rate // 2
        c.note_enrolled  = (f"Carry-over: {c.prior_month_rate:,.0f} × 50% = "
                            f"{c.bonus_enrolled:,.0f}")
        _apply_package(c, is_counsellor, cfg, sr)
        _apply_advance_offset(c, sr); return

    # ── STEP 5: CountsAsEnrolled gate ──────────────────────────────────────────
    if not sr.counts_as_enrolled and not sr.is_current_enrolled:
        c.note_enrolled = f"Status: {c.app_status} → 0"; return

    # ── STEP 6: Partner case (v6.3 FIX #6: * or ** institution → 400k) ───────
    if _is_partner_case(c.institution):
        r = rates.get("out_sys_co", 400_000)
        c.bonus_enrolled = r; c.base_rate = r
        c.note_enrolled = f"Partner institution: {r:,.0f}"
        return

    # ── STEP 7: Base rate ─────────────────────────────────────────────────────
    resolved_tier = tier if tier != TIER_MEET else resolve_meet_tier(c.incentive, cfg)

    if c.is_flat_country:
        base = rates.get("out_sys_co", 500000)
        c.note_enrolled = f"Flat-rate country: {base:,.0f}"
    elif c.is_vietnam:
        if scheme == SCHEME_CO_SUB:
            base = rates.get("rmit_vn", 600_000)
            c.note_enrolled = f"Vietnam (CO_SUB): {base:,.0f}"
        else:
            if c.institution_type == INST_RMIT_VN:
                base = 1_000_000; c.note_enrolled = f"RMIT VN: {base:,.0f}"
            elif c.institution_type == INST_BUV_VN:
                base = 600_000;   c.note_enrolled = f"BUV VN: {base:,.0f}"
            else:
                base = 500_000;   c.note_enrolled = f"Vietnam domestic: {base:,.0f}"
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
    # FIX #7: base_rate captured AFTER split, BEFORE package
    c.base_rate = c.bonus_enrolled

    # ── STEP 8A: Pre-sales split ──────────────────────────────────────────────
    if is_counsellor and c.presales_agent not in (PRESALES_NONE, "", "NONE"):
        c.bonus_enrolled = c.bonus_enrolled // 2
        c.base_rate      = c.bonus_enrolled  # update post-presales for priority
        c.note_enrolled  = (c.note_enrolled +
                            f" | Pre-sales 50/50 with {c.presales_agent}").strip(" | ")

    # ── STEP 9: Package then priority ─────────────────────────────────────────
    _apply_package(c, is_counsellor, cfg, sr)
    _apply_priority(c, cfg)
    _apply_advance_offset(c, sr)


def _apply_package(c: CaseRecord, is_counsellor: bool,
                   cfg: BonusConfig, sr: StatusRule) -> None:
    """Applies package bonus. For current-enrolled, applies 50% split."""
    if c.package_type and c.package_type.upper() not in (PKG_NONE, ""):
        # Resolve free-text package name to canonical code, then standardise
        # c.package_type so downstream notes/output use the standard form.
        resolved = cfg.resolve_service_code(c.package_type, SVC_PACKAGE)
        if resolved:
            c.package_type = resolved
        pf = cfg.get_service_fee(c.package_type, SVC_PACKAGE)
        if pf:
            amt = pf.coun_bonus if is_counsellor else pf.co_bonus
            if amt > 0:
                if sr.is_current_enrolled:
                    amt = amt // 2
                c.bonus_enrolled += amt
                c.note_enrolled = (
                    c.note_enrolled + f" | Package {c.package_type}: +{amt:,.0f}"
                ).strip(" | ")


def _apply_priority(c: CaseRecord, cfg: BonusConfig) -> None:
    """v6.3 FIX #9: priority calc uses c.base_rate (pre-package), not bonus_enrolled."""
    if c.base_rate <= 0: return
    inst_lower = c.institution.lower()
    for p in cfg.priority_instns:
        if p.name.lower() in inst_lower or inst_lower in p.name.lower():
            af     = 1.0 if p.achieved_ytd >= p.annual_target else 0.5
            af_pct = int(af * 100)
            c.bonus_priority = int(c.base_rate * p.bonus_pct * af)
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
    target, scheme = cfg.get_staff_target(staff_name, year, month)
    enrolled_count  = count_enrolled_for_tier(cases, scheme, cfg)
    if enrolled_override >= 0:
        enrolled_count = enrolled_override
    tier            = determine_tier(enrolled_count, target, inherited_tier)

    for c in cases:
        if c.row_type == ROW_ADDON: continue
        case_scheme = (SCHEME_HN_DIRECT
                       if c.office in (OFFICE_HN, OFFICE_DN)
                       and scheme not in (SCHEME_HN_DIRECT, SCHEME_CO_SUB)
                       else scheme)
        calc_single_case(c, tier, target, enrolled_count,
                         case_scheme, cfg, month, year, is_counsellor)

    _process_addon_rows(cases, cfg)

    tier_display = resolve_meet_tier(0, cfg) if tier == TIER_MEET else tier
    return cases, tier_display, target, enrolled_count
