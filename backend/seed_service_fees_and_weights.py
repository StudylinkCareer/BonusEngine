import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import ServiceFeeRate, ClientWeight
from sqlalchemy import text

# ============================================================
# MIGRATE: rebuild ref_service_fee_rates with new columns
# ============================================================
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS ref_service_fee_rates"))
    conn.commit()
    conn.execute(text("""
        CREATE TABLE ref_service_fee_rates (
            id SERIAL PRIMARY KEY,
            service_code VARCHAR(100) UNIQUE NOT NULL,
            keywords TEXT,
            coun_bonus INTEGER DEFAULT 0,
            co_bonus INTEGER DEFAULT 0,
            category VARCHAR(30),
            applies_to VARCHAR(30),
            timing VARCHAR(200),
            description TEXT,
            note TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """))
    conn.commit()
    print("✅ ref_service_fee_rates table rebuilt\n")

db = SessionLocal()
db.query(ClientWeight).delete()
db.commit()

# ============================================================
# SERVICE FEE RATES
# SERVICE_FEE rows fire at Step 2.8 and EXIT (no tier stacking)
# PACKAGE rows fire at Step 9 and STACK on top of tier bonus
# CONTRACT rows fire at Step 9 and STACK on top of tier bonus
# ============================================================

SERVICE_FEE_RATES = [

    # ----------------------------------------------------------
    # SERVICE_FEE rows — CO only, fire at Step 2.8 and EXIT
    # ----------------------------------------------------------
    {"service_code": "STUDY_PERMIT_RENEWAL",   "keywords": "study permit|gia han study|student permit renewal",                       "coun_bonus": 0, "co_bonus": 250_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Study permit renewal",                                                                  "note": ""},
    {"service_code": "VISA_RENEWAL",            "keywords": "visa renewal|gia han visa|renew visa|student visa extension",             "coun_bonus": 0, "co_bonus": 400_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Student visa renewal AUS/NZ",                                                            "note": ""},
    {"service_code": "VISA_ONLY",               "keywords": "visa only|visa service|first visa",                                       "coun_bonus": 0, "co_bonus": 600_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Visa only (first visa) = 600,000",                                                       "note": "CONFIRMED Dec 2025 bao cao"},
    {"service_code": "VISA_485",                "keywords": "visa 485|graduate visa|post-study|485",                                   "coun_bonus": 0, "co_bonus": 600_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Visa 485 post-study work visa",                                                          "note": ""},
    {"service_code": "CAQ",                     "keywords": "caq|certificat d'acceptation|quebec",                                    "coun_bonus": 0, "co_bonus": 250_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "CAQ (Quebec Acceptance Certificate)",                                                    "note": ""},
    {"service_code": "GUARDIAN_CHANGE",         "keywords": "changing guardian|doi nguoi giam ho|guardian change",                    "coun_bonus": 0, "co_bonus": 250_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Changing guardian",                                                                      "note": ""},
    {"service_code": "GUARDIAN_GRANTED",        "keywords": "guardian granted|guardian visa granted",                                  "coun_bonus": 0, "co_bonus": 600_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Guardian visa Granted",                                                                  "note": ""},
    {"service_code": "GUARDIAN_REFUSED",        "keywords": "guardian refused|guardian visa refused",                                  "coun_bonus": 0, "co_bonus": 300_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Guardian visa Refused",                                                                  "note": ""},
    {"service_code": "GUARDIAN_VISA",           "keywords": "guardian visa|visa bao ho",                                               "coun_bonus": 0, "co_bonus": 250_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Guardian from AUS (Aug 2022+)",                                                          "note": ""},
    {"service_code": "DEPENDANT_GRANTED",       "keywords": "dependant granted|dependent granted",                                     "coun_bonus": 0, "co_bonus": 400_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Dependant visa Granted",                                                                 "note": ""},
    {"service_code": "DEPENDANT_REFUSED",       "keywords": "dependant refused|dependent refused",                                     "coun_bonus": 0, "co_bonus": 150_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Dependant visa Refused",                                                                 "note": ""},
    {"service_code": "HOMESTAY_CHANGE",         "keywords": "changing homestay|doi homestay|homestay change",                          "coun_bonus": 0, "co_bonus": 250_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Changing homestay",                                                                      "note": ""},
    {"service_code": "EXTRA_SCHOOL",            "keywords": "enrolling 1 more school|them truong|extra school",                        "coun_bonus": 0, "co_bonus": 250_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Enrolling additional school",                                                            "note": ""},
    {"service_code": "VISITOR_EXCHANGE",        "keywords": "visitor|exchange|transferred school",                                     "coun_bonus": 0, "co_bonus": 250_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Visitor/Exchange/other admin",                                                           "note": "CONFIRMED Jul 2025"},
    {"service_code": "CANCELLED_FULL_SERVICE",  "keywords": "full service|ghi danh|phi da thu",                                        "coun_bonus": 0, "co_bonus": 400_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Cancelled full-service (fees paid)",                                                     "note": ""},
    {"service_code": "TRANSFER_NO_COMMISSION",  "keywords": "transfer no commission|chuyen truong khong hoa hong",                     "coun_bonus": 0, "co_bonus": 250_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "School transfer - no commission",                                                        "note": ""},
    {"service_code": "STUDENT_VISA_RENEWAL",    "keywords": "student visa renewal|visa gia han",                                       "coun_bonus": 0, "co_bonus": 400_000, "category": "SERVICE_FEE", "applies_to": "ALL",          "timing": "CO at file close",              "description": "Alias for VISA_RENEWAL",                                                                 "note": ""},
    {"service_code": "DIFFICULT_CASE",          "keywords": "difficult case|out system full|ngoai he thong 20m",                       "coun_bonus": 0, "co_bonus": 500_000, "category": "SERVICE_FEE", "applies_to": "OUT_OF_SYSTEM", "timing": "CO at enrolment",               "description": "Difficult case / Out-system full service 20M+. Set col 27 = OUT_OF_SYSTEM AND col 19 = DIFFICULT_CASE. CO gets 400k base + 500k = 900k total.", "note": "Source: 07_CONTRACT_BONUS. CONFIRMED +500k"},

    # ----------------------------------------------------------
    # PACKAGE rows — STACK on top of tier bonus (Step 9)
    # AP Packages
    # ----------------------------------------------------------
    {"service_code": "AP_STANDARD_PLUS_3TR",    "keywords": "standard plus|goi 2 ap|3tr",                                             "coun_bonus": 500_000,   "co_bonus": 0,       "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun at signing (deducted from enrolment month)",  "description": "AP Standard Plus 3M — CO: no extra bonus",                              "note": ""},
    {"service_code": "AP_SUPERIOR_6TR",          "keywords": "superior|goi 3 ap|6tr",                                                  "coun_bonus": 1_000_000, "co_bonus": 500_000, "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun at signing / CO at enrolment",                "description": "AP Superior 6M",                                                         "note": "CONFIRMED Feb 2025 bao cao"},
    {"service_code": "AP_SUPERIOR_6TR_ALT",      "keywords": "superior package 6tr",                                                    "coun_bonus": 1_000_000, "co_bonus": 500_000, "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun at signing / CO at enrolment",                "description": "AP Superior 6M -- alternate capitalisation alias",                       "note": ""},
    {"service_code": "AP_PREMIUM_9TR",           "keywords": "premium ap|premium package|9tr",                                         "coun_bonus": 1_500_000, "co_bonus": 500_000, "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun at signing / CO at enrolment",                "description": "AP Premium 9M",                                                          "note": ""},

    # Canada Packages
    {"service_code": "CA_SDS_7TR5",              "keywords": "sds|7tr5|5tr5|goi 1 canada",                                             "coun_bonus": 0,         "co_bonus": 0,       "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun = scheme at enrolment only",                  "description": "Canada SDS 7.5M — no CO extra",                                         "note": ""},
    {"service_code": "CA_STANDARD_9TR5",         "keywords": "standard regular|9tr5|goi 2 canada",                                     "coun_bonus": 1_000_000, "co_bonus": 0,       "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun at signing (includes visa refused)",          "description": "Canada Standard 9.5M — no CO extra",                                    "note": ""},
    {"service_code": "CA_PREMIUM_14TR",          "keywords": "premium canada|14tr|goi 3 canada",                                       "coun_bonus": 2_000_000, "co_bonus": 500_000, "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun at signing / CO at signing",                  "description": "Canada Premium 14M",                                                     "note": ""},

    # USA Packages
    {"service_code": "USA_STANDARD_16TR",        "keywords": "standard|16tr|standard package usa|goi 1 my",                            "coun_bonus": 1_000_000, "co_bonus": 0,       "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun at signing (clawback if refused)",            "description": "USA Standard In-Full 16M — no CO extra",                                "note": ""},
    {"service_code": "USA_SUPERIOR_IN_45TR",     "keywords": "superior usa in|45tr|goi 2 my",                                          "coun_bonus": 2_000_000, "co_bonus": 500_000, "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun at signing / CO at signing",                  "description": "USA Superior In-Full 45M",                                               "note": ""},
    {"service_code": "USA_STANDARD_OUT_28TR",    "keywords": "standard out|28tr|goi 3 my",                                             "coun_bonus": 500_000,   "co_bonus": 0,       "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun at signing (clawback if refused)",            "description": "USA Standard Out-Full 28M — no CO extra",                               "note": ""},
    {"service_code": "USA_SUPERIOR_OUT_68TR",    "keywords": "superior usa out|68tr|goi 4 my",                                         "coun_bonus": 1_500_000, "co_bonus": 500_000, "category": "PACKAGE",     "applies_to": "DIRECT",       "timing": "Coun at signing / CO at signing",                  "description": "USA Superior Out-Full 68M",                                              "note": ""},

    # ----------------------------------------------------------
    # CONTRACT rows — from 07_CONTRACT_BONUS, STACK on tier bonus
    # ----------------------------------------------------------
    {"service_code": "OUT_SYSTEM_FULL_AUS",      "keywords": "out system full aus|outsystem aus full",                                  "coun_bonus": 1_100_000, "co_bonus": 500_000, "category": "CONTRACT",    "applies_to": "OUT_OF_SYSTEM", "timing": "Coun at signing / CO at enrolment",               "description": "Out-system full service AUS 20M. Source: 07_CONTRACT_BONUS.",            "note": "Coun 1,100,000 signing bonus regardless of visa outcome"},
    {"service_code": "GUARDIAN_AU_ADDON",        "keywords": "guardian au addon|guardian au",                                           "coun_bonus": 0,         "co_bonus": 125_000, "category": "CONTRACT",    "applies_to": "ALL",          "timing": "CO at file close (50/50 split with other CO)",     "description": "Guardian from AUS add-on. Source: rate table row 19.",                  "note": "250k total split 50/50 = 125k per CO. CONFIRMED Apr 2025 bao cao"},
    {"service_code": "REFERRAL_LOVELY_COFFEE",   "keywords": "lovely cup|referral partner",                                             "coun_bonus": 100_000,   "co_bonus": 0,       "category": "CONTRACT",    "applies_to": "ALL",          "timing": "Coun at referral conversion",                      "description": "Add-on service referral (Lovely Cup of Coffee). Source: 07_CONTRACT_BONUS.", "note": "100k per referral to Counsellor only"},
    {"service_code": "PREMIUM_PACKAGE_ALIAS",    "keywords": "premium package",                                                         "coun_bonus": 0,         "co_bonus": 500_000, "category": "PACKAGE",     "applies_to": "PACKAGE",      "timing": "at enrolment",                                     "description": "AP Premium 9M — alias without suffix. CO: 500,000 at enrolment.",       "note": "Alias for 'Premium Package (9tr)' — same rates"},
    {"service_code": "CA_REGULAR_9TR5",          "keywords": "regular|9tr5",                                                            "coun_bonus": 0,         "co_bonus": 0,       "category": "PACKAGE",     "applies_to": "PACKAGE",      "timing": "at enrolment",                                     "description": "Canada Regular 9.5M — no CO extra bonus.",                              "note": "Canada Regular package: counsellor bonus only; CO = 0"},
]

for r in SERVICE_FEE_RATES:
    db.add(ServiceFeeRate(
        service_code=r["service_code"],
        keywords=r["keywords"],
        coun_bonus=r["coun_bonus"],
        co_bonus=r["co_bonus"],
        category=r["category"],
        applies_to=r["applies_to"],
        timing=r["timing"],
        description=r["description"],
        note=r["note"],
        is_active=True,
    ))
db.commit()
print(f"✅ Loaded {len(SERVICE_FEE_RATES)} service fee rates")


# ============================================================
# CLIENT WEIGHTS
# ============================================================

CLIENT_WEIGHTS = [
    {"canonical_code": "DU_HOC_FULL",       "display_name": "Du học (Ghi danh + visa) — Full service",       "weight_direct": 1.0, "weight_referred": 0.7, "weight_master": 0.7, "weight_outsys": 0.0, "weight_outsys_usa": 0.7, "note": "Most common type"},
    {"canonical_code": "DU_HOC_ENROL_ONLY", "display_name": "Du học (Ghi danh) — Enrolment only",            "weight_direct": 1.0, "weight_referred": 0.7, "weight_master": 1.0, "weight_outsys": 0.0, "weight_outsys_usa": 0.7, "note": "Sub-agent handles visa; CO gets Enrol only thru partner rate"},
    {"canonical_code": "SUMMER_STUDY",      "display_name": "Du học hè — Summer study",                       "weight_direct": 0.0, "weight_referred": 0.0, "weight_master": 0.0, "weight_outsys": 0.0, "weight_outsys_usa": 0.0, "note": "No target count; fixed bonus only"},
    {"canonical_code": "VIETNAM_DOMESTIC",  "display_name": "Du học tại chỗ (Vietnam)",                       "weight_direct": 0.5, "weight_referred": 0.0, "weight_master": 0.0, "weight_outsys": 0.0, "weight_outsys_usa": 0.0, "note": "Counsellor only; CO not involved"},
    {"canonical_code": "GUARDIAN_VISA",     "display_name": "Visa Giám hộ — Guardian visa",                   "weight_direct": 0.0, "weight_referred": 0.0, "weight_master": 0.0, "weight_outsys": 0.0, "weight_outsys_usa": 0.0, "note": "Fixed rate applies (see Sheet 02)"},
    {"canonical_code": "TOURIST_VISA",      "display_name": "Visa Du lịch — Tourist visa",                    "weight_direct": 0.0, "weight_referred": 0.0, "weight_master": 0.0, "weight_outsys": 0.0, "weight_outsys_usa": 0.0, "note": "Fixed rate"},
    {"canonical_code": "MIGRATION_VISA",    "display_name": "Visa Định cư — Migration visa",                  "weight_direct": 0.0, "weight_referred": 0.0, "weight_master": 0.0, "weight_outsys": 0.0, "weight_outsys_usa": 0.0, "note": "Fixed rate"},
    {"canonical_code": "DEPENDANT_VISA",    "display_name": "Visa Phụ thuộc — Dependant visa",                "weight_direct": 0.0, "weight_referred": 0.0, "weight_master": 0.0, "weight_outsys": 0.0, "weight_outsys_usa": 0.0, "note": "Fixed rate"},
    {"canonical_code": "VISA_ONLY_SERVICE", "display_name": "Visa Du học only — Visa only service",           "weight_direct": 0.0, "weight_referred": 0.0, "weight_master": 0.0, "weight_outsys": 0.0, "weight_outsys_usa": 0.0, "note": "Fixed rate"},
]

for w in CLIENT_WEIGHTS:
    db.add(ClientWeight(**w, is_active=True))
db.commit()
print(f"✅ Loaded {len(CLIENT_WEIGHTS)} client weights")

print(f"\n✅ All done!")
print(f"   Service fee rates: {len(SERVICE_FEE_RATES)}")
print(f"   Client weights:    {len(CLIENT_WEIGHTS)}")
db.close()
