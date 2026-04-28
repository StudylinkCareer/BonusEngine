import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import BaseRate, IncentiveTier
from datetime import date

db = SessionLocal()
START = date(2021, 9, 1)

# =============================================================================
# FIX: MEET_HIGH and MEET_LOW rates were swapped in the database.
#
# CORRECT logic (from VBA code + Python engine):
#   MEET_HIGH fires when customer incentive >= threshold (e.g. >= 5,000,000)
#   MEET_LOW  fires when customer incentive <  threshold (e.g. <  5,000,000)
#
# CORRECT rates (from policy document 02_BASE_BONUS_RATES):
#   "Meet target -- incentive >= 5M" → LOWER per-case rate
#     (customer already got a high incentive → counsellor gets less per case)
#   "Meet target -- incentive < 5M"  → HIGHER per-case rate
#     (customer got low incentive → counsellor gets more per case)
#
# So:
#   MEET_HIGH → LOWER rates (1,400k COUN / 1,000k CO for HCM)
#   MEET_LOW  → HIGHER rates (1,800k COUN / 1,400k CO for HCM)
#
# Previous seed had these backwards. This script corrects them.
# =============================================================================

CORRECTED_MEET_RATES = [
    # HCM_DIRECT
    {"scheme": "HCM_DIRECT", "tier": "MEET_HIGH", "role": "COUN", "amount": 1_400_000,
     "description": "HCM Direct — Meet target, incentive >= 5M (LOWER rate) — Counsellor"},
    {"scheme": "HCM_DIRECT", "tier": "MEET_HIGH", "role": "CO",   "amount": 1_000_000,
     "description": "HCM Direct — Meet target, incentive >= 5M (LOWER rate) — CO"},
    {"scheme": "HCM_DIRECT", "tier": "MEET_LOW",  "role": "COUN", "amount": 1_800_000,
     "description": "HCM Direct — Meet target, incentive < 5M (HIGHER rate) — Counsellor"},
    {"scheme": "HCM_DIRECT", "tier": "MEET_LOW",  "role": "CO",   "amount": 1_400_000,
     "description": "HCM Direct — Meet target, incentive < 5M (HIGHER rate) — CO"},
    # HN_DIRECT
    {"scheme": "HN_DIRECT",  "tier": "MEET_HIGH", "role": "COUN", "amount": 1_000_000,
     "description": "HN/DN Direct — Meet target, incentive >= 5M (LOWER rate) — Counsellor"},
    {"scheme": "HN_DIRECT",  "tier": "MEET_HIGH", "role": "CO",   "amount":   800_000,
     "description": "HN/DN Direct — Meet target, incentive >= 5M (LOWER rate) — CO"},
    {"scheme": "HN_DIRECT",  "tier": "MEET_LOW",  "role": "COUN", "amount": 1_400_000,
     "description": "HN/DN Direct — Meet target, incentive < 5M (HIGHER rate) — Counsellor"},
    {"scheme": "HN_DIRECT",  "tier": "MEET_LOW",  "role": "CO",   "amount": 1_100_000,
     "description": "HN/DN Direct — Meet target, incentive < 5M (HIGHER rate) — CO"},
    # CO_SUB
    {"scheme": "CO_SUB",     "tier": "MEET_HIGH", "role": "CO",   "amount":   900_000,
     "description": "CO Sub — Enrolment only in-system, Meet target, incentive >= 5M"},
    {"scheme": "CO_SUB",     "tier": "MEET_LOW",  "role": "CO",   "amount":   900_000,
     "description": "CO Sub — Enrolment only in-system, Meet target, incentive < 5M"},
    # CO_SUB full service (MEET_FULL variants)
    {"scheme": "CO_SUB",     "tier": "MEET_FULL", "role": "CO",   "amount": 1_100_000,
     "description": "CO Sub — Enrolment + visa in-system (full service) — Meet target"},
]

updated = 0
for r in CORRECTED_MEET_RATES:
    row = db.query(BaseRate).filter(
        BaseRate.scheme == r["scheme"],
        BaseRate.tier   == r["tier"],
        BaseRate.role   == r["role"],
        BaseRate.is_active == True,
    ).first()
    if row:
        row.amount      = r["amount"]
        row.description = r["description"]
        updated += 1
    else:
        # Not found — insert it
        db.add(BaseRate(
            scheme=r["scheme"], tier=r["tier"], role=r["role"],
            amount=r["amount"], description=r["description"],
            start_date=START, is_active=True,
        ))
        updated += 1

db.commit()
print(f"✅ Fixed {updated} MEET_HIGH/MEET_LOW base rate records")


# =============================================================================
# SEED: IncentiveTier table — Customer Incentive Threshold
#
# PURPOSE: Controls the MEET_HIGH vs MEET_LOW tier split.
#   If customer incentive >= threshold → MEET_HIGH (lower per-case bonus)
#   If customer incentive <  threshold → MEET_LOW  (higher per-case bonus)
#
# WHY A TABLE: The threshold (currently 5,000,000 VND) is expected to change.
# By storing it here, the value can be updated without any code changes.
# Simply add a new active row with a new start_date and update the old
# row's end_date — the engine always uses the most recently started active record.
#
# FUTURE EXTENSIBILITY: Additional incentive types can be added as new rows
# with different type values (e.g. VOLUME_BONUS, SEASONAL, SERVICE_BONUS).
# =============================================================================

# Clear existing MEET_THRESHOLD records
deleted = db.query(IncentiveTier).filter(
    IncentiveTier.type == "MEET_THRESHOLD"
).delete()
db.commit()

db.add(IncentiveTier(
    type             = "MEET_THRESHOLD",
    name             = "Customer Incentive Threshold — Meet Tier Split",
    threshold_amount = 5_000_000,
    service_types    = '["ALL"]',
    package_types    = '["ALL"]',
    start_date       = START,
    end_date         = None,
    description      = (
        "Controls the MEET tier split based on customer incentive value (col 18). "
        "If customer incentive >= 5,000,000 VND → MEET_HIGH tier (lower per-case rate). "
        "If customer incentive < 5,000,000 VND → MEET_LOW tier (higher per-case rate). "
        "Rationale: when the company has already given the customer a high incentive, "
        "the counsellor/CO per-case bonus is lower to balance total cost. "
        "To change the threshold: add a new row with updated threshold_amount and "
        "a new start_date — no code changes required."
    ),
    is_active = True,
))
db.commit()
print(f"✅ Seeded IncentiveTier — Customer Incentive Threshold: 5,000,000 VND")

print(f"\n✅ All done!")
print(f"   - MEET_HIGH now = LOWER rate (incentive >= 5M)")
print(f"   - MEET_LOW  now = HIGHER rate (incentive < 5M)")
print(f"   - Threshold stored in DB — change it there, no code needed")
db.close()
