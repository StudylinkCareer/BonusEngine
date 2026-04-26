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
    # When target is zero (or unset), the staff isn't on a tiered scheme for
    # this period. Default to UNDER tier — enrolments still pay the low rate
    # but don't trigger OVER tier rates. This matches báo cáo behavior for
    # Yến's HN office cases, where her HN target was wound down to 0 from
    # Mar 2024 onwards but she still processed an occasional HN file.
    if target <= 0:
        if inherited_tier:
            return inherited_tier
        return TIER_UNDER
    if enrolled > target:  return TIER_OVER
    if enrolled == target: return TIER_MEET
    return TIER_UNDER


def resolve_meet_tier(incentive: int, cfg: "BonusConfig" = None) -> str:
    threshold = cfg.incentive_threshold if cfg else INCENTIVE_THRESHOLD
    return TIER_MEET_HIGH if incentive >= threshold else TIER_MEET_LOW


def count_enrolled_for_tier(cases: List[CaseRecord], scheme: str,
                             cfg: BonusConfig,
                             month: int = 0, year: int = 0) -> int:
    weighted = 0.0
    for c in cases:
        if c.row_type == ROW_ADDON or c.is_duplicate or c.exclude_from_calc:
            print(f"  [COUNT SKIP] {c.contract_id} {c.student_name}: row_type/dup/exclude")
            continue
        if c.deferral.upper() in DEFERRAL_ZERO_VALUES:
            print(f"  [COUNT SKIP] {c.contract_id} {c.student_name}: deferral={c.deferral}")
            continue
        sr = cfg.get_status_rule(c.app_status)
        # Apr 2026: same-period carry-over fix — if course start is in the
        # current period, the case behaves as a normal enrolled (not carry-over),
        # so it should count toward the tier target.
        same_period_enrol = bool(
            month and year and c.course_start
            and c.course_start.year == year
            and c.course_start.month == month
        )
        carry_for_count = sr.is_carry_over and not same_period_enrol
        if carry_for_count or sr.is_zero_bonus or not sr.counts_as_enrolled:
            print(f"  [COUNT SKIP] {c.contract_id} {c.student_name}: status={c.app_status} "
                  f"carry={sr.is_carry_over} same_period={same_period_enrol} "
                  f"zero={sr.is_zero_bonus} counts={sr.counts_as_enrolled}")
            continue
        if sr.fees_paid_non_enrolled:
            if c.institution_type in (INST_MASTER_AGENT, INST_GROUP, INST_OUT_OF_SYS):
                print(f"  [COUNT SKIP] {c.contract_id} {c.student_name}: fees_paid + {c.institution_type}")
                continue
        # Apr 2026: agent-referral weighting now flows through get_kpi_weight
        # so all weight rules live in ref_kpi_weights and can be tuned in DB.
        # (Old code: special-cased is_agent_referred=True + DIRECT to 0.7 here.)
        w = cfg.get_kpi_weight(c.client_type_code, c.institution_type, scheme,
                               is_agent_referred=c.is_agent_referred)
        print(f"  [COUNT KEEP] {c.contract_id} {c.student_name}: weight={w} "
              f"agent_ref={c.is_agent_referred} inst_type={c.institution_type}")
        weighted += w
    print(f"  [COUNT TOTAL] weighted={weighted} → int={int(weighted)}")
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
        # Apr 2026: base_rate for priority calc is the underlying tier rate
        # (not the override total, which already includes package). Priority %
        # always applies to base, never to package.
        resolved_tier = tier if tier != TIER_MEET else resolve_meet_tier(c.incentive, cfg)
        rate_key = f"coun_{resolved_tier}" if is_counsellor else resolved_tier
        derived_base = rates.get(rate_key, rates.get(resolved_tier, rates.get(TIER_UNDER, 800_000)))
        c.base_rate = derived_base
        c.note_enrolled = f"Management override: {c.prior_month_rate:,.0f}"
        _apply_priority(c, cfg, year)
        return

    # Pending add-on amount captured from Step 2.8b when applies_as=ADD.
    # Applied AFTER base rate + package, so Guardian / Dependant supplement
    # rather than replace the case's main bonus path.
    pending_addon: int = 0
    pending_addon_label: str = ""
    pending_addon_share: bool = False

    # ── STEP 2.8b: Service fee (v6.3 FIX #3: CONTRACT zero falls through) ────
    if c.service_fee_type and c.service_fee_type.upper() not in (SVC_NONE, ""):
        sf = (cfg.get_service_fee(c.service_fee_type, SVC_SERVICE_FEE) or
              cfg.get_service_fee(c.service_fee_type, SVC_CONTRACT))
        if sf:
            amount = sf.coun_bonus if is_counsellor else sf.co_bonus

            # NEW: applies_as=ADD → capture amount, do NOT return.
            # Add-on family (Guardian, Dependant): the case continues through
            # base rate + package logic, then receives this add-on at the end.
            if getattr(sf, "applies_as", "REPLACE") == "ADD":
                pending_addon       = amount
                pending_addon_label = sf.code
                pending_addon_share = bool(getattr(sf, "share_with_other_co", False))
                # fall through to Step 3+
            else:
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
                        _apply_package(c, is_counsellor, cfg, sr, tier=tier)
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
    # Apr 2026: scope tightened — carry-over fires ONLY when the course start
    # is in a period prior to the current run period. Same-period course start
    # means both events (enrolment + visa) happened this month, so the case
    # behaves like a normal "Closed - Visa granted, then enrolled" — full base
    # rate, no advance offset.
    same_period_enrol = bool(
        c.course_start
        and c.course_start.year == year
        and c.course_start.month == month
    )
    if sr.is_carry_over and not same_period_enrol:
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
        _apply_package(c, is_counsellor, cfg, sr, tier=tier)
        # Apr 2026 (v6.5): carry-over cases at priority partners get the
        # remaining 50% of the priority bonus too. Without this call the
        # priority side of the carry-over was missing entirely.
        # base_rate has already been set to prior_month_rate above; halve it
        # so priority is calculated on the same 50% notional that the
        # enrolled bonus is on.
        c.base_rate = c.bonus_enrolled
        _apply_priority(c, cfg, year)
        _apply_advance_offset(c, sr); return

    # ── STEP 5: CountsAsEnrolled gate ──────────────────────────────────────────
    if not sr.counts_as_enrolled and not sr.is_current_enrolled:
        c.note_enrolled = f"Status: {c.app_status} → 0"; return

    # ── STEP 6: Partner haircut for fees-paid (non-enrolled) at * institution ──
    # When the case is at a * partner institution AND the status is fees-paid
    # / cancelled-with-fee (NOT counts_as_enrolled), apply the flat PARTNER
    # rate. For enrolled cases, the institution_type field on the v7 input
    # determines treatment:
    #   • inst_type = DIRECT       → full tier base rate (in-system enrolment)
    #   • inst_type = MASTER_AGENT → reduced via Step 6.5/Step 7 logic
    #   • inst_type = OUT_OF_SYSTEM → 2× out_sys_co = 800k (out-of-system
    #     enrolment, e.g., USA via GE/GEEBEE/GUS or AUS via Can-Achieve).
    if _is_partner_case(c.institution) and not sr.counts_as_enrolled:
        r = rates.get("out_sys_co", 400_000)
        c.bonus_enrolled = r; c.base_rate = r
        c.note_enrolled = f"Partner institution: {r:,.0f}"
        return
    # Out-of-system enrolment (operator-flagged) — scheme-specific rate.
    # HCM_DIRECT: 2× out_sys_co (800k for USA via GE/GEEBEE/GUS, AUS via
    #             Can-Achieve, etc.) — out-of-system enrolment is rarer and
    #             pays a doubled bonus.
    # CO_SUB:     PARTNER rate (400k) — CO Sub officers earn the standard
    #             partner rate on out-of-system referrals.
    if (sr.counts_as_enrolled
        and c.institution_type == INST_OUT_OF_SYS):
        if scheme == SCHEME_CO_SUB:
            r = rates.get("out_sys_co", 400_000)
        else:
            r = rates.get("out_sys_co", 400_000) * 2
        c.bonus_enrolled = r; c.base_rate = r
        c.note_enrolled = f"Out-of-system enrolment ({scheme}): {r:,.0f}"
        return

    # ── STEP 6.5: Enrolled at ** GROUP / MASTER / OUT_OF_SYSTEM ──────────────
    # Apr 2026 (v6.4): a case enrolled through a double-star (**) partner
    # institution that is also classified as GROUP / MASTER_AGENT / OUT_OF_SYSTEM
    # receives a flat out-of-system rate (800k for HCM_DIRECT) — not the
    # tier-based rate, and no package bonus on top. This codifies the rule
    # that out-of-system enrolments don't compound with the standard tier and
    # package incentive structure.
    if (sr.counts_as_enrolled
        and "**" in (c.institution or "")
        and c.institution_type in (INST_GROUP, INST_MASTER_AGENT, INST_OUT_OF_SYS)):
        r = rates.get("out_sys_co", 800_000) * 2  # out_sys_co=400k base, ** doubles to 800k
        # NOTE: rate currently derived as 2× out_sys_co. If business changes the
        # ** enrolled rate independently of the * fees-paid rate, add a separate
        # ref_base_rates entry (e.g. tier='OUT_SYS_ENROLLED') and read it here.
        c.bonus_enrolled = r
        c.base_rate      = r
        c.note_enrolled  = f"Enrolled out-of-system (**): {r:,.0f}"
        # No package bonus, no priority — but pending add-on (Guardian/etc) still applies
        if pending_addon > 0:
            payout = pending_addon // 2 if pending_addon_share else pending_addon
            c.bonus_enrolled += payout
            c.note_enrolled = (c.note_enrolled +
                f" | {pending_addon_label}: +{payout:,.0f}").strip(" | ")
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
        # CO_SUB always pays 50% on Current-Enrolled regardless of tier.
        # HCM_DIRECT at OVER tier pays 100% (full lifetime amount this month
        # because the staff has over-achieved their target). Other HCM_DIRECT
        # tiers pay 50% upfront, 50% as carry-over when visa arrives.
        # Counsellor role always pays 100%.
        if scheme == SCHEME_CO_SUB:
            split = 0.5
            sfx = " | 50% chua co visa (CO_SUB)"
        elif not is_counsellor and tier == TIER_OVER:
            split = 1.0
            sfx = " | 100% (Over target current-enrolled)"
        else:
            split = 1.0 if is_counsellor else 0.5
            sfx = " | 100% da nhap hoc" if is_counsellor else " | 50% chua co visa"
        c.note_enrolled = (c.note_enrolled + sfx).strip(" | ")
    elif sr.is_carry_over and same_period_enrol:
        # Same-period carry-over status: both enrolment and visa happened in
        # the current period, so no prior advance was paid. Use full 1.0
        # split, treating it as a normal closed-enrolled case.
        split = 1.0
        c.note_enrolled = (c.note_enrolled + " | Same-period (no prior advance)").strip(" | ")
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

    # ── STEP 9: Package then add-on then priority ────────────────────────────
    _apply_package(c, is_counsellor, cfg, sr, tier=tier)

    # NEW: apply Guardian / Dependant / other ADD-category service fees AFTER
    # the package bonus has been added. Halve the amount when the rule has
    # share_with_other_co=True (Guardian splits 50/50 with the other CO who
    # handled the visa portion). Priority bonus runs after this so it can use
    # the post-add-on base_rate if needed.
    if pending_addon > 0:
        payout = pending_addon // 2 if pending_addon_share else pending_addon
        c.bonus_enrolled += payout
        suffix = (f"{pending_addon_label}: 50/50 split = +{payout:,.0f}"
                  if pending_addon_share
                  else f"{pending_addon_label}: +{payout:,.0f}")
        c.note_enrolled = (c.note_enrolled + " | " + suffix).strip(" | ")

    _apply_priority(c, cfg, year)
    _apply_advance_offset(c, sr)


def _apply_package(c: CaseRecord, is_counsellor: bool,
                   cfg: BonusConfig, sr: StatusRule, tier: str = "") -> None:
    """Applies package bonus. For current-enrolled below OVER tier, applies 50% split."""
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
                # Apr 2026: at OVER tier, current-enrolled receives the full
                # package bonus (consistent with the full base rate paid in
                # Step 8 — báo cáo treats the case lifetime amount as paid up
                # front). Lower tiers still halve.
                if sr.is_current_enrolled and tier != TIER_OVER:
                    amt = amt // 2
                c.bonus_enrolled += amt
                c.note_enrolled = (
                    c.note_enrolled + f" | Package {c.package_type}: +{amt:,.0f}"
                ).strip(" | ")


def _apply_priority(c: CaseRecord, cfg: BonusConfig, year: int = 0) -> None:
    """Priority bonus calculation.

    For each case at a priority partner institution:
        bonus_priority = base_rate × bonus_pct × factor

    Apr 2026: priority partnerships are now annual decisions (the bonus_pct,
    annual_target, etc. can change year over year, including dropping to 0%
    for a year). Lookup is by (institution_name, year) — when the case's
    year doesn't match any partner row, no priority bonus is paid.

    Factor source (in priority order):
      1. c.priority_factor (per-case override from v7 input). Use this when
         the báo cáo author has recorded an explicit factor for this case.
      2. Derived from priority_instns: 1.0 if achieved_ytd >= annual_target,
         else 0.5. Only used when achieved_ytd is populated (> 0) so we
         have actual YTD tracking data.

    If neither signal is present, the engine pays NO priority bonus. This
    avoids the previous behavior of assuming 50% factor when no data was
    available (which over-paid priority on cases where the partnership had
    ended or never paid priority for that staff).
    """
    if c.base_rate <= 0: return
    inst_lower = c.institution.lower()
    for p in cfg.priority_instns:
        # Year-aware match: skip rows for a different year. A row with year=0
        # (legacy / not yet migrated) matches any year — backwards compatible.
        if year and p.year and p.year != year:
            continue
        if p.name.lower() in inst_lower or inst_lower in p.name.lower():
            # When bonus_pct is 0 (e.g., 2025 partnerships zeroed out), there
            # is nothing to pay regardless of factor.
            if p.bonus_pct == 0:
                return
            if c.priority_factor > 0:
                af = c.priority_factor
                source = "v7 input"
            elif p.achieved_ytd > 0:
                # YTD data populated — derive factor from target progress
                af = 1.0 if p.achieved_ytd >= p.annual_target else 0.5
                source = f"YTD {p.achieved_ytd}/{p.annual_target}"
            else:
                # No factor signal at all — pay no priority bonus
                return
            af_pct = int(af * 100)
            c.bonus_priority = int(c.base_rate * p.bonus_pct * af)
            c.note_priority  = f"Them {p.bonus_pct*100:.0f}% bonus cho {p.name}"
            c.note_priority2 = f"Factor {af_pct}% (source: {source})"
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
    target, scheme = cfg.get_staff_target(staff_name, year, month, office=office)
    enrolled_count  = count_enrolled_for_tier(cases, scheme, cfg, month=month, year=year)
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
