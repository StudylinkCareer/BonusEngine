import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models import ClientTypeMap, ReferenceList

db = SessionLocal()

# =============================================================================
# CLIENT TYPE MAP — ALL CRM text variants → canonical codes
# Source: 15_CLIENT_TYPE_MAP sheet in engine workbook
# Engine does case-insensitive exact match on raw_value
# =============================================================================

d1 = db.query(ClientTypeMap).delete()
db.commit()
print(f"Cleared {d1} existing client type mappings\n")

CLIENT_TYPE_MAP = [
    # DU_HOC_FULL — Full service (enrolment + visa)
    {"raw_value": "Du học (Ghi danh + visa)",             "canonical": "DU_HOC_FULL",       "display_name": "Du học (Ghi danh + visa) — Full service"},
    {"raw_value": "Du hoc (Ghi danh + visa)",             "canonical": "DU_HOC_FULL",       "display_name": "Du học (Ghi danh + visa) — Full service"},
    {"raw_value": "Du học (ghi danh + visa)",             "canonical": "DU_HOC_FULL",       "display_name": "Du học (Ghi danh + visa) — Full service"},
    {"raw_value": "Du hoc (ghi danh + visa)",             "canonical": "DU_HOC_FULL",       "display_name": "Du học (Ghi danh + visa) — Full service"},
    {"raw_value": "Du học (Ghi danh+visa)",               "canonical": "DU_HOC_FULL",       "display_name": "Du học (Ghi danh + visa) — Full service"},
    {"raw_value": "Du học (Nộp đơn hỗ trợ tài chính)",   "canonical": "DU_HOC_FULL",       "display_name": "Du học — Financial aid application"},

    # DU_HOC_ENROL_ONLY — Enrolment only, sub-agent handles visa
    {"raw_value": "Du học (Ghi danh)",                    "canonical": "DU_HOC_ENROL_ONLY", "display_name": "Du học (Ghi danh) — Enrolment only"},
    {"raw_value": "Du hoc (Ghi danh)",                    "canonical": "DU_HOC_ENROL_ONLY", "display_name": "Du học (Ghi danh) — Enrolment only"},
    {"raw_value": "Du học (ghi danh)",                    "canonical": "DU_HOC_ENROL_ONLY", "display_name": "Du học (Ghi danh) — Enrolment only"},
    {"raw_value": "Du học (ghi danh chuyển trường)",      "canonical": "DU_HOC_ENROL_ONLY", "display_name": "Du học — School transfer enrolment"},

    # SUMMER_STUDY
    {"raw_value": "Du học hè",                            "canonical": "SUMMER_STUDY",      "display_name": "Du học hè — Summer study"},
    {"raw_value": "Du hoc he",                            "canonical": "SUMMER_STUDY",      "display_name": "Du học hè — Summer study"},
    {"raw_value": "Du hoc hè",                            "canonical": "SUMMER_STUDY",      "display_name": "Du học hè — Summer study"},
    {"raw_value": "Du học he",                            "canonical": "SUMMER_STUDY",      "display_name": "Du học hè — Summer study"},

    # VIETNAM_DOMESTIC
    {"raw_value": "Du học tại chỗ (Vietnam)",             "canonical": "VIETNAM_DOMESTIC",  "display_name": "Du học tại chỗ (Vietnam)"},
    {"raw_value": "Du hoc tai cho (Vietnam)",             "canonical": "VIETNAM_DOMESTIC",  "display_name": "Du học tại chỗ (Vietnam)"},
    {"raw_value": "Du học tại chỗ",                       "canonical": "VIETNAM_DOMESTIC",  "display_name": "Du học tại chỗ (Vietnam)"},
    {"raw_value": "Du hoc tai cho",                       "canonical": "VIETNAM_DOMESTIC",  "display_name": "Du học tại chỗ (Vietnam)"},

    # GUARDIAN_VISA
    {"raw_value": "Visa Giám hộ",                         "canonical": "GUARDIAN_VISA",     "display_name": "Visa Giám hộ — Guardian visa"},
    {"raw_value": "Visa Giam ho",                         "canonical": "GUARDIAN_VISA",     "display_name": "Visa Giám hộ — Guardian visa"},
    {"raw_value": "Visa giám hộ",                         "canonical": "GUARDIAN_VISA",     "display_name": "Visa Giám hộ — Guardian visa"},

    # TOURIST_VISA
    {"raw_value": "Visa Du lịch",                         "canonical": "TOURIST_VISA",      "display_name": "Visa Du lịch — Tourist visa"},
    {"raw_value": "Visa du lich",                         "canonical": "TOURIST_VISA",      "display_name": "Visa Du lịch — Tourist visa"},
    {"raw_value": "Visa Du Lịch",                         "canonical": "TOURIST_VISA",      "display_name": "Visa Du lịch — Tourist visa"},

    # MIGRATION_VISA
    {"raw_value": "Visa Định cư",                         "canonical": "MIGRATION_VISA",    "display_name": "Visa Định cư — Migration visa"},
    {"raw_value": "Visa Dinh cu",                         "canonical": "MIGRATION_VISA",    "display_name": "Visa Định cư — Migration visa"},
    {"raw_value": "Visa định cư",                         "canonical": "MIGRATION_VISA",    "display_name": "Visa Định cư — Migration visa"},

    # DEPENDANT_VISA
    {"raw_value": "Visa Phụ thuộc",                       "canonical": "DEPENDANT_VISA",    "display_name": "Visa Phụ thuộc — Dependant visa"},
    {"raw_value": "Visa Phu thuoc",                       "canonical": "DEPENDANT_VISA",    "display_name": "Visa Phụ thuộc — Dependant visa"},
    {"raw_value": "Visa phụ thuộc",                       "canonical": "DEPENDANT_VISA",    "display_name": "Visa Phụ thuộc — Dependant visa"},

    # VISA_ONLY_SERVICE
    {"raw_value": "Visa Du học only",                     "canonical": "VISA_ONLY_SERVICE", "display_name": "Visa Du học only — Visa only service"},
    {"raw_value": "Visa Du hoc only",                     "canonical": "VISA_ONLY_SERVICE", "display_name": "Visa Du học only — Visa only service"},
    {"raw_value": "Visa du học only",                     "canonical": "VISA_ONLY_SERVICE", "display_name": "Visa Du học only — Visa only service"},
    {"raw_value": "Du học (visa)",                        "canonical": "VISA_ONLY_SERVICE", "display_name": "Du học (visa) — Visa only service"},
]

for r in CLIENT_TYPE_MAP:
    db.add(ClientTypeMap(**r, is_active=True))
db.commit()
print(f"✅ Loaded {len(CLIENT_TYPE_MAP)} client type map entries")


# =============================================================================
# SKIP LABELS — Row labels the engine should skip when parsing input files
# Source: 13_SKIP_LABELS sheet in engine workbook
# Stored in ref_lists with list_name="skip_labels"
# =============================================================================

db.query(ReferenceList).filter(ReferenceList.list_name == "skip_labels").delete()
db.commit()

SKIP_LABELS = [
    {"value": "No.",                              "note": "Column header row"},
    {"value": "Closed files",                     "note": "Section header"},
    {"value": "Closed files - Enrolled",          "note": "Section header variant"},
    {"value": "Enrolled",                         "note": "Section header"},
    {"value": "Closed file",                      "note": "Section header variant"},
    {"value": "TONG",                             "note": "Vietnamese: Total summary row"},
    {"value": "TONG (bonus Enrolled",             "note": "Summary row variant"},
    {"value": "TỔNG",                             "note": "Vietnamese diacritics variant of TONG"},
    {"value": "TỔNG (Bonus Enrolled + Bonus Priority)", "note": "Full summary row label"},
    {"value": "Data - updated",                   "note": "Metadata row"},
    {"value": "Data - update",                    "note": "Catches Data - update dd/mm/yyyy variants"},
    {"value": "Ngoc Vien",                        "note": "Staff name used as section header"},
    {"value": "Ngọc Viên",                        "note": "Vietnamese diacritics variant of Ngoc Vien"},
    {"value": "Trong tháng",                      "note": "Monthly no-cases note row"},
    {"value": "No Target",                        "note": "Staff with no target note rows"},
]

for i, r in enumerate(SKIP_LABELS):
    db.add(ReferenceList(
        list_name="skip_labels",
        value=r["value"],
        sort_order=i,
        is_active=True,
    ))
db.commit()
print(f"✅ Loaded {len(SKIP_LABELS)} skip labels")

print(f"\n✅ All done!")
print(f"   Client type map entries: {len(CLIENT_TYPE_MAP)}")
print(f"   Skip labels:             {len(SKIP_LABELS)}")
db.close()
