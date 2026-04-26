# =============================================================================
# config.py  |  StudyLink Bonus Engine
# Loads ALL configuration from PostgreSQL — zero hardcoded rates or rules.
#
# v6.3 compatibility patches applied (Apr 2026):
#   PATCH 1: get_service_fee accepts optional category filter (2-arg signature)
#   PATCH 2: base_rates inject flat keys "out_sys_co" / "out_sys_coun" per scheme
#            (sourced from ref_base_rates rows where tier='OUT_SYS')
#   PATCH 3: base_rates inject flat key "rmit_vn" for CO_SUB scheme
#            (sourced from ref_special_rates rate_code='RMIT_VN_SUB')
# =============================================================================

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple
import unicodedata

from .constants import (
    SCHEME_HCM_DIRECT, SCHEME_HN_DIRECT, SCHEME_CO_SUB,
    OFFICE_HCM, OFFICE_HN, OFFICE_DN,
    SKIP_LABELS,
    TIER_UNDER, TIER_MEET_HIGH, TIER_MEET_LOW, TIER_MEET, TIER_OVER,
)


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
    start_date: Optional[date] = None
    end_date: Optional[date] = None


@dataclass
class ServiceFeeRuleObj:
    code: str
    co_bonus: int = 0
    coun_bonus: int = 0
    category: str = "SERVICE_FEE"   # SERVICE_FEE | PACKAGE | CONTRACT
    applies_to: str = "ALL"          # ALL | DIRECT | OUT_OF_SYSTEM | MASTER_AGENT
    applies_as: str = "REPLACE"      # REPLACE = primary fee replaces base rate
                                      # ADD     = additive (Guardian/Dependant) — added after base+package
    share_with_other_co: bool = False # True → halve at payout (50/50 split with another CO)
    keywords: str = ""
    active: bool = True
    description: str = ""


@dataclass
class CountryRuleObj:
    crm_text: str
    code: str
    is_flat_country: bool = False
    is_vietnam: bool = False
    flat_co_amount: int = 0
    flat_coun_amount: int = 0
    counts_toward_target: bool = True
    scheme_overrides: Dict[str, Tuple[int, int]] = field(default_factory=dict)


@dataclass
class PriorityInstitutionObj:
    name: str
    bonus_pct: float = 0.0
    annual_target: int = 0
    achieved_ytd: int = 0


@dataclass
class SpecialRateObj:
    rate_code: str
    scheme: str
    country_code: Optional[str]
    institution_pattern: Optional[str]
    client_type_code: Optional[str]
    role: str
    amount: int
    conditions: str = ""


@dataclass
class AdvanceRuleObj:
    rule_name: str
    advance_pct: float = 0.5
    trigger_status: str = "Current - Enrolled"
    service_type: str = "ALL"
    country_code: str = "ALL"
    institution_pattern: Optional[str] = None
    client_type_code: str = "ALL"
    sort_order: int = 100


@dataclass
class PartnerInstitutionRateObj:
    partner_level: str  # SINGLE | DOUBLE
    flag_pattern: str   # * or **
    co_amount: int = 0
    coun_amount: int = 0


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
        self.base_rates:        Dict[str, Dict[str, Dict[str, int]]] = {}
        # scheme → tier → role → amount
        self.special_rates:     List[SpecialRateObj]             = []
        self.advance_rules:     List[AdvanceRuleObj]             = []
        self.partner_rates:     List[PartnerInstitutionRateObj]  = []
        self.incentive_threshold: int                            = 5_000_000

        # Flat country index: country_code → scheme → (co_amount, coun_amount)
        self._flat_countries:   Dict[str, Dict[str, Tuple[int,int]]] = {}

    # ── Lookups ──────────────────────────────────────────────────────────────

    def get_status_rule(self, status: str) -> StatusRuleObj:
        return self.status_rules.get(status.strip().lower(),
               StatusRuleObj(status=status, is_zero_bonus=True))

    def get_service_fee(self, code: str, category: str = "") -> Optional[ServiceFeeRuleObj]:
        """
        PATCH 1 (v6.3 compat): optional category filter.
        Existing 1-arg callers continue to work — category defaults to "" (no filter).
        v6.3 calc.py uses the 2-arg form to disambiguate SERVICE_FEE vs CONTRACT vs PACKAGE.
        """
        if not code or code.upper() in ("NONE", ""): return None
        r = self.service_fees.get(code.strip().lower())
        if not r or not r.active: return None
        if category and r.category.upper() != category.upper(): return None
        return r

    def resolve_service_code(self, text: str, category: str = "") -> Optional[str]:
        """
        Resolve a free-text service or package name to a canonical service_code.

        Two-step resolution:
          1. Direct code match: 'USA_STANDARD_16TR' → 'USA_STANDARD_16TR'
          2. Keyword fallback: scans ref_service_fee_rates.keywords (pipe-separated)
             for a substring match against `text`. Longest keyword wins, so a
             specific token like '9tr5' beats a generic token like 'standard'
             when both rows have keywords matching the input.

        The category filter scopes resolution to PACKAGE / SERVICE_FEE / CONTRACT.

        Returns canonical service_code (e.g. 'USA_STANDARD_16TR') or None.
        """
        if not text:
            return None
        text_lower = text.strip().lower()
        if text_lower in ("none", ""):
            return None

        # Step 1: direct code match
        direct = self.service_fees.get(text_lower)
        if direct and direct.active:
            if not category or direct.category.upper() == category.upper():
                return direct.code

        # Step 2: keyword fallback — collect (keyword, code) pairs, longest first
        candidates: List[Tuple[str, str]] = []
        for rule in self.service_fees.values():
            if not rule.active or not rule.keywords:
                continue
            if category and rule.category.upper() != category.upper():
                continue
            for kw in rule.keywords.split("|"):
                kw = kw.strip().lower()
                if kw:
                    candidates.append((kw, rule.code))
        candidates.sort(key=lambda x: len(x[0]), reverse=True)

        for kw, code in candidates:
            if kw in text_lower:
                return code

        return None

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

    def get_staff_scheme(self, name: str) -> str:
        resolved = self.resolve_staff_name(name)
        for key in [resolved.lower(), name.strip().lower()]:
            st = self.staff_targets.get(key)
            if st: return st.scheme
        # Look up in staff names directly
        st = self.staff_targets.get(self._ascii(name))
        return st.scheme if st else SCHEME_HCM_DIRECT

    def get_base_rate(self, scheme: str, tier: str, role: str = "CO") -> int:
        """Returns base rate amount for scheme/tier/role. Returns 0 if not found."""
        return self.base_rates.get(scheme, {}).get(tier, {}).get(role, 0)

    def get_country(self, crm_text: str) -> CountryRuleObj:
        return self.country_codes.get(crm_text.strip().lower(),
               CountryRuleObj(crm_text=crm_text, code=crm_text))

    def get_client_type_code(self, crm_text: str) -> str:
        return self.client_types.get(crm_text.strip().lower(), "")

    def is_skip_label(self, label: str) -> bool:
        return label.strip().lower() in self.skip_labels

    def get_flat_country_rate(self, country_code_or_name: str, scheme: str) -> Optional[Tuple[int,int]]:
        """Returns (co_amount, coun_amount) if this is a flat-rate country, else None."""
        key = country_code_or_name.strip().upper()
        scheme_rates = self._flat_countries.get(key)
        if not scheme_rates: return None
        return scheme_rates.get(scheme) or scheme_rates.get("ALL")

    def is_flat_country(self, country_code_or_name: str) -> bool:
        return country_code_or_name.strip().upper() in self._flat_countries

    def get_partner_rate(self, institution_name: str) -> Optional[PartnerInstitutionRateObj]:
        """Returns partner rate if institution contains ** or * flag. Checks ** first."""
        for pr in sorted(self.partner_rates, key=lambda x: len(x.flag_pattern), reverse=True):
            if pr.flag_pattern in institution_name:
                return pr
        return None

    def get_advance_rule(self, status: str, service_type: str = "",
                          country_code: str = "", institution: str = "",
                          client_type_code: str = "") -> Optional[AdvanceRuleObj]:
        """Returns the highest-priority advance rule that matches the given case."""
        matches = []
        for rule in self.advance_rules:
            if rule.trigger_status.lower() not in status.lower(): continue
            if rule.service_type != "ALL" and service_type and rule.service_type != service_type: continue
            if rule.country_code != "ALL" and country_code and rule.country_code != country_code: continue
            if rule.institution_pattern and rule.institution_pattern.lower() not in institution.lower(): continue
            if rule.client_type_code != "ALL" and client_type_code and rule.client_type_code != client_type_code: continue
            matches.append(rule)
        if not matches: return None
        return min(matches, key=lambda r: r.sort_order)

    def get_special_rate(self, scheme: str, country_code: str, country_name: str,
                          institution: str, client_type_code: str, role: str) -> Optional[SpecialRateObj]:
        """
        Returns the first matching special rate for this case combination.
        Match priority: RMIT/BUV VN → Other VN → Summer → Guardian → Dependant → Visa renewal → Other.
        """
        vn_codes = {"VN", "VIET NAM", "VIETNAM"}
        is_vn = country_code.upper() in vn_codes or country_name.lower() in ("vietnam", "viet nam")

        for sr in self.special_rates:
            if sr.scheme not in (scheme, "ALL"): continue
            if sr.role not in (role, "ALL"): continue
            if not self._active_on_today(sr): continue

            # Country check
            if sr.country_code:
                if sr.country_code in ("VN", "THAI_PHIL_ML"):
                    if sr.country_code == "VN" and not is_vn: continue
                    if sr.country_code == "THAI_PHIL_ML" and not self.is_flat_country(country_code): continue
                elif sr.country_code.upper() != country_code.upper(): continue

            # Institution pattern check
            if sr.institution_pattern:
                patterns = sr.institution_pattern.lower().split("|")
                if not any(p in institution.lower() for p in patterns): continue

            # Client type check
            if sr.client_type_code and sr.client_type_code != client_type_code: continue

            if sr.amount > 0:
                return sr

        return None

    def _active_on_today(self, obj) -> bool:
        """Check if an object with start_date/end_date is currently active."""
        today = date.today()
        if hasattr(obj, 'start_date') and obj.start_date and obj.start_date > today:
            return False
        if hasattr(obj, 'end_date') and obj.end_date and obj.end_date < today:
            return False
        return True

    def get_kpi_weight(self, ct_code: str, inst_type: str, scheme: str) -> float:
        from .constants import (CT_SUMMER, CT_GUARDIAN, CT_TOURIST,
                                 CT_MIGRATION, CT_DEPENDANT, CT_VISA_ONLY, CT_VIETNAM,
                                 INST_MASTER_AGENT, INST_OUT_OF_SYS)
        if ct_code in (CT_SUMMER, CT_GUARDIAN, CT_TOURIST, CT_MIGRATION, CT_DEPENDANT, CT_VISA_ONLY):
            return 0.0
        if ct_code == CT_VIETNAM:
            return 0.5
        if inst_type == INST_MASTER_AGENT:
            return 1.0
        if inst_type == INST_OUT_OF_SYS:
            return 0.7
        return 1.0


# =============================================================================
# PRIMARY LOADER — reads from PostgreSQL, zero hardcoding
# =============================================================================

def load_config(db, run_date: Optional[date] = None) -> BonusConfig:
    """
    Load BonusConfig from PostgreSQL reference tables.
    run_date defaults to today; used to filter start/end date ranges.
    """
    from ..models import (
        StaffName as StaffNameModel,
        StaffTarget as StaffTargetModel,
        CountryCode, ClientTypeMap,
        StatusRule as StatusRuleModel,
        ServiceFeeRate, MasterAgent,
        ReferenceList, PriorityInstitution,
        YtdTracker, BaseRate, IncentiveTier,
        SpecialRate, CountryRate, PartnerInstitution,
        AdvanceRule,
    )

    today = run_date or date.today()
    cfg = BonusConfig()

    def _date_active(row) -> bool:
        if hasattr(row, 'start_date') and row.start_date and row.start_date > today:
            return False
        if hasattr(row, 'end_date') and row.end_date and row.end_date < today:
            return False
        return True

    # ── Status Rules ─────────────────────────────────────────────────────────
    for r in db.query(StatusRuleModel).all():
        if not _date_active(r): continue
        cfg.status_rules[r.status_value.lower()] = StatusRuleObj(
            status=r.status_value,
            counts_as_enrolled=r.counts_as_enrolled or r.requires_enrol,
            coun_pct=r.coun_pct if hasattr(r,'coun_pct') and r.coun_pct is not None else 1.0,
            co_direct_pct=r.co_direct_pct if hasattr(r,'co_direct_pct') and r.co_direct_pct is not None else 1.0,
            co_sub_pct=r.co_sub_pct if hasattr(r,'co_sub_pct') and r.co_sub_pct is not None else 1.0,
            is_carry_over=r.is_carry_over if hasattr(r,'is_carry_over') else False,
            is_current_enrolled=r.is_current_enrolled if hasattr(r,'is_current_enrolled') else False,
            is_zero_bonus=(not r.is_eligible) if hasattr(r,'is_eligible') else (r.is_zero_bonus if hasattr(r,'is_zero_bonus') else False),
            fees_paid_non_enrolled=r.fees_paid_non_enrolled if hasattr(r,'fees_paid_non_enrolled') else False,
            is_visa_granted=r.requires_visa if hasattr(r,'requires_visa') else False,
            dedup_rank=r.dedup_rank if hasattr(r,'dedup_rank') else 0,
        )

    # ── Countries ─────────────────────────────────────────────────────────────
    for r in db.query(CountryCode).filter(CountryCode.is_active==True).all():
        cfg.country_codes[r.country_name.lower()] = CountryRuleObj(
            crm_text=r.country_name,
            code=r.country_code or r.country_name,
            is_vietnam=r.country_code in ("VN",) if r.country_code else False,
        )

    # ── Client Types ──────────────────────────────────────────────────────────
    for r in db.query(ClientTypeMap).filter(ClientTypeMap.is_active==True).all():
        cfg.client_types[r.raw_value.lower()] = r.canonical

    # ── Staff Name Map ────────────────────────────────────────────────────────
    for r in db.query(StaffNameModel).filter(StaffNameModel.is_active==True).all():
        cfg.staff_name_map[r.full_name.lower()] = r.full_name
        if r.short_name:
            cfg.staff_name_map[r.short_name.lower()] = r.full_name

    for r in db.query(ReferenceList).filter(
        ReferenceList.list_name=="staff_name_map", ReferenceList.is_active==True
    ).all():
        cfg.staff_name_map[r.value.lower()] = r.value

    # ── Staff Targets ─────────────────────────────────────────────────────────
    for r in db.query(StaffTargetModel).all():
        key = r.staff_name.lower()
        if key not in cfg.staff_targets:
            # Look up scheme from StaffName table
            sn = db.query(StaffNameModel).filter(
                StaffNameModel.full_name == r.staff_name
            ).first()
            scheme = sn.scheme if sn and sn.scheme else SCHEME_HCM_DIRECT
            office = r.office or (sn.office if sn else OFFICE_HCM)
            cfg.staff_targets[key] = StaffTargetObj(
                name=r.staff_name, office=office, role="CO", scheme=scheme,
                start_date=sn.start_date if sn else None,
                end_date=sn.end_date if sn else None,
            )
        st = cfg.staff_targets[key]
        if r.year not in st.targets:
            st.targets[r.year] = {}
        st.targets[r.year][r.month] = r.target

    # ── Service Fees ──────────────────────────────────────────────────────────
    for r in db.query(ServiceFeeRate).filter(ServiceFeeRate.is_active==True).all():
        cfg.service_fees[r.service_code.lower()] = ServiceFeeRuleObj(
            code=r.service_code,
            co_bonus=r.co_bonus,
            coun_bonus=r.coun_bonus,
            category=r.category or "SERVICE_FEE",
            applies_to=r.applies_to or "ALL",
            applies_as=(r.applies_as or "REPLACE") if hasattr(r, 'applies_as') else "REPLACE",
            share_with_other_co=bool(r.share_with_other_co) if hasattr(r, 'share_with_other_co') else False,
            keywords=r.keywords or "",
            active=True,
            description=r.description or "",
        )

    # ── Master Agents ─────────────────────────────────────────────────────────
    for r in db.query(MasterAgent).filter(MasterAgent.is_active==True).all():
        cfg.master_agents.append(r.agent_name)

    # ── Skip Labels ───────────────────────────────────────────────────────────
    skip = db.query(ReferenceList).filter(
        ReferenceList.list_name=="skip_labels", ReferenceList.is_active==True
    ).all()
    if skip:
        cfg.skip_labels = frozenset(r.value.lower() for r in skip)

    # ── Priority Institutions (with aliases) ─────────────────────────────────
    # Each canonical row produces one PriorityInstitutionObj. Each alias of
    # that row produces an additional virtual PriorityInstitutionObj sharing
    # the same bonus_pct, annual_target, and achieved_ytd. calc.py's substring
    # match in _apply_priority then finds a hit regardless of which name the
    # CRM data uses. YTD is still tracked against the canonical name only.
    ytd_lookup: Dict[str, int] = {}
    for y in db.query(YtdTracker).filter(YtdTracker.year==today.year).all():
        ytd_lookup[y.institution_name.lower()] = ytd_lookup.get(y.institution_name.lower(), 0) + y.enrolment_count

    # Pre-load aliases keyed by parent priority_instn_id
    from ..models import InstitutionAlias
    aliases_by_parent: Dict[int, List[str]] = {}
    for a in db.query(InstitutionAlias).filter(InstitutionAlias.is_active==True).all():
        aliases_by_parent.setdefault(a.priority_instn_id, []).append(a.alias_name)

    for r in db.query(PriorityInstitution).filter(PriorityInstitution.is_active==True).all():
        ytd = ytd_lookup.get(r.institution_name.lower(), 0)
        # Canonical entry
        cfg.priority_instns.append(PriorityInstitutionObj(
            name=r.institution_name,
            bonus_pct=r.bonus_pct,
            annual_target=r.annual_target,
            achieved_ytd=ytd,
        ))
        # One virtual entry per alias — same bonus parameters, alias as the name
        for alias_name in aliases_by_parent.get(r.id, []):
            cfg.priority_instns.append(PriorityInstitutionObj(
                name=alias_name,
                bonus_pct=r.bonus_pct,
                annual_target=r.annual_target,
                achieved_ytd=ytd,
            ))

    # ── Base Rates — from ref_base_rates ─────────────────────────────────────
    for r in db.query(BaseRate).filter(BaseRate.is_active==True).all():
        if not _date_active(r): continue
        if r.scheme not in cfg.base_rates:
            cfg.base_rates[r.scheme] = {}
        if r.tier not in cfg.base_rates[r.scheme]:
            cfg.base_rates[r.scheme][r.tier] = {}
        # Keep the most recently started record if duplicates exist
        existing = cfg.base_rates[r.scheme][r.tier].get(r.role, -1)
        if existing == -1 or r.amount > 0:
            cfg.base_rates[r.scheme][r.tier][r.role] = r.amount

    # ── Incentive Threshold ───────────────────────────────────────────────────
    tier_rule = db.query(IncentiveTier).filter(
        IncentiveTier.type=="MEET_THRESHOLD",
        IncentiveTier.is_active==True
    ).order_by(IncentiveTier.start_date.desc()).first()
    if tier_rule and _date_active(tier_rule):
        cfg.incentive_threshold = tier_rule.threshold_amount

    # ── Special Rates ─────────────────────────────────────────────────────────
    for r in db.query(SpecialRate).filter(SpecialRate.is_active==True).all():
        if not _date_active(r): continue
        cfg.special_rates.append(SpecialRateObj(
            rate_code=r.rate_code, scheme=r.scheme,
            country_code=r.country_code, institution_pattern=r.institution_pattern,
            client_type_code=r.client_type_code, role=r.role,
            amount=r.amount, conditions=r.conditions or "",
        ))

    # ── Flat Country Rates ────────────────────────────────────────────────────
    for r in db.query(CountryRate).filter(CountryRate.is_active==True, CountryRate.rate_type=="FLAT").all():
        if not _date_active(r): continue
        key = (r.country_code or r.country_name).upper()
        if key not in cfg._flat_countries:
            cfg._flat_countries[key] = {}
        cfg._flat_countries[key][r.scheme] = (r.co_amount, r.coun_amount)
        # Also index by country name
        name_key = r.country_name.upper()
        if name_key not in cfg._flat_countries:
            cfg._flat_countries[name_key] = {}
        cfg._flat_countries[name_key][r.scheme] = (r.co_amount, r.coun_amount)

    # ── Partner Institution Rates ─────────────────────────────────────────────
    for r in db.query(PartnerInstitution).filter(PartnerInstitution.is_active==True).all():
        if not _date_active(r): continue
        cfg.partner_rates.append(PartnerInstitutionRateObj(
            partner_level=r.partner_level,
            flag_pattern=r.flag_pattern,
            co_amount=r.co_amount,
            coun_amount=r.coun_amount,
        ))
    # Sort: check ** before * (longer pattern first)
    cfg.partner_rates.sort(key=lambda x: len(x.flag_pattern), reverse=True)

    # ── Advance Rules ─────────────────────────────────────────────────────────
    for r in db.query(AdvanceRule).filter(AdvanceRule.is_active==True).all():
        if not _date_active(r): continue
        cfg.advance_rules.append(AdvanceRuleObj(
            rule_name=r.rule_name,
            advance_pct=r.advance_pct,
            trigger_status=r.trigger_status,
            service_type=r.service_type or "ALL",
            country_code=r.country_code or "ALL",
            institution_pattern=r.institution_pattern,
            client_type_code=r.client_type_code or "ALL",
            sort_order=r.sort_order or 100,
        ))
    cfg.advance_rules.sort(key=lambda x: x.sort_order)

    # =========================================================================
    # v6.3 COMPATIBILITY POST-PROCESSING
    # Inject flat keys into base_rates so v6.3 calc.py's _get_rates() finds them
    # alongside the tier dicts. The DB stores these values in different shapes;
    # calc.py expects them as flat entries inside each scheme's base_rates dict.
    # =========================================================================

    # PATCH 2: out_sys_co / out_sys_coun from ref_base_rates tier='OUT_SYS'
    # CO_SUB has no OUT_SYS rows by design — CO_SUB cases never go out-of-system.
    for scheme, tier_dict in cfg.base_rates.items():
        out_sys = tier_dict.get("OUT_SYS")
        if out_sys:
            tier_dict["out_sys_co"]   = out_sys.get("CO", 0)
            tier_dict["out_sys_coun"] = out_sys.get("COUN", 0)

    # PATCH 3: rmit_vn for CO_SUB scheme from ref_special_rates rate_code='RMIT_VN_SUB'
    # Used by calc.py Step 7 when scheme==CO_SUB and country is Vietnam.
    if SCHEME_CO_SUB in cfg.base_rates:
        for sr in cfg.special_rates:
            if sr.rate_code == "RMIT_VN_SUB" and sr.scheme == SCHEME_CO_SUB:
                cfg.base_rates[SCHEME_CO_SUB]["rmit_vn"] = sr.amount
                break

    return cfg
