# =============================================================================
# models.py  |  StudyLink Bonus Engine
# All SQLAlchemy ORM models. Zero hardcoded rates or rules.
# Every configurable value lives in a DB table with start/end date controls.
# =============================================================================

from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Date,
    Float, ForeignKey, Text, UniqueConstraint, JSON
)
from sqlalchemy.orm import relationship
from .database import Base


# =============================================================================
# CORE APPLICATION TABLES
# =============================================================================

class User(Base):
    __tablename__ = "users"
    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, index=True, nullable=False)
    full_name       = Column(String(100))
    email           = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(200), nullable=False)
    is_active       = Column(Boolean, default=True)
    is_admin        = Column(Boolean, default=False)
    staff_name      = Column(String(100))
    created_at      = Column(DateTime, default=datetime.utcnow)
    runs     = relationship("Run", back_populates="created_by_user")
    signoffs = relationship("Signoff", back_populates="user")


class Run(Base):
    __tablename__ = "runs"
    id             = Column(Integer, primary_key=True, index=True)
    staff_name     = Column(String(100), nullable=False, index=True)
    office         = Column(String(10))   # HCM | HN | DN
    run_month      = Column(Integer, nullable=False)
    run_year       = Column(Integer, nullable=False)
    status         = Column(String(20), default="pending")
    input_file     = Column(String(300))
    total_bonus    = Column(Integer, default=0)
    enrolled_count = Column(Integer, default=0)
    tier           = Column(String(20))
    target         = Column(Integer, default=0)
    warnings       = Column(Text)
    errors         = Column(Text)
    created_at     = Column(DateTime, default=datetime.utcnow)
    calculated_at  = Column(DateTime)
    created_by     = Column(Integer, ForeignKey("users.id"))
    created_by_user = relationship("User", back_populates="runs")
    cases    = relationship("Case", back_populates="run", cascade="all, delete-orphan")
    signoffs = relationship("Signoff", back_populates="run", cascade="all, delete-orphan")


class Case(Base):
    __tablename__ = "cases"
    id      = Column(Integer, primary_key=True, index=True)
    run_id  = Column(Integer, ForeignKey("runs.id"), nullable=False, index=True)
    original_no      = Column(String(10))
    student_name     = Column(String(200))
    student_id       = Column(String(20))
    contract_id      = Column(String(20), index=True)
    contract_date    = Column(Date)
    client_type      = Column(String(100))
    client_type_code = Column(String(50))
    country          = Column(String(100))
    country_code     = Column(String(10))
    agent            = Column(String(200))
    system_type      = Column(String(50))
    app_status       = Column(String(100))
    visa_date        = Column(Date)
    institution      = Column(String(300))
    course_start     = Column(Date)
    course_status    = Column(String(50))
    counsellor       = Column(String(100))
    case_officer     = Column(String(100))
    presales_agent   = Column(String(100), default="NONE")
    incentive        = Column(Integer, default=0)
    notes            = Column(Text)
    service_fee_type = Column(String(50), default="NONE")
    deferral         = Column(String(50), default="NONE")
    package_type     = Column(String(100), default="NONE")
    office_override  = Column(String(10), default="HCM")
    handover         = Column(String(5), default="NO")
    target_owner     = Column(String(100))
    case_transition  = Column(String(5), default="NO")
    prior_month_rate = Column(Integer, default=0)
    institution_type = Column(String(30), default="DIRECT")
    group_agent_name = Column(String(100))
    targets_name     = Column(String(100))
    row_type         = Column(String(10), default="BASE")
    addon_code       = Column(String(50))
    addon_count      = Column(Integer, default=0)
    bonus_enrolled   = Column(Integer, default=0)
    note_enrolled    = Column(Text)
    note_enrolled2   = Column(Text)
    bonus_priority   = Column(Integer, default=0)
    note_priority    = Column(Text)
    note_priority2   = Column(Text)
    prior_advances   = Column(Integer, default=0)
    net_payable      = Column(Integer, default=0)
    stored_base_rate = Column(Integer, default=0)
    is_recovery_item = Column(Boolean, default=False)
    has_warnings     = Column(Boolean, default=False)
    warn_msg         = Column(Text)
    is_flagged       = Column(Boolean, default=False)
    run = relationship("Run", back_populates="cases")


class Signoff(Base):
    __tablename__ = "signoffs"
    id        = Column(Integer, primary_key=True, index=True)
    run_id    = Column(Integer, ForeignKey("runs.id"), nullable=False)
    user_id   = Column(Integer, ForeignKey("users.id"), nullable=False)
    action    = Column(String(30))
    comment   = Column(Text)
    signed_at = Column(DateTime, default=datetime.utcnow)
    run  = relationship("Run", back_populates="signoffs")
    user = relationship("User", back_populates="signoffs")


class AdvancePayment(Base):
    """
    09_ADVANCE_TRACKER — Ledger of advance payments for Current-Enrolled cases.
    payment_type: Advance | Final | Recovery
    is_settled: True when the corresponding Closed file has been processed.
    """
    __tablename__ = "advance_payments"
    id                 = Column(Integer, primary_key=True, index=True)
    contract_id        = Column(String(20), nullable=False, index=True)
    student_name       = Column(String(200))
    staff_name         = Column(String(100), nullable=False, index=True)
    period_month       = Column(Integer)
    period_year        = Column(Integer)
    advance_paid       = Column(Integer, default=0)
    status_at_payment  = Column(String(100))
    full_bonus_at_tier = Column(Integer, default=0)
    payment_type       = Column(String(20), default="Advance")  # Advance | Final | Recovery
    is_settled         = Column(Boolean, default=False)
    settled_at         = Column(DateTime)
    recorded_at        = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# STAFF TABLES
# =============================================================================

class StaffName(Base):
    """
    12_STAFF_NAMES — Master list of active and historical staff.
    start_date / end_date control employment period.
    scheme determines which bonus rate table applies (HCM_DIRECT, CO_SUB, HN_DIRECT).
    """
    __tablename__ = "ref_staff_names"
    id         = Column(Integer, primary_key=True, index=True)
    full_name  = Column(String(100), unique=True, nullable=False, index=True)
    short_name = Column(String(50))
    office     = Column(String(10))   # HCM | HN | DN
    role       = Column(String(30))   # counsellor | case_officer | presales
    scheme     = Column(String(30))   # HCM_DIRECT | CO_SUB | HN_DIRECT
    start_date = Column(Date)         # employment start
    end_date   = Column(Date)         # employment end (null = still active)
    is_active  = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StaffTarget(Base):
    """
    04_STAFF_TARGETS — Monthly enrolment targets per staff member.
    One row per staff/month/year. Pivot view in the UI.
    """
    __tablename__ = "ref_staff_targets"
    id         = Column(Integer, primary_key=True, index=True)
    staff_name = Column(String(100), nullable=False, index=True)
    office     = Column(String(10))
    month      = Column(Integer, nullable=False)
    year       = Column(Integer, nullable=False)
    target     = Column(Integer, default=0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint('staff_name','month','year', name='uq_target_staff_month_year'),)


# =============================================================================
# BASE RATES TABLE
# Replaces all hardcoded rates in config.py._default_base_rates()
# =============================================================================

class BaseRate(Base):
    """
    02_BASE_BONUS_RATES — All base bonus rates loaded from DB.

    scheme:    HCM_DIRECT | CO_SUB | HN_DIRECT
    tier:      UNDER | MEET_HIGH | MEET_LOW | OVER | OUT_SYS | VISA_ONLY | PARTNER
               MEET_HIGH = meet target AND total enrolled bonus < 5M (higher per-case rate)
               MEET_LOW  = meet target AND total enrolled bonus >= 5M (lower per-case rate)
    role:      COUN (counsellor) | CO (case officer)
    amount:    VND amount per enrolled case

    Trigger:   Applied when scheme + tier + role match the current calculation context.
    Condition: start_date <= run_date <= end_date (null end_date = indefinite).
               Only the most recently started active record for a given scheme/tier/role
               is used in calculation.
    """
    __tablename__ = "ref_base_rates"
    id          = Column(Integer, primary_key=True, index=True)
    scheme      = Column(String(30), nullable=False, index=True)
    tier        = Column(String(30), nullable=False, index=True)
    role        = Column(String(10), nullable=False)  # COUN | CO
    amount      = Column(Integer, default=0)
    start_date  = Column(Date, nullable=False)
    end_date    = Column(Date)
    description = Column(Text)
    conditions  = Column(Text)  # Plain English: when and how this rate is triggered
    is_active   = Column(Boolean, default=True)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# INCENTIVE TIERS TABLE
# Replaces hardcoded INCENTIVE_THRESHOLD = 5_000_000
# =============================================================================

class IncentiveTier(Base):
    """
    Configurable incentive threshold that splits MEET tier into MEET_HIGH / MEET_LOW.
    Extensible for future incentive types (volume bonuses, seasonal promotions, etc.)

    type:         MEET_THRESHOLD  — splits the Meet tier based on total monthly bonus
                  VOLUME_BONUS    — additional bonus for hitting a case count
                  SEASONAL        — time-limited promotion
                  SERVICE_BONUS   — linked to specific service/package types

    threshold_amount:  VND threshold value (e.g. 5,000,000 for the current Meet split)
    service_types:     JSON array of service fee codes this applies to, or ["ALL"]
    package_types:     JSON array of package codes this applies to, or ["ALL"]

    Trigger:  If type=MEET_THRESHOLD and sum(enrolled_bonus) >= threshold_amount
              → use MEET_LOW rate. If < threshold → use MEET_HIGH rate.

    Condition: start_date <= run_date <= end_date. One active MEET_THRESHOLD at a time.
    """
    __tablename__ = "ref_incentive_tiers"
    id                = Column(Integer, primary_key=True, index=True)
    type              = Column(String(50), nullable=False)  # MEET_THRESHOLD | VOLUME_BONUS | SEASONAL | SERVICE_BONUS
    name              = Column(String(200), nullable=False)
    threshold_amount  = Column(Integer, default=0)
    service_types     = Column(Text, default='["ALL"]')  # JSON array
    package_types     = Column(Text, default='["ALL"]')  # JSON array
    start_date        = Column(Date, nullable=False)
    end_date          = Column(Date)
    description       = Column(Text)  # what this incentive covers
    is_active         = Column(Boolean, default=True)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# SPECIAL RATES TABLE
# Vietnam domestic, summer, guardian, visa-only etc. No hardcoding.
# =============================================================================

class SpecialRate(Base):
    """
    Special fixed-rate cases that bypass tier calculation entirely.

    rate_code:          Unique identifier (e.g. RMIT_VN, OTHER_VN, SUMMER, GUARDIAN_VN_G)
    scheme:             HCM_DIRECT | CO_SUB | HN_DIRECT | ALL (applies to all schemes)
    country_code:       ISO code or null (null = applies regardless of country)
    institution_pattern: Substring to match in institution name (e.g. "rmit", "buv")
                         null = matches any institution in the country
    client_type_code:   Canonical client type code (e.g. SUMMER_STUDY) or null
    role:               COUN | CO | ALL
    amount:             VND flat rate

    Trigger order (first match wins):
      1. country_code = VN AND institution_pattern matches → RMIT_VN or OTHER_VN rate
      2. client_type_code = SUMMER_STUDY → SUMMER rate
      3. country_code = VN (any institution) → OTHER_VN rate

    Condition: start_date <= run_date <= end_date.
    """
    __tablename__ = "ref_special_rates"
    id                   = Column(Integer, primary_key=True, index=True)
    rate_code            = Column(String(50), nullable=False, index=True)
    rate_name            = Column(String(200), nullable=False)
    scheme               = Column(String(30), default="ALL")
    country_code         = Column(String(10))
    institution_pattern  = Column(String(200))  # substring match
    client_type_code     = Column(String(50))
    role                 = Column(String(10), default="ALL")  # COUN | CO | ALL
    amount               = Column(Integer, default=0)
    start_date           = Column(Date, nullable=False)
    end_date             = Column(Date)
    conditions           = Column(Text)  # plain English: when/how triggered
    description          = Column(Text)
    is_active            = Column(Boolean, default=True)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# COUNTRY RATES TABLE
# Flat-rate countries (Thailand, Philippines, Malaysia) with per-country amounts
# =============================================================================

class CountryRate(Base):
    """
    Countries that receive a flat bonus rate bypassing the tier calculation.
    These DO NOT count toward the counsellor's monthly target.

    rate_type:  FLAT = fixed amount regardless of tier
                TIERED = use normal tier but with country-specific rates

    Trigger: country_code (or country_name substring) matches the case country.
    Condition: start_date <= run_date <= end_date.
    """
    __tablename__ = "ref_country_rates"
    id                  = Column(Integer, primary_key=True, index=True)
    country_name        = Column(String(100), nullable=False)
    country_code        = Column(String(10))
    scheme              = Column(String(30), default="ALL")
    rate_type           = Column(String(20), default="FLAT")
    co_amount           = Column(Integer, default=0)
    coun_amount         = Column(Integer, default=0)
    counts_toward_target = Column(Boolean, default=False)  # false = no target impact
    start_date          = Column(Date, nullable=False)
    end_date            = Column(Date)
    conditions          = Column(Text)
    description         = Column(Text)
    is_active           = Column(Boolean, default=True)
    updated_at          = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# PARTNER INSTITUTIONS TABLE
# * and ** institutions with configurable fixed rates
# =============================================================================

class PartnerInstitution(Base):
    """
    Out-of-system partner institutions identified by a flag (*/**) in the CRM
    institution name. These bypass tier calculation and receive a fixed rate.

    partner_level: SINGLE (*) = sub-agent referred, CO does enrollment only
                   DOUBLE (**) = premium partner, higher fixed rate (future use)

    co_amount:   Fixed bonus for the Case Officer
    coun_amount: Fixed bonus for the Counsellor (if applicable)

    How identified: institution name contains the flag_pattern in the CRM file.
    flag_pattern: "**" for double-star, "*" for single-star.
    Institution names with ** will match BOTH the ** rule AND the * rule —
    the system checks ** first, then *.

    Trigger: IsPartnerCase = institution_name contains flag_pattern.
    Condition: start_date <= run_date <= end_date.
    """
    __tablename__ = "ref_partner_instns"
    id                = Column(Integer, primary_key=True, index=True)
    partner_level     = Column(String(10), nullable=False)   # SINGLE | DOUBLE
    flag_pattern      = Column(String(5), nullable=False)    # * or **
    rate_name         = Column(String(200))
    co_amount         = Column(Integer, default=0)
    coun_amount       = Column(Integer, default=0)
    country_code      = Column(String(10))  # null = applies to all countries
    start_date        = Column(Date, nullable=False)
    end_date          = Column(Date)
    conditions        = Column(Text)
    description       = Column(Text)
    is_active         = Column(Boolean, default=True)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# ADVANCE PAYMENT RULES TABLE
# Configurable advance % and conditions — no hardcoding of 50%
# =============================================================================

class AdvanceRule(Base):
    """
    Rules governing when and how much advance payment is made for Current-Enrolled cases.

    advance_pct:        Percentage of the full bonus paid in advance (default 0.50 = 50%)
    trigger_status:     The application status that triggers this advance (default "Current - Enrolled")
    service_type:       Specific service fee code this applies to, or "ALL"
    country_code:       Specific country code, or "ALL"
    institution_pattern: Substring match on institution name, or null (any)
    client_type_code:   Specific client type canonical code, or "ALL"

    How advance deduction works at settlement:
      When the Closed file is processed:
        net_payable = full_bonus - sum(prior_advances for this contract_id)
        If net_payable < 0: flagged as RECOVERY item, net_payable = 0

    start_date <= run_date <= end_date to apply this rule.
    Rules are evaluated in priority order (lower sort_order wins).
    """
    __tablename__ = "ref_advance_rules"
    id                   = Column(Integer, primary_key=True, index=True)
    rule_name            = Column(String(200), nullable=False)
    advance_pct          = Column(Float, default=0.5)
    trigger_status       = Column(String(100), default="Current - Enrolled")
    service_type         = Column(String(50), default="ALL")
    country_code         = Column(String(10), default="ALL")
    institution_pattern  = Column(String(200))
    client_type_code     = Column(String(50), default="ALL")
    sort_order           = Column(Integer, default=100)  # lower = higher priority
    start_date           = Column(Date, nullable=False)
    end_date             = Column(Date)
    conditions           = Column(Text)
    description          = Column(Text)
    is_active            = Column(Boolean, default=True)
    updated_at           = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# EXISTING REFERENCE TABLES (updated with date controls and split percentages)
# =============================================================================

class MasterAgent(Base):
    """11_MASTER_AGENTS — Master agent and group classification."""
    __tablename__ = "ref_master_agents"
    id                         = Column(Integer, primary_key=True, index=True)
    agent_name                 = Column(String(200), nullable=False, index=True)
    agent_type                 = Column(String(30))   # MASTER_AGENT | GROUP | DIRECT
    triggers_master_agent_rate = Column(Boolean, default=False)
    notes                      = Column(String(300))
    is_active                  = Column(Boolean, default=True)
    updated_at                 = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CountryCode(Base):
    """14_COUNTRY_CODES — Country name to code mapping."""
    __tablename__ = "ref_country_codes"
    id           = Column(Integer, primary_key=True, index=True)
    country_name = Column(String(100), unique=True, nullable=False)
    country_code = Column(String(10))
    region       = Column(String(50))
    is_active    = Column(Boolean, default=True)

class ClientTypeMap(Base):
    """15_CLIENT_TYPE_MAP — Normalises raw CRM client type text to canonical codes."""
    __tablename__ = "ref_client_type_map"
    id           = Column(Integer, primary_key=True, index=True)
    raw_value    = Column(String(200), unique=True, nullable=False)
    canonical    = Column(String(50), nullable=False)
    display_name = Column(String(200))
    is_active    = Column(Boolean, default=True)


class StatusRule(Base):
    """
    05_STATUS_RULES — Application status eligibility and payment split rules.

    Payment splits determine what % of the base rate each role receives:
      coun_pct:      Counsellor share (0.0 - 1.0)
      co_direct_pct: CO share for HCM_DIRECT / HN_DIRECT scheme
      co_sub_pct:    CO share for CO_SUB scheme

    Special flags:
      is_carry_over:       "Enrolled, then Visa granted" — CO receives deferred 50% from prior month
      is_current_enrolled: "Current - Enrolled" — advance payment triggers; CO gets 50% now
      is_zero_bonus:       Cancelled/refused statuses — no bonus
      fees_paid_non_enrolled: Visa-only or cancelled after payment — special handling

    Condition: start_date <= run_date <= end_date (null dates = always active)
    """
    __tablename__ = "ref_status_rules"
    id                   = Column(Integer, primary_key=True, index=True)
    status_value         = Column(String(100), unique=True, nullable=False)
    is_eligible          = Column(Boolean, default=True)
    counts_as_enrolled   = Column(Boolean, default=False)
    coun_pct             = Column(Float, default=1.0)
    co_direct_pct        = Column(Float, default=1.0)
    co_sub_pct           = Column(Float, default=1.0)
    is_carry_over        = Column(Boolean, default=False)
    is_current_enrolled  = Column(Boolean, default=False)
    is_zero_bonus        = Column(Boolean, default=False)
    fees_paid_non_enrolled = Column(Boolean, default=False)
    requires_visa        = Column(Boolean, default=False)
    requires_enrol       = Column(Boolean, default=False)
    dedup_rank           = Column(Integer, default=0)
    start_date           = Column(Date)
    end_date             = Column(Date)
    conditions           = Column(Text)  # when and how this rule is applied
    triggers             = Column(Text)  # what data in the CRM triggers this rule
    note                 = Column(String(300))


class ServiceFeeRate(Base):
    """09_SERVICE_FEE_RATES — Consolidated service fee + contract + package bonus rules."""
    __tablename__ = "ref_service_fee_rates"
    id           = Column(Integer, primary_key=True, index=True)
    service_code = Column(String(100), unique=True, nullable=False, index=True)
    keywords     = Column(Text)           # pipe-separated match keywords
    coun_bonus   = Column(Integer, default=0)
    co_bonus     = Column(Integer, default=0)
    category     = Column(String(30))     # SERVICE_FEE | PACKAGE | CONTRACT
    applies_to   = Column(String(30))     # ALL | DIRECT | OUT_OF_SYSTEM | MASTER_AGENT
    timing       = Column(String(200))
    description  = Column(Text)
    note         = Column(Text)
    is_active    = Column(Boolean, default=True)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ReferenceList(Base):
    """Generic dropdown list store — all UI validation dropdowns."""
    __tablename__ = "ref_lists"
    id         = Column(Integer, primary_key=True, index=True)
    list_name  = Column(String(50), nullable=False, index=True)
    value      = Column(String(200), nullable=False)
    sort_order = Column(Integer, default=0)
    is_active  = Column(Boolean, default=True)
    __table_args__ = (UniqueConstraint('list_name', 'value', name='uq_reflist_name_value'),)


class PriorityInstitution(Base):
    """03_PRIORITY_INSTNS — Partner institutions with annual targets and priority bonus %."""
    __tablename__ = "ref_priority_instns"
    id               = Column(Integer, primary_key=True, index=True)
    country_code     = Column(String(10), nullable=False)
    institution_name = Column(String(200), nullable=False, index=True)
    annual_target    = Column(Integer, default=0)
    bonus_pct        = Column(Float, default=0.0)
    direct_target    = Column(Integer, default=0)
    sub_target       = Column(Integer, default=0)
    is_active        = Column(Boolean, default=True)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class YtdTracker(Base):
    """
    08_YTD_TRACKER — Year-to-date enrolment counts per priority institution.
    One row per institution × year × month. History is preserved indefinitely.
    Updated automatically after each bonus run via UpdateYTDTracker().
    Replaces the manual CONTROL sheet YTD column from the Excel engine.
    """
    __tablename__ = "ref_ytd_tracker"
    id               = Column(Integer, primary_key=True, index=True)
    institution_name = Column(String(200), nullable=False, index=True)
    year             = Column(Integer, nullable=False)
    month            = Column(Integer, nullable=False)
    enrolment_count  = Column(Integer, default=0)
    updated_at       = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint('institution_name','year','month', name='uq_ytd_inst_year_month'),)


class ClientWeight(Base):
    """06_CLIENT_WEIGHTS — KPI weighting per client type and institution type."""
    __tablename__ = "ref_client_weights"
    id                = Column(Integer, primary_key=True, index=True)
    canonical_code    = Column(String(50), unique=True, nullable=False, index=True)
    display_name      = Column(String(200))
    weight_direct     = Column(Float, default=1.0)
    weight_referred   = Column(Float, default=0.7)
    weight_master     = Column(Float, default=0.7)
    weight_outsys     = Column(Float, default=0.0)
    weight_outsys_usa = Column(Float, default=0.7)
    note              = Column(String(200))
    is_active         = Column(Boolean, default=True)


class ContractBonus(Base):
    """07_CONTRACT_BONUS — Package and contract bonus rules."""
    __tablename__ = "ref_contract_bonuses"
    id              = Column(Integer, primary_key=True, index=True)
    package_name    = Column(String(200), nullable=False)
    service_fee_vnd = Column(String(50))
    coun_bonus      = Column(String(200))
    co_bonus        = Column(String(200))
    timing          = Column(String(200))
    note            = Column(String(300))
    is_active       = Column(Boolean, default=True)
    updated_at      = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# REVIEW WORKFLOW TABLES (replaces SQLite tables previously in routers/reports.py)
# =============================================================================
# These three tables drive the upload → review → submit → approve UI flow.
# Tables are auto-created by Base.metadata.create_all() in main.py at startup.
# Distinct names from `runs` / `cases` to avoid collisions with the existing
# upload pipeline; future work could consolidate.

class BonusReport(Base):
    """
    bonus_reports — one row per uploaded review (was the SQLite `reports` table).
    Uses a hex-token primary key so URLs like /review/aa83a51d4e31ff9b are not
    enumerable by ID.
    """
    __tablename__ = "bonus_reports"
    id           = Column(String(20), primary_key=True)   # secrets.token_hex(8)
    staff_name   = Column(String(100), nullable=False, index=True)
    month        = Column(Integer, nullable=False)
    year         = Column(Integer, nullable=False)
    office       = Column(String(10), nullable=False)
    status       = Column(String(20), default="pending")
    uploaded_by  = Column(String(100))
    uploaded_at  = Column(DateTime, default=datetime.utcnow)
    approved_by  = Column(String(100))
    approved_at  = Column(DateTime)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    notes        = Column(Text)
    target       = Column(Integer, default=0)
    enrolled     = Column(Integer, default=0)
    tier         = Column(String(20))
    engine_total = Column(Integer, default=0)
    manual_total = Column(Integer, default=0)
    gap          = Column(Integer, default=0)
    base_rate    = Column(Integer, default=0)
    cases = relationship("BonusReportCase", back_populates="report",
                         cascade="all, delete-orphan")


class BonusReportCase(Base):
    """
    bonus_report_cases — one row per case in a review (was SQLite `report_cases`).
    Mirrors the engine's CaseRecord shape; persisted after upload and editable
    by Bonus Admin via the field-edit endpoint.
    """
    __tablename__ = "bonus_report_cases"
    id                 = Column(String(50), primary_key=True)
    report_id          = Column(String(20), ForeignKey("bonus_reports.id"),
                                nullable=False, index=True)
    contract_id        = Column(String(20))
    student_name       = Column(String(200))
    student_id         = Column(String(20))
    app_status         = Column(String(100))
    client_type        = Column(String(100))
    country            = Column(String(100))
    institution        = Column(String(300))
    refer_agent        = Column(String(200))
    course_start       = Column(String(20))   # ISO date string
    visa_date          = Column(String(20))
    notes              = Column(Text)
    institution_type   = Column(String(30))
    service_fee_type   = Column(String(50))
    package_type       = Column(String(100))
    is_vietnam         = Column(Boolean, default=False)
    is_agent_referred  = Column(Boolean, default=False)
    office             = Column(String(10))
    row_type           = Column(String(10), default="BASE")
    scheme             = Column(String(30))
    counts_as_enrolled = Column(Boolean, default=False)
    prior_month_rate   = Column(String(20))
    deferral           = Column(String(50), default="NONE")
    handover           = Column(String(5),  default="NO")
    target_owner       = Column(String(100))
    targets_name       = Column(String(100))
    presales_agent     = Column(String(100), default="NONE")
    incentive          = Column(Integer, default=0)
    group_agent_name   = Column(String(100))
    case_transition    = Column(String(5), default="NO")
    bonus_enrolled     = Column(Integer, default=0)
    bonus_priority     = Column(Integer, default=0)
    note_enrolled      = Column(Text)
    note_enrolled_2    = Column(Text)
    note_priority      = Column(Text)
    note_priority_2    = Column(Text)
    gap                = Column(Integer, default=0)
    section            = Column(String(20))
    report = relationship("BonusReport", back_populates="cases")
    __table_args__ = (
        UniqueConstraint('report_id', 'contract_id', name='uq_bonus_report_contract'),
    )


class BonusFieldChange(Base):
    """
    bonus_field_changes — audit log of every edit to a case field (was SQLite
    `field_changes`). Append-only; never updated or deleted.
    """
    __tablename__ = "bonus_field_changes"
    id          = Column(Integer, primary_key=True, autoincrement=True)
    report_id   = Column(String(20), nullable=False, index=True)
    case_id     = Column(String(50), nullable=False)
    field_name  = Column(String(100), nullable=False)
    field_label = Column(String(100))
    old_value   = Column(Text)
    new_value   = Column(Text)
    comment     = Column(Text)
    changed_by  = Column(String(100), nullable=False)
    changed_at  = Column(DateTime, default=datetime.utcnow)
