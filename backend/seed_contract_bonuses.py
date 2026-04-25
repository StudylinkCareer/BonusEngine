import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import ContractBonus

db = SessionLocal()

deleted = db.query(ContractBonus).delete()
db.commit()
print(f"Cleared {deleted} existing contract bonuses\n")

CONTRACT_BONUSES = [
    {
        "package_name":    "Superior Package (gói Superior)",
        "service_fee_vnd": "6,000,000",
        "coun_bonus":      "1,000,000 at contract sign (clawback if visa refused)",
        "co_bonus":        "500,000 at enrolment",
        "timing":          "Split: contract sign + enrolment",
        "note":            "Source: AP Package PDF (gói 3 Superior)",
    },
    {
        "package_name":    "Premium Package (gói Premium)",
        "service_fee_vnd": "9,000,000",
        "coun_bonus":      "1,500,000 at contract sign (clawback if visa refused)",
        "co_bonus":        "500,000 at enrolment",
        "timing":          "Split: contract sign + enrolment",
        "note":            "Source: AP Package PDF (gói 4 Premium)",
    },
    {
        "package_name":    "Difficult case / Out-system full service",
        "service_fee_vnd": "20,000,000+",
        "coun_bonus":      "1,100,000 at contract sign (clawback if refused)",
        "co_bonus":        "500,000 at enrolment",
        "timing":          "Separate from tier bonus",
        "note":            "Counsellor gets sign bonus regardless",
    },
    {
        "package_name":    "Out-system full service (AUS)",
        "service_fee_vnd": "20,000,000",
        "coun_bonus":      "1,100,000 at contract sign",
        "co_bonus":        "500,000 at enrolment",
        "timing":          "Separate from tier bonus",
        "note":            "",
    },
    {
        "package_name":    "Guardian from AU (Aug 2022+)",
        "service_fee_vnd": "100 USD / 2,500,000",
        "coun_bonus":      "—",
        "co_bonus":        "250,000 split 50/50 with other CO",
        "timing":          "At file close",
        "note":            "Only if guardian from Australia side",
    },
    {
        "package_name":    "Guardian visa fee collected (VN to AU)",
        "service_fee_vnd": "500 USD / 12,000,000",
        "coun_bonus":      "—",
        "co_bonus":        "As per guardian rate table",
        "timing":          "At visa outcome",
        "note":            "G: 600k / F: 300k (sub scheme)",
    },
    {
        "package_name":    "Add-on service referral (Lovely Cup of Coffee)",
        "service_fee_vnd": "—",
        "coun_bonus":      "100,000 per referral",
        "co_bonus":        "—",
        "timing":          "At referral conversion",
        "note":            "Special partner program",
    },
]

for b in CONTRACT_BONUSES:
    db.add(ContractBonus(**b, is_active=True))

db.commit()
print(f"✅ Loaded {len(CONTRACT_BONUSES)} contract bonuses successfully!")
db.close()
