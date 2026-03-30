# =============================================================================
# config.py  |  StudyLink Bonus Engine v1.0
# Config loader — reads from PostgreSQL reference tables.
# engine.xlsm is no longer required at runtime.
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import unicodedata

from .constants import *


@dataclass
class StatusRule:
    status: str
    counts_as_enrolled: bool = False
    coun_pct: float = 0.0
    co_direct_pct: float = 0.0
    co_sub_pct: float = 0.0
    is_carry_over: bool = False
    is_current_enrolled: bool = False
    is_zero_bonus: bool = False
    fees_paid_non_enrolled: bool = False
    is_visa_granted: bool = False
    dedup_rank: int = 0


@dataclass
class StaffTarget:
    name: str
    office: str = OFFICE_HCM
    role: str = "CO"
    scheme: str = SCHEME_HCM_DIRECT
    targets: Dict[int, Dict[int, int]] = field(default_factory=dict)


@dataclass
class ServiceFeeRule:
    code: str
    coun_bonus: int = 0
    co_bonus: int = 0
    active: bool = True
    category: str = ""
    applies_to: str = "ALL"
    description: str = ""


@dataclass
class CountryRule:
    crm_text: str
    code: str
    is_flat_country: bool = False
    is_vietnam: bool = False


@dataclass
class PriorityInstitution:
    name: str
    bonus_pct: float = 0.0
    annual_target: int = 0
    achieved_ytd: int = 0


class BonusConfig:
    def __init__(self):
        self.status_rules:    Dict[str, StatusRule]      = {}
        self.staff_targets:   Dict[str, StaffTarget]     = {}
        self.service_fees:    Dict[str, ServiceFeeRule]  = {}
        self.country_codes:   Dict[str, CountryRule]     = {}
        self.client_types:    Dict[str, str]             = {}
        self.staff_name_map:  Dict[str, str]             = {}
        self.skip_labels:     frozenset                  = SKIP_LABELS
        self.master_agents:   List[str]                  = []
        self.priority_instns: List[PriorityInstitution]  = []
        self.base_rates:      Dict[str, Dict[str, int]]  = {}

    def get_status_rule(self, status: str) -> StatusRule:
        return self.status_rules.get(status.strip().lower(),
               StatusRule(status=status, is_zero_bonus=True))

    def get_service_fee(self, code: str, category: str = "") -> Optional[ServiceFeeRule]:
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

    def get_service_fee_any(self, code: str) -> Optional[ServiceFeeRule]:
        return self.service_fees.get(code.strip().lower()) if code else None

    def resolve_staff_name(self, crm_name: str) -> str:
        return self.staff_name_map.get(crm_name.strip().lower(), crm_name.strip())

    @staticmethod
    def _ascii(s: str) -> str:
        return unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode('ascii').lower().strip()

    def get_staff_target(self, name: str, year: int, month: int) -> Tuple[int, str]:
        resolved = self.resolve_staff_name(name)
        for key in [resolved.lower(), name.strip().lower()]:
            st = self.staff_targets.get(key)
            if st is not None:
                return st.targets.get(year, {}).get(month, 0), st.scheme
        name_ascii     = self._ascii(name)
        resolved_ascii = self._ascii(resolved)
        for key, st in self.staff_targets.items():
            if self._ascii(key) in (name_ascii, resolved_ascii):
                return st.targets.get(year, {}).get(month, 0), st.scheme
        for key, st in self.staff_targets.items():
            ka = self._ascii(key)
            if ka in name_ascii or name_ascii in ka:
                return st.targets.get(year, {}).get(month, 0), st.scheme
        return 0, SCHEME_HCM_DIRECT

    def get_staff_scheme(self, name: str) -> str:
        resolved = self.resolve_staff_name(name)
        for key in [resolved.lower(), name.strip().lower()]:
            st = self.staff_targets.get(key)
            if st is not None:
                return st.scheme
        return SCHEME_HCM_DIRECT

    def get_base_rate(self, scheme: str, tier: str) -> int:
        return self.base_rates.get(scheme, {}).get(tier, 0)

    def get_base_rate_coun(self, scheme: str, tier: str) -> int:
        return self.base_rates.get(scheme, {}).get(f"coun_{tier}", 0)

    def get_country(self, crm_text: str) -> CountryRule:
        return self.country_codes.get(crm_text.strip().lower(),
               CountryRule(crm_text=crm_text, code=crm_text))

    def get_client_type_code(self, crm_text: str) -> str:
        return self.client_types.get(crm_text.strip().lower(), "")

    def is_skip_label(self, label: str) -> bool:
        return label.strip().lower() in self.skip_labels

    def get_kpi_weight(self, ct_code: str, inst_type: str, scheme: str) -> float:
        if ct_code in (CT_SUMMER, CT_GUARDIAN, CT_TOURIST,
                       CT_MIGRATION, CT_DEPENDANT, CT_VISA_ONLY):
            return 0.0
        if ct_code == CT_VIETNAM:
            return 0.5
        if inst_type == INST_MASTER_AGENT:
            return 1.0
        if inst_type == INST_OUT_OF_SYS:
            return 0.7
        return 1.0


# =============================================================================
# PRIMARY LOADER — reads from PostgreSQL
# =============================================================================

def load_config(db) -> BonusConfig:
    """
    Load BonusConfig from PostgreSQL reference tables.
    Pass a SQLAlchemy Session as `db`.
    Replaces the old load_config(workbook_path) — no xlsm needed at runtime.
    """
    from ..models import (
        StaffName as StaffNameModel,
        StaffTarget as StaffTargetModel,
        CountryCode, ClientTypeMap,
        StatusRule as StatusRuleModel,
        ServiceFeeRate, MasterAgent,
        ReferenceList
    )

    cfg = BonusConfig()

    # --- Status Rules ---
    for r in db.query(StatusRuleModel).all():
        cfg.status_rules[r.status_value.lower()] = StatusRule(
            status=r.status_value,
            counts_as_enrolled=r.requires_enrol,
            is_zero_bonus=not r.is_eligible,
            is_visa_granted=r.requires_visa,
        )

    # --- Countries ---
    for r in db.query(CountryCode).filter(CountryCode.is_active == True).all():
        cfg.country_codes[r.country_name.lower()] = CountryRule(
            crm_text=r.country_name,
            code=r.country_code or r.country_name,
        )

    # --- Client Types ---
    for r in db.query(ClientTypeMap).filter(ClientTypeMap.is_active == True).all():
        cfg.client_types[r.raw_value.lower()] = r.canonical

    # --- Staff Name Map from StaffName table ---
    for r in db.query(StaffNameModel).filter(StaffNameModel.is_active == True).all():
        cfg.staff_name_map[r.full_name.lower()] = r.full_name
        if r.short_name:
            cfg.staff_name_map[r.short_name.lower()] = r.full_name

    # Also load CRM name mappings from ref_lists
    for r in db.query(ReferenceList).filter(
        ReferenceList.list_name == "staff_name_map",
        ReferenceList.is_active == True
    ).all():
        # value = CRM name; we need the canonical — look it up from StaffName
        # For now map CRM name to itself (ASCII normalisation handles the rest)
        cfg.staff_name_map[r.value.lower()] = r.value

    # --- Staff Targets ---
    for r in db.query(StaffTargetModel).all():
        key = r.staff_name.lower()
        if key not in cfg.staff_targets:
            office = r.office or OFFICE_HCM
            scheme = (SCHEME_CO_SUB if "sub" in (r.office or "").lower()
                      else SCHEME_HN_DIRECT if office in (OFFICE_HN, OFFICE_DN)
                      else SCHEME_HCM_DIRECT)
            cfg.staff_targets[key] = StaffTarget(
                name=r.staff_name,
                office=office,
                role="CO",
                scheme=scheme
            )
        st = cfg.staff_targets[key]
        if r.year not in st.targets:
            st.targets[r.year] = {}
        st.targets[r.year][r.month] = r.target

    # --- Service Fees ---
    for r in db.query(ServiceFeeRate).filter(ServiceFeeRate.is_active == True).all():
        cfg.service_fees[r.fee_type.lower()] = ServiceFeeRule(
            code=r.fee_type,
            coun_bonus=0,
            co_bonus=r.flat_amount,
            active=r.is_active,
            description=r.note or "",
        )

    # --- Master Agents ---
    for r in db.query(MasterAgent).filter(MasterAgent.is_active == True).all():
        cfg.master_agents.append(r.agent_name)

    # --- Skip Labels ---
    skip = db.query(ReferenceList).filter(
        ReferenceList.list_name == "skip_labels",
        ReferenceList.is_active == True
    ).all()
    if skip:
        cfg.skip_labels = frozenset(r.value.lower() for r in skip)

    # --- Base rates ---
    cfg.base_rates = _default_base_rates()

    return cfg


def _default_base_rates() -> dict:
    """
    Base rates sourced from engine.xlsm 02_BASE_BONUS_RATES.
    Will be moved to PostgreSQL in a future update.
    """
    return {
        SCHEME_HCM_DIRECT: {
            "out_sys_co":             400_000,
            "visa_only_co":           200_000,
            f"coun_{TIER_UNDER}":     500_000,
            TIER_UNDER:               700_000,
            f"coun_{TIER_MEET_HIGH}": 700_000,
            TIER_MEET_HIGH:           900_000,
            f"coun_{TIER_MEET_LOW}":  600_000,
            TIER_MEET_LOW:            800_000,
            f"coun_{TIER_OVER}":      900_000,
            TIER_OVER:              1_100_000,
        },
        SCHEME_HN_DIRECT: {
            "out_sys_co":             400_000,
            "visa_only_co":           200_000,
            f"coun_{TIER_UNDER}":     500_000,
            TIER_UNDER:               700_000,
            f"coun_{TIER_MEET_HIGH}": 700_000,
            TIER_MEET_HIGH:           900_000,
            f"coun_{TIER_MEET_LOW}":  600_000,
            TIER_MEET_LOW:            800_000,
            f"coun_{TIER_OVER}":      900_000,
            TIER_OVER:              1_100_000,
        },
        SCHEME_CO_SUB: {
            "fixed":          400_000,
            TIER_UNDER:       700_000,
            TIER_MEET_HIGH:   900_000,
            TIER_MEET_LOW:    900_000,
            TIER_OVER:      1_100_000,
            "rmit_vn":        600_000,
            "other_vn":       300_000,
            "summer":         300_000,
            "flat":           300_000,
        },
    }
