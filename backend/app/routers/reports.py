"""
backend/app/routers/reports.py
Router supporting the full UI workflow:
  GET   /reports/                                  — list all reports (dashboard queue)
  GET   /reports/{id}                              — single report metadata
  POST  /reports/upload                            — upload CRM file → engine → cases stored
  GET   /reports/{id}/cases                        — all cases for review table
  GET   /reports/{id}/trail                        — full field-change audit log
  PATCH /reports/{id}/cases/{cid}/fields/{field}   — edit one field (with mandatory comment)
  POST  /reports/{id}/submit                       — Bonus Admin submits for manager approval
  POST  /reports/{id}/approve                      — Manager/Admin approves → calculation triggered
  POST  /reports/{id}/return                       — Manager returns for revision
  GET   /reports/{id}/bonus-report                 — final Báo cáo data
  GET   /reports/{id}/pdf                          — download PDF
  POST  /reports/{id}/email                        — email to staff or payroll (stub)
"""

import io
import os
import secrets
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .auth import get_current_user
from ..models import User
from ..database import get_db

ENGINE_AVAILABLE = False
try:
    from ..engine.config import load_config
    from ..engine.input import parse_crm_report
    from ..engine.classify import classify_cases
    from ..engine.calc import calculate_bonuses
    ENGINE_AVAILABLE = True
except ImportError:
    pass

DB_PATH = os.environ.get("DB_PATH", "bonusengine.db")

def get_sqlite():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_schema():
    with get_sqlite() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS reports (
            id           TEXT PRIMARY KEY,
            staff_name   TEXT NOT NULL,
            month        INTEGER NOT NULL,
            year         INTEGER NOT NULL,
            office       TEXT NOT NULL,
            status       TEXT DEFAULT 'pending',
            uploaded_by  TEXT,
            uploaded_at  TEXT DEFAULT (datetime('now')),
            approved_by  TEXT,
            approved_at  TEXT,
            updated_at   TEXT DEFAULT (datetime('now')),
            notes        TEXT,
            target       INTEGER,
            enrolled     INTEGER,
            tier         TEXT,
            engine_total INTEGER DEFAULT 0,
            manual_total INTEGER DEFAULT 0,
            gap          INTEGER DEFAULT 0,
            base_rate    INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS report_cases (
            id                  TEXT PRIMARY KEY,
            report_id           TEXT NOT NULL REFERENCES reports(id),
            contract_id         TEXT,
            student_name        TEXT,
            student_id          TEXT,
            app_status          TEXT,
            client_type         TEXT,
            country             TEXT,
            institution         TEXT,
            refer_agent         TEXT,
            course_start        TEXT,
            visa_date           TEXT,
            notes               TEXT,
            institution_type    TEXT,
            service_fee_type    TEXT,
            package_type        TEXT,
            is_vietnam          INTEGER DEFAULT 0,
            is_agent_referred   INTEGER DEFAULT 0,
            office              TEXT,
            row_type            TEXT DEFAULT 'BASE',
            scheme              TEXT,
            counts_as_enrolled  INTEGER DEFAULT 0,
            prior_month_rate    TEXT,
            deferral            TEXT DEFAULT 'NONE',
            handover            TEXT DEFAULT 'NO',
            target_owner        TEXT,
            bonus_enrolled      INTEGER DEFAULT 0,
            bonus_priority      INTEGER DEFAULT 0,
            note_enrolled       TEXT,
            note_enrolled_2     TEXT,
            note_priority       TEXT,
            gap                 INTEGER DEFAULT 0,
            section             TEXT,
            UNIQUE(report_id, contract_id)
        );

        CREATE TABLE IF NOT EXISTS field_changes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id   TEXT NOT NULL,
            case_id     TEXT NOT NULL,
            field_name  TEXT NOT NULL,
            field_label TEXT,
            old_value   TEXT,
            new_value   TEXT,
            comment     TEXT,
            changed_by  TEXT NOT NULL,
            changed_at  TEXT DEFAULT (datetime('now'))
        );
        """)

_ensure_schema()

router = APIRouter()

EDITABLE_FIELDS = {
    "institution_type", "service_fee_type", "package_type",
    "office", "row_type", "scheme", "note_enrolled",
    "prior_month_rate", "deferral", "handover", "target_owner",
}
ENGINE_FIELDS = {
    "institution_type", "service_fee_type", "package_type",
    "office", "row_type", "scheme", "note_enrolled",
}


@router.get("/")
def list_reports(current_user: User = Depends(get_current_user)):
    with get_sqlite() as conn:
        rows = conn.execute("""
            SELECT r.*, COUNT(c.id) AS case_count
            FROM reports r
            LEFT JOIN report_cases c ON c.report_id = r.id
            GROUP BY r.id
            ORDER BY r.uploaded_at DESC
        """).fetchall()
    return [dict(r) for r in rows]


@router.get("/{report_id}")
def get_report(report_id: str, current_user: User = Depends(get_current_user)):
    with get_sqlite() as conn:
        row = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
    if not row:
        raise HTTPException(404, "Report not found")
    return dict(row)


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
    import tempfile
    tmp_path = os.path.join(tempfile.gettempdir(), f"{report_id}_{file.filename}")

    with open(tmp_path, "wb") as f:
        f.write(content)

    parsed_cases = []
    target, tier, enrolled, engine_total = 13, None, 0, 0

    if ENGINE_AVAILABLE:
        try:
            # Load config from PostgreSQL — no xlsm file needed
            cfg = load_config(db)
            raw_cases, _  = parse_crm_report(tmp_path, cfg)
            classified    = classify_cases(raw_cases, cfg, staff_name, year, month, {})
            calculated, tier, tgt, enr = calculate_bonuses(
                classified, staff_name, year, month, cfg)
            target, enrolled = tgt, enr

            for c in calculated:
                parsed_cases.append({
                    "id":                f"{report_id}_{c.contract_id}",
                    "contract_id":       c.contract_id,
                    "student_name":      getattr(c, "student_name", ""),
                    "student_id":        getattr(c, "student_id", ""),
                    "app_status":        c.app_status,
                    "client_type":       c.client_type,
                    "country":           c.country,
                    "institution":       c.institution,
                    "refer_agent":       getattr(c, "refer_agent", ""),
                    "institution_type":  c.institution_type,
                    "service_fee_type":  c.service_fee_type,
                    "package_type":      c.package_type,
                    "is_vietnam":        int(c.is_vietnam),
                    "is_agent_referred": int(c.is_agent_referred),
                    "office":            getattr(c, "office", office),
                    "row_type":          getattr(c, "row_type", "BASE"),
                    "scheme":            getattr(c, "scheme", ""),
                    "counts_as_enrolled": int(getattr(c, "counts_as_enrolled", False)),
                    "bonus_enrolled":    c.bonus_enrolled,
                    "note_enrolled":     c.note_enrolled,
                    "section":           "enrolled" if getattr(c, "counts_as_enrolled", False) else "closed",
                })
            print(f"[UPLOAD DEBUG] Cases from engine: {len(parsed_cases)}")
            engine_total = sum(c.get("bonus_enrolled", 0) for c in parsed_cases)

        except Exception as e:
            import traceback
            print(f"[ENGINE ERROR] {e}")
            traceback.print_exc()

    try:
        os.unlink(tmp_path)
    except Exception:
        pass

    uploader = current_user.full_name or current_user.username

    with get_sqlite() as conn:
        conn.execute("""
            INSERT INTO reports
              (id, staff_name, month, year, office, status, uploaded_by,
               notes, target, enrolled, tier, engine_total)
            VALUES (?, ?, ?, ?, ?, 'in_review', ?, ?, ?, ?, ?, ?)
        """, (report_id, staff_name, month, year, office,
              uploader, notes, target, enrolled, tier, engine_total))

        for c in parsed_cases:
            conn.execute("""
                INSERT OR REPLACE INTO report_cases
                  (id, report_id, contract_id, student_name, student_id,
                   app_status, client_type, country, institution, refer_agent,
                   institution_type, service_fee_type, package_type,
                   is_vietnam, is_agent_referred, office, row_type, scheme,
                   counts_as_enrolled, bonus_enrolled, note_enrolled, section)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c["id"], report_id, c["contract_id"], c["student_name"], c.get("student_id", ""),
                c["app_status"], c.get("client_type", ""), c.get("country", ""),
                c.get("institution", ""), c.get("refer_agent", ""),
                c.get("institution_type", ""), c.get("service_fee_type", ""),
                c.get("package_type", ""), c.get("is_vietnam", 0),
                c.get("is_agent_referred", 0), c.get("office", office),
                c.get("row_type", "BASE"), c.get("scheme", ""),
                c.get("counts_as_enrolled", 0), c.get("bonus_enrolled", 0),
                c.get("note_enrolled", ""), c.get("section", "closed"),
            ))
        conn.commit()

        saved = conn.execute(
            "SELECT COUNT(*) FROM report_cases WHERE report_id=?", (report_id,)
        ).fetchone()[0]
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


@router.get("/{report_id}/cases")
def get_cases(report_id: str, current_user: User = Depends(get_current_user)):
    with get_sqlite() as conn:
        rows = conn.execute(
            "SELECT * FROM report_cases WHERE report_id = ? ORDER BY rowid",
            (report_id,)
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/{report_id}/trail")
def get_trail(report_id: str, current_user: User = Depends(get_current_user)):
    with get_sqlite() as conn:
        rows = conn.execute(
            "SELECT * FROM field_changes WHERE report_id = ? ORDER BY changed_at DESC",
            (report_id,)
        ).fetchall()
    return [dict(r) for r in rows]


@router.patch("/{report_id}/cases/{case_id}/fields/{field}")
def update_field(
    report_id: str,
    case_id:   str,
    field:     str,
    body:      dict,
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

    with get_sqlite() as conn:
        row = conn.execute(
            f"SELECT {field} FROM report_cases WHERE id = ? AND report_id = ?",
            (case_id, report_id)
        ).fetchone()
        if not row:
            raise HTTPException(404, "Case not found")

        old_value = dict(row)[field]

        conn.execute(
            f"UPDATE report_cases SET {field} = ? WHERE id = ? AND report_id = ?",
            (new_value, case_id, report_id)
        )
        conn.execute("""
            INSERT INTO field_changes
              (report_id, case_id, field_name, field_label,
               old_value, new_value, comment, changed_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report_id, case_id, field,
            field.replace("_", " ").title(),
            str(old_value) if old_value is not None else "",
            str(new_value),
            comment,
            current_user.full_name or current_user.username,
        ))
        conn.execute(
            "UPDATE reports SET updated_at = datetime('now') WHERE id = ?",
            (report_id,)
        )
        conn.commit()

    return {"ok": True, "field": field, "new_value": new_value}


@router.post("/{report_id}/submit")
def submit_report(report_id: str, current_user: User = Depends(get_current_user)):
    with get_sqlite() as conn:
        conn.execute(
            "UPDATE reports SET status = 'submitted', updated_at = datetime('now') WHERE id = ?",
            (report_id,)
        )
        conn.commit()
    return {"ok": True, "status": "submitted"}


@router.post("/{report_id}/approve")
def approve_report(report_id: str, current_user: User = Depends(get_current_user)):
    if not current_user.is_admin:
        raise HTTPException(403, "Only administrators can approve reports")

    approver = current_user.full_name or current_user.username

    with get_sqlite() as conn:
        conn.execute("""
            UPDATE reports
            SET status      = 'approved',
                approved_by = ?,
                approved_at = datetime('now'),
                updated_at  = datetime('now')
            WHERE id = ?
        """, (approver, report_id))
        conn.commit()

    return {"ok": True, "status": "approved"}


@router.post("/{report_id}/return")
def return_report(
    report_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    comment = (body.get("comment") or "").strip()

    with get_sqlite() as conn:
        conn.execute(
            "UPDATE reports SET status = 'returned', updated_at = datetime('now') WHERE id = ?",
            (report_id,)
        )
        if comment:
            conn.execute("""
                INSERT INTO field_changes
                  (report_id, case_id, field_name, field_label,
                   old_value, new_value, comment, changed_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                report_id, "REPORT", "status", "Report Status",
                "submitted", "returned", comment,
                current_user.full_name or current_user.username,
            ))
        conn.commit()

    return {"ok": True, "status": "returned"}


@router.get("/{report_id}/bonus-report")
def get_bonus_report(report_id: str, current_user: User = Depends(get_current_user)):
    with get_sqlite() as conn:
        r = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        cases = conn.execute(
            "SELECT * FROM report_cases WHERE report_id = ? ORDER BY rowid",
            (report_id,)
        ).fetchall()
    if not r:
        raise HTTPException(404, "Report not found")
    return {**dict(r), "cases": [dict(c) for c in cases]}


@router.get("/{report_id}/pdf")
def download_pdf(report_id: str, current_user: User = Depends(get_current_user)):
    with get_sqlite() as conn:
        r = conn.execute(
            "SELECT * FROM reports WHERE id = ?", (report_id,)
        ).fetchone()
        cases = conn.execute(
            "SELECT * FROM report_cases WHERE report_id = ? ORDER BY rowid",
            (report_id,)
        ).fetchall()
    if not r:
        raise HTTPException(404, "Report not found")

    r, cases = dict(r), [dict(c) for c in cases]

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
        h2_s   = ParagraphStyle("H2",   fontSize=11, fontName="Helvetica-Bold",
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


@router.post("/{report_id}/email")
def send_email(
    report_id: str,
    body: dict,
    current_user: User = Depends(get_current_user),
):
    recipient = body.get("recipient", "staff")
    print(f"[EMAIL STUB] report={report_id} recipient={recipient}")
    return {"ok": True, "recipient": recipient, "status": "stub"}
