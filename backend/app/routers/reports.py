"""
backend/app/routers/reports.py

Review workflow router. Backed by PostgreSQL via SQLAlchemy ORM.
Tables auto-created at startup by main.py's Base.metadata.create_all().

Endpoints:
  GET   /reports/                                  — list all reports
  GET   /reports/{id}                              — single report metadata
  POST  /reports/upload                            — upload CRM file → engine → cases stored
  GET   /reports/{id}/cases                        — all cases for review table
  GET   /reports/{id}/trail                        — full field-change audit log
  PATCH /reports/{id}/cases/{cid}/fields/{field}   — edit one field (with mandatory comment)
  POST  /reports/{id}/submit                       — Bonus Admin submits for manager approval
  POST  /reports/{id}/approve                      — Manager/Admin approves
  POST  /reports/{id}/return                       — Manager returns for revision
  POST  /reports/{id}/recalculate                  — Re-run engine over saved cases
  GET   /reports/{id}/bonus-report                 — final Báo cáo data
  GET   /reports/{id}/pdf                          — download PDF
  POST  /reports/{id}/email                        — email to staff or payroll (stub)
"""

import io
import os
import secrets
import tempfile
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .auth import get_current_user
from ..models import (
    User,
    BonusReport,
    BonusReportCase,
    BonusFieldChange,
)
from ..database import get_db

ENGINE_AVAILABLE = False
try:
    from ..engine.config   import load_config
    from ..engine.input    import parse_crm_report
    from ..engine.classify import classify_cases
    from ..engine.calc     import calculate_bonuses
    ENGINE_AVAILABLE = True
except ImportError:
    pass


router = APIRouter()


# ── Edit policy ──────────────────────────────────────────────────────────────
EDITABLE_FIELDS = {
    "institution_type", "service_fee_type", "package_type",
    "office", "row_type", "scheme", "note_enrolled",
    "prior_month_rate", "deferral", "handover", "target_owner",
    "targets_name", "case_transition", "presales_agent", "incentive",
    "group_agent_name",
    # Apr 2026 — direct bonus override (cleaner than MGMT_EXCEPTION abuse
    # of prior_month_rate). Editing either flips manual_override=True so
    # recalc preserves the operator value.
    "bonus_enrolled", "bonus_priority",
}
ENGINE_FIELDS = {
    "institution_type", "service_fee_type", "package_type",
    "office", "row_type", "scheme", "note_enrolled",
    "bonus_enrolled", "bonus_priority",
}
# Fields whose edit triggers manual_override=True on the case.
MANUAL_OVERRIDE_FIELDS = {"bonus_enrolled", "bonus_priority"}
# Fields stored as int on the DB — coerce string input from the form.
INT_FIELDS = {"bonus_enrolled", "bonus_priority", "incentive"}


# ── Serialisation helpers (ORM row → JSON-ready dict) ────────────────────────
def _report_to_dict(r: BonusReport, case_count: int = None) -> Dict[str, Any]:
    """Serialise BonusReport for API response. Includes case_count when supplied."""
    d = {
        "id":           r.id,
        "staff_name":   r.staff_name,
        "month":        r.month,
        "year":         r.year,
        "office":       r.office,
        "status":       r.status,
        "uploaded_by":  r.uploaded_by,
        "uploaded_at":  r.uploaded_at.isoformat() if r.uploaded_at else None,
        "approved_by":  r.approved_by,
        "approved_at":  r.approved_at.isoformat() if r.approved_at else None,
        "updated_at":   r.updated_at.isoformat()  if r.updated_at  else None,
        "notes":        r.notes,
        "target":       r.target,
        "enrolled":     r.enrolled,
        "tier":         r.tier,
        "engine_total": r.engine_total,
        "manual_total": r.manual_total,
        "gap":          r.gap,
        "base_rate":    r.base_rate,
    }
    if case_count is not None:
        d["case_count"] = case_count
    return d


def _case_to_dict(c: BonusReportCase) -> Dict[str, Any]:
    return {
        "id":                 c.id,
        "report_id":          c.report_id,
        "contract_id":        c.contract_id,
        "student_name":       c.student_name,
        "student_id":         c.student_id,
        "app_status":         c.app_status,
        "client_type":        c.client_type,
        "country":            c.country,
        "institution":        c.institution,
        "refer_agent":        c.refer_agent,
        "course_start":       c.course_start,
        "visa_date":          c.visa_date,
        "notes":              c.notes,
        "institution_type":   c.institution_type,
        "service_fee_type":   c.service_fee_type,
        "package_type":       c.package_type,
        "is_vietnam":         int(bool(c.is_vietnam)),
        "is_agent_referred":  int(bool(c.is_agent_referred)),
        "office":             c.office,
        "row_type":           c.row_type,
        "scheme":             c.scheme,
        "counts_as_enrolled": int(bool(c.counts_as_enrolled)),
        "prior_month_rate":   c.prior_month_rate,
        "deferral":           c.deferral,
        "handover":           c.handover,
        "target_owner":       c.target_owner,
        "targets_name":       c.targets_name,
        "presales_agent":     c.presales_agent,
        "incentive":          c.incentive,
        "group_agent_name":   c.group_agent_name,
        "case_transition":    c.case_transition,
        "bonus_enrolled":     c.bonus_enrolled,
        "bonus_priority":     c.bonus_priority,
        "note_enrolled":      c.note_enrolled,
        "note_enrolled_2":    c.note_enrolled_2,
        "note_priority":      c.note_priority,
        "note_priority_2":    c.note_priority_2,
        "gap":                c.gap,
        "section":            c.section,
    }


def _trail_to_dict(t: BonusFieldChange) -> Dict[str, Any]:
    return {
        "id":          t.id,
        "report_id":   t.report_id,
        "case_id":     t.case_id,
        "field_name":  t.field_name,
        "field_label": t.field_label,
        "old_value":   t.old_value,
        "new_value":   t.new_value,
        "comment":     t.comment,
        "changed_by":  t.changed_by,
        "changed_at":  t.changed_at.isoformat() if t.changed_at else None,
    }


# ── List / get reports ───────────────────────────────────────────────────────
@router.get("/")
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all reports with case counts, newest first."""
    rows = (
        db.query(
            BonusReport,
            func.count(BonusReportCase.id).label("case_count"),
        )
        .outerjoin(BonusReportCase, BonusReportCase.report_id == BonusReport.id)
        .group_by(BonusReport.id)
        .order_by(desc(BonusReport.uploaded_at))
        .all()
    )
    return [_report_to_dict(r, case_count=cc) for (r, cc) in rows]


@router.get("/{report_id}")
def get_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    r = db.query(BonusReport).filter(BonusReport.id == report_id).first()
    if not r:
        raise HTTPException(404, "Report not found")
    return _report_to_dict(r)


# ── Upload + run engine ──────────────────────────────────────────────────────
@router.post("/upload")
async def upload_report(
    file:       UploadFile = File(...),
    staff_name: str        = Form(...),
    month:      int        = Form(...),
    year:       int        = Form(...),
    office:     str        = Form(...),
    notes:      str        = Form(""),
    current_user: User     = Depends(get_current_user),
    db:         Session    = Depends(get_db),
):
    content   = await file.read()
    report_id = secrets.token_hex(8)
    tmp_path  = os.path.join(tempfile.gettempdir(),
                             f"{report_id}_{file.filename}")
    with open(tmp_path, "wb") as f:
        f.write(content)

    parsed_cases: List[Dict[str, Any]] = []
    target, tier, enrolled, engine_total = 0, None, 0, 0

    if ENGINE_AVAILABLE:
        try:
            cfg          = load_config(db)
            raw_cases, _ = parse_crm_report(tmp_path, cfg)
            classified   = classify_cases(raw_cases, cfg, staff_name, year, month, {})
            calculated, tier, tgt, enr = calculate_bonuses(
                classified, staff_name, year, month, cfg, office=office)
            target, enrolled = tgt, enr
            print(f"[UPLOAD DEBUG] staff={staff_name} office={office} "
                  f"year={year} month={month} → target={tgt} enrolled={enr} tier={tier}")

            # Apr 2026: 6-scheme rebuild removed the per-office scheme
            # transformation. Office is now a separate dimension on
            # ref_base_rates, so the staff's home scheme is used as-is for
            # every case. Operator overrides set c.scheme directly via the
            # Review Board UI; that override is captured below in case_scheme.
            base_scheme = cfg.get_staff_scheme(staff_name)

            for c in calculated:
                # counts_as_enrolled lives on the StatusRule, not on CaseRecord.
                status_rule    = cfg.get_status_rule(c.app_status)
                counts_enrolled = bool(status_rule.counts_as_enrolled)

                # Per-case scheme: use the operator override if set, otherwise
                # fall back to the staff's home scheme.
                case_scheme = c.scheme or base_scheme

                parsed_cases.append({
                    "id":                 f"{report_id}_{c.contract_id}",
                    "contract_id":        c.contract_id,
                    "student_name":       c.student_name,
                    "student_id":         c.student_id,
                    "app_status":         c.app_status,
                    "client_type":        c.client_type,
                    "country":            c.country,
                    "institution":        c.institution,
                    "refer_agent":        c.agent,            # CaseRecord field is `agent`
                    "course_start":       c.course_start.isoformat() if c.course_start else "",
                    "visa_date":          c.visa_date.isoformat()    if c.visa_date    else "",
                    "notes":              c.notes,
                    "institution_type":   c.institution_type,
                    "service_fee_type":   c.service_fee_type,
                    "package_type":       c.package_type,
                    "is_vietnam":         bool(c.is_vietnam),
                    "is_agent_referred":  bool(c.is_agent_referred),
                    "office":             c.office or office,
                    "row_type":           c.row_type,
                    "scheme":             case_scheme,
                    "counts_as_enrolled": counts_enrolled,
                    "prior_month_rate":   str(c.prior_month_rate) if c.prior_month_rate else "",
                    "deferral":           c.deferral,
                    "handover":           c.handover,
                    "target_owner":       c.target_owner,
                    "targets_name":       c.targets_name,
                    "presales_agent":     c.presales_agent,
                    "incentive":          c.incentive,
                    "group_agent_name":   c.group_agent_name,
                    "case_transition":    c.case_transition,
                    "bonus_enrolled":     c.bonus_enrolled,
                    "bonus_priority":     c.bonus_priority,
                    "note_enrolled":      c.note_enrolled,
                    "note_enrolled_2":    c.note_enrolled2,
                    "note_priority":      c.note_priority,
                    "note_priority_2":    c.note_priority2,
                    "section":            "enrolled" if counts_enrolled else "closed",
                })
            print(f"[UPLOAD DEBUG] Cases from engine: {len(parsed_cases)}")
            engine_total = sum(c.get("bonus_enrolled", 0) + c.get("bonus_priority", 0)
                               for c in parsed_cases)

        except Exception as e:
            import traceback
            print(f"[ENGINE ERROR] {e}")
            traceback.print_exc()

    try:
        os.unlink(tmp_path)
    except Exception:
        pass

    uploader = current_user.full_name or current_user.username

    # ── Persist via ORM ──────────────────────────────────────────────────────
    report = BonusReport(
        id           = report_id,
        staff_name   = staff_name,
        month        = month,
        year         = year,
        office       = office,
        status       = "in_review",
        uploaded_by  = uploader,
        notes        = notes,
        target       = target,
        enrolled     = enrolled,
        tier         = tier,
        engine_total = engine_total,
    )
    db.add(report)

    for cdata in parsed_cases:
        case = BonusReportCase(
            id                 = cdata["id"],
            report_id          = report_id,
            contract_id        = cdata["contract_id"],
            student_name       = cdata["student_name"],
            student_id         = cdata["student_id"],
            app_status         = cdata["app_status"],
            client_type        = cdata["client_type"],
            country            = cdata["country"],
            institution        = cdata["institution"],
            refer_agent        = cdata["refer_agent"],
            course_start       = cdata["course_start"],
            visa_date          = cdata["visa_date"],
            notes              = cdata["notes"],
            institution_type   = cdata["institution_type"],
            service_fee_type   = cdata["service_fee_type"],
            package_type       = cdata["package_type"],
            is_vietnam         = cdata["is_vietnam"],
            is_agent_referred  = cdata["is_agent_referred"],
            office             = cdata["office"],
            row_type           = cdata["row_type"],
            scheme             = cdata["scheme"],
            counts_as_enrolled = cdata["counts_as_enrolled"],
            prior_month_rate   = cdata["prior_month_rate"],
            deferral           = cdata["deferral"],
            handover           = cdata["handover"],
            target_owner       = cdata["target_owner"],
            targets_name       = cdata["targets_name"],
            presales_agent     = cdata["presales_agent"],
            incentive          = cdata["incentive"],
            group_agent_name   = cdata["group_agent_name"],
            case_transition    = cdata["case_transition"],
            bonus_enrolled     = cdata["bonus_enrolled"],
            bonus_priority     = cdata["bonus_priority"],
            note_enrolled      = cdata["note_enrolled"],
            note_enrolled_2    = cdata["note_enrolled_2"],
            note_priority      = cdata["note_priority"],
            note_priority_2    = cdata["note_priority_2"],
            section            = cdata["section"],
        )
        db.add(case)

    db.commit()

    saved = (
        db.query(func.count(BonusReportCase.id))
        .filter(BonusReportCase.report_id == report_id)
        .scalar()
    )
    print(f"[UPLOAD DEBUG] Cases saved to DB: {saved}")

    return {
        "id":               report_id,
        "case_count":       len(parsed_cases),
        "tier":             tier,
        "target":           target,
        "enrolled":         enrolled,
        "engine_total":     engine_total,
        "engine_available": ENGINE_AVAILABLE,
    }


# ── Cases for review table ───────────────────────────────────────────────────
@router.get("/{report_id}/cases")
def get_cases(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(BonusReportCase)
        .filter(BonusReportCase.report_id == report_id)
        .order_by(BonusReportCase.id)
        .all()
    )
    return [_case_to_dict(c) for c in rows]


# ── Audit trail ──────────────────────────────────────────────────────────────
@router.get("/{report_id}/trail")
def get_trail(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (
        db.query(BonusFieldChange)
        .filter(BonusFieldChange.report_id == report_id)
        .order_by(desc(BonusFieldChange.changed_at))
        .all()
    )
    return [_trail_to_dict(t) for t in rows]


# ── Edit a single case field ─────────────────────────────────────────────────
@router.patch("/{report_id}/cases/{case_id}/fields/{field}")
def update_field(
    report_id: str,
    case_id:   str,
    field:     str,
    body:      dict,
    db:        Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if field not in EDITABLE_FIELDS:
        raise HTTPException(400, f"Field '{field}' is not editable")

    comment   = (body.get("comment") or "").strip()
    new_value = body.get("value", "")

    if field in ENGINE_FIELDS and not comment:
        raise HTTPException(
            422, "A comment is required when overriding an engine-suggested value"
        )

    # Coerce numeric fields. Frontend sends strings — DB columns are integers.
    if field in INT_FIELDS:
        try:
            new_value = int(str(new_value).replace(",", "").replace(".", "").strip() or 0)
        except ValueError:
            raise HTTPException(422, f"'{field}' requires a numeric value")

    case = (
        db.query(BonusReportCase)
        .filter(
            BonusReportCase.id        == case_id,
            BonusReportCase.report_id == report_id,
        )
        .first()
    )
    if not case:
        raise HTTPException(404, "Case not found")

    old_value = getattr(case, field)

    # Apr 2026 — bonus override audit hardening.
    # When the operator overrides bonus_enrolled or bonus_priority, the
    # engine's last-computed baseline is auto-prepended to the comment so
    # the audit log immutably captures what the engine WOULD have paid,
    # regardless of any subsequent edits. The operator's reason follows.
    if field in MANUAL_OVERRIDE_FIELDS:
        baseline_field = (
            "engine_baseline_enrolled" if field == "bonus_enrolled"
            else "engine_baseline_priority"
        )
        baseline_val = getattr(case, baseline_field, 0) or 0
        # Lock the baseline + override values into the comment so the audit
        # row is self-contained even if the case is later edited again.
        audit_prefix = (
            f"[Engine baseline {field}: {baseline_val:,} → "
            f"override: {new_value:,}] "
        )
        comment = audit_prefix + comment

    setattr(case, field, new_value)

    # Apr 2026 — flag the case as manually overridden so recalc preserves
    # the operator's value instead of recomputing it.
    if field in MANUAL_OVERRIDE_FIELDS:
        case.manual_override = True

    db.add(BonusFieldChange(
        report_id   = report_id,
        case_id     = case_id,
        field_name  = field,
        field_label = field.replace("_", " ").title(),
        old_value   = str(old_value) if old_value is not None else "",
        new_value   = str(new_value),
        comment     = comment,
        changed_by  = current_user.full_name or current_user.username,
    ))

    # touch the parent report's updated_at
    rep = db.query(BonusReport).filter(BonusReport.id == report_id).first()
    if rep:
        rep.updated_at = datetime.utcnow()

    db.commit()
    return {"ok": True, "field": field, "new_value": new_value}


# ── State transitions ────────────────────────────────────────────────────────
@router.post("/{report_id}/submit")
def submit_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rep = db.query(BonusReport).filter(BonusReport.id == report_id).first()
    if not rep:
        raise HTTPException(404, "Report not found")
    rep.status     = "submitted"
    rep.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "status": "submitted"}


@router.post("/{report_id}/approve")
def approve_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_admin:
        raise HTTPException(403, "Only administrators can approve reports")

    rep = db.query(BonusReport).filter(BonusReport.id == report_id).first()
    if not rep:
        raise HTTPException(404, "Report not found")

    rep.status      = "approved"
    rep.approved_by = current_user.full_name or current_user.username
    rep.approved_at = datetime.utcnow()
    rep.updated_at  = datetime.utcnow()
    db.commit()
    return {"ok": True, "status": "approved"}


@router.post("/{report_id}/return")
def return_report(
    report_id: str,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rep = db.query(BonusReport).filter(BonusReport.id == report_id).first()
    if not rep:
        raise HTTPException(404, "Report not found")

    comment = (body.get("comment") or "").strip()

    rep.status     = "returned"
    rep.updated_at = datetime.utcnow()

    if comment:
        db.add(BonusFieldChange(
            report_id   = report_id,
            case_id     = "REPORT",
            field_name  = "status",
            field_label = "Report Status",
            old_value   = "submitted",
            new_value   = "returned",
            comment     = comment,
            changed_by  = current_user.full_name or current_user.username,
        ))

    db.commit()
    return {"ok": True, "status": "returned"}


# ── Recalculate ──────────────────────────────────────────────────────────────
# Re-runs the bonus engine over all persisted cases in a report. Used after
# Bonus Admin edits classification fields during review. Delegates to the
# recalc service module so the engine logic stays in one place.
@router.post("/{report_id}/recalculate")
def recalculate(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rep = db.query(BonusReport).filter(BonusReport.id == report_id).first()
    if not rep:
        raise HTTPException(404, "Report not found")

    # Don't allow recalculation of finalised reports — their bonus values
    # are locked once approved or distributed.
    if rep.status in ("approved", "distributed"):
        raise HTTPException(
            400,
            f"Cannot recalculate a {rep.status} report. "
            f"Use 'return' to reopen it for editing first."
        )

    if not ENGINE_AVAILABLE:
        raise HTTPException(500, "Engine module not loaded on server")

    # Imported lazily so the router still loads even if the service module
    # has an import-time error — surfaces a clearer message at call time.
    from ..services.recalc import recalculate_report
    return recalculate_report(db, rep, current_user)


# ── Final báo cáo ────────────────────────────────────────────────────────────
@router.get("/{report_id}/bonus-report")
def get_bonus_report(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rep = db.query(BonusReport).filter(BonusReport.id == report_id).first()
    if not rep:
        raise HTTPException(404, "Report not found")
    cases = (
        db.query(BonusReportCase)
        .filter(BonusReportCase.report_id == report_id)
        .order_by(BonusReportCase.id)
        .all()
    )
    return {**_report_to_dict(rep), "cases": [_case_to_dict(c) for c in cases]}


# ── PDF download ─────────────────────────────────────────────────────────────
@router.get("/{report_id}/pdf")
def download_pdf(
    report_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rep = db.query(BonusReport).filter(BonusReport.id == report_id).first()
    if not rep:
        raise HTTPException(404, "Report not found")
    cases = (
        db.query(BonusReportCase)
        .filter(BonusReportCase.report_id == report_id)
        .order_by(BonusReportCase.id)
        .all()
    )

    r     = _report_to_dict(rep)
    cases = [_case_to_dict(c) for c in cases]

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import cm
        from reportlab.platypus import (HRFlowable, Paragraph, SimpleDocTemplate,
                                         Spacer, Table, TableStyle)

        MONTHS = ["", "January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        NAVY   = colors.HexColor("#0f2137")
        GOLD   = colors.HexColor("#f59e0b")
        LIGHT  = colors.HexColor("#f8f9fc")
        BORDER = colors.HexColor("#e2e8f0")

        buf    = io.BytesIO()
        doc    = SimpleDocTemplate(buf, pagesize=A4,
                     leftMargin=1.8*cm, rightMargin=1.8*cm,
                     topMargin=1.5*cm,  bottomMargin=1.5*cm)
        styles = getSampleStyleSheet()
        note_s = ParagraphStyle("Note", fontSize=8, fontName="Helvetica",
                                textColor=colors.HexColor("#475569"))
        h2_s   = ParagraphStyle("H2", fontSize=11, fontName="Helvetica-Bold",
                                textColor=NAVY, spaceBefore=12, spaceAfter=6)

        enrolled = [c for c in cases if c.get("section") == "enrolled"]
        closed   = [c for c in cases if c.get("section") != "enrolled"]
        tot_enr  = sum(c.get("bonus_enrolled", 0) for c in cases)
        tot_pri  = sum(c.get("bonus_priority",  0) for c in cases)
        grand    = tot_enr + tot_pri

        def make_section_table(case_list, show_priority=True):
            hdr = ["#", "Student Name", "Contract ID", "Status", "Enrolled Bonus"]
            if show_priority:
                hdr.append("Priority")
            hdr.append("Note")
            rows = [hdr]
            for i, c in enumerate(case_list, 1):
                row = [
                    str(i),
                    Paragraph(c.get("student_name", ""), styles["Normal"]),
                    c.get("contract_id", ""),
                    Paragraph((c.get("app_status", "") or "")[:45], note_s),
                    f"{c.get('bonus_enrolled', 0):,}" if c.get("bonus_enrolled") else "—",
                ]
                if show_priority:
                    row.append(f"{c.get('bonus_priority', 0):,}" if c.get("bonus_priority") else "—")
                row.append(Paragraph((c.get("note_enrolled", "") or "")[:80], note_s))
                rows.append(row)
            cw = [0.8*cm, 5*cm, 2.5*cm, 4*cm, 2.5*cm]
            if show_priority:
                cw.append(2*cm)
            cw.append(3.5*cm)
            t = Table(rows, colWidths=cw, repeatRows=1)
            t.setStyle(TableStyle([
                ("BACKGROUND",    (0, 0), (-1, 0),  NAVY),
                ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
                ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, -1), 8),
                ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
                ("ALIGN",         (4, 0), (-2, -1), "RIGHT"),
                ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, LIGHT]),
                ("GRID",          (0, 0), (-1, -1), 0.3, BORDER),
                ("TOPPADDING",    (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            return t

        story = []

        hdr_data = [[
            Paragraph(
                "<font color='#f59e0b'><b>STUDYLINK CAREER</b></font><br/>"
                "<font size='16'><b>Performance Bonus Report</b></font><br/>"
                "<font size='8' color='#94a3b8'>Báo cáo thưởng hiệu suất</font>",
                ParagraphStyle("TL", fontName="Helvetica", textColor=colors.white, fontSize=10),
            ),
            Paragraph(
                f"<font size='8' color='#94a3b8'>Period / Kỳ báo cáo</font><br/>"
                f"<b><font size='14'>{MONTHS[r['month']]} {r['year']}</font></b>",
                ParagraphStyle("TR", fontName="Helvetica", textColor=colors.white,
                               fontSize=10, alignment=TA_RIGHT),
            ),
        ]]
        hdr = Table(hdr_data, colWidths=[12*cm, 5*cm])
        hdr.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), NAVY),
            ("TOPPADDING",    (0, 0), (-1, -1), 14),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ("LEFTPADDING",   (0, 0), (0,  -1), 16),
            ("RIGHTPADDING",  (-1,0), (-1, -1), 16),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(hdr)

        info = Table([[
            f"Staff: {r['staff_name']}",
            f"Office: {r['office']}",
            f"Target: {r.get('target', '—')}",
            f"Enrolled: {r.get('enrolled', '—')}",
            f"Tier: {r.get('tier', '—')}",
        ]], colWidths=[4.2*cm] * 4 + [4.4*cm])
        info.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), LIGHT),
            ("FONTSIZE",      (0, 0), (-1, -1), 8),
            ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
            ("TEXTCOLOR",     (0, 0), (-1, -1), NAVY),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("LEFTPADDING",   (0, 0), (0,  -1), 10),
            ("BOX",           (0, 0), (-1, -1), 0.5, BORDER),
        ]))
        story.append(info)
        story.append(Spacer(1, 14))

        if enrolled:
            story.append(Paragraph("Closed Files — Enrolled / Hồ sơ đã nhập học", h2_s))
            story.append(HRFlowable(width="100%", thickness=1.5, color=NAVY))
            story.append(Spacer(1, 6))
            story.append(make_section_table(enrolled, show_priority=True))
            story.append(Spacer(1, 12))

        if closed:
            story.append(Paragraph("Closed Files — Other / Hồ sơ đóng khác", h2_s))
            story.append(HRFlowable(width="100%", thickness=1, color=BORDER))
            story.append(Spacer(1, 6))
            story.append(make_section_table(closed, show_priority=False))
            story.append(Spacer(1, 16))

        tots = Table([
            ["Bonus Enrolled / Bonus nhập học", f"{tot_enr:,} ₫"],
            ["Priority Bonus / Bonus ưu tiên",  f"{tot_pri:,} ₫"],
            ["TOTAL PAYABLE / TỔNG THỰC NHẬN",  f"{grand:,} ₫"],
        ], colWidths=[10*cm, 6*cm], hAlign="RIGHT")
        tots.setStyle(TableStyle([
            ("FONTNAME",      (0, 0),  (-1, -1), "Helvetica"),
            ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0),  (-1, -1), 9),
            ("FONTSIZE",      (0, -1), (-1, -1), 11),
            ("ALIGN",         (1, 0),  (1,  -1), "RIGHT"),
            ("BACKGROUND",    (0, -1), (-1, -1), NAVY),
            ("TEXTCOLOR",     (0, -1), (0,  -1), colors.white),
            ("TEXTCOLOR",     (1, -1), (1,  -1), GOLD),
            ("TOPPADDING",    (0, 0),  (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0),  (-1, -1), 6),
            ("LEFTPADDING",   (0, 0),  (0,  -1), 10),
            ("RIGHTPADDING",  (-1, 0), (-1, -1), 10),
            ("LINEABOVE",     (0, -1), (-1, -1), 1.5, NAVY),
            ("BOX",           (0, 0),  (-1, -1), 0.5, BORDER),
            ("INNERGRID",     (0, 0),  (-1, -2), 0.3, BORDER),
        ]))
        story.append(tots)
        story.append(Spacer(1, 20))

        footer = Table([[
            Paragraph(f"Generated {datetime.now().strftime('%d %B %Y')}", note_s),
            Paragraph(
                f"Approved by {r.get('approved_by', '—')} · Document #{r['id']}",
                ParagraphStyle("FR", fontName="Helvetica", fontSize=8,
                               textColor=colors.HexColor("#94a3b8"), alignment=TA_RIGHT),
            ),
        ]], colWidths=[9*cm, 8*cm])
        footer.setStyle(TableStyle([
            ("LINEABOVE",  (0, 0), (-1, 0), 0.5, BORDER),
            ("TOPPADDING", (0, 0), (-1,-1), 8),
        ]))
        story.append(footer)

        doc.build(story)
        buf.seek(0)

        fname = (
            f"BonusReport_{r['staff_name'].replace(' ', '_')}"
            f"_{MONTHS[r['month']]}_{r['year']}.pdf"
        )
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    except ImportError:
        raise HTTPException(
            500,
            "PDF generation requires reportlab — run: pip install reportlab",
        )


# ── Email stub ───────────────────────────────────────────────────────────────
@router.post("/{report_id}/email")
def send_email(
    report_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    recipient = body.get("recipient", "staff")
    print(f"[EMAIL STUB] report={report_id} recipient={recipient}")
    return {"ok": True, "recipient": recipient, "status": "stub"}
