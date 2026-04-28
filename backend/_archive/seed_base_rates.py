import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import BaseRate, SpecialRate, CountryRate
from datetime import date

db = SessionLocal()

# Effective date — Sep 2021 per source workbook
START = date(2021, 9, 1)

# =============================================================================
# CLEAR EXISTING
# =============================================================================
d1 = db.query(BaseRate).delete()
d2 = db.query(SpecialRate).delete()
d3 = db.query(CountryRate).delete()
db.commit()
print(f"Cleared: {d1} base rates, {d2} special rates, {d3} country rates\n")

# =============================================================================
# BASE RATES
# Tiers:
#   OUT_SYS    = Out-system / fees paid yet visa refused / extra high risk
#   VISA_ONLY  = Visa only (first visa) — CO only
#   UNDER      = Sub referrals / enrol thru agent / under target
#   MEET_HIGH  = Meet target AND incentive < 5,000,000 (higher per-case rate)
#   MEET_LOW   = Meet target AND incentive >= 5,000,000 (lower per-case rate)
#   OVER       = Over target (ALL cases)
#
# Schemes:
#   HCM_DIRECT = Section A: HCM office counsellor/CO direct
#   HN_DIRECT  = Section C: HN/DN office counsellor/CO direct
#   CO_SUB     = Section B: CO for sub-agents
# =============================================================================

BASE_RATES = [

    # -------------------------------------------------------------------------
    # SECTION A: HCM DIRECT
    # Country group: AUS, NZ, SG, US, CAN, UK & Europe
    # -------------------------------------------------------------------------
    {"scheme": "HCM_DIRECT", "tier": "OUT_SYS",   "role": "COUN", "amount":   600_000, "description": "HCM Direct — Out-system / Fees paid visa refused / Extra high risk — Counsellor"},
    {"scheme": "HCM_DIRECT", "tier": "OUT_SYS",   "role": "CO",   "amount":   400_000, "description": "HCM Direct — Out-system / Fees paid visa refused / Extra high risk — CO"},
    {"scheme": "HCM_DIRECT", "tier": "VISA_ONLY",  "role": "CO",   "amount":   600_000, "description": "HCM Direct — Visa only (first visa) — CO only"},
    {"scheme": "HCM_DIRECT", "tier": "UNDER",      "role": "COUN", "amount": 1_000_000, "description": "HCM Direct — Sub referrals / Enrol thru agent / Under target — Counsellor"},
    {"scheme": "HCM_DIRECT", "tier": "UNDER",      "role": "CO",   "amount":   800_000, "description": "HCM Direct — Sub referrals / Enrol thru agent / Under target — CO"},
    {"scheme": "HCM_DIRECT", "tier": "MEET_LOW",   "role": "COUN", "amount": 1_400_000, "description": "HCM Direct — Meet target, incentive >= 5M — Counsellor"},
    {"scheme": "HCM_DIRECT", "tier": "MEET_LOW",   "role": "CO",   "amount": 1_000_000, "description": "HCM Direct — Meet target, incentive >= 5M — CO"},
    {"scheme": "HCM_DIRECT", "tier": "MEET_HIGH",  "role": "COUN", "amount": 1_800_000, "description": "HCM Direct — Meet target, incentive < 5M — Counsellor"},
    {"scheme": "HCM_DIRECT", "tier": "MEET_HIGH",  "role": "CO",   "amount": 1_400_000, "description": "HCM Direct — Meet target, incentive < 5M — CO"},
    {"scheme": "HCM_DIRECT", "tier": "OVER",       "role": "COUN", "amount": 2_200_000, "description": "HCM Direct — Over target (ALL cases) — Counsellor"},
    {"scheme": "HCM_DIRECT", "tier": "OVER",       "role": "CO",   "amount": 1_800_000, "description": "HCM Direct — Over target (ALL cases) — CO"},

    # -------------------------------------------------------------------------
    # SECTION B: CO SUB-AGENTS
    # Country group: AUS, NZ, SG, US, CAN, UK & Europe
    # -------------------------------------------------------------------------
    # Enrol only thru partner (out-sys, sub does visa) — Fixed rate
    {"scheme": "CO_SUB",     "tier": "PARTNER",    "role": "CO",   "amount":   400_000, "description": "CO Sub — Enrol only thru partner (out-sys, sub does visa) — Fixed"},
    # Enrolment only in-system (sub does visa)
    {"scheme": "CO_SUB",     "tier": "UNDER",      "role": "CO",   "amount":   700_000, "description": "CO Sub — Enrolment only in-system, sub does visa — Under target"},
    {"scheme": "CO_SUB",     "tier": "MEET_HIGH",  "role": "CO",   "amount":   900_000, "description": "CO Sub — Enrolment only in-system, sub does visa — Meet target"},
    {"scheme": "CO_SUB",     "tier": "OVER",       "role": "CO",   "amount": 1_100_000, "description": "CO Sub — Enrolment only in-system, sub does visa — Over target"},
    # Enrolment + visa in-system (CO full service)
    {"scheme": "CO_SUB",     "tier": "UNDER_FULL", "role": "CO",   "amount":   800_000, "description": "CO Sub — Enrolment + visa in-system (full service) — Under target"},
    {"scheme": "CO_SUB",     "tier": "MEET_FULL",  "role": "CO",   "amount": 1_100_000, "description": "CO Sub — Enrolment + visa in-system (full service) — Meet target"},
    {"scheme": "CO_SUB",     "tier": "OVER_FULL",  "role": "CO",   "amount": 1_300_000, "description": "CO Sub — Enrolment + visa in-system (full service) — Over target"},

    # -------------------------------------------------------------------------
    # SECTION C: HN/DN DIRECT
    # Country group: AUS, NZ, SG, US, CAN, UK & Europe
    # -------------------------------------------------------------------------
    {"scheme": "HN_DIRECT",  "tier": "OUT_SYS",   "role": "COUN", "amount":   600_000, "description": "HN/DN Direct — Out-system / Fees paid visa refused / Extra high risk — Counsellor"},
    {"scheme": "HN_DIRECT",  "tier": "OUT_SYS",   "role": "CO",   "amount":   400_000, "description": "HN/DN Direct — Out-system / Fees paid visa refused / Extra high risk — CO"},
    {"scheme": "HN_DIRECT",  "tier": "VISA_ONLY",  "role": "CO",   "amount":   600_000, "description": "HN/DN Direct — Visa only (first visa) — CO only"},
    {"scheme": "HN_DIRECT",  "tier": "UNDER",      "role": "COUN", "amount":   900_000, "description": "HN/DN Direct — Under target / No target / Sub referrals — Counsellor"},
    {"scheme": "HN_DIRECT",  "tier": "UNDER",      "role": "CO",   "amount":   700_000, "description": "HN/DN Direct — Under target / No target / Sub referrals — CO"},
    {"scheme": "HN_DIRECT",  "tier": "MEET_LOW",   "role": "COUN", "amount": 1_000_000, "description": "HN/DN Direct — Meet target, incentive >= 5M — Counsellor"},
    {"scheme": "HN_DIRECT",  "tier": "MEET_LOW",   "role": "CO",   "amount":   800_000, "description": "HN/DN Direct — Meet target, incentive >= 5M — CO"},
    {"scheme": "HN_DIRECT",  "tier": "MEET_HIGH",  "role": "COUN", "amount": 1_400_000, "description": "HN/DN Direct — Meet target, incentive < 5M — Counsellor"},
    {"scheme": "HN_DIRECT",  "tier": "MEET_HIGH",  "role": "CO",   "amount": 1_100_000, "description": "HN/DN Direct — Meet target, incentive < 5M — CO"},
    {"scheme": "HN_DIRECT",  "tier": "OVER",       "role": "COUN", "amount": 1_700_000, "description": "HN/DN Direct — Over target (ALL cases) — Counsellor"},
    {"scheme": "HN_DIRECT",  "tier": "OVER",       "role": "CO",   "amount": 1_300_000, "description": "HN/DN Direct — Over target (ALL cases) — CO"},
]

for r in BASE_RATES:
    db.add(BaseRate(
        scheme=r["scheme"], tier=r["tier"], role=r["role"],
        amount=r["amount"], start_date=START,
        description=r["description"], is_active=True,
    ))
db.commit()
print(f"✅ Loaded {len(BASE_RATES)} base rates")


# =============================================================================
# SPECIAL RATES
# Fixed rates that bypass tier calculation entirely
# =============================================================================

SPECIAL_RATES = [
    # --- HCM & HN DIRECT: RMIT VN / BUV VN (under/post-grad) ---
    {"rate_code": "RMIT_VN",           "rate_name": "RMIT VN / BUV VN (under/post-grad)",          "scheme": "HCM_DIRECT", "role": "COUN", "amount": 1_000_000, "institution_pattern": "rmit|buv",   "conditions": "VN institution, under/post-grad program"},
    {"rate_code": "RMIT_VN_HN",        "rate_name": "RMIT VN / BUV VN (under/post-grad) HN",       "scheme": "HN_DIRECT",  "role": "COUN", "amount": 1_000_000, "institution_pattern": "rmit|buv",   "conditions": "VN institution, under/post-grad program"},
    {"rate_code": "RMIT_VN_SUB",       "rate_name": "RMIT VN / BUV VN (under/post-grad) Sub",      "scheme": "CO_SUB",     "role": "CO",   "amount":   600_000, "institution_pattern": "rmit|buv",   "conditions": "VN institution, under/post-grad program"},

    # --- OTHER VN programs / RMIT Eng / BUV Eng ---
    {"rate_code": "OTHER_VN",          "rate_name": "Other VN programs / RMIT Eng / BUV Eng",       "scheme": "HCM_DIRECT", "role": "COUN", "amount":   500_000, "institution_pattern": None,          "conditions": "VN program, English or other"},
    {"rate_code": "OTHER_VN_HN",       "rate_name": "Other VN programs / RMIT Eng / BUV Eng HN",    "scheme": "HN_DIRECT",  "role": "COUN", "amount":   500_000, "institution_pattern": None,          "conditions": "VN program, English or other"},
    {"rate_code": "OTHER_VN_SUB",      "rate_name": "Other VN programs Sub",                         "scheme": "CO_SUB",     "role": "CO",   "amount":   300_000, "institution_pattern": None,          "conditions": "VN program"},

    # --- Summer study (du hoc he) ---
    {"rate_code": "SUMMER",            "rate_name": "Summer study (du hoc he)",                      "scheme": "HCM_DIRECT", "role": "COUN", "amount":   600_000, "client_type_code": "SUMMER_STUDY",  "conditions": "Summer study program"},
    {"rate_code": "SUMMER_HN",         "rate_name": "Summer study (du hoc he) HN",                   "scheme": "HN_DIRECT",  "role": "COUN", "amount":   600_000, "client_type_code": "SUMMER_STUDY",  "conditions": "Summer study program"},
    {"rate_code": "SUMMER_SUB",        "rate_name": "Summer study Sub",                              "scheme": "CO_SUB",     "role": "CO",   "amount":   300_000, "client_type_code": "SUMMER_STUDY",  "conditions": "Summer study program"},

    # --- Visa 485 ---
    {"rate_code": "VISA_485_COUN",     "rate_name": "Visa 485 — Counsellor",                         "scheme": "ALL",        "role": "COUN", "amount":   400_000, "client_type_code": "VISA_485",       "conditions": "Visa 485 application"},
    {"rate_code": "VISA_485_CO",       "rate_name": "Visa 485 — CO",                                 "scheme": "ALL",        "role": "CO",   "amount":   600_000, "client_type_code": "VISA_485",       "conditions": "Visa 485 application"},

    # --- Guardian (Giam ho) ---
    {"rate_code": "GUARDIAN_G_COUN",   "rate_name": "Guardian (Giam ho) — Granted — Counsellor",    "scheme": "ALL",        "role": "COUN", "amount":   500_000, "client_type_code": "GUARDIAN_G",     "conditions": "Guardian visa granted. Counsellor only involved if lodging visa with student"},
    {"rate_code": "GUARDIAN_G_CO",     "rate_name": "Guardian (Giam ho) — Granted — CO",             "scheme": "ALL",        "role": "CO",   "amount":   600_000, "client_type_code": "GUARDIAN_G",     "conditions": "Guardian visa granted"},
    {"rate_code": "GUARDIAN_G_SUB",    "rate_name": "Guardian (Giam ho) — Granted — CO Sub",         "scheme": "CO_SUB",     "role": "CO",   "amount":   600_000, "client_type_code": "GUARDIAN_G",     "conditions": "Guardian granted — CO Sub rate"},
    {"rate_code": "GUARDIAN_R_COUN",   "rate_name": "Guardian (Giam ho) — Refused — Counsellor",    "scheme": "ALL",        "role": "COUN", "amount":   200_000, "client_type_code": "GUARDIAN_R",     "conditions": "Guardian visa refused"},
    {"rate_code": "GUARDIAN_R_CO",     "rate_name": "Guardian (Giam ho) — Refused — CO",             "scheme": "ALL",        "role": "CO",   "amount":   300_000, "client_type_code": "GUARDIAN_R",     "conditions": "Guardian visa refused"},
    {"rate_code": "GUARDIAN_R_SUB",    "rate_name": "Guardian (Giam ho) — Refused — CO Sub",         "scheme": "CO_SUB",     "role": "CO",   "amount":   300_000, "client_type_code": "GUARDIAN_R",     "conditions": "Guardian refused — CO Sub rate"},

    # --- Guardian from AUS (Aug 2022+) ---
    {"rate_code": "GUARDIAN_AUS_CO",   "rate_name": "Guardian from AUS (Aug 2022+) — CO",            "scheme": "HCM_DIRECT", "role": "CO",   "amount":   250_000, "client_type_code": "GUARDIAN_AUS",   "conditions": "Guardian UC from Aug 2022 onwards"},
    {"rate_code": "GUARDIAN_AUS_HN",   "rate_name": "Guardian from AUS (Aug 2022+) — CO HN",         "scheme": "HN_DIRECT",  "role": "CO",   "amount":   250_000, "client_type_code": "GUARDIAN_AUS",   "conditions": "Guardian UC from Aug 2022 onwards"},
    {"rate_code": "GUARDIAN_AUS_SUB",  "rate_name": "Guardian from AUS (Aug 2022+) Enrol+Visa Sub",  "scheme": "CO_SUB",     "role": "CO",   "amount":   250_000, "client_type_code": "GUARDIAN_AUS",   "conditions": "Guardian from AUS Aug 2022+ enrol+visa"},

    # --- Dependant (Nguoi phu thuoc) ---
    {"rate_code": "DEPEND_G_COUN",     "rate_name": "Dependant (Nguoi phu thuoc) — Granted — Counsellor", "scheme": "ALL", "role": "COUN", "amount": 300_000, "client_type_code": "DEPEND_G",     "conditions": "Dependant visa granted. Counsellor only involved if lodging visa"},
    {"rate_code": "DEPEND_G_CO",       "rate_name": "Dependant (Nguoi phu thuoc) — Granted — CO",    "scheme": "ALL",        "role": "CO",   "amount":   400_000, "client_type_code": "DEPEND_G",       "conditions": "Dependant visa granted"},
    {"rate_code": "DEPEND_G_SUB",      "rate_name": "Dependant (Nguoi phu thuoc) — Granted — CO Sub","scheme": "CO_SUB",     "role": "CO",   "amount":   400_000, "client_type_code": "DEPEND_G",       "conditions": "Dependant granted — CO Sub rate"},
    {"rate_code": "DEPEND_R_COUN",     "rate_name": "Dependant (Nguoi phu thuoc) — Refused — Counsellor", "scheme": "ALL", "role": "COUN", "amount": 150_000, "client_type_code": "DEPEND_R",     "conditions": "Dependant visa refused"},
    {"rate_code": "DEPEND_R_CO",       "rate_name": "Dependant (Nguoi phu thuoc) — Refused — CO",    "scheme": "ALL",        "role": "CO",   "amount":   150_000, "client_type_code": "DEPEND_R",       "conditions": "Dependant visa refused"},
    {"rate_code": "DEPEND_R_SUB",      "rate_name": "Dependant (Nguoi phu thuoc) — Refused — CO Sub","scheme": "CO_SUB",     "role": "CO",   "amount":   200_000, "client_type_code": "DEPEND_R",       "conditions": "Dependant refused — CO Sub rate"},

    # --- Student visa renewal / extension AUS NZ ---
    {"rate_code": "VISA_RENEWAL_CO",   "rate_name": "Student visa renewal/extension — AUS NZ — CO", "scheme": "ALL",        "role": "CO",   "amount":   400_000, "client_type_code": "VISA_RENEWAL",   "conditions": "Student visa renewal or extension, AUS/NZ only"},

    # --- Visitor/Exchange/Other admin ---
    {"rate_code": "ADMIN_CO",          "rate_name": "Visitor/Exchange/Business/Study permit renewal/Transfer/Guardian renewal/Enrol 1 more/CAQ/Change guardian or homestay — CO",
                                                                                                      "scheme": "ALL",        "role": "CO",   "amount":   250_000, "client_type_code": "ADMIN",          "conditions": "Coun gets split 50/50 when enrolling a school"},
    {"rate_code": "ADMIN_SUB_CO",      "rate_name": "Visitor/Exchange/Other admin — CO Sub",         "scheme": "CO_SUB",     "role": "CO",   "amount":   250_000, "client_type_code": "ADMIN",          "conditions": "Visitor/Exchange/Other admin — CO Sub fixed rate"},
]

for r in SPECIAL_RATES:
    db.add(SpecialRate(
        rate_code=r["rate_code"],
        rate_name=r["rate_name"],
        scheme=r.get("scheme", "ALL"),
        role=r.get("role", "ALL"),
        amount=r["amount"],
        institution_pattern=r.get("institution_pattern"),
        client_type_code=r.get("client_type_code"),
        conditions=r.get("conditions"),
        start_date=START,
        is_active=True,
    ))
db.commit()
print(f"✅ Loaded {len(SPECIAL_RATES)} special rates")


# =============================================================================
# COUNTRY RATES
# Flat-rate countries — Thailand, Philippines, Malaysia
# These do NOT count toward counsellor monthly target
# Note: 2 no-target cases = 1 in-system target
# =============================================================================

COUNTRY_RATES = [
    # HCM Direct
    {"country_name": "Thailand",     "country_code": "TH", "scheme": "HCM_DIRECT", "coun_amount": 1_000_000, "co_amount": 500_000, "description": "HCM — Thai/Phil/ML no target. 2 no-target = 1 in-system target"},
    {"country_name": "Philippines",  "country_code": "PH", "scheme": "HCM_DIRECT", "coun_amount": 1_000_000, "co_amount": 500_000, "description": "HCM — Thai/Phil/ML no target. 2 no-target = 1 in-system target"},
    {"country_name": "Malaysia",     "country_code": "MY", "scheme": "HCM_DIRECT", "coun_amount": 1_000_000, "co_amount": 500_000, "description": "HCM — Thai/Phil/ML no target. 2 no-target = 1 in-system target"},
    # HN Direct
    {"country_name": "Thailand",     "country_code": "TH", "scheme": "HN_DIRECT",  "coun_amount":   800_000, "co_amount": 400_000, "description": "HN/DN — Thai/Phil/ML no target. 2 no-target = 1 in-system target"},
    {"country_name": "Philippines",  "country_code": "PH", "scheme": "HN_DIRECT",  "coun_amount":   800_000, "co_amount": 400_000, "description": "HN/DN — Thai/Phil/ML no target. 2 no-target = 1 in-system target"},
    {"country_name": "Malaysia",     "country_code": "MY", "scheme": "HN_DIRECT",  "coun_amount":   800_000, "co_amount": 400_000, "description": "HN/DN — Thai/Phil/ML no target. 2 no-target = 1 in-system target"},
    # CO Sub
    {"country_name": "Thailand",     "country_code": "TH", "scheme": "CO_SUB",     "coun_amount":         0, "co_amount": 300_000, "description": "CO Sub — Thai/Phil/ML fixed rate"},
    {"country_name": "Philippines",  "country_code": "PH", "scheme": "CO_SUB",     "coun_amount":         0, "co_amount": 300_000, "description": "CO Sub — Thai/Phil/ML fixed rate"},
    {"country_name": "Malaysia",     "country_code": "MY", "scheme": "CO_SUB",     "coun_amount":         0, "co_amount": 300_000, "description": "CO Sub — Thai/Phil/ML fixed rate"},
]

for r in COUNTRY_RATES:
    db.add(CountryRate(
        country_name=r["country_name"],
        country_code=r["country_code"],
        scheme=r["scheme"],
        rate_type="FLAT",
        coun_amount=r["coun_amount"],
        co_amount=r["co_amount"],
        counts_toward_target=False,
        description=r["description"],
        start_date=START,
        is_active=True,
    ))
db.commit()
print(f"✅ Loaded {len(COUNTRY_RATES)} country rates")

print(f"\n✅ All rates loaded successfully!")
print(f"   Base rates:    {len(BASE_RATES)}")
print(f"   Special rates: {len(SPECIAL_RATES)}")
print(f"   Country rates: {len(COUNTRY_RATES)}")
db.close()
