# =============================================================================
# models.py
# SQLAlchemy ORM models — one class per database table.
# =============================================================================

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Float, ForeignKey, Text, Date, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .database import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    username      = Column(String(50), unique=True, index=True, nullable=False)
    full_name     = Column(String(100))
    email         = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(200), nullable=False)
    is_active     = Column(Boolean, default=True)
    is_admin      = Column(Boolean, default=False)
    staff_name    = Column(String(100))   # Links to canonical staff name
    created_at    = Column(DateTime, default=datetime.utcnow)

    runs          = relationship("Run", back_populates="created_by_user")
    signoffs      = relationship("Signoff", back_populates="user")


class Run(Base):
    """One row per staff member per month submission."""
    __tablename__ = "runs"

    id            = Column(Integer, primary_key=True, index=True)
    staff_name    = Column(String(100), nullable=False, index=True)
    office        = Column(String(10))
    run_month     = Column(Integer, nullable=False)
    run_year      = Column(Integer, nullable=False)
    status        = Column(String(20), default="pending")
    # status values: pending | reviewed | signed_off | calculated | approved

    input_file    = Column(String(300))   # Original uploaded filename
    total_bonus   = Column(Integer, default=0)
    enrolled_count = Column(Integer, default=0)
    tier          = Column(String(20))
    target        = Column(Integer, default=0)

    warnings      = Column(Text)          # JSON array of warning strings
    errors        = Column(Text)          # JSON array of blocking errors

    created_at    = Column(DateTime, default=datetime.utcnow)
    calculated_at = Column(DateTime)

    created_by    = Column(Integer, ForeignKey("users.id"))
    created_by_user = relationship("User", back_populates="runs")

    cases         = relationship("Case", back_populates="run",
                                 cascade="all, delete-orphan")
    signoffs      = relationship("Signoff", back_populates="run",
                                 cascade="all, delete-orphan")


class Case(Base):
    """One row per case per run."""
    __tablename__ = "cases"

    id              = Column(Integer, primary_key=True, index=True)
    run_id          = Column(Integer, ForeignKey("runs.id"), nullable=False, index=True)

    # CRM data
    original_no     = Column(String(10))
    student_name    = Column(String(200))
    student_id      = Column(String(20))
    contract_id     = Column(String(20), index=True)
    contract_date   = Column(Date)
    client_type     = Column(String(100))
    client_type_code = Column(String(50))
    country         = Column(String(100))
    country_code    = Column(String(10))
    agent           = Column(String(200))
    system_type     = Column(String(50))
    app_status      = Column(String(100))
    visa_date       = Column(Date)
    institution     = Column(String(300))
    course_start    = Column(Date)
    course_status   = Column(String(50))
    counsellor      = Column(String(100))
    case_officer    = Column(String(100))

    # Operator fields
    presales_agent  = Column(String(100), default="NONE")
    incentive       = Column(Integer, default=0)
    notes           = Column(Text)
    service_fee_type = Column(String(50), default="NONE")
    deferral        = Column(String(50), default="NONE")
    package_type    = Column(String(100), default="NONE")
    office_override = Column(String(10), default="HCM")
    handover        = Column(String(5), default="NO")
    target_owner    = Column(String(100))
    case_transition = Column(String(5), default="NO")
    prior_month_rate = Column(Integer, default=0)
    institution_type = Column(String(30), default="DIRECT")
    group_agent_name = Column(String(100))
    targets_name    = Column(String(100))
    row_type        = Column(String(10), default="BASE")
    addon_code      = Column(String(50))
    addon_count     = Column(Integer, default=0)

    # Calculated output
    bonus_enrolled  = Column(Integer, default=0)
    note_enrolled   = Column(Text)
    note_enrolled2  = Column(Text)
    bonus_priority  = Column(Integer, default=0)
    note_priority   = Column(Text)
    note_priority2  = Column(Text)
    prior_advances  = Column(Integer, default=0)
    net_payable     = Column(Integer, default=0)
    stored_base_rate = Column(Integer, default=0)
    is_recovery_item = Column(Boolean, default=False)

    # Flags
    has_warnings    = Column(Boolean, default=False)
    warn_msg        = Column(Text)
    is_flagged      = Column(Boolean, default=False)  # Amber flag — needs review

    run             = relationship("Run", back_populates="cases")


class Signoff(Base):
    """Audit trail of approvals."""
    __tablename__ = "signoffs"

    id          = Column(Integer, primary_key=True, index=True)
    run_id      = Column(Integer, ForeignKey("runs.id"), nullable=False)
    user_id     = Column(Integer, ForeignKey("users.id"), nullable=False)
    action      = Column(String(30))   # reviewed | signed_off | approved | rejected
    comment     = Column(Text)
    signed_at   = Column(DateTime, default=datetime.utcnow)

    run         = relationship("Run", back_populates="signoffs")
    user        = relationship("User", back_populates="signoffs")


class AdvancePayment(Base):
    """Ledger of 50% advance payments made for Current-Enrolled cases."""
    __tablename__ = "advance_payments"

    id              = Column(Integer, primary_key=True, index=True)
    contract_id     = Column(String(20), nullable=False, index=True)
    student_name    = Column(String(200))
    staff_name      = Column(String(100), nullable=False)
    period_month    = Column(Integer)
    period_year     = Column(Integer)
    advance_paid    = Column(Integer, default=0)
    status_at_payment = Column(String(100))
    full_bonus_at_tier = Column(Integer, default=0)
    is_settled      = Column(Boolean, default=False)
    settled_at      = Column(DateTime)
    recorded_at     = Column(DateTime, default=datetime.utcnow)


# =============================================================================
# Reference table models — one class per configurable lookup table
# =============================================================================

class StaffName(Base):
    """
    Master list of staff names — single source of truth used by
    STAFF_TARGETS, STAFF_NAMES, Pre-sales Agent dropdowns, and
    counsellor/case officer field validation.
    Vietnamese UTF-8 names stored natively in PostgreSQL.
    """
    __tablename__ = "ref_staff_names"

    id            = Column(Integer, primary_key=True, index=True)
    full_name     = Column(String(100), unique=True, nullable=False, index=True)
    short_name    = Column(String(50))
    office        = Column(String(10))       # HCM | HN | DN
    role          = Column(String(30))       # counsellor | case_officer | presales | co
    is_active     = Column(Boolean, default=True)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StaffTarget(Base):
    """Monthly enrolment targets per staff member."""
    __tablename__ = "ref_staff_targets"

    id            = Column(Integer, primary_key=True, index=True)
    staff_name    = Column(String(100), nullable=False, index=True)
    office        = Column(String(10))
    month         = Column(Integer, nullable=False)
    year          = Column(Integer, nullable=False)
    target        = Column(Integer, default=0)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MasterAgent(Base):
    """Master agent and group classification."""
    __tablename__ = "ref_master_agents"

    id            = Column(Integer, primary_key=True, index=True)
    agent_name    = Column(String(200), nullable=False, index=True)
    agent_type    = Column(String(30))       # MASTER_AGENT | GROUP | DIRECT
    office        = Column(String(10))
    is_active     = Column(Boolean, default=True)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CountryCode(Base):
    """Country name to code mapping."""
    __tablename__ = "ref_country_codes"

    id            = Column(Integer, primary_key=True, index=True)
    country_name  = Column(String(100), unique=True, nullable=False)
    country_code  = Column(String(10))
    region        = Column(String(50))
    is_active     = Column(Boolean, default=True)


class ClientTypeMap(Base):
    """Normalises the many Vietnamese client type variants to a canonical code."""
    __tablename__ = "ref_client_type_map"

    id            = Column(Integer, primary_key=True, index=True)
    raw_value     = Column(String(200), unique=True, nullable=False)
    canonical     = Column(String(50), nullable=False)
    display_name  = Column(String(200))
    is_active     = Column(Boolean, default=True)


class StatusRule(Base):
    """Which application statuses are eligible for bonus calculation."""
    __tablename__ = "ref_status_rules"

    id              = Column(Integer, primary_key=True, index=True)
    status_value    = Column(String(100), unique=True, nullable=False)
    is_eligible     = Column(Boolean, default=True)
    requires_visa   = Column(Boolean, default=False)
    requires_enrol  = Column(Boolean, default=False)
    note            = Column(String(200))


class ServiceFeeRate(Base):
    """Fee rates per service fee type."""
    __tablename__ = "ref_service_fee_rates"

    id              = Column(Integer, primary_key=True, index=True)
    fee_type        = Column(String(50), unique=True, nullable=False)
    rate_pct        = Column(Float, default=0.0)
    flat_amount     = Column(Integer, default=0)
    note            = Column(String(200))
    is_active       = Column(Boolean, default=True)


class ReferenceList(Base):
    """
    Generic key-value store for simple dropdown lists:
    Package Type, Deferral, Office Override, Add-on Codes, etc.
    """
    __tablename__ = "ref_lists"

    id            = Column(Integer, primary_key=True, index=True)
    list_name     = Column(String(50), nullable=False, index=True)
    value         = Column(String(200), nullable=False)
    sort_order    = Column(Integer, default=0)
    is_active     = Column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint('list_name', 'value', name='uq_reflist_name_value'),
    )
