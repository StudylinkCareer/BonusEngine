# =============================================================================
# constants.py  |  StudyLink Bonus Engine
# Replaces: modConstants.bas
# =============================================================================

# Scheme identifiers (Apr 2026 rebuild — 6 scheme model)
# Schemes are split by role (CO vs Counsellor) AND by direct/sub/VP.
# Office is now a separate dimension on ref_base_rates rather than a scheme
# variant — the same scheme works in any office (HCM, HN, DN, MEL).
SCHEME_CO_SUB     = "CO_SUB"       # Case Officer, Sub-agent
SCHEME_CO_DIR     = "CO_DIR"       # Case Officer, Direct  (was HCM_DIRECT)
SCHEME_CO_VP      = "CO_VP"        # Case Officer, VP
SCHEME_COUNS_SUB  = "COUNS_SUB"    # Counsellor, Sub-agent
SCHEME_COUNS_DIR  = "COUNS_DIR"    # Counsellor, Direct
SCHEME_COUNS_VP   = "COUNS_VP"     # Counsellor, VP

# Tier identifiers
TIER_UNDER     = "UNDER"
TIER_MEET_HIGH = "MEET_HIGH"
TIER_MEET_LOW  = "MEET_LOW"
TIER_MEET      = "MEET"
TIER_OVER      = "OVER"

# Office identifiers
OFFICE_HCM     = "HCM"
OFFICE_HN      = "HN"
OFFICE_DN      = "DN"
OFFICE_MEL     = "MEL"             # was VP_MEL
OFFICE_DEFAULT = "HCM"

# Institution types
INST_DIRECT       = "DIRECT"
INST_MASTER_AGENT = "MASTER_AGENT"
INST_GROUP        = "GROUP"
INST_OUT_OF_SYS   = "OUT_OF_SYSTEM"
INST_RMIT_VN      = "RMIT_VN"
INST_BUV_VN       = "BUV_VN"
INST_OTHER_VN     = "OTHER_VN"

# Client type codes
CT_DU_HOC_FULL  = "DU_HOC_FULL"
CT_DU_HOC_ENROL = "DU_HOC_ENROL_ONLY"
CT_SUMMER       = "SUMMER_STUDY"
CT_VIETNAM      = "VIETNAM_DOMESTIC"
CT_GUARDIAN     = "GUARDIAN_VISA"
CT_TOURIST      = "TOURIST_VISA"
CT_MIGRATION    = "MIGRATION_VISA"
CT_DEPENDANT    = "DEPENDANT_VISA"
CT_VISA_ONLY    = "VISA_ONLY_SERVICE"

# Deferral codes
DEFERRAL_NONE = "NONE"
DEFERRAL_ZERO_VALUES = frozenset({"FEE_TRANSFERRED","DEFERRED","FEE_WAIVED","NO_SERVICE"})

# Service fee categories
SVC_SERVICE_FEE = "SERVICE_FEE"
SVC_PACKAGE     = "PACKAGE"
SVC_CONTRACT    = "CONTRACT"
SVC_ADDON       = "ADDON"

# Row types
ROW_BASE  = "BASE"
ROW_ADDON = "ADDON"

# Sentinels
PRESALES_NONE  = "NONE"
PKG_NONE       = "NONE"
SVC_NONE       = "NONE"
MGMT_EXCEPTION = "MGMT_EXCEPTION"
ADDON_STATUS   = "Bundled support package"

# Policy thresholds
INCENTIVE_THRESHOLD = 5_000_000

# Config sheet names
WS_BASE_RATES   = "02_BASE_BONUS_RATES"
WS_PRIORITY     = "03_PRIORITY_INSTNS"
WS_TARGETS      = "04_STAFF_TARGETS"
WS_STATUS_RULES = "05_STATUS_RULES"
WS_WEIGHTS      = "06_CLIENT_WEIGHTS"
WS_SERVICE_FEES = "09_SERVICE_FEE_RATES"
WS_MASTER_AGENTS= "11_MASTER_AGENTS"
WS_STAFF_NAMES  = "12_STAFF_NAMES"
WS_SKIP_LABELS  = "13_SKIP_LABELS"
WS_COUNTRIES    = "14_COUNTRY_CODES"
WS_CLIENT_TYPES = "15_CLIENT_TYPE_MAP"

# CRM skip labels
SKIP_LABELS = frozenset({
    "no.", "closed files", "closed files - enrolled", "enrolled",
    "closed file", "tong", "tổng", "data - updated", "ngoc vien",
    "ngọc viên", "tổng (bonus enrolled + bonus priority)",
})
