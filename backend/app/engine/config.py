# =============================================================================
# config.py
# Equivalent of modConfig.bas
# Loads all policy lookup tables from the engine workbook config sheets.
# All data is loaded once at startup and held in module-level dictionaries.
# =============================================================================

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import openpyxl

from .constants import (
    SCHEME_HCM_DIRECT, SCHEME_HN_DIRECT, SCHEME_CO_SUB,
    OFFICE_HCM, OFFICE_HN, OFFICE_DN, OFFICE_DEFAULT,
    WS_CONFIG_RATES, WS_CONFIG_PRIORITY, WS_CONFIG_TARGETS,
    WS_CONFIG_STATUS, WS_CONFIG_WEIGHTS, WS_SERVICE_FEE,
    WS_MASTER_AGENTS, WS_STAFF_NAMES, WS_SKIP_LABELS,
    WS_COUNTRY_CODES, WS_CLIENT_TYPE_MAP,
    TIER_UNDER, TIER_MEET, TIER_OVER, TIER_MEET_HIGH, TIER_MEET_LOW,
)


# =============================================================================
# Data classes (equivalent to VBA Type definitions)
# =============================================================================

@dataclass
class StaffConfig:
    name: str = ""
    office: str = OFFICE_DEFAULT
    role: str = ""
    partner: str = ""
    scheme: str = SCHEME_HCM_DIRECT
    targets: Dict[int, int] = field(default_factory=lambda: {m: 0 for m in range(1, 13)})


@dataclass
class StatusRule:
    status: str = ""
    counts_as_enrolled: bool = False
    split_coun_pct: float = 0.0
    split_co_direct_pct: float = 0.0
    split_co_sub_pct: float = 0.0
    is_carry_over: bool = False
    is_current_enrolled: bool = False
    is_zero_bonus: bool = False
    fees_paid_non_enrolled: bool = False
    is_visa_granted: bool = False
    deduplication_rank: int = 0
    notes: str = ""


@dataclass
class ClientWeightRule:
    client_type_code: str = ""
    weight_in_system: float = 1.0
    weight_sub_agent: float = 1.0
    weight_master_agent: float = 1.0
    weight_out_system: float = 1.0
    weight_out_system_usa: float = 1.0


@dataclass
class CountryCodeRule:
    crm_text: str = ""
    canonical_code: str = ""
    is_flat_country: bool = False
    is_vietnam: bool = False


@dataclass
class ServiceFeeRule:
    service_code: str = ""
    keywords: str = ""
    counsellor_bonus: int = 0
    co_bonus: int = 0
    active: bool = True
    category: str = ""
    description: str = ""


@dataclass
class StaffNameMap:
    crm_name: str = ""
    targets_name: str = ""


@dataclass
class PriorityInstitution:
    name: str = ""
    bonus_pct: float = 0.0
    annual_target: int = 0
    achieved_ytd: int = 0


# =============================================================================
# Module-level config store
# =============================================================================

class BonusConfig:
    """
    Holds all loaded configuration. One instance is created per engine run.
    Equivalent to the module-level Public arrays in modConfig.bas.
    """

    def __init__(self):
        # Staff
        self.staff: List[StaffConfig] = []
        self.staff_name_map: List[StaffNameMap] = []

        # Policy rules
        self.status_rules: Dict[str, StatusRule] = {}
        self.client_weights: Dict[str, ClientWeightRule] = {}
        self.country_codes: List[CountryCodeRule] = []
        self.client_type_map: Dict[str, str] = {}  # crm_text -> canonical_code
        self.skip_labels: List[str] = []
        self.master_agents: List[str] = []
        self.priority_instns: List[PriorityInstitution] = []
        self.service_fees: Dict[str, ServiceFeeRule] = {}

        # Base rates — HCM Direct
        # Index: 0=OutSystem, 1=Under, 2=MeetHigh, 3=MeetLow, 4=Over
        self.rate_hcm_coun: Dict[int, int] = {i: 0 for i in range(5)}
        self.rate_hcm_co:   Dict[int, int] = {i: 0 for i in range(5)}

        # Base rates — HN/DN Direct
        self.rate_hn_coun: Dict[int, int] = {i: 0 for i in range(5)}
        self.rate_hn_co:   Dict[int, int] = {i: 0 for i in range(5)}

        # CO Sub rates
        # 0=Partner, 1-3=EnrolOnly(Under/Meet/Over), 4-6=EnrolVisa(Under/Meet/Over)
        self.rate_co_sub: Dict[int, int] = {i: 0 for i in range(7)}

        # Special fixed rates
        self.rate_rmit_vn: int = 0
        self.rate_other_vn: int = 0
        self.rate_hn_rmit_vn: int = 0
        self.rate_hn_other_vn: int = 0
        self.rate_co_sub_vn_enrol: int = 0
        self.rate_co_sub_buv_vn: int = 0
        self.rate_co_sub_other_vn: int = 0
        self.rate_summer: int = 0
        self.rate_hn_summer: int = 0
        self.rate_co_sub_summer: int = 0
        self.rate_flat_coun: int = 0
        self.rate_flat_co: int = 0
        self.rate_hn_flat_coun: int = 0
        self.rate_hn_flat_co: int = 0
        self.rate_visa_only_hcm_co: int = 0
        self.rate_visa_485_coun: int = 0
        self.rate_visa_485_co: int = 0
        self.rate_guardian_granted_coun: int = 0
        self.rate_guardian_granted_co: int = 0
        self.rate_guardian_refused_coun: int = 0
        self.rate_guardian_refused_co: int = 0
        self.rate_dependant_granted_coun: int = 0
        self.rate_dependant_granted_co: int = 0
        self.rate_dependant_refused_coun: int = 0
        self.rate_dependant_refused_co: int = 0

    # -------------------------------------------------------------------------
    # Lookup helpers
    # -------------------------------------------------------------------------

    def get_status_rule(self, status: str) -> StatusRule:
        """Case-insensitive exact match. Returns safe zero-bonus default if not found."""
        key = status.strip().lower()
        for s, rule in self.status_rules.items():
            if s.strip().lower() == key:
                return rule
        # Unknown status — return safe default (zero bonus)
        return StatusRule(status=status, is_zero_bonus=True)

    def get_staff_config(self, name: str, office: str) -> Optional[StaffConfig]:
        """
        Resolves name via staff_name_map first, then matches on resolved name + office.
        Falls back to same name under any office (cross-office cases).
        Returns None if truly not found.
        """
        resolved = self.resolve_staff_name(name)
        office_norm = office.strip().upper() if office else OFFICE_DEFAULT

        # Pass 1: exact name + office match
        for s in self.staff:
            if (s.name.strip().lower() == resolved.lower() and
                    s.office.strip().upper() == office_norm):
                return s

        # Pass 2: name found under different office (cross-office case)
        for s in self.staff:
            if s.name.strip().lower() == resolved.lower():
                # Return a copy with zeroed targets for the secondary office
                import copy
                secondary = copy.deepcopy(s)
                secondary.office = office_norm
                secondary.targets = {m: 0 for m in range(1, 13)}
                if office_norm in (OFFICE_HN, OFFICE_DN):
                    secondary.scheme = SCHEME_HN_DIRECT
                return secondary

        return None

    def resolve_staff_name(self, crm_name: str) -> str:
        """Looks up CRM name in staff_name_map. Returns targets-sheet name if found."""
        crm_lower = crm_name.strip().lower()
        for m in self.staff_name_map:
            if m.crm_name.strip().lower() == crm_lower:
                return m.targets_name
        return crm_name

    def get_client_type_code(self, crm_text: str) -> str:
        """Maps CRM Vietnamese text to canonical client type code."""
        if not crm_text:
            return ""
        crm_lower = crm_text.strip().lower()
        # Check if already a canonical code
        for code in self.client_weights:
            if code.lower() == crm_lower:
                return code
        # Check mapping table
        return self.client_type_map.get(crm_lower, "")

    def get_country_code(self, crm_text: str) -> CountryCodeRule:
        """Returns CountryCodeRule for a CRM country text."""
        crm_lower = crm_text.strip().lower()
        for c in self.country_codes:
            if c.crm_text.strip().lower() == crm_lower:
                return c
        return CountryCodeRule(crm_text=crm_text, canonical_code=crm_text)

    def is_flat_country(self, canonical_code: str) -> bool:
        for c in self.country_codes:
            if c.canonical_code.upper() == canonical_code.upper():
                return c.is_flat_country
        return False

    def is_vietnam_country(self, canonical_code: str) -> bool:
        for c in self.country_codes:
            if c.canonical_code.upper() == canonical_code.upper():
                return c.is_vietnam
        return False

    def is_skip_label(self, label: str) -> bool:
        label_lower = label.strip().lower()
        return any(s.strip().lower() == label_lower for s in self.skip_labels)

    def is_master_agent(self, name: str) -> bool:
        name_lower = name.strip().lower()
        return any(m.strip().lower() == name_lower for m in self.master_agents)

    def get_kpi_weight(self, client_type_code: str, scheme: str, inst_type: str) -> float:
        """Returns KPI weight for tier counting."""
        from .constants import (
            INST_TYPE_MASTER_AGENT, INST_TYPE_OUT_OF_SYS, SCHEME_CO_SUB
        )
        rule = self.client_weights.get(client_type_code)
        if not rule:
            return 1.0
        if inst_type == INST_TYPE_MASTER_AGENT:
            return rule.weight_master_agent
        if inst_type == INST_TYPE_OUT_OF_SYS:
            return rule.weight_out_system
        if scheme == SCHEME_CO_SUB:
            return rule.weight_sub_agent
        return rule.weight_in_system

    def get_base_rate(self, scheme: str, tier: str) -> int:
        """Returns base bonus rate for a given scheme and tier."""
        tier_index = {
            TIER_UNDER:     1,
            TIER_MEET_LOW:  3,
            TIER_MEET_HIGH: 2,
            TIER_MEET:      2,  # Default MEET to MEET_HIGH until resolved
            TIER_OVER:      4,
        }.get(tier, 1)

        if scheme == SCHEME_HCM_DIRECT:
            return self.rate_hcm_co.get(tier_index, 0)
        elif scheme == SCHEME_HN_DIRECT:
            return self.rate_hn_co.get(tier_index, 0)
        elif scheme == SCHEME_CO_SUB:
            return self.rate_co_sub.get(tier_index, 0)
        return 0

    def get_base_rate_coun(self, scheme: str, tier: str) -> int:
        """Returns counsellor base bonus rate."""
        tier_index = {
            TIER_UNDER:     1,
            TIER_MEET_LOW:  3,
            TIER_MEET_HIGH: 2,
            TIER_MEET:      2,
            TIER_OVER:      4,
        }.get(tier, 1)

        if scheme == SCHEME_HN_DIRECT:
            return self.rate_hn_coun.get(tier_index, 0)
        return self.rate_hcm_coun.get(tier_index, 0)

    def get_service_fee(self, code: str, category: str = "") -> Optional[ServiceFeeRule]:
        """Looks up service fee rule by code and optional category."""
        code_lower = code.strip().lower()
        for c, rule in self.service_fees.items():
            if c.strip().lower() == code_lower:
                if category and rule.category.strip().lower() != category.lower():
                    continue
                return rule
        return None


# =============================================================================
# Loader — reads from engine workbook Excel file
# =============================================================================

def load_config(workbook_path: str, run_year: int) -> BonusConfig:
    """
    Loads all configuration from the engine workbook.
    Returns a fully populated BonusConfig instance.
    """
    cfg = BonusConfig()
    wb = openpyxl.load_workbook(workbook_path, data_only=True)

    _load_status_rules(wb, cfg)
    _load_client_weights(wb, cfg)
    _load_country_codes(wb, cfg)
    _load_client_type_map(wb, cfg)
    _load_skip_labels(wb, cfg)
    _load_master_agents(wb, cfg)
    _load_staff_name_map(wb, cfg)
    _load_staff_targets(wb, cfg, run_year)
    _load_base_rates(wb, cfg)
    _load_service_fees(wb, cfg)
    _load_priority_instns(wb, cfg)

    return cfg


def _cell_str(cell) -> str:
    v = cell.value
    return str(v).strip() if v is not None else ""


def _cell_int(cell) -> int:
    v = cell.value
    try:
        return int(float(str(v))) if v is not None else 0
    except (ValueError, TypeError):
        return 0


def _cell_float(cell) -> float:
    v = cell.value
    if v is None:
        return 0.0
    s = str(v).replace("%", "").strip()
    try:
        f = float(s)
        return f / 100 if "%" in str(v) else f
    except (ValueError, TypeError):
        return 0.0


def _cell_bool(cell) -> bool:
    v = _cell_str(cell).upper()
    return v == "Y"


def _load_status_rules(wb, cfg: BonusConfig):
    """05_STATUS_RULES: cols A=Status, B=CountsAsEnrolled, C=SplitCoun%,
       D=SplitCODirect%, E=SplitCOSub%, F=Notes, G=IsCarryOver, H=IsCurrentEnrolled,
       I=IsZeroBonus, J=FeesPaidNonEnrolled, K=IsVisaGranted, L=DeduplicationRank"""
    ws = wb[WS_CONFIG_STATUS]
    for row in ws.iter_rows(min_row=2):
        status = _cell_str(row[0])
        if not status or status.startswith("("):
            continue
        rule = StatusRule(
            status=status,
            counts_as_enrolled=_cell_bool(row[1]),
            split_coun_pct=_cell_float(row[2]),
            split_co_direct_pct=_cell_float(row[3]),
            split_co_sub_pct=_cell_float(row[4]),
            notes=_cell_str(row[5]) if len(row) > 5 else "",
            is_carry_over=_cell_bool(row[6]) if len(row) > 6 else False,
            is_current_enrolled=_cell_bool(row[7]) if len(row) > 7 else False,
            is_zero_bonus=_cell_bool(row[8]) if len(row) > 8 else False,
            fees_paid_non_enrolled=_cell_bool(row[9]) if len(row) > 9 else False,
            is_visa_granted=_cell_bool(row[10]) if len(row) > 10 else False,
            deduplication_rank=_cell_int(row[11]) if len(row) > 11 else 0,
        )
        cfg.status_rules[status] = rule


def _load_client_weights(wb, cfg: BonusConfig):
    """06_CLIENT_WEIGHTS: A=Label, B=ClientTypeCode, C=WeightInSystem,
       D=WeightSubAgent, E=WeightMasterAgent, F=WeightOutSystem, G=WeightOutSystemUSA"""
    ws = wb[WS_CONFIG_WEIGHTS]
    for row in ws.iter_rows(min_row=2):
        code = _cell_str(row[1])
        if not code or code.startswith("("):
            continue
        rule = ClientWeightRule(
            client_type_code=code,
            weight_in_system=_cell_float(row[2]),
            weight_sub_agent=_cell_float(row[3]),
            weight_master_agent=_cell_float(row[4]),
            weight_out_system=_cell_float(row[5]),
            weight_out_system_usa=_cell_float(row[6]) if len(row) > 6 else 0.0,
        )
        cfg.client_weights[code] = rule


def _load_country_codes(wb, cfg: BonusConfig):
    """14_COUNTRY_CODES: A=CRMText, B=CanonicalCode, C=IsFlatCountry, D=IsVietnam"""
    if WS_COUNTRY_CODES not in wb.sheetnames:
        return
    ws = wb[WS_COUNTRY_CODES]
    for row in ws.iter_rows(min_row=3):
        crm = _cell_str(row[0])
        if not crm:
            continue
        cfg.country_codes.append(CountryCodeRule(
            crm_text=crm,
            canonical_code=_cell_str(row[1]),
            is_flat_country=_cell_bool(row[2]),
            is_vietnam=_cell_bool(row[3]) if len(row) > 3 else False,
        ))


def _load_client_type_map(wb, cfg: BonusConfig):
    """15_CLIENT_TYPE_MAP: A=CRMText, B=CanonicalCode"""
    if WS_CLIENT_TYPE_MAP not in wb.sheetnames:
        return
    ws = wb[WS_CLIENT_TYPE_MAP]
    for row in ws.iter_rows(min_row=4):
        crm = _cell_str(row[0])
        code = _cell_str(row[1])
        if crm and code:
            cfg.client_type_map[crm.lower()] = code


def _load_skip_labels(wb, cfg: BonusConfig):
    """13_SKIP_LABELS: A=Label"""
    if WS_SKIP_LABELS not in wb.sheetnames:
        return
    ws = wb[WS_SKIP_LABELS]
    for row in ws.iter_rows(min_row=2):
        lbl = _cell_str(row[0])
        if lbl:
            cfg.skip_labels.append(lbl)


def _load_master_agents(wb, cfg: BonusConfig):
    """11_MASTER_AGENTS: A=AgentName"""
    if WS_MASTER_AGENTS not in wb.sheetnames:
        return
    ws = wb[WS_MASTER_AGENTS]
    for row in ws.iter_rows(min_row=2):
        name = _cell_str(row[0])
        if name:
            cfg.master_agents.append(name)


def _load_staff_name_map(wb, cfg: BonusConfig):
    """12_STAFF_NAMES: B=CRMName, C=TargetsName"""
    if WS_STAFF_NAMES not in wb.sheetnames:
        return
    ws = wb[WS_STAFF_NAMES]
    for row in ws.iter_rows(min_row=5):
        crm = _cell_str(row[1]) if len(row) > 1 else ""
        tgt = _cell_str(row[2]) if len(row) > 2 else ""
        if crm and tgt and not crm.startswith("("):
            cfg.staff_name_map.append(StaffNameMap(crm_name=crm, targets_name=tgt))


def _load_staff_targets(wb, cfg: BonusConfig, run_year: int):
    """04_STAFF_TARGETS: A=Year or Name, B=Office, C=Role, D=Partner, E-P=Jan-Dec"""
    ws = wb[WS_CONFIG_TARGETS]
    in_year = False
    for row in ws.iter_rows(min_row=4):
        cell_a = _cell_str(row[0])
        if not cell_a:
            # Check col E for year
            if len(row) > 4:
                yr = row[4].value
                if yr and str(yr).isdigit():
                    in_year = (int(yr) == run_year)
            continue
        if cell_a.isdigit():
            in_year = (int(cell_a) == run_year)
            continue
        if not in_year:
            continue
        office = _cell_str(row[1]).upper() or OFFICE_DEFAULT
        role   = _cell_str(row[2]).upper()
        partner = _cell_str(row[3])

        if office in (OFFICE_HN, OFFICE_DN):
            scheme = SCHEME_HN_DIRECT
        elif role == "CO_SUB":
            scheme = SCHEME_CO_SUB
        else:
            scheme = SCHEME_HCM_DIRECT

        targets = {}
        for m in range(1, 13):
            col_idx = 4 + m  # Col E=Jan(1), F=Feb(2)...
            targets[m] = _cell_int(row[col_idx]) if len(row) > col_idx else 0

        cfg.staff.append(StaffConfig(
            name=cell_a,
            office=office,
            role=role,
            partner=partner,
            scheme=scheme,
            targets=targets,
        ))


def _load_base_rates(wb, cfg: BonusConfig):
    """02_BASE_BONUS_RATES: loaded by label lookup via FindRateRow."""
    ws = wb[WS_CONFIG_RATES]
    all_rows = list(ws.iter_rows(values_only=True))

    def find_row(label: str, start: int, end: int) -> Optional[int]:
        """Find row index (0-based) where col A contains label (case-insensitive partial)."""
        label_lower = label.lower()
        for i in range(start, min(end, len(all_rows))):
            cell = str(all_rows[i][0] or "").lower()
            if label_lower in cell:
                return i
        return None

    def get_rate(row_idx: Optional[int], col: int) -> int:
        if row_idx is None or row_idx >= len(all_rows):
            return 0
        try:
            v = all_rows[row_idx][col]
            return int(float(str(v))) if v is not None else 0
        except (ValueError, TypeError):
            return 0

    # Section A: HCM Direct (rows 1-30 approx)
    r = find_row("under", 1, 30)
    cfg.rate_hcm_coun[1] = get_rate(r, 2)
    cfg.rate_hcm_co[1]   = get_rate(r, 3)

    r = find_row("meet", 1, 30)
    cfg.rate_hcm_coun[2] = get_rate(r, 2)
    cfg.rate_hcm_co[2]   = get_rate(r, 3)

    r = find_row("over", 1, 30)
    cfg.rate_hcm_coun[4] = get_rate(r, 2)
    cfg.rate_hcm_co[4]   = get_rate(r, 3)

    # Section B: Special fixed rates
    r = find_row("rmit", 1, 50)
    cfg.rate_rmit_vn = get_rate(r, 2)

    r = find_row("buv", 1, 50)
    cfg.rate_co_sub_buv_vn = get_rate(r, 2)

    r = find_row("other vn", 1, 50)
    cfg.rate_other_vn = get_rate(r, 2)

    r = find_row("summer", 1, 50)
    cfg.rate_summer = get_rate(r, 2)

    r = find_row("flat", 1, 50)
    cfg.rate_flat_coun = get_rate(r, 2)
    cfg.rate_flat_co   = get_rate(r, 3)

    r = find_row("visa only", 1, 50)
    cfg.rate_visa_only_hcm_co = get_rate(r, 3)

    # Section C: HN Direct
    r = find_row("under", 30, 80)
    cfg.rate_hn_coun[1] = get_rate(r, 2)
    cfg.rate_hn_co[1]   = get_rate(r, 3)

    r = find_row("meet", 30, 80)
    cfg.rate_hn_coun[2] = get_rate(r, 2)
    cfg.rate_hn_co[2]   = get_rate(r, 3)

    r = find_row("over", 30, 80)
    cfg.rate_hn_coun[4] = get_rate(r, 2)
    cfg.rate_hn_co[4]   = get_rate(r, 3)

    # Section D: CO Sub
    r = find_row("partner", 50, 120)
    cfg.rate_co_sub[0] = get_rate(r, 2)

    r = find_row("enrol only", 50, 120)
    cfg.rate_co_sub[1] = get_rate(r, 2)  # Under
    cfg.rate_co_sub[2] = get_rate(r, 3)  # Meet
    cfg.rate_co_sub[3] = get_rate(r, 4)  # Over

    r = find_row("enrol.*visa", 50, 120)
    if r is None:
        r = find_row("visa.*enrol", 50, 120)
    cfg.rate_co_sub[4] = get_rate(r, 2)  # Under
    cfg.rate_co_sub[5] = get_rate(r, 3)  # Meet
    cfg.rate_co_sub[6] = get_rate(r, 4)  # Over


def _load_service_fees(wb, cfg: BonusConfig):
    """09_SERVICE_FEE_RATES: A=Code, B=Keywords, C=CounsellorBonus, D=COBonus,
       E=Active, F=Category, G=Description"""
    if WS_SERVICE_FEE not in wb.sheetnames:
        return
    ws = wb[WS_SERVICE_FEE]
    for row in ws.iter_rows(min_row=2):
        code = _cell_str(row[0])
        if not code or code.startswith("("):
            continue
        rule = ServiceFeeRule(
            service_code=code,
            keywords=_cell_str(row[1]) if len(row) > 1 else "",
            counsellor_bonus=_cell_int(row[2]) if len(row) > 2 else 0,
            co_bonus=_cell_int(row[3]) if len(row) > 3 else 0,
            active=_cell_bool(row[4]) if len(row) > 4 else True,
            category=_cell_str(row[5]) if len(row) > 5 else "",
            description=_cell_str(row[6]) if len(row) > 6 else "",
        )
        cfg.service_fees[code] = rule


def _load_priority_instns(wb, cfg: BonusConfig):
    """03_PRIORITY_INSTNS: A=Name, B=BonusPct, C=AnnualTarget"""
    if WS_CONFIG_PRIORITY not in wb.sheetnames:
        return
    ws = wb[WS_CONFIG_PRIORITY]
    for row in ws.iter_rows(min_row=2):
        name = _cell_str(row[0])
        if not name or name.startswith("("):
            continue
        cfg.priority_instns.append(PriorityInstitution(
            name=name,
            bonus_pct=_cell_float(row[1]),
            annual_target=_cell_int(row[2]) if len(row) > 2 else 0,
        ))
