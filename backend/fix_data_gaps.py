import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import PriorityInstitution, CountryRate, ServiceFeeRate
from datetime import date

db = SessionLocal()
START = date(2021, 9, 1)

# =============================================================================
# FIX 1: Priority Institution bonus_pct — update from 0% to correct values
# Source: Priority_2024__final__v2.pdf
# =============================================================================
print("Fixing priority institution bonus percentages...")

BONUS_PCT_MAP = {
    "Australian Catholic University (ACU)":                      0.25,
    "Curtin University":                                         0.30,
    "Deakin University":                                         0.25,
    "Education Queensland International (EQI)":                 0.30,
    "Griffith University":                                       0.30,
    "James Cook University Brisbane (JCUB)":                    0.20,
    "Kaplan Business School Australia":                         0.20,
    "La Trobe University":                                       0.60,
    "Macquarie University":                                      0.30,
    "Monash University":                                         0.50,
    "RMIT University":                                           0.20,
    "Swinburne University of Technology":                       0.20,
    "The University of Adelaide":                               0.70,
    "The University of New South Wales (UNSW)":                 0.25,
    "The University of Queensland":                             0.40,
    "University of Newcastle":                                   0.20,
    "University of South Australia (UniSA)":                    0.70,
    "University of Tasmania (UTAS)":                            0.25,
    "University of Technology Sydney (UTS)":                    0.30,
    "University of Western Australia (UWA)":                    0.70,
    "VIC DET (Dept of Education & Training, VIC)":              0.20,
    "Griffith College (Navitas)":                               0.40,
    "WSU College / WSU Sydney City (Navitas)":                  0.40,
    "Other Navitas AU: Eynesbury, CC, ECUC, SAIBT, DC, LC, WSUIC, GC": 0.30,
    "Algonquin College":                                         0.30,
    "Cape Breton University (CBU)":                             0.50,
    "Braemar College":                                           0.30,
    "Toronto Metropolitan University":                          0.20,
    "University of Guelph":                                      0.40,
    "University of Regina":                                      0.30,
    "ICM (Navitas)":                                             0.40,
    "Toronto Met Uni Intl College (Navitas)":                   0.40,
    "Other Navitas CA: FIC, ULIC, WLIC":                        0.30,
    "ENZ (any NZ providers)":                                    0.40,
    "LightPath":                                                 0.40,
    "Other Navitas NZ: UCIC":                                    0.30,
    "Raffles Education Network":                                 0.20,
    "Nanyang Institute of Management (NIM)":                    0.20,
}

updated = 0
not_found = []
for inst_name, pct in BONUS_PCT_MAP.items():
    row = db.query(PriorityInstitution).filter(
        PriorityInstitution.institution_name == inst_name
    ).first()
    if row:
        row.bonus_pct = pct
        updated += 1
    else:
        not_found.append(inst_name)

db.commit()
print(f"✅ Updated bonus_pct for {updated} priority institutions")
if not_found:
    print(f"⚠️  Not found in DB: {not_found}")


# =============================================================================
# FIX 2: Add South Korea to Country Rates
# Policy: "2 Thái Lan, Hàn Quốc, Malay = 1 In-system Full service"
# South Korea = flat-rate, no target, same structure as Thailand/Philippines
# =============================================================================
print("\nAdding South Korea to country rates...")

# Check if already exists
existing = db.query(CountryRate).filter(
    CountryRate.country_code == "KR"
).first()

if not existing:
    for scheme, coun_amt, co_amt, desc in [
        ("HCM_DIRECT", 1_000_000, 500_000, "HCM — South Korea no target. 2 no-target = 1 in-system target"),
        ("HN_DIRECT",  800_000,   400_000, "HN/DN — South Korea no target. 2 no-target = 1 in-system target"),
        ("CO_SUB",     0,         300_000, "CO Sub — South Korea fixed rate"),
    ]:
        db.add(CountryRate(
            country_name="South Korea",
            country_code="KR",
            scheme=scheme,
            rate_type="FLAT",
            coun_amount=coun_amt,
            co_amount=co_amt,
            counts_toward_target=False,
            description=desc,
            start_date=START,
            is_active=True,
        ))
    db.commit()
    print("✅ Added South Korea (KR) to country rates — 3 rows (HCM, HN, CO_SUB)")
else:
    print("⏭  South Korea already exists in country rates")


# =============================================================================
# FIX 3: Standard Plus (AP 3M deposit) — set coun_bonus to 0
# Policy: "gói phí dịch vụ chỉ thu cọc KH (ví dụ gói Standard Plus của Úc
# đóng cọc 3 triệu) thì sẽ không được nhận bonus"
# =============================================================================
print("\nFixing Standard Plus bonus (deposit-only — no bonus)...")

row = db.query(ServiceFeeRate).filter(
    ServiceFeeRate.service_code == "AP_STANDARD_PLUS_3TR"
).first()

if row:
    row.coun_bonus = 0
    row.co_bonus = 0
    row.note = "Deposit-only package — NO bonus per policy (gói chỉ thu cọc)"
    db.commit()
    print("✅ AP_STANDARD_PLUS_3TR bonus set to 0 (deposit-only, no bonus)")
else:
    print("⚠️  AP_STANDARD_PLUS_3TR not found in service fee rates")


print("\n✅ All fixes applied successfully!")
db.close()
