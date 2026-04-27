# =============================================================================
# services/validator.py  |  Field validation classifier
# =============================================================================
# For each case field in a report, classify the current value as:
#   - "ok"      Value matches a canonical entry. No action required.
#   - "alias"   Value matches a known alias. Operator should pick canonical.
#   - "missing" Field is blank but mandatory.
#   - "unknown" Value is neither canonical nor a known alias. Blocking.
#
# This module is pure functions — no DB writes, no engine runs. It only reads
# reference data and classifies. Endpoints in routers/reports.py call this
# and serialise the result for the frontend.
# =============================================================================

from typing import Optional, Dict, List, Set
from sqlalchemy.orm import Session

from ..models import (
    BonusReportCase, ClientTypeMap, CountryCode,
    PriorityInstitution, InstitutionAlias,
    StatusRule, ServiceFeeRate, ReferenceList,
)


# ── Hardcoded enums (small, stable lists with no aliases) ────────────────────
_OFFICE_VALUES = ["HCM", "HN", "DN"]
_INSTITUTION_TYPE_VALUES = [
    "DIRECT", "MASTER_AGENT", "GROUP", "OUT_OF_SYSTEM", "RMIT_VN", "OTHER_VN"
]
_DEFERRAL_VALUES = ["NONE", "DEFERRED", "FEE_TRANSFERRED", "FEE_WAIVED", "NO_SERVICE"]
_HANDOVER_VALUES = ["YES", "NO"]
_CASE_TRANSITION_VALUES = ["YES", "NO"]
_ROW_TYPE_VALUES = ["BASE", "ADDON"]
_SYSTEM_TYPE_VALUES = ["Trong hệ thống", "Ngoài hệ thống"]


# ── Required fields (presence check only — no list lookup) ───────────────────
REQUIRED_TEXT_FIELDS = {"student_id", "student_name", "contract_id"}


# ── Field → reference type mapping ───────────────────────────────────────────
# Maps a BonusReportCase field name to a "reference type" string. The
# reference type drives which classifier function runs. Fields not in this
# map (e.g. notes, course_start, bonus_enrolled) are not validated here —
# they're free text, dates, or engine output.
FIELD_REF_TYPE: Dict[str, str] = {
    "client_type":      "client_type",
    "country":          "country",
    "institution":      "institution",
    "app_status":       "app_status",
    "service_fee_type": "service_fee_type",
    "package_type":     "package_type",
    "office":           "office",
    "system_type":      "system_type",
    "institution_type": "institution_type",
    "deferral":         "deferral",
    "handover":         "handover",
    "case_transition":  "case_transition",
    "row_type":         "row_type",
    "student_id":       "required_text",
    "student_name":     "required_text",
    "contract_id":      "required_text",
}


# ── Reference list builders (cached per request via the loader) ──────────────
class ReferenceLoader:
    """
    Loads reference data once and caches in memory for the duration of one
    validation pass. Avoids repeated DB hits when validating many cases.

    Usage:
        loader = ReferenceLoader(db)
        result = classify_field("client_type", "Du hoc (Ghi danh)", loader)
    """

    def __init__(self, db: Session):
        self.db = db
        self._client_type_map: Optional[Dict[str, dict]] = None
        self._countries: Optional[Set[str]] = None
        self._institutions: Optional[Dict[str, str]] = None
        self._statuses: Optional[Set[str]] = None
        self._service_fees: Optional[Set[str]] = None
        self._packages: Optional[Set[str]] = None

    @property
    def client_type_map(self) -> Dict[str, dict]:
        """raw_value → {canonical_code, display_name, is_canonical}.

        is_canonical = True when raw_value is the preferred form of its
        canonical code (the first row added for each code, by convention).
        """
        if self._client_type_map is None:
            rows = (self.db.query(ClientTypeMap)
                    .filter(ClientTypeMap.is_active == True)
                    .order_by(ClientTypeMap.id)
                    .all())
            seen_canonical = set()
            m = {}
            for r in rows:
                is_canonical = r.canonical not in seen_canonical
                if is_canonical:
                    seen_canonical.add(r.canonical)
                m[r.raw_value] = {
                    "canonical_code": r.canonical,
                    "display_name":   r.display_name,
                    "is_canonical":   is_canonical,
                }
            self._client_type_map = m
        return self._client_type_map

    @property
    def countries(self) -> Set[str]:
        if self._countries is None:
            rows = (self.db.query(CountryCode)
                    .filter(CountryCode.is_active == True).all())
            self._countries = {r.country_name for r in rows if r.country_name}
        return self._countries

    @property
    def institutions(self) -> Dict[str, str]:
        """Lower-case institution-or-alias name → canonical institution_name.

        Both the canonical names from PriorityInstitution and the aliases from
        InstitutionAlias are included. The lookup is lower-cased to handle
        casing differences in CRM exports.
        """
        if self._institutions is None:
            m = {}
            # Canonicals
            for r in (self.db.query(PriorityInstitution)
                      .filter(PriorityInstitution.is_active == True).all()):
                if r.institution_name:
                    m[r.institution_name.lower()] = r.institution_name
            # Aliases
            for a in (self.db.query(InstitutionAlias)
                      .filter(InstitutionAlias.is_active == True).all()):
                parent = a.institution
                if a.alias_name and parent and parent.is_active:
                    m[a.alias_name.lower()] = parent.institution_name
            self._institutions = m
        return self._institutions

    @property
    def statuses(self) -> Set[str]:
        if self._statuses is None:
            rows = self.db.query(StatusRule).all()
            self._statuses = {r.status_value for r in rows if r.status_value}
        return self._statuses

    @property
    def service_fees(self) -> Set[str]:
        if self._service_fees is None:
            rows = (self.db.query(ServiceFeeRate)
                    .filter(ServiceFeeRate.is_active == True).all())
            self._service_fees = {
                r.service_code for r in rows
                if r.service_code and (r.category or "") != "PACKAGE"
            }
            self._service_fees.add("NONE")  # NONE is always allowed (blank service)
        return self._service_fees

    @property
    def packages(self) -> Set[str]:
        if self._packages is None:
            rows = (self.db.query(ServiceFeeRate)
                    .filter(ServiceFeeRate.is_active == True,
                            ServiceFeeRate.category == "PACKAGE").all())
            self._packages = {r.service_code for r in rows if r.service_code}
            # Also pick up package values from ReferenceList if any are stored there
            for r in (self.db.query(ReferenceList)
                      .filter(ReferenceList.list_name == "package_type",
                              ReferenceList.is_active == True).all()):
                if r.value:
                    self._packages.add(r.value)
            self._packages.add("NONE")  # NONE means "no package signed"
        return self._packages


# ── Classifier ───────────────────────────────────────────────────────────────
def classify_field(field: str, value: Optional[str],
                   loader: ReferenceLoader) -> dict:
    """Classify a single field value. Returns:

    {
      "status":         "ok" | "alias" | "missing" | "unknown",
      "current":        the value passed in (or "" if None),
      "canonical":      the preferred value (only set when status="alias")
      "canonical_code": the code from a *_map table (only for client_type)
    }

    For fields not in FIELD_REF_TYPE the function returns status="ok"
    unconditionally (we don't validate free-text or engine output fields).
    """
    ref_type = FIELD_REF_TYPE.get(field)
    if ref_type is None:
        return {"status": "ok", "current": value or "",
                "canonical": None, "canonical_code": None}

    val = (value or "").strip()

    # Required text fields — presence only
    if ref_type == "required_text":
        if not val:
            return {"status": "missing", "current": "",
                    "canonical": None, "canonical_code": None}
        return {"status": "ok", "current": val,
                "canonical": None, "canonical_code": None}

    # Empty value where a list is expected → "missing"
    # Some list fields tolerate "NONE" as the blank sentinel.
    if not val:
        return {"status": "missing", "current": "",
                "canonical": None, "canonical_code": None}

    # Dispatch by reference type
    if ref_type == "client_type":
        return _classify_client_type(val, loader)
    if ref_type == "country":
        return _classify_against_set(val, loader.countries)
    if ref_type == "institution":
        return _classify_institution(val, loader)
    if ref_type == "app_status":
        return _classify_against_set(val, loader.statuses)
    if ref_type == "service_fee_type":
        return _classify_against_set(val, loader.service_fees)
    if ref_type == "package_type":
        return _classify_against_set(val, loader.packages)
    if ref_type == "office":
        return _classify_against_set(val, set(_OFFICE_VALUES))
    if ref_type == "system_type":
        return _classify_against_set(val, set(_SYSTEM_TYPE_VALUES))
    if ref_type == "institution_type":
        return _classify_against_set(val, set(_INSTITUTION_TYPE_VALUES))
    if ref_type == "deferral":
        return _classify_against_set(val, set(_DEFERRAL_VALUES))
    if ref_type == "handover":
        return _classify_against_set(val, set(_HANDOVER_VALUES))
    if ref_type == "case_transition":
        return _classify_against_set(val, set(_CASE_TRANSITION_VALUES))
    if ref_type == "row_type":
        return _classify_against_set(val, set(_ROW_TYPE_VALUES))

    # Fallback (should not happen)
    return {"status": "ok", "current": val,
            "canonical": None, "canonical_code": None}


def _classify_client_type(val: str, loader: ReferenceLoader) -> dict:
    """Look up val in the client type map.

    If val is in the map AND is the canonical row → "ok"
    If val is in the map but a non-canonical row → "alias" (with canonical)
    If val is not in the map → "unknown"
    """
    m = loader.client_type_map
    if val in m:
        entry = m[val]
        if entry["is_canonical"]:
            return {"status": "ok", "current": val,
                    "canonical": None,
                    "canonical_code": entry["canonical_code"]}
        # Find the canonical raw_value for this code
        canonical_value = next(
            (k for k, v in m.items()
             if v["canonical_code"] == entry["canonical_code"] and v["is_canonical"]),
            None,
        )
        return {"status": "alias", "current": val,
                "canonical": canonical_value,
                "canonical_code": entry["canonical_code"]}
    return {"status": "unknown", "current": val,
            "canonical": None, "canonical_code": None}


def _classify_institution(val: str, loader: ReferenceLoader) -> dict:
    """Institution lookup is alias-aware via ref_institution_aliases.

    Note: many institutions in CRM data are NOT in the priority list
    (e.g. non-partner schools the engine doesn't pay priority on).
    For those, status is "ok" — they're valid institutions, just not
    priority partners. We only flag values that look like attempts to
    type a partner name but got it wrong.

    Implementation: if the value matches a canonical exactly → "ok"
                    if the value matches an alias → "alias"
                    otherwise → "ok" (assume non-partner institution)
    """
    institutions = loader.institutions
    val_lower = val.lower().strip()
    if val_lower in institutions:
        canonical = institutions[val_lower]
        if val == canonical:
            return {"status": "ok", "current": val,
                    "canonical": None, "canonical_code": None}
        # Different from canonical (case mismatch or alias)
        return {"status": "alias", "current": val,
                "canonical": canonical, "canonical_code": None}
    # Not a partner institution — that's fine, just no priority bonus eligible
    return {"status": "ok", "current": val,
            "canonical": None, "canonical_code": None}


def _classify_against_set(val: str, allowed: Set[str]) -> dict:
    """For canonical-only reference types (no alias variants).

    Match is exact. If you expect a value to match but doesn't, it's
    likely a casing or whitespace issue — operator picks the right
    value from the dropdown.
    """
    if val in allowed:
        return {"status": "ok", "current": val,
                "canonical": None, "canonical_code": None}
    return {"status": "unknown", "current": val,
            "canonical": None, "canonical_code": None}


# ── Whole-report classifier ──────────────────────────────────────────────────
def classify_report(db: Session, cases: List[BonusReportCase]) -> dict:
    """Classify every validatable field on every case in a report.

    Returns:
      {
        "case_validations": [
          {"case_id": ..., "fields": {"client_type": {...}, ...}}, ...
        ],
        "summary": {"total_cases": N, "fields_ok": ..., "fields_alias": ...,
                    "fields_missing": ..., "fields_unknown": ...}
      }
    """
    loader = ReferenceLoader(db)
    case_validations = []
    counts = {"ok": 0, "alias": 0, "missing": 0, "unknown": 0}

    for c in cases:
        fields_result = {}
        for field in FIELD_REF_TYPE.keys():
            current_val = getattr(c, field, None)
            res = classify_field(field, current_val, loader)
            fields_result[field] = res
            counts[res["status"]] = counts.get(res["status"], 0) + 1
        case_validations.append({
            "case_id": c.id,
            "fields":  fields_result,
        })

    return {
        "case_validations": case_validations,
        "summary": {
            "total_cases":    len(cases),
            "fields_ok":      counts["ok"],
            "fields_alias":   counts["alias"],
            "fields_missing": counts["missing"],
            "fields_unknown": counts["unknown"],
        },
    }


# ── Reference list builder for the dropdown endpoint ─────────────────────────
def get_reference_list(db: Session, ref_type: str) -> dict:
    """Build the dropdown list for a given reference type.

    Returns:
      {
        "type": ref_type,
        "canonical": [{"value": ..., "code": ..., "display": ...}, ...],
        "aliases":   {alias_value: canonical_code, ...}
      }

    For ref types without aliases, aliases is an empty dict.
    """
    loader = ReferenceLoader(db)

    if ref_type == "client_type":
        m = loader.client_type_map
        canonical = [
            {"value": v, "code": e["canonical_code"], "display": e["display_name"]}
            for v, e in m.items() if e["is_canonical"]
        ]
        aliases = {v: e["canonical_code"] for v, e in m.items() if not e["is_canonical"]}
        return {"type": ref_type, "canonical": canonical, "aliases": aliases}

    if ref_type == "country":
        return _simple_list(ref_type, sorted(loader.countries))

    if ref_type == "institution":
        # Combine canonical and alias mappings into a single response
        canonicals = []
        for r in (db.query(PriorityInstitution)
                  .filter(PriorityInstitution.is_active == True)
                  .order_by(PriorityInstitution.institution_name).all()):
            canonicals.append({
                "value": r.institution_name, "code": None,
                "display": f"{r.institution_name} ({r.country_code})",
            })
        # De-dup by name
        seen = set()
        canonicals = [c for c in canonicals
                      if not (c["value"] in seen or seen.add(c["value"]))]
        aliases = {}
        for a in (db.query(InstitutionAlias)
                  .filter(InstitutionAlias.is_active == True).all()):
            if a.institution and a.institution.is_active:
                aliases[a.alias_name] = a.institution.institution_name
        return {"type": ref_type, "canonical": canonicals, "aliases": aliases}

    if ref_type == "app_status":
        return _simple_list(ref_type, sorted(loader.statuses))
    if ref_type == "service_fee_type":
        return _simple_list(ref_type, sorted(loader.service_fees))
    if ref_type == "package_type":
        return _simple_list(ref_type, sorted(loader.packages))
    if ref_type == "office":
        return _simple_list(ref_type, _OFFICE_VALUES)
    if ref_type == "system_type":
        return _simple_list(ref_type, _SYSTEM_TYPE_VALUES)
    if ref_type == "institution_type":
        return _simple_list(ref_type, _INSTITUTION_TYPE_VALUES)
    if ref_type == "deferral":
        return _simple_list(ref_type, _DEFERRAL_VALUES)
    if ref_type == "handover":
        return _simple_list(ref_type, _HANDOVER_VALUES)
    if ref_type == "case_transition":
        return _simple_list(ref_type, _CASE_TRANSITION_VALUES)
    if ref_type == "row_type":
        return _simple_list(ref_type, _ROW_TYPE_VALUES)

    raise ValueError(f"Unknown reference type: {ref_type}")


def _simple_list(ref_type: str, values: List[str]) -> dict:
    return {
        "type": ref_type,
        "canonical": [{"value": v, "code": None, "display": v} for v in values],
        "aliases": {},
    }
