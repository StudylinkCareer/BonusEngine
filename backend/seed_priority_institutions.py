import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import PriorityInstitution

db = SessionLocal()

deleted = db.query(PriorityInstitution).delete()
db.commit()
print(f"Cleared {deleted} existing priority institutions\n")

INSTITUTIONS = [
    # AU
    {"country_code": "AU", "institution_name": "Australian Catholic University (ACU)",             "annual_target": 6,  "bonus_pct": 0.0, "direct_target": 4,  "sub_target": 2,  "is_active": True},
    {"country_code": "AU", "institution_name": "Curtin University",                                "annual_target": 6,  "bonus_pct": 0.0, "direct_target": 3,  "sub_target": 3,  "is_active": True},
    {"country_code": "AU", "institution_name": "Deakin University",                                "annual_target": 6,  "bonus_pct": 0.0, "direct_target": 4,  "sub_target": 2,  "is_active": True},
    {"country_code": "AU", "institution_name": "Education Queensland International (EQI)",         "annual_target": 10, "bonus_pct": 0.0, "direct_target": 3,  "sub_target": 7,  "is_active": True},
    {"country_code": "AU", "institution_name": "Griffith University",                              "annual_target": 3,  "bonus_pct": 0.0, "direct_target": 2,  "sub_target": 1,  "is_active": True},
    {"country_code": "AU", "institution_name": "James Cook University Brisbane (JCUB)",            "annual_target": 5,  "bonus_pct": 0.0, "direct_target": 3,  "sub_target": 2,  "is_active": True},
    {"country_code": "AU", "institution_name": "Kaplan Business School Australia",                 "annual_target": 4,  "bonus_pct": 0.0, "direct_target": 2,  "sub_target": 2,  "is_active": True},
    {"country_code": "AU", "institution_name": "La Trobe University",                              "annual_target": 8,  "bonus_pct": 0.0, "direct_target": 5,  "sub_target": 3,  "is_active": True},
    {"country_code": "AU", "institution_name": "Macquarie University",                             "annual_target": 10, "bonus_pct": 0.0, "direct_target": 5,  "sub_target": 5,  "is_active": True},
    {"country_code": "AU", "institution_name": "Monash University",                                "annual_target": 10, "bonus_pct": 0.0, "direct_target": 3,  "sub_target": 7,  "is_active": True},
    {"country_code": "AU", "institution_name": "RMIT University",                                  "annual_target": 8,  "bonus_pct": 0.0, "direct_target": 3,  "sub_target": 5,  "is_active": True},
    {"country_code": "AU", "institution_name": "Swinburne University of Technology",               "annual_target": 14, "bonus_pct": 0.0, "direct_target": 7,  "sub_target": 7,  "is_active": True},
    {"country_code": "AU", "institution_name": "The University of Adelaide",                       "annual_target": 14, "bonus_pct": 0.0, "direct_target": 7,  "sub_target": 7,  "is_active": True},
    {"country_code": "AU", "institution_name": "The University of New South Wales (UNSW)",         "annual_target": 5,  "bonus_pct": 0.0, "direct_target": 2,  "sub_target": 3,  "is_active": True},
    {"country_code": "AU", "institution_name": "The University of Queensland",                     "annual_target": 6,  "bonus_pct": 0.0, "direct_target": 4,  "sub_target": 2,  "is_active": True},
    {"country_code": "AU", "institution_name": "University of Newcastle",                          "annual_target": 3,  "bonus_pct": 0.0, "direct_target": 3,  "sub_target": 0,  "is_active": True},
    {"country_code": "AU", "institution_name": "University of South Australia (UniSA)",            "annual_target": 14, "bonus_pct": 0.0, "direct_target": 7,  "sub_target": 7,  "is_active": True},
    {"country_code": "AU", "institution_name": "University of Tasmania (UTAS)",                    "annual_target": 5,  "bonus_pct": 0.0, "direct_target": 3,  "sub_target": 2,  "is_active": True},
    {"country_code": "AU", "institution_name": "University of Technology Sydney (UTS)",            "annual_target": 6,  "bonus_pct": 0.0, "direct_target": 3,  "sub_target": 3,  "is_active": True},
    {"country_code": "AU", "institution_name": "University of Western Australia (UWA)",            "annual_target": 8,  "bonus_pct": 0.0, "direct_target": 4,  "sub_target": 4,  "is_active": True},
    {"country_code": "AU", "institution_name": "VIC DET (Dept of Education & Training, VIC)",     "annual_target": 15, "bonus_pct": 0.0, "direct_target": 7,  "sub_target": 8,  "is_active": True},
    {"country_code": "AU", "institution_name": "Griffith College (Navitas)",                       "annual_target": 2,  "bonus_pct": 0.0, "direct_target": 1,  "sub_target": 1,  "is_active": True},
    {"country_code": "AU", "institution_name": "WSU College / WSU Sydney City (Navitas)",          "annual_target": 1,  "bonus_pct": 0.0, "direct_target": 1,  "sub_target": 0,  "is_active": True},
    {"country_code": "AU", "institution_name": "Other Navitas AU: Eynesbury, CC, ECUC, SAIBT, DC, LC, WSUIC, GC", "annual_target": 7, "bonus_pct": 0.0, "direct_target": 3, "sub_target": 4, "is_active": True},
    # CA
    {"country_code": "CA", "institution_name": "Algonquin College",                                "annual_target": 4,  "bonus_pct": 0.0, "direct_target": 2,  "sub_target": 2,  "is_active": True},
    {"country_code": "CA", "institution_name": "Cape Breton University (CBU)",                     "annual_target": 5,  "bonus_pct": 0.0, "direct_target": 5,  "sub_target": 0,  "is_active": True},
    {"country_code": "CA", "institution_name": "Braemar College",                                  "annual_target": 4,  "bonus_pct": 0.0, "direct_target": 4,  "sub_target": 0,  "is_active": True},
    {"country_code": "CA", "institution_name": "Toronto Metropolitan University",                  "annual_target": 3,  "bonus_pct": 0.0, "direct_target": 3,  "sub_target": 0,  "is_active": True},
    {"country_code": "CA", "institution_name": "University of Guelph",                             "annual_target": 1,  "bonus_pct": 0.0, "direct_target": 1,  "sub_target": 0,  "is_active": True},
    {"country_code": "CA", "institution_name": "University of Regina",                             "annual_target": 2,  "bonus_pct": 0.0, "direct_target": 2,  "sub_target": 0,  "is_active": True},
    {"country_code": "CA", "institution_name": "ICM (Navitas)",                                    "annual_target": 1,  "bonus_pct": 0.0, "direct_target": 1,  "sub_target": 0,  "is_active": True},
    {"country_code": "CA", "institution_name": "Toronto Met Uni Intl College (Navitas)",           "annual_target": 1,  "bonus_pct": 0.0, "direct_target": 1,  "sub_target": 0,  "is_active": True},
    {"country_code": "CA", "institution_name": "Other Navitas CA: FIC, ULIC, WLIC",               "annual_target": 2,  "bonus_pct": 0.0, "direct_target": 2,  "sub_target": 0,  "is_active": True},
    # NZ
    {"country_code": "NZ", "institution_name": "ENZ (any NZ providers)",                           "annual_target": 10, "bonus_pct": 0.0, "direct_target": 5,  "sub_target": 5,  "is_active": True},
    {"country_code": "NZ", "institution_name": "LightPath",                                        "annual_target": 3,  "bonus_pct": 0.0, "direct_target": 3,  "sub_target": 0,  "is_active": True},
    {"country_code": "NZ", "institution_name": "Other Navitas NZ: UCIC",                           "annual_target": 1,  "bonus_pct": 0.0, "direct_target": 1,  "sub_target": 0,  "is_active": True},
    # SING
    {"country_code": "SING", "institution_name": "Raffles Education Network",                      "annual_target": 1,  "bonus_pct": 0.0, "direct_target": 1,  "sub_target": 0,  "is_active": True},
    {"country_code": "SING", "institution_name": "Nanyang Institute of Management (NIM)",          "annual_target": 1,  "bonus_pct": 0.0, "direct_target": 1,  "sub_target": 0,  "is_active": True},
]

for inst in INSTITUTIONS:
    db.add(PriorityInstitution(**inst))

db.commit()
print(f"✅ Loaded {len(INSTITUTIONS)} priority institutions successfully!")
print(f"\nNotes:")
print(f"  - University of Newcastle & Toronto Metropolitan University = via other agents only")
print(f"  - Priority Bonus = Enrolled Bonus × Bonus% × Achievement Factor")
print(f"  - Achievement Factor = 100% if actual >= target, 50% if < target")
print(f"  - Individual bonus paid 50% at enrolment, 50% after annual KPI reached")
db.close()
