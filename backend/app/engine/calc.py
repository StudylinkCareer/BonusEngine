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

from typing import List, Tuple, Dict
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


def _get_rates(cfg: BonusConfig, scheme: str, office: str = "") -> dict:
    """
    v6.3 FIX #1: Returns FLAT dict suitable for calc.py lookups.
    Input structure:  {tier: {CO: amt, COUN: amt}, "out_sys_co": amt, ...}
    Output structure: {tier: CO_amt, "coun_<tier>": COUN_amt, "out_sys_co": amt, ...}

    Stage 4: rate lookups now take an `office` argument. The internal dict
    is keyed by (scheme, office) since rates can vary by office. Falls back
    to HCM rates if the requested office has no rate card defined yet.

    Backward-compatible with the legacy two-level shape (no office key) so
    that in-memory seed data and tests keep working during the transition.
    """
    scheme_dict = cfg.base_rates.get(scheme) or cfg.base_rates.get(SCHEME_HCM_DIRECT, {})

    # Detect shape by looking at the first key. If it's an office code
    # (HCM, HN, DN, VP_xxx), this is the new three-level shape and we
    # need to dereference office. If it's a tier code (UNDER, MEET_*,
    # OVER, ...), this is the legacy two-level shape — use it directly.
    OFFICE_CODES = {OFFICE_HCM, OFFICE_HN, OFFICE_DN}
    raw = None
    if scheme_dict:
        sample_key = next(iter(scheme_dict.keys()))
        # Treat as new-shape if key matches a known office or starts with VP_
        is_new_shape = (sample_key in OFFICE_CODES
                        or (isinstance(sample_key, str) and sample_key.startswith("VP_")))
        if is_new_shape:
            raw = scheme_dict.get(office or OFFICE_HCM)
            if raw is None:
                raw = scheme_dict.get(OFFICE_HCM, {})
        else:
            raw = scheme_dict  # legacy shape — keys are tiers directly

    flat = {}
    for k, v in (raw or {}).items():
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
    rates = _get_rates(cfg, scheme, c.office)

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
        _apply_priority(c, cfg, year, month, scheme)
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
        _apply_priority(c, cfg, year, month, scheme)
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

    _apply_priority(c, cfg, year, month, scheme)
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


def _apply_priority(c: CaseRecord, cfg: BonusConfig,
                     year: int = 0, month: int = 0,
                     scheme: str = "") -> None:
    """Priority bonus calculation.

    For each case at a priority partner institution:
        bonus_priority = base_rate × bonus_pct × factor

    Policy (Apr 2026 v3, table-driven):
      • Status gate: only paid on cases that count as enrolled. Cancellations,
        visa refusals, and visa-only cases get base_rate (cancellation fee
        retention) but no priority.
      • Sub-agent gate: cases with is_agent_referred=True don't get priority
        UNLESS the staff scheme is CO_SUB. CO Direct staff don't get priority
        on agent-referred cases (the agent took the commission). CO Sub
        staff DO get priority — handling sub-agent referrals is their job.
      • Year gate: priority_instns has annual rows. bonus_pct=0 for the year
        means no priority is paid (e.g., 2025 partnerships zeroed across the
        board).
      • Factor: derived from priority_promotions table by (partner, month).
        Default factor = 0.5 (historical baseline). Promotions override.

    Per-case override (c.priority_factor) wins over all of above — used
    for documented exceptions like discount packages and handovers.
    """
    if c.base_rate <= 0: return
    # Status gate — only enrolled cases
    sr = cfg.get_status_rule(c.app_status)
    if not sr.counts_as_enrolled:
        return
    # Sub-agent gate — direct-scheme staff don't get priority on agent
    # referrals. CO Sub staff are exempt from this gate because referrals
    # are their core work.
    #
    # Per business rule (clarified Apr 2026): the Refer Agent field
    # identifies StudyLink's role in the case from StudyLink's perspective.
    #   - CO Direct staff cases: Refer Agent should be StudyLink-internal
    #     (the team enters StudyLink/VP-Mel/văn phòng-... in the field).
    #   - CO Sub staff cases: Refer Agent names the external sub-agency.
    #
    # So when we see CO Direct + external agent, that's a data quality
    # issue, NOT a legitimate case configuration. We refuse priority
    # (conservative — under-pay rather than over-pay) AND flag the case
    # so the operator can either correct the agent field or set an
    # explicit per-case override.
    if c.is_agent_referred and scheme != SCHEME_CO_SUB and c.priority_factor <= 0:
        c.add_warning(
            f"Priority not paid: Refer Agent '{c.agent}' looks external but "
            f"staff scheme is {scheme} (Direct). For CO Direct cases the "
            f"Refer Agent should be StudyLink or an internal office. "
            f"Either correct the Refer Agent or set a per-case priority "
            f"factor override if this case is a legitimate exception."
        )
        return
    inst_lower = c.institution.lower()
    for p in cfg.priority_instns:
        if year and p.year and p.year != year:
            continue
        if p.name.lower() in inst_lower or inst_lower in p.name.lower():
            if p.bonus_pct == 0:
                return
            af, source = _lookup_priority_factor(c, p, cfg, year, month)
            if af <= 0:
                return
            af_pct = int(af * 100)
            c.bonus_priority = int(c.base_rate * p.bonus_pct * af)
            c.note_priority  = f"Them {p.bonus_pct*100:.0f}% bonus cho {p.name}"
            c.note_priority2 = f"Factor {af_pct}% (source: {source})"
            break


def _lookup_priority_factor(c: CaseRecord,
                             p: 'PriorityInstitutionObj',
                             cfg: BonusConfig,
                             year: int = 0,
                             month: int = 0) -> tuple:
    """Decide the priority factor for one case at one priority partner.

    Returns (factor, source_description).

    Priority order:
      1. c.priority_factor > 0  → per-case override (v7 input). Used for
         documented exceptions like discount packages and handovers.
      2. Promotions table       → row where year matches AND
         effective_from <= report_period <= effective_to. At most one
         row should match per partner per period (overlap-prevention is
         enforced at save time and at engine load time).
      3. Default 0.5            → the historical baseline.

    The report period is built from year+month parameters (the báo cáo
    being processed). This is the right anchor because promotions reflect
    when the bonus is being paid, not when the case was originally signed.
    """
    # 1. Per-case override
    if c.priority_factor > 0:
        return c.priority_factor, "v7 input"

    # 2. Promotions table — find the row that brackets the report period
    if year and month and cfg.priority_promotions:
        from datetime import date
        report_period = date(year, month, 1)
        inst_lower = c.institution.lower()
        for pr in cfg.priority_promotions:
            if pr.year != year:
                continue
            pn = pr.institution_name.lower()
            if not (pn in inst_lower or inst_lower in pn):
                continue
            if pr.effective_from <= report_period <= pr.effective_to:
                return pr.factor, (
                    f"promotion {pr.effective_from.isoformat()} "
                    f"to {pr.effective_to.isoformat()}"
                )

    # 3. Default baseline
    return 0.5, "default 50%"


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
    """Compute bonuses for every case in a staff's monthly report.

    Multi-bucket model (Stage 4): each case has its own (scheme, office)
    pair (set during upload from staff defaults, optionally overridden by
    operator in Review). Cases are grouped into buckets, each bucket gets
    its own tier calculation against its own target, and base rates for
    cases in that bucket use that bucket's tier.

    Returns:
      cases:         the input list, mutated in place with bonus values
      tier_display:  tier string for the staff's HOME bucket (backwards
                     compat for callers that expect a single tier; full
                     per-bucket detail is in cfg._last_bucket_results)
      target:        target for the home bucket (backwards compat)
      enrolled:      enrolled count for the home bucket (backwards compat)

    The full per-bucket breakdown is also stashed on the BonusConfig
    object as `cfg._last_bucket_results` for the caller to retrieve. This
    is a bit ugly but avoids breaking the function signature for existing
    callers (recalc.py, reports.py upload path).
    """
    # ── Group cases into buckets by scheme (Stage 4 model) ──────────────────
    #
    # Bucket key is the SCHEME, not (scheme, office). Rationale:
    #   - A staff member's tier is computed against their home target.
    #   - Cases that classify into a different OFFICE (e.g. an HCM staff
    #     with an RMIT case classified to HN) still belong to the staff's
    #     home tier — the office assignment affects rate-card lookup only.
    #   - But cases under a DIFFERENT SCHEME (e.g. Phạm Thị Lợi default
    #     CO_SUB plus a few CO_DIRECT VP_DN cases via operator override)
    #     are genuinely separate buckets — different target, different tier.
    #
    # So we bucket by scheme. Within each bucket, individual cases keep
    # their own office for rate-card lookup. This preserves single-scheme
    # behaviour (An, Yến) while enabling multi-scheme staff (Lợi).
    home_target, home_scheme = cfg.get_staff_target(
        staff_name, year, month, office=office)

    buckets: Dict[str, List[CaseRecord]] = {}
    for c in cases:
        if c.row_type == ROW_ADDON:
            continue
        case_scheme = c.scheme or home_scheme
        buckets.setdefault(case_scheme, []).append(c)

    # ── Calculate per bucket ────────────────────────────────────────────────
    bucket_results = []
    home_bucket_tier = ""
    home_bucket_target = home_target
    home_bucket_enrolled = 0

    for bucket_scheme, bucket_cases in buckets.items():
        # Look up target for this bucket. Home scheme uses the staff's home
        # target. Other schemes look up their own target row, which may not
        # exist (e.g., Lợi defaulting to CO_SUB has a CO_SUB target, but a
        # few CO_DIRECT cases would need a separate CO_DIRECT target).
        if bucket_scheme == home_scheme:
            bucket_target = home_target
        else:
            # Try to find a target for this scheme's home office; fall
            # back to home_target if none exists yet.
            bucket_target, _ = cfg.get_staff_target(
                staff_name, year, month, office=office)
            # Note: ref_staff_targets keying could be extended to scheme
            # in a future iteration. For now we use the staff's home
            # target as a sensible fallback when no scheme-specific target
            # is configured.

        # Count enrolled IN THIS BUCKET only
        bucket_enrolled = count_enrolled_for_tier(
            bucket_cases, bucket_scheme, cfg, month=month, year=year)

        # Inherited tier override only applies to the home bucket
        bucket_inherited = (inherited_tier
                             if bucket_scheme == home_scheme
                             else "")

        # Override count only applies to the home bucket
        bucket_count = bucket_enrolled
        if enrolled_override >= 0 and bucket_scheme == home_scheme:
            bucket_count = enrolled_override

        bucket_tier = determine_tier(bucket_count, bucket_target, bucket_inherited)

        # Calculate each case in the bucket using THIS bucket's tier.
        # The case's own c.office determines the rate-card lookup —
        # same scheme, but office-specific rates if seeded.
        for c in bucket_cases:
            calc_single_case(c, bucket_tier, bucket_target, bucket_count,
                             bucket_scheme, cfg, month, year, is_counsellor)

        # Tally bucket totals for the breakdown record
        bucket_total = sum((c.bonus_enrolled or 0) + (c.bonus_priority or 0)
                           for c in bucket_cases)
        tier_display = resolve_meet_tier(0, cfg) if bucket_tier == TIER_MEET else bucket_tier

        bucket_results.append({
            "scheme":       bucket_scheme,
            "office":       office,  # display office (the report's office),
                                     # not per-case (cases keep their own office)
            "target":       bucket_target,
            "enrolled":     bucket_count,
            "tier":         tier_display,
            "case_count":   len(bucket_cases),
            "bucket_total": bucket_total,
        })

        # Capture home bucket details for backwards-compat return values
        if bucket_scheme == home_scheme:
            home_bucket_tier = tier_display
            home_bucket_target = bucket_target
            home_bucket_enrolled = bucket_count

    # ── Process addon rows after all buckets calculated ─────────────────────
    _process_addon_rows(cases, cfg)

    # ── Stash full breakdown on cfg for caller retrieval ────────────────────
    cfg._last_bucket_results = bucket_results

    # If staff has no cases in their home bucket, surface the largest bucket
    # as the "primary" tier for backwards compat. This avoids returning empty
    # strings and preserves single-bucket behaviour for existing tests.
    if not home_bucket_tier and bucket_results:
        primary = max(bucket_results, key=lambda b: b["case_count"])
        home_bucket_tier     = primary["tier"]
        home_bucket_target   = primary["target"]
        home_bucket_enrolled = primary["enrolled"]

    return cases, home_bucket_tier, home_bucket_target, home_bucket_enrolled

