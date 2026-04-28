# =============================================================================
# models.py  |  StudyLink Bonus Engine v1.0
# Core data structures — equivalent to VBA Type definitions in modInput.bas
# =============================================================================

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .constants import *


@dataclass
class CaseRecord:
    """
    One row from a CRM closed-file report, enriched with operator classifications
    and engine-calculated results.

    Fields 1-19: Raw CRM data (read directly from report)
    Fields 20-33: Operator / classifier fields (auto-set by classify.py)
    Fields 34+: Engine output (set by calc.py)
    """

    # ── Raw CRM fields ────────────────────────────────────────────────────────
    original_no:    str  = ""
    student_name:   str  = ""
    student_id:     str  = ""
    contract_id:    str  = ""
    contract_date:  Optional[date] = None
    client_type:    str  = ""    # CRM Vietnamese text
    country:        str  = ""    # CRM country text
    agent:          str  = ""    # Refer source agent
    system_type:    str  = ""    # Trong / Ngoài hệ thống
    app_status:     str  = ""    # Application report status
    visa_date:      Optional[date] = None
    institution:    str  = ""
    course_start:   Optional[date] = None
    course_status:  str  = ""
    counsellor:     str  = ""    # CRM full name
    case_officer:   str  = ""    # CRM full name
    presales_agent: str  = PRESALES_NONE
    incentive:      int  = 0     # Customer incentive (VND)
    notes:          str  = ""

    # ── Operator / classifier fields ──────────────────────────────────────────
    service_fee_type: str = SVC_NONE       # Code from 09_SERVICE_FEE_RATES
    deferral:         str = DEFERRAL_NONE  # Deferral / waiver code
    package_type:     str = PKG_NONE       # Package code from 09_SERVICE_FEE_RATES
    office:           str = OFFICE_DEFAULT # HCM / HN / DN
    scheme:           str = ""             # Stage 4: per-case scheme
                                            # (HCM_DIRECT / HN_DIRECT / CO_SUB / etc.)
                                            # Empty → engine defaults to staff home scheme.
                                            # Operator can override per case in Review UI.
    handover:         str = "NO"           # YES / NO
    target_owner:     str = ""             # Relevant if handover = YES
    case_transition:  str = "NO"           # YES / NO
    prior_month_rate: int = 0              # Col 27 — mandatory for carry-overs
    institution_type: str = INST_DIRECT    # DIRECT / MASTER_AGENT / GROUP / OUT_OF_SYSTEM / etc.
    group_agent_name: str = ""             # Required if inst_type = MASTER_AGENT or GROUP
    targets_name:     str = ""             # Canonical staff name from 04_STAFF_TARGETS
    row_type:         str = ROW_BASE       # BASE / ADDON
    addon_code:       str = ""             # ADDON rows only
    addon_count:      int = 0              # ADDON rows only

    # ── Per-case priority factor override (Apr 2026 v6.5) ─────────────────────
    # When > 0, _apply_priority uses this factor instead of deriving from
    # achieved_ytd vs annual_target. Captures the partner-specific business
    # decision recorded by the báo cáo author (e.g., RMIT promoted to 100%
    # effective Feb 2024 while other partners stayed at 50%).
    # Range: 0.5 = half bonus, 1.0 = full bonus. 0 (default) means "use
    # achieved_ytd-based logic".
    priority_factor: float = 0.0

    # ── Derived fields (set during parsing/classification) ────────────────────
    client_type_code: str  = ""       # Canonical code from 15_CLIENT_TYPE_MAP
    country_code:     str  = ""       # Canonical code from 14_COUNTRY_CODES
    is_flat_country:  bool = False    # Thailand, Malaysia, Philippines
    is_vietnam:       bool = False    # Vietnam domestic program
    exclude_from_calc:bool = False    # Cross-office exclusion
    is_duplicate:     bool = False    # Lower-ranked duplicate of same ContractID
    warn_flags:       list = field(default_factory=list)  # Non-blocking warnings
    is_agent_referred: bool = False  # External refer-source agent → 0.7 KPI weight

    # ── Engine output fields (set by calc.py) ─────────────────────────────────
    bonus_enrolled:   int  = 0
    note_enrolled:    str  = ""
    note_enrolled2:   str  = ""
    bonus_priority:   int  = 0
    note_priority:    str  = ""
    note_priority2:   str  = ""
    prior_advances:   int  = 0
    net_payable:      int  = 0
    base_rate:        int  = 0     # Stored base rate before split
    is_recovery:      bool = False  # Net payable < 0

    # ── Display fields ────────────────────────────────────────────────────────
    display_no: int = 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warn_flags) > 0

    @property
    def is_flagged(self) -> bool:
        """Amber flag — needs operator attention before calculation."""
        return (self.package_type in (PKG_NONE, "") and
                self.service_fee_type in (SVC_NONE, ""))

    def add_warning(self, msg: str):
        self.warn_flags.append(msg)
