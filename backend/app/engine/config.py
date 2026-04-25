# =============================================================================
# config.py  |  StudyLink Bonus Engine v6.3
# Reconstructed: 2-arg get_service_fee + standalone build (no DB required)
# =============================================================================

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple
import unicodedata

from .constants import *


@dataclass
class StatusRuleObj:
    status: str
    counts_as_enrolled: bool = False
    coun_pct: float = 1.0
    co_direct_pct: float = 1.0
    co_sub_pct: float = 1.0
    is_carry_over: bool = False
    is_current_enrolled: bool = False
    is_zero_bonus: bool = False
    fees_paid_non_enrolled: bool = False
    is_visa_granted: bool = False
    dedup_rank: int = 0


@dataclass
class StaffTargetObj:
    name: str
    office: str = OFFICE_HCM
    role: str = "CO"
    scheme: str = SCHEME_HCM_DIRECT
    targets: Dict[int, Dict[int, int]] = field(default_factory=dict)


@dataclass
class ServiceFeeRuleObj:
    code: str
    co_bonus: int = 0
    coun_bonus: int = 0
    category: str = "SERVICE_FEE"
    applies_to: str = "ALL"
    keywords: str = ""
    active: bool = True
    description: str = ""


@dataclass
class CountryRuleObj:
    crm_text: str
    code: str
    is_flat_country: bool = False
    is_vietnam: bool = False


@dataclass
class PriorityInstitutionObj:
    name: str
    bonus_pct: float = 0.0
    annual_target: int = 0
    achieved_ytd: int = 0


# Backwards-compatible alias — calc.py imports StatusRule from this module
StatusRule = StatusRuleObj


class BonusConfig:
    def __init__(self):
        self.status_rules:      Dict[str, StatusRuleObj]         = {}
        self.staff_targets:     Dict[str, StaffTargetObj]        = {}
        self.service_fees:      Dict[str, ServiceFeeRuleObj]     = {}
        self.country_codes:     Dict[str, CountryRuleObj]        = {}
        self.client_types:      Dict[str, str]                   = {}
        self.staff_name_map:    Dict[str, str]                   = {}
        self.skip_labels:       frozenset                        = SKIP_LABELS
        self.master_agents:     List[str]                        = []
        self.priority_instns:   List[PriorityInstitutionObj]     = []
        # base_rates: scheme → (tier → {CO/COUN: amt}) PLUS flat keys (out_sys_co etc)
        self.base_rates:        Dict[str, Dict]                  = {}
        self.incentive_threshold: int = INCENTIVE_THRESHOLD

    def get_status_rule(self, status: str) -> StatusRuleObj:
        return self.status_rules.get(status.strip().lower(),
               StatusRuleObj(status=status, is_zero_bonus=True))

    def get_service_fee(self, code: str, category: str = "") -> Optional[ServiceFeeRuleObj]:
        """v6.3 fix #2: optional category filter parameter."""
        if not code or code.upper() in (SVC_NONE, ""):
            return None
        r = self.service_fees.get(code.strip().lower())
        if r is None:
            return None
        if category and r.category.upper() != category.upper():
            return None
        if not r.active:
            return None
        return r

    def resolve_staff_name(self, crm_name: str) -> str:
        return self.staff_name_map.get(crm_name.strip().lower(), crm_name.strip())

    @staticmethod
    def _ascii(s: str) -> str:
        return unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii').lower().strip()

    def get_staff_target(self, name: str, year: int, month: int) -> Tuple[int, str]:
        resolved = self.resolve_staff_name(name)
        for key in [resolved.lower(), name.strip().lower()]:
            st = self.staff_targets.get(key)
            if st: return st.targets.get(year,{}).get(month,0), st.scheme
        na = self._ascii(name); ra = self._ascii(resolved)
        for key, st in self.staff_targets.items():
            if self._ascii(key) in (na, ra):
                return st.targets.get(year,{}).get(month,0), st.scheme
        for key, st in self.staff_targets.items():
            ka = self._ascii(key)
            if ka in na or na in ka:
                return st.targets.get(year,{}).get(month,0), st.scheme
        return 0, SCHEME_HCM_DIRECT

    def get_country(self, crm_text: str) -> CountryRuleObj:
        return self.country_codes.get(crm_text.strip().lower(),
               CountryRuleObj(crm_text=crm_text, code=crm_text))

    def get_client_type_code(self, crm_text: str) -> str:
        return self.client_types.get(crm_text.strip().lower(), "")

    def is_skip_label(self, label: str) -> bool:
        return label.strip().lower() in self.skip_labels

    def get_kpi_weight(self, ct_code: str, inst_type: str, scheme: str) -> float:
        if ct_code in (CT_SUMMER, CT_GUARDIAN, CT_TOURIST, CT_MIGRATION,
                       CT_DEPENDANT, CT_VISA_ONLY):
            return 0.0
        if ct_code == CT_VIETNAM:
            return 0.5
        if inst_type == INST_MASTER_AGENT:
            return 1.0
        if inst_type == INST_OUT_OF_SYS:
            return 0.7
        return 1.0
