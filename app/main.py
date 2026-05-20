"""Weekly Funnel Report Generator - FastAPI application."""

import logging
from typing import Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import HTMLResponse, Response

from app.analysis_engine import (
    build_funnel_report,
    parse_raw_candidates,
)
from app.docx_generator import generate_docx
from app.email_sender import send_report_email
from app.html_generator import generate_html
from app.models import FunnelReport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Weekly Funnel Report Generator",
    description="Upload your weekly tracker Excel and generate formatted funnel reports.",
    version="2.0.0",
)

_current_report: Optional[FunnelReport] = None


@app.get("/", response_class=HTMLResponse)
async def home():
    """Render the upload form."""
    return UPLOAD_PAGE


@app.post("/api/report/generate", response_class=HTMLResponse)
async def generate_report(
    tracker_file: UploadFile = File(..., description="Weekly tracker Excel/CSV"),
    support_items: str = Form("", description="Support items, one per line"),
    report_year: int = Form(2026),
):
    """Generate the funnel report from the uploaded tracker file."""
    global _current_report

    content = await tracker_file.read()
    skill_groups, monthly, source_mix = parse_raw_candidates(
        content=content, filename=tracker_file.filename,
    )

    support = [s.strip() for s in support_items.strip().split("\n") if s.strip()]

    report = build_funnel_report(
        skill_groups=skill_groups,
        monthly_delivery=monthly,
        support_items=support,
        source_hire_pct=source_mix.get("hire_pct"),
        source_linkedin_pct=source_mix.get("linkedin_pct"),
        total_sourced=source_mix.get("total_sourced", 0),
        report_year=report_year,
    )
    _current_report = report

    return generate_html(report)


@app.get("/api/report/download")
async def download_report():
    """Download the latest report as a Word document."""
    if _current_report is None:
        return HTMLResponse(
            "<h2>No report generated yet. Go back and upload data first.</h2>",
            status_code=400,
        )
    docx_bytes = generate_docx(_current_report)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=Weekly_Funnel_Report.docx"},
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "funnel-report-generator", "version": "2.0.0"}


@app.post("/api/report/send-email")
async def send_email(
    to_emails: str = Form(..., description="Comma-separated recipient emails"),
    cc_emails: str = Form("", description="Comma-separated CC emails"),
    subject: str = Form("Weekly Funnel Report", description="Email subject"),
    attach_docx: bool = Form(True, description="Attach Word document"),
):
    """Send the latest generated report via email."""
    if _current_report is None:
        return {"success": False, "message": "No report generated yet."}

    to_list = [e.strip() for e in to_emails.split(",") if e.strip()]
    cc_list = [e.strip() for e in cc_emails.split(",") if e.strip()] if cc_emails.strip() else []

    if not to_list:
        return {"success": False, "message": "At least one recipient email is required."}

    html_body = generate_html(_current_report)
    docx_bytes = generate_docx(_current_report) if attach_docx else None

    return send_report_email(
        to_emails=to_list,
        cc_emails=cc_list,
        subject=subject,
        html_body=html_body,
        docx_bytes=docx_bytes,
    )


# ── Upload page HTML ───────────────────────────────────────────────────

UPLOAD_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Weekly Funnel Report Generator</title>
<style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Segoe UI', Calibri, Arial, sans-serif; background: #f4f6f9; color: #232f3e; }
    .container { max-width: 720px; margin: 40px auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 32px; }
    h1 { color: #232f3e; text-align: center; margin-bottom: 8px; }
    .subtitle { text-align: center; color: #666; margin-bottom: 24px; font-size: 0.95em; }
    .section { margin: 20px 0; padding: 16px; background: #fafbfc; border-radius: 6px; border: 1px solid #e8ecf0; }
    .section h3 { color: #0073bb; margin-bottom: 8px; font-size: 1em; }
    .section p { font-size: 0.85em; color: #555; margin-bottom: 8px; }
    label { display: block; font-weight: 600; margin: 8px 0 4px; font-size: 0.9em; }
    .required::after { content: " *"; color: #d32f2f; }
    input[type="file"] { display: block; margin: 4px 0 12px; padding: 12px; border: 2px dashed #0073bb; border-radius: 6px; width: 100%; background: #f0f7fc; cursor: pointer; font-size: 0.95em; }
    input[type="file"]:hover { border-color: #005a8e; background: #e4f0fa; }
    input[type="number"] { padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; width: 100%; font-size: 0.9em; }
    textarea { width: 100%; padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; font-size: 0.9em; min-height: 80px; resize: vertical; }
    .btn { display: block; width: 100%; padding: 14px; background: #0073bb; color: #fff; border: none; border-radius: 6px; font-size: 1.1em; cursor: pointer; margin-top: 20px; }
    .btn:hover { background: #005a8e; }
    .help { font-size: 0.78em; color: #888; margin-top: 4px; }
    .format-list { font-size: 0.82em; color: #444; margin: 8px 0 0 16px; }
    .format-list li { margin: 2px 0; }
    .badge { display: inline-block; background: #e8f5e9; color: #2e7d32; padding: 2px 8px; border-radius: 3px; font-size: 0.75em; font-weight: 600; }
</style>
</head>
<body>
<div class="container">
    <h1>Weekly Funnel Report Generator</h1>
    <p class="subtitle">Upload your weekly tracker Excel and the tool will auto-generate the full funnel report</p>

    <form action="/api/report/generate" method="post" enctype="multipart/form-data">

        <div class="section">
            <h3>1. Upload Weekly Tracker <span class="badge">Required</span></h3>
            <p>Upload the Excel file with the Base Sheet containing candidate-level data.
               The tool will automatically detect columns and compute all metrics.</p>
            <label class="required" for="tracker_file">Tracker File (.xlsx / .csv)</label>
            <input type="file" name="tracker_file" id="tracker_file" accept=".csv,.xlsx,.xls" required>
            <p class="help">Expected columns in the data:</p>
            <ul class="format-list">
                <li><strong>Skill Group</strong> — e.g. "NA-AWS, FA-II, L5"</li>
                <li><strong>Final Status</strong> — e.g. "Offer Accept", "Rejected at BPS", "OS Incline"</li>
                <li><strong>Channel Mix</strong> (optional) — e.g. "LinkedIn", "Hire"</li>
                <li><strong>OS Incline Date</strong> (optional) — for monthly glidepath</li>
                <li><strong>Offer Accept Date</strong> (optional) — for monthly glidepath</li>
                <li><strong>Req ID</strong> (optional) — for demand count</li>
            </ul>
        </div>

        <div class="section">
            <h3>2. Support Required (Optional)</h3>
            <label for="support_items">Support Items (one per line)</label>
            <textarea name="support_items" id="support_items" placeholder="e.g. DAS: Req ID 3100130 pending HM review since March 9..."></textarea>
        </div>

        <div class="section">
            <h3>3. Report Settings</h3>
            <label for="report_year">Report Year</label>
            <input type="number" name="report_year" id="report_year" value="2026">
        </div>

        <button type="submit" class="btn">Generate Funnel Report</button>
    </form>
</div>
</body>
</html>"""
