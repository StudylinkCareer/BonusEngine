import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import engine, SessionLocal
from app.models import Base, User, StaffName, CountryCode, ClientTypeMap, StatusRule, ReferenceList
from app.routers.auth import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# =============================================================================
# ADMIN USER
# =============================================================================
existing = db.query(User).filter(User.username == "admin").first()
if existing:
    db.delete(existing)
    db.commit()

db.add(User(
    username="admin",
    full_name="Administrator",
    email="admin@studylink.com",
    hashed_password=hash_password("admin123"),
    staff_name="Admin",
    is_admin=True,
))
db.commit()
print("Admin user created!")

# =============================================================================
# STAFF NAMES — single master list
# =============================================================================
if db.query(StaffName).count() == 0:
    staff = [
        {"full_name": "Đoàn Ngọc Trúc Quỳnh", "short_name": "Trúc Quỳnh (HCM)", "office": "HCM", "role": "counsellor"},
        {"full_name": "Trúc Quỳnh (HN)",       "short_name": "Trúc Quỳnh (HN)",  "office": "HN",  "role": "counsellor"},
        {"full_name": "Lê Thị Trường An",       "short_name": "Trường An",         "office": "HCM", "role": "counsellor"},
        {"full_name": "Nguyễn Thành Vinh",      "short_name": "Vinh",              "office": "HCM", "role": "counsellor"},
        {"full_name": "Nguyễn Thị Mỹ Ly",       "short_name": "Mỹ Ly",             "office": "HCM", "role": "counsellor"},
        {"full_name": "Phạm Thị Lợi",           "short_name": "Lợi",               "office": "DN",  "role": "counsellor"},
        {"full_name": "Phạm Thị Ngọc Thảo",     "short_name": "Ngọc Thảo",         "office": "HCM", "role": "counsellor"},
        {"full_name": "Quan Hoàng Yến",          "short_name": "Hoàng Yến",         "office": "HCM", "role": "counsellor"},
        {"full_name": "Trần Thanh Gia Mẫn",      "short_name": "Gia Mẫn",           "office": "HCM", "role": "counsellor"},
        {"full_name": "Thái Thị Huỳnh Anh",      "short_name": "Huỳnh Anh",         "office": "HCM", "role": "presales"},
    ]
    for s in staff:
        db.add(StaffName(**s))
    db.commit()
    print(f"Staff names seeded: {len(staff)} records")

# =============================================================================
# COUNTRY CODES
# =============================================================================
if db.query(CountryCode).count() == 0:
    countries = [
        ("Australia", "AU", "Oceania"),
        ("Canada", "CA", "Americas"),
        ("China", "CN", "Asia"),
        ("Czech Republic", "CZ", "Europe"),
        ("Denmark", "DK", "Europe"),
        ("Finland", "FI", "Europe"),
        ("France", "FR", "Europe"),
        ("Germany", "DE", "Europe"),
        ("Grenada", "GD", "Americas"),
        ("Hungary", "HU", "Europe"),
        ("Ireland", "IE", "Europe"),
        ("Japan", "JP", "Asia"),
        ("Malaysia", "MY", "Asia"),
        ("Netherlands", "NL", "Europe"),
        ("New Zealand", "NZ", "Oceania"),
        ("Norway", "NO", "Europe"),
        ("Philippines", "PH", "Asia"),
        ("Singapore", "SG", "Asia"),
        ("South Korea", "KR", "Asia"),
        ("Sweden", "SE", "Europe"),
        ("Switzerland", "CH", "Europe"),
        ("Taiwan", "TW", "Asia"),
        ("Thailand", "TH", "Asia"),
        ("UK", "GB", "Europe"),
        ("USA", "US", "Americas"),
        ("Viet Nam", "VN", "Asia"),
        ("Vietnam", "VN", "Asia"),
    ]
    for name, code, region in countries:
        db.add(CountryCode(country_name=name, country_code=code, region=region))
    db.commit()
    print(f"Country codes seeded: {len(countries)} records")

# =============================================================================
# CLIENT TYPE MAP — normalise Vietnamese variants
# =============================================================================
if db.query(ClientTypeMap).count() == 0:
    client_types = [
        ("Du hoc (Ghi danh + visa)", "DU_HOC_GD_VISA"),
        ("Du hoc (Ghi danh)", "DU_HOC_GD"),
        ("Du hoc (ghi danh + visa)", "DU_HOC_GD_VISA"),
        ("Du hoc he", "DU_HOC_HE"),
        ("Du hoc hè", "DU_HOC_HE"),
        ("Du hoc tai cho", "DU_HOC_TAI_CHO"),
        ("Du hoc tai cho (Vietnam)", "DU_HOC_TAI_CHO"),
        ("Du học (Ghi danh + visa)", "DU_HOC_GD_VISA"),
        ("Du học (Ghi danh)", "DU_HOC_GD"),
        ("Du học (Ghi danh+visa)", "DU_HOC_GD_VISA"),
        ("Du học (Nộp đơn hỗ trợ tài chính)", "DU_HOC_TC"),
        ("Du học (ghi danh + visa)", "DU_HOC_GD_VISA"),
        ("Du học (ghi danh chuyển trường)", "DU_HOC_CHUYEN_TRUONG"),
        ("Du học (ghi danh)", "DU_HOC_GD"),
        ("Du học (visa)", "DU_HOC_VISA"),
        ("Du học he", "DU_HOC_HE"),
        ("Du học hè", "DU_HOC_HE"),
        ("Du học tại chỗ", "DU_HOC_TAI_CHO"),
        ("Du học tại chỗ (Vietnam)", "DU_HOC_TAI_CHO"),
        ("Visa Dinh cu", "VISA_DINH_CU"),
        ("Visa Du Lịch", "VISA_DU_LICH"),
        ("Visa Du hoc only", "VISA_DU_HOC"),
        ("Visa Du học only", "VISA_DU_HOC"),
        ("Visa Giam ho", "VISA_GIAM_HO"),
        ("Visa Giám hộ", "VISA_GIAM_HO"),
        ("Visa Phu thuoc", "VISA_PHU_THUOC"),
        ("Visa Phụ thuộc", "VISA_PHU_THUOC"),
        ("Visa du học only", "VISA_DU_HOC"),
        ("Visa du lich", "VISA_DU_LICH"),
        ("Visa giám hộ", "VISA_GIAM_HO"),
        ("Visa phụ thuộc", "VISA_PHU_THUOC"),
        ("Visa Định cư", "VISA_DINH_CU"),
        ("Visa định cư", "VISA_DINH_CU"),
    ]
    for raw, canonical in client_types:
        db.add(ClientTypeMap(raw_value=raw, canonical=canonical, display_name=raw))
    db.commit()
    print(f"Client type map seeded: {len(client_types)} records")

# =============================================================================
# STATUS RULES
# =============================================================================
if db.query(StatusRule).count() == 0:
    statuses = [
        ("Closed - Visa granted, then enrolled", True, True, True),
        ("Closed - Visa granted (visa only)", True, True, False),
        ("Closed - Visa granted then cancelled", True, True, False),
        ("Closed - Visa refused", False, False, False),
        ("Closed - Visa refused then granted", True, True, False),
        ("Closed - Enrolment (only)", True, False, True),
        ("Closed - Enrolled then cancelled", False, False, False),
        ("Closed - Enrolled, then Visa granted", True, True, True),
        ("Closed - Cancelled", False, False, False),
        ("Current - Enrolled", True, False, True),
        ("Current - Visa refused", False, False, False),
        ("Pending - Visa refused", False, False, False),
        ("Closed - Institution refused", False, False, False),
        ("Closed - Visa granted", True, True, False),
        ("Closed - Enrolled then visa refused", False, False, False),
        ("Closed - Enrolment", True, False, True),
    ]
    for status, eligible, req_visa, req_enrol in statuses:
        db.add(StatusRule(
            status_value=status,
            is_eligible=eligible,
            requires_visa=req_visa,
            requires_enrol=req_enrol
        ))
    db.commit()
    print(f"Status rules seeded: {len(statuses)} records")

# =============================================================================
# REFERENCE LISTS — generic dropdowns
# =============================================================================
def seed_list(list_name, values):
    if db.query(ReferenceList).filter(ReferenceList.list_name == list_name).count() == 0:
        for i, v in enumerate(values):
            db.add(ReferenceList(list_name=list_name, value=v, sort_order=i))
        db.commit()
        print(f"Reference list '{list_name}' seeded: {len(values)} values")

seed_list("package_type", [
    "NONE", "Standard Plus (3tr)", "Superior Package (6tr)", "superior Package 6tr",
    "Premium Package (9tr)", "SDS (7tr5)", "Standard Package (9tr5)",
    "Premium Canada (14tr)", "Standard Package (16tr)",
    "Superior Package USA In-Full (45tr)", "Standard Package USA Out-Full (28tr)",
    "Superior Package USA Out-Full (68tr)", "Premium Package", "Regular (9tr5)",
])

seed_list("institution_type", [
    "DIRECT", "MASTER_AGENT", "GROUP", "OUT_OF_SYSTEM", "RMIT_VN", "OTHER_VN",
])

seed_list("deferral", [
    "NONE", "DEFERRED", "FEE_TRANSFERRED", "FEE_WAIVED", "NO_SERVICE",
])

seed_list("system_type", [
    "Trong hệ thống", "Ngoài hệ thống",
])

seed_list("addon_code", [
    "VISITOR_VISA", "STUDY_PERMIT_RENEWAL", "GUARDIAN_VISA_RENEWAL",
    "SCHOOL_TRANSFER_DET", "CAQ", "GUARDIAN_HOMESTAY_CHANGE",
    "EXCHANGE", "EXTRA_SCHOOL",
])

seed_list("service_fee_type", [
    "NONE", "CANCELLED_FULL_SERVICE", "CAQ", "DEPENDANT_GRANTED",
    "DEPENDANT_REFUSED", "DIFFICULT_CASE", "EXTRA_SCHOOL",
    "GUARDIAN_AU_ADDON", "GUARDIAN_CHANGE", "GUARDIAN_GRANTED",
    "GUARDIAN_REFUSED", "GUARDIAN_VISA", "HOMESTAY_CHANGE",
    "OUT_SYSTEM_FULL_AUS", "REFERRAL_LOVELY_COFFEE", "STUDENT_VISA_RENEWAL",
    "STUDY_PERMIT_RENEWAL", "TRANSFER_NO_COMMISSION", "VISA_485",
    "VISA_ONLY", "VISA_RENEWAL", "VISITOR_EXCHANGE",
])

db.close()
print("Seed complete!")
