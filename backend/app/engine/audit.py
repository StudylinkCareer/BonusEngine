# =============================================================================
# audit.py  |  StudyLink Bonus Engine v1.0
# NEW MODULE — no VBA equivalent
#
# Automated reconciliation engine.
# Runs every available CRM/manual pair through the engine and produces
# a structured deviation report.
# =============================================================================

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .constants import *
from .config import BonusConfig
from .models import CaseRecord
from .input import parse_crm_report, read_manual_report
from .classify import classify_cases
from .calc import calculate_bonuses


@dataclass
class CaseDeviation:
    contract_id:   str
    student_name:  str
    app_status:    str
    engine_bonus:  int
    manual_bonus:  int
    gap:           int
    engine_note:   str
    flags:         List[str] = field(default_factory=list)

    @property
    def has_gap(self) -> bool:
        return self.gap != 0


@dataclass
class MonthResult:
    staff_name:    str
    year:          int
    month:         int
    office:        str
    target:        int
    enrolled:      int
    tier:          str
    engine_total:  int
    manual_total:  int
    gap:           int
    passed:        bool
    cases:         List[CaseRecord]         = field(default_factory=list)
    deviations:    List[CaseDeviation]      = field(default_factory=list)
    warnings:      List[str]                = field(default_factory=list)
    clarifications: List[str]               = field(default_factory=list)

    @property
    def month_name(self) -> str:
        return ["","Jan","Feb","Mar","Apr","May","Jun",
                "Jul","Aug","Sep","Oct","Nov","Dec"][self.month]


def run_audit(
    crm_path:            str,
    manual_path:         str,
    staff_name:          str,
    year:                int,
    month:               int,
    cfg:                 BonusConfig,
    operator_overrides:  Dict[str, dict] = None,
    is_counsellor:       bool = False,
    office:              str  = OFFICE_HCM,
    enrolled_override:   int  = -1,
) -> MonthResult:
    """
    Runs one CRM/manual pair through the full engine pipeline and
    returns a structured MonthResult with deviations.
    """
    # Parse CRM
    cases, warnings = parse_crm_report(crm_path, cfg)

    # Classify
    cases = classify_cases(cases, cfg, staff_name, year, month, operator_overrides)

    # Calculate
    cases, tier, target, enrolled = calculate_bonuses(
        cases, staff_name, year, month, cfg, is_counsellor,
        enrolled_override=enrolled_override,
    )

    # Read manual
    manual_total, manual_by_contract = read_manual_report(manual_path)

    # Engine total (non-duplicate BASE rows only)
    engine_total = sum(
        c.bonus_enrolled for c in cases
        if not c.is_duplicate and c.row_type == ROW_BASE
    )

    # Build deviations
    deviations = []
    for c in cases:
        if c.is_duplicate or c.row_type == ROW_ADDON:
            continue
        manual_bonus = manual_by_contract.get(c.contract_id, 0)
        gap = c.bonus_enrolled - manual_bonus
        dev = CaseDeviation(
            contract_id  = c.contract_id,
            student_name = c.student_name,
            app_status   = c.app_status,
            engine_bonus = c.bonus_enrolled,
            manual_bonus = manual_bonus,
            gap          = gap,
            engine_note  = c.note_enrolled,
            flags        = list(c.warn_flags),
        )
        if c.contract_id not in manual_by_contract:
            dev.flags.append("NOT IN MANUAL")
        deviations.append(dev)

    # Cases in manual but not in engine
    engine_contracts = {c.contract_id for c in cases if not c.is_duplicate}
    for cid, mb in manual_by_contract.items():
        if cid not in engine_contracts and mb != 0:
            deviations.append(CaseDeviation(
                contract_id  = cid,
                student_name = "— not in CRM —",
                app_status   = "",
                engine_bonus = 0,
                manual_bonus = mb,
                gap          = -mb,
                engine_note  = "",
                flags        = ["IN MANUAL ONLY"],
            ))

    result = MonthResult(
        staff_name   = staff_name,
        year         = year,
        month        = month,
        office       = office,
        target       = target,
        enrolled     = enrolled,
        tier         = tier,
        engine_total = engine_total,
        manual_total = manual_total,
        gap          = engine_total - manual_total,
        passed       = engine_total == manual_total,
        cases        = cases,
        deviations   = deviations,
        warnings     = warnings,
    )

    return result


def print_result(r: MonthResult) -> None:
    """Prints a formatted audit result to stdout."""
    sym = "✅" if r.passed else "❌"
    print(f"\n{'='*72}")
    print(f"{sym}  {r.staff_name} — {r.month_name} {r.year}  |  Office: {r.office}")
    print(f"   Target={r.target}  Enrolled={r.enrolled}  Tier={r.tier}")
    print(f"   Engine: {r.engine_total:>12,.0f}   Manual: {r.manual_total:>12,.0f}   "
          f"Gap: {r.gap:>+12,.0f}")

    if r.warnings:
        for w in r.warnings[:5]:
            print(f"   ⚠  {w}")

    if not r.passed:
        print(f"\n   {'No':>3} {'Contract':>12} {'Status':>40} "
              f"{'Engine':>10} {'Manual':>10} {'Gap':>9}")
        print(f"   {'-'*3} {'-'*12} {'-'*40} {'-'*10} {'-'*10} {'-'*9}")
        for d in r.deviations:
            flag = " ←" if d.has_gap else ""
            print(f"   {' ':>3} {d.contract_id:>12} {d.app_status:>40} "
                  f"{d.engine_bonus:>10,.0f} {d.manual_bonus:>10,.0f} "
                  f"{d.gap:>+9,.0f}{flag}")
            if d.has_gap and d.engine_note:
                print(f"       Note: {d.engine_note[:75]}")
            if d.flags:
                print(f"       Flags: {', '.join(d.flags)}")


def print_summary(results: List[MonthResult]) -> None:
    """Prints a summary table across all results."""
    passed  = sum(1 for r in results if r.passed)
    total   = len(results)
    print(f"\n{'='*72}")
    print(f"AUDIT SUMMARY: {passed}/{total} months passed")
    print(f"\n   {'Staff':<20} {'Period':<12} {'Engine':>12} {'Manual':>12} {'Gap':>10} {'Status'}")
    print(f"   {'-'*20} {'-'*12} {'-'*12} {'-'*12} {'-'*10} {'-'*8}")
    for r in results:
        sym = "✅" if r.passed else "❌"
        print(f"   {r.staff_name:<20} {r.month_name+' '+str(r.year):<12} "
              f"{r.engine_total:>12,.0f} {r.manual_total:>12,.0f} "
              f"{r.gap:>+10,.0f} {sym}")

    if passed < total:
        print(f"\n   FAILED MONTHS:")
        for r in [x for x in results if not x.passed]:
            all_deviations = [d for d in r.deviations if d.has_gap]
            print(f"\n   {r.staff_name} {r.month_name} {r.year} "
                  f"(Gap: {r.gap:+,.0f}):")
            for d in all_deviations[:10]:
                print(f"     {d.contract_id} {d.app_status[:35]:35} "
                      f"Engine={d.engine_bonus:,.0f} Manual={d.manual_bonus:,.0f} "
                      f"Δ={d.gap:+,.0f}")
