# =============================================================================
# constants.py
# Equivalent of modConstants.bas
# All constants used throughout the bonus calculation engine.
# =============================================================================

# -- Scheme identifiers -------------------------------------------------------
SCHEME_HCM_DIRECT = "HCM_DIRECT"   # Counsellor/CO Direct, HCM office
SCHEME_HN_DIRECT  = "HN_DIRECT"    # Counsellor/CO Direct, HN or DN office
SCHEME_CO_SUB     = "CO_SUB"       # CO for Sub-agents
SCHEME_DIRECT     = "DIRECT"       # Direct counsellor role
SCHEME_CO         = "CO"           # Case Officer role

# -- Tier identifiers ---------------------------------------------------------
TIER_UNDER     = "UNDER"
TIER_MEET_HIGH = "MEET_HIGH"
TIER_MEET_LOW  = "MEET_LOW"
TIER_MEET      = "MEET"
TIER_OVER      = "OVER"

# -- Office identifiers -------------------------------------------------------
OFFICE_HCM     = "HCM"
OFFICE_HN      = "HN"
OFFICE_DN      = "DN"
OFFICE_DEFAULT = "HCM"

# -- Incentive threshold (VND) ------------------------------------------------
INCENTIVE_THRESHOLD = 5_000_000

# -- Client type codes --------------------------------------------------------
CLIENT_TYPE_DU_HOC_FULL      = "DU_HOC_FULL"
CLIENT_TYPE_DU_HOC_ENROL     = "DU_HOC_ENROL_ONLY"
CLIENT_TYPE_SUMMER_STUDY     = "SUMMER_STUDY"
CLIENT_TYPE_VIETNAM_DOMESTIC = "VIETNAM_DOMESTIC"
CLIENT_TYPE_GUARDIAN_VISA    = "GUARDIAN_VISA"
CLIENT_TYPE_TOURIST_VISA     = "TOURIST_VISA"
CLIENT_TYPE_MIGRATION_VISA   = "MIGRATION_VISA"
CLIENT_TYPE_DEPENDANT_VISA   = "DEPENDANT_VISA"
CLIENT_TYPE_VISA_ONLY        = "VISA_ONLY_SERVICE"

# -- Institution type values --------------------------------------------------
INST_TYPE_DIRECT       = "DIRECT"
INST_TYPE_MASTER_AGENT = "MASTER_AGENT"
INST_TYPE_GROUP        = "GROUP"
INST_TYPE_OUT_OF_SYS   = "OUT_OF_SYSTEM"
INST_TYPE_RMIT_VN      = "RMIT_VN"
INST_TYPE_BUV_VN       = "BUV_VN"
INST_TYPE_OTHER_VN     = "OTHER_VN"

# -- Deferral values ----------------------------------------------------------
DEFERRAL_NONE            = "NONE"
DEFERRAL_FEE_TRANSFERRED = "FEE_TRANSFERRED"
DEFERRAL_DEFERRED        = "DEFERRED"
DEFERRAL_FEE_WAIVED      = "FEE_WAIVED"
DEFERRAL_NO_SERVICE      = "NO_SERVICE"

# -- Pre-sales sentinel -------------------------------------------------------
PRESALES_NONE = "NONE"

# -- Row type sentinels -------------------------------------------------------
ROW_TYPE_BASE  = "BASE"
ROW_TYPE_ADDON = "ADDON"

# -- ADDON status sentinel ----------------------------------------------------
ADDON_STATUS = "Bundled support package"

# -- Input column positions (1-based, matching v7 template) ------------------
COL_NO             = 1
COL_NAME           = 2
COL_STUDENT_ID     = 3
COL_CONTRACT_ID    = 4
COL_CONTRACT_DATE  = 5
COL_CLIENT_TYPE    = 6
COL_COUNTRY        = 7
COL_AGENT          = 8
COL_SYSTEM         = 9
COL_STATUS         = 10
COL_VISA_DATE      = 11
COL_INSTITUTION    = 12
COL_COURSE_START   = 13
COL_COURSE_STATUS  = 14
COL_COUNSELLOR     = 15
COL_CO             = 16
COL_PRESALES_AGENT = 17
COL_INCENTIVE      = 18
COL_NOTES          = 19
COL_SERVICE_FEE    = 20
COL_DEFERRAL       = 21
COL_PACKAGE_TYPE   = 22
COL_OFFICE         = 23
COL_HANDOVER       = 24
COL_TARGET_OWNER   = 25
COL_CASE_TRANS     = 26
COL_PRIOR_RATE     = 27
COL_INST_TYPE      = 28
COL_GROUP_AGENT    = 29
COL_TARGETS_NAME   = 30
COL_ROW_TYPE       = 31
COL_ADDON_CODE     = 32
COL_ADDON_COUNT    = 33

# -- Output column positions (engine-written, cols 34+) ----------------------
COL_BONUS_ENR        = 34
COL_NOTE_ENR         = 35
COL_NOTE_ENR2        = 36
COL_BONUS_PRI        = 37
COL_NOTE_PRI         = 38
COL_NOTE_PRI2        = 39
COL_PRIOR_ADVANCE    = 40
COL_NET_PAYABLE      = 41
COL_STORED_BASE_RATE = 42

# -- Status deduplication ranks -----------------------------------------------
# Higher rank wins when same ContractID appears multiple times
RANK_CLOSED_FULL      = 5
RANK_CLOSED_ENROLMENT = 4
RANK_CLOSED_CARRYOVER = 3
RANK_CURRENT_ENROLLED = 2
RANK_CLOSED_ZERO      = 1
RANK_UNKNOWN          = 0

# -- Config sheet names -------------------------------------------------------
WS_CONFIG_RATES     = "02_BASE_BONUS_RATES"
WS_CONFIG_PRIORITY  = "03_PRIORITY_INSTNS"
WS_CONFIG_TARGETS   = "04_STAFF_TARGETS"
WS_CONFIG_STATUS    = "05_STATUS_RULES"
WS_CONFIG_WEIGHTS   = "06_CLIENT_WEIGHTS"
WS_YTD_TRACKER      = "08_YTD_TRACKER"
WS_SERVICE_FEE      = "09_SERVICE_FEE_RATES"
WS_MASTER_AGENTS    = "11_MASTER_AGENTS"
WS_STAFF_NAMES      = "12_STAFF_NAMES"
WS_SKIP_LABELS      = "13_SKIP_LABELS"
WS_COUNTRY_CODES    = "14_COUNTRY_CODES"
WS_CLIENT_TYPE_MAP  = "15_CLIENT_TYPE_MAP"

# -- Colours (RGB integers, matching VBA constants) ---------------------------
CLR_BRAND_DARK  = 0x1E4E79   # Dark navy
CLR_BRAND_MID   = 0x2E75B6   # Mid blue
CLR_BRAND_LIGHT = 0xBDD7EE   # Light blue
CLR_GREEN_BG    = 0xE2EFDA   # Light green
CLR_AMBER_BG    = 0xFFFF8C   # Amber
CLR_RED_BG      = 0xFF0000   # Red
CLR_WHITE       = 0xFFFFFF
CLR_BLACK       = 0x000000

# -- Tier calculation: target = 0 behaviour -----------------------------------
# When a staff member has target = 0 for a month:
#   - Any enrolment (count > 0) = OVER
#   - No enrolments             = UNDER
# This is correct policy: a zero target means any result exceeds it.
# DO NOT default to UNDER when target = 0 and enrolled > 0.
TARGET_ZERO_BEHAVIOUR = "OVER_IF_ENROLLED"
