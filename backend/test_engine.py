#!/usr/bin/env python3
# =============================================================================
# test_engine.py  |  StudyLink Bonus Engine v6.3 — Standalone Test Runner
# Builds BonusConfig from known reference data (no DB) and runs:
#   1. Hoàng Yến Jan 2024 HCM  → 6,130,000
#   2. Lê Thị Trường An Jul 2024 → 17,761,250
# =============================================================================

import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, 'app'))

from app.engine.config import (
    BonusConfig, StatusRuleObj, ServiceFeeRuleObj, StaffTargetObj,
    PriorityInstitutionObj, CountryRuleObj
)
from app.engine.calc import calculate_bonuses
from app.engine.constants import *
from legacy_adapter import read_baocao, to_engine_dict, build_case_records


def build_config() -> BonusConfig:
    cfg = BonusConfig()

    # ── Base rates (HCM_DIRECT) ───────────────────────────────────────────────
    cfg.base_rates = {
        SCHEME_HCM_DIRECT: {
            TIER_UNDER:     {"CO": 800_000,   "COUN": 1_400_000},
            TIER_MEET_HIGH: {"CO": 1_000_000, "COUN": 1_400_000},
            TIER_MEET_LOW:  {"CO": 1_400_000, "COUN": 1_800_000},
            TIER_OVER:      {"CO": 1_400_000, "COUN": 2_000_000},
            "out_sys_co":    400_000,
            "out_sys_coun":  600_000,
        },
        SCHEME_HN_DIRECT: {
            TIER_UNDER:     {"CO": 600_000,   "COUN": 1_000_000},
            TIER_MEET_HIGH: {"CO": 800_000,   "COUN": 1_000_000},
            TIER_MEET_LOW:  {"CO": 1_100_000, "COUN": 1_400_000},
            TIER_OVER:      {"CO": 1_100_000, "COUN": 1_400_000},
            "out_sys_co":    400_000,
            "out_sys_coun":  600_000,
        },
        SCHEME_CO_SUB: {
            TIER_UNDER:     {"CO": 700_000},
            TIER_MEET_HIGH: {"CO": 900_000},
            TIER_MEET_LOW:  {"CO": 900_000},
            TIER_OVER:      {"CO": 1_100_000},
            "out_sys_co":    400_000,
            "out_sys_coun":  600_000,
            "rmit_vn":       600_000,
        },
    }
    cfg.incentive_threshold = 5_000_000

    # ── Status rules ──────────────────────────────────────────────────────────
    statuses = [
        # status, counts, coun, co_d, co_s, carry, current, zero, fees_paid, rank
        ("Closed - Visa granted, then enrolled",   True,  1.0, 1.0, 1.0, False, False, False, False, 5),
        ("Closed - Enrolled, then Visa granted",   True,  0.0, 0.5, 0.5, True,  False, False, False, 3),
        ("Closed - Enrolment",                     True,  1.0, 1.0, 1.0, False, False, False, False, 4),
        ("Closed - Enrolment (only)",              True,  1.0, 1.0, 1.0, False, False, False, False, 4),
        ("Closed - Visa granted",                  False, 1.0, 1.0, 0.0, False, False, False, False, 0),
        ("Closed - Visa granted (visa only)",      False, 1.0, 1.0, 0.0, False, False, False, False, 0),
        ("Closed - Visa granted (plus enrolled)",  True,  1.0, 1.0, 1.0, False, False, False, False, 5),
        ("Closed - Visa granted then cancelled",   False, 0.0, 0.0, 0.0, False, False, False, True,  1),
        ("Closed - Visa refused",                  False, 0.0, 0.0, 0.0, False, False, True,  False, 0),
        ("Closed - Visa refused then granted",     True,  1.0, 1.0, 1.0, False, False, False, False, 5),
        ("Closed - Cancelled",                     False, 0.0, 0.0, 0.0, False, False, False, True,  1),
        ("Closed - Enrolled then cancelled",       False, 0.0, 0.0, 0.0, False, False, True,  False, 1),
        ("Closed - Institution refused",           False, 0.0, 0.0, 0.0, False, False, True,  False, 0),
        ("Current - Enrolled",                     False, 1.0, 0.5, 0.5, False, True,  False, False, 2),
        ("Current - Visa refused",                 False, 0.0, 0.0, 0.0, False, False, True,  False, 0),
        ("Pending - Visa refused",                 False, 0.0, 0.0, 0.0, False, False, True,  False, 0),
    ]
    for s in statuses:
        cfg.status_rules[s[0].lower()] = StatusRuleObj(
            status=s[0], counts_as_enrolled=s[1],
            coun_pct=s[2], co_direct_pct=s[3], co_sub_pct=s[4],
            is_carry_over=s[5], is_current_enrolled=s[6],
            is_zero_bonus=s[7], fees_paid_non_enrolled=s[8], dedup_rank=s[9],
        )

    # ── Service fees ──────────────────────────────────────────────────────────
    fees = [
        # code, co_bonus, coun_bonus, category
        ("VISA_ONLY",                   200_000,  400_000, SVC_SERVICE_FEE),
        ("VISA_485",                    400_000,  600_000, SVC_SERVICE_FEE),
        ("VISA_RENEWAL",                250_000,  250_000, SVC_SERVICE_FEE),
        ("VISA_RENEWAL_SUPPORT",        250_000,        0, SVC_SERVICE_FEE),
        ("STUDY_PERMIT_RENEWAL",        250_000,  250_000, SVC_SERVICE_FEE),
        ("CAQ",                         250_000,  250_000, SVC_SERVICE_FEE),
        ("EXTRA_SCHOOL",                250_000,  250_000, SVC_SERVICE_FEE),
        ("VISITOR_EXCHANGE",            250_000,  250_000, SVC_SERVICE_FEE),
        ("CANCELLED_FULL_SERVICE",      400_000,  400_000, SVC_SERVICE_FEE),
        ("GUARDIAN_GRANTED",            500_000,  500_000, SVC_SERVICE_FEE),
        ("GUARDIAN_REFUSED",            250_000,  250_000, SVC_SERVICE_FEE),
        ("DEPENDANT_GRANTED",           500_000,  500_000, SVC_SERVICE_FEE),
        ("DEPENDANT_REFUSED",           250_000,  250_000, SVC_SERVICE_FEE),
        ("AP_STANDARD_PLUS_3TR",              0,        0, SVC_SERVICE_FEE),
        ("MGMT_EXCEPTION",                    0,        0, SVC_SERVICE_FEE),
        ("NO_COMM",                           0,        0, SVC_SERVICE_FEE),
        # Packages (stack on tier rate)
        ("Superior Package (6tr)",      500_000, 1_000_000, SVC_PACKAGE),
        ("superior Package 8tr",        500_000, 1_000_000, SVC_PACKAGE),
        ("Premium Package (9tr)",       500_000, 1_500_000, SVC_PACKAGE),
        ("Standard Package (16tr)",     500_000, 1_000_000, SVC_PACKAGE),
        ("Standard Package (9tr5)",     500_000, 1_000_000, SVC_PACKAGE),
        ("SDS (7tr5)",                  500_000, 1_000_000, SVC_PACKAGE),
        ("SDS (6tr5)",                  500_000, 1_000_000, SVC_PACKAGE),
        ("Standard Master (15tr)",    1_500_000, 1_500_000, SVC_PACKAGE),
        ("Premium Canada (14tr)",       500_000, 1_000_000, SVC_PACKAGE),
        ("Standard Plus (3tr)",               0,        0, SVC_PACKAGE),
        # Contract category — fee-collected detection
        ("CAN_SDS_7TR5",                      0,  500_000, SVC_CONTRACT),
        ("CAN_REGULAR_9TR5",                  0,  500_000, SVC_CONTRACT),
        ("US_STANDARD_16TR",                  0, 1_000_000, SVC_CONTRACT),
        ("OUT_SYSTEM_30TR",                   0,        0, SVC_CONTRACT),
        ("DIFFICULT_CASE_20TR",       1_100_000, 1_100_000, SVC_CONTRACT),
        # ADDON
        ("GUARDIAN_AU_ADDON",           125_000,  125_000, SVC_ADDON),
    ]
    for (code, co_b, coun_b, cat) in fees:
        cfg.service_fees[code.lower()] = ServiceFeeRuleObj(
            code=code, co_bonus=co_b, coun_bonus=coun_b,
            category=cat, active=True
        )

    # ── Staff targets ─────────────────────────────────────────────────────────
    st_yen = StaffTargetObj(name="Quan Hoàng Yến", office="HCM",
                             role="CO", scheme=SCHEME_HCM_DIRECT)
    st_yen.targets = {y: {m: (6 if m <= 8 else 5) for m in range(1, 13)}
                      for y in [2024, 2025]}
    cfg.staff_targets["quan hoàng yến"] = st_yen
    cfg.staff_targets["quan hoang yen"] = st_yen
    cfg.staff_targets["hoàng yến"]      = st_yen

    st_an = StaffTargetObj(name="Lê Thị Trường An", office="HCM",
                            role="CO", scheme=SCHEME_CO_SUB)
    st_an.targets = {y: {m: 13 for m in range(1, 13)}
                     for y in [2024, 2025]}
    cfg.staff_targets["lê thị trường an"] = st_an
    cfg.staff_targets["le thi truong an"] = st_an
    cfg.staff_targets["trường an"]        = st_an

    # ── Priority institutions (default = 0 YTD; override per-test below) ────
    priorities = [
        # name, bonus_pct, annual_target
        ("Department of Education and Early Chilhood Development, Victoria (VIC DET)", 0.20, 15),
        ("vic det",                                              0.20, 15),
        ("RMIT University",                                      0.20,  8),
        ("Monash University",                                    0.50, 10),
        ("University of Western Australia (UWA)",                0.70,  8),
        ("University of Western Australia",                      0.70,  8),
        ("The University of Adelaide",                           0.70, 14),
        ("University of South Australia (UniSA)",                0.70, 14),
        ("Australian Catholic University - ACU",                 0.25,  6),
        ("La Trobe University",                                  0.60,  8),
        ("Deakin University",                                    0.25,  6),
        ("Macquarie University",                                 0.30, 10),
        ("The University of New South Wales - UNSW",             0.25,  5),
        ("The University of Queensland",                         0.40,  6),
        ("Cape Breton University (CBU)",                         0.50,  5),
        ("Swinburne University of Technology",                   0.20, 14),
        ("Curtin University",                                    0.30,  6),
    ]
    for (name, pct, tgt) in priorities:
        cfg.priority_instns.append(PriorityInstitutionObj(
            name=name, bonus_pct=pct, annual_target=tgt, achieved_ytd=0
        ))


    # ── Country codes ─────────────────────────────────────────────────────────
    countries = [
        ("Australia",   "AU", False, False),
        ("Canada",      "CA", False, False),
        ("USA",         "US", False, False),
        ("United States","US", False, False),
        ("UK",          "UK", False, False),
        ("United Kingdom","UK", False, False),
        ("New Zealand", "NZ", False, False),
        ("Singapore",   "SG", False, False),
        ("Germany",     "DE", False, False),
        ("Vietnam",     "VN", False, True),
        ("Viet Nam",    "VN", False, True),
        ("Thailand",    "TH", True,  False),
        ("Malaysia",    "MY", True,  False),
        ("Philippines", "PH", True,  False),
    ]
    for name, code, flat, vn in countries:
        cfg.country_codes[name.lower()] = CountryRuleObj(
            crm_text=name, code=code,
            is_flat_country=flat, is_vietnam=vn
        )

    # ── Client type map ───────────────────────────────────────────────────────
    cfg.client_types = {
        "du học (ghi danh + visa)":     CT_DU_HOC_FULL,
        "du học (chỉ ghi danh)":        CT_DU_HOC_ENROL,
        "du học hè":                    CT_SUMMER,
        "summer study":                 CT_SUMMER,
        "vietnam domestic":             CT_VIETNAM,
        "guardian visa":                CT_GUARDIAN,
        "tourist visa":                 CT_TOURIST,
        "migration visa":               CT_MIGRATION,
        "dependant visa":               CT_DEPENDANT,
        "visa only service":            CT_VISA_ONLY,
    }

    # ── Staff name map ────────────────────────────────────────────────────────
    cfg.staff_name_map = {
        "quan hoàng yến":   "Quan Hoàng Yến",
        "quan hoang yen":   "Quan Hoàng Yến",
        "hoàng yến":        "Quan Hoàng Yến",
        "lê thị trường an": "Lê Thị Trường An",
        "le thi truong an": "Lê Thị Trường An",
        "trường an":        "Lê Thị Trường An",
    }
    return cfg


def set_priority_ytd(cfg: BonusConfig, ytd_overrides: dict):
    """Reset all to 0 then apply overrides for priority institutions (per-test)."""
    for p in cfg.priority_instns:
        p.achieved_ytd = 0
    for p in cfg.priority_instns:
        for key, val in ytd_overrides.items():
            if key.lower() in p.name.lower():
                p.achieved_ytd = val
                break


def run_test(filepath, year, month, staff_name, is_counsellor,
             scheme, expected_enrolled, expected_priority,
             cfg: BonusConfig, customer_incentive=0):

    print(f"\n{'='*70}")
    print(f" TEST: {staff_name}  |  {month:02d}/{year}")
    print(f" Expected: Enr={expected_enrolled:,}  Pri={expected_priority:,}  "
          f"Total={expected_enrolled+expected_priority:,}")
    print(f"{'='*70}")

    cases_raw, meta = read_baocao(filepath, year, month, scheme, customer_incentive)
    print(f" Rows: {meta['total_rows_read']} cases + "
          f"{len([c for c in cases_raw if c.is_addon])} addons")
    print(f" File totals: Enr={meta['actual_total_enrolled']:,}  "
          f"Pri={meta['actual_total_priority']:,}")

    cases_dicts = [to_engine_dict(c, scheme) for c in cases_raw]
    records     = build_case_records(cases_dicts, cfg)

    results, tier, target, enrolled_count = calculate_bonuses(
        records, staff_name, year, month, cfg,
        is_counsellor=is_counsellor,
        office=("HCM" if "HCM" in scheme or scheme == "CO_SUB" else "HN"),
    )

    total_enrolled = sum(r.bonus_enrolled for r in results if r.row_type != "ADDON")
    total_priority = sum(r.bonus_priority for r in results)

    print(f"\n TIER: {tier}  |  Target: {target}  |  Enrolled count: {enrolled_count}")
    print(f"\n {'No':<4} {'Student':<25} {'Status':<35} {'Enr':>10} {'Pri':>8}")
    print(f" {'-'*4} {'-'*25} {'-'*35} {'-'*10} {'-'*8}")
    for r in results:
        if r.row_type == "ADDON":
            print(f" {'':4} {'  + ADDON':<25} {r.addon_code:<35} {r.bonus_enrolled:>10,}")
            continue
        print(f" {(r.original_no or ''):<4} {(r.student_name or '')[:25]:<25} "
              f"{(r.app_status or '')[:35]:<35} "
              f"{r.bonus_enrolled:>10,} {r.bonus_priority:>8,}")
        if r.note_enrolled:
            print(f"        → {r.note_enrolled[:90]}")

    print(f"\n {'TOTAL ENGINE':>30}: Enr {total_enrolled:>11,}  Pri {total_priority:>11,}")
    print(f" {'TOTAL EXPECTED':>30}: Enr {expected_enrolled:>11,}  Pri {expected_priority:>11,}")

    ok_e = total_enrolled == expected_enrolled
    ok_p = total_priority == expected_priority
    diff_e = total_enrolled - expected_enrolled
    diff_p = total_priority - expected_priority

    print(f"\n {'✅' if ok_e else '❌'} Enrolled diff: {diff_e:+,}")
    print(f" {'✅' if ok_p else '❌'} Priority diff: {diff_p:+,}")
    print(f" {'✅ PASS' if (ok_e and ok_p) else '❌ FAIL'}")
    return ok_e and ok_p


if __name__ == "__main__":
    PROJECT = "/mnt/project"
    cfg = build_config()

    results = []

    # Jan 2024: low YTD across the board (start of year)
    set_priority_ytd(cfg, {})  # all 0

    ok1 = run_test(
        filepath    = f"{PROJECT}/Báo_cáo_Quan_Hoàng_Yến_tháng_01_2024_VP_HCM.xlsx",
        year=2024, month=1,
        staff_name  = "Quan Hoàng Yến",
        is_counsellor = False,
        scheme      = SCHEME_HCM_DIRECT,
        expected_enrolled = 6_050_000,
        expected_priority =    80_000,
        cfg         = cfg,
        customer_incentive = 0,
    )
    results.append(("Hoàng Yến Jan 2024 HCM", ok1))

    # Jul 2024: by mid-year, RMIT and VIC DET targets achieved
    set_priority_ytd(cfg, {
        "rmit university": 8,
        "vic det":         15,
        "victoria (vic det)": 15,
    })

    ok2 = run_test(
        filepath    = f"{PROJECT}/Báo_cáo_Lê_Thị_Trường_An_tháng_07_2024.xlsx",
        year=2024, month=7,
        staff_name  = "Lê Thị Trường An",
        is_counsellor = False,
        scheme      = SCHEME_CO_SUB,
        expected_enrolled = 15_850_000,
        expected_priority =  1_911_250,
        cfg         = cfg,
        customer_incentive = 0,
    )
    results.append(("Lê Thị Trường An Jul 2024", ok2))

    print(f"\n{'='*70}")
    print(" SUMMARY")
    print(f"{'='*70}")
    for name, passed in results:
        print(f" {'✅ PASS' if passed else '❌ FAIL'}  {name}")
    p = sum(1 for _, x in results if x)
    print(f"\n {p}/{len(results)} tests passed")
