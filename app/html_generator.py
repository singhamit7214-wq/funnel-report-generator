"""Generate an HTML preview of the weekly funnel report."""

from app.models import FunnelReport


def _pct(val) -> str:
    if val is None:
        return "N/A"
    return f"{val:.1f}%"


def generate_html(report: FunnelReport) -> str:
    """Generate a full HTML report for browser preview."""
    from app.analysis_engine import compute_funnel_metrics

    metrics = compute_funnel_metrics(report.skill_groups)
    t = metrics["totals"]

    # ── Business updates HTML ──
    biz_html = ""
    for idx, biz in enumerate(report.business_updates, 1):
        pipeline_parts = []
        if biz.pipeline_onsite:
            pipeline_parts.append(f"{biz.pipeline_onsite} at Onsite")
        if biz.pipeline_bps:
            pipeline_parts.append(f"{biz.pipeline_bps} BPS")
        if biz.pipeline_assessment:
            pipeline_parts.append(f"{biz.pipeline_assessment} at Assessment")
        if biz.pipeline_hm_review:
            pipeline_parts.append(f"{biz.pipeline_hm_review} at HM Review")
        total_p = (biz.pipeline_onsite + biz.pipeline_bps
                   + biz.pipeline_assessment + biz.pipeline_hm_review)

        conv_line = ""
        if biz.incline_conversion_pct is not None:
            conv_line = (
                f"<li>Onsite incline conversion: <strong>{biz.incline_conversion_pct:.0f}%</strong> "
                f"({biz.os_inclines}/{biz.os_completed}) vs goal {biz.conversion_goal_pct:.0f}%"
            )
            if pipeline_parts:
                conv_line += f", active pipeline of {total_p} candidates ({', '.join(pipeline_parts)})"
            conv_line += ".</li>"

        biz_html += f"""
        <div class="biz-card">
            <h3>{idx}. {biz.business_name}</h3>
            <ul>
                <li>GSS delivered <strong>{biz.os_inclines}</strong> OS inclines →
                    <strong>{biz.offer_accepts}</strong> offer accepts
                    {"/ " + str(biz.offer_stage) + " at Offer Stage" if biz.offer_stage else ""}
                    {"/ " + str(biz.offer_declines) + " decline(s)" if biz.offer_declines else ""}
                </li>
                {conv_line}
            </ul>
        </div>"""

    # ── Monthly glidepath HTML ──
    monthly_html = ""
    if report.monthly_delivery:
        month_headers = "".join(f"<th>{m.month}</th>" for m in report.monthly_delivery)
        row_sourcers = "".join(f"<td>{m.num_sourcers}</td>" for m in report.monthly_delivery)
        row_os = "".join(f"<td>{m.os_inclines_actual}</td>" for m in report.monthly_delivery)
        row_onsite = "".join(f"<td>{m.onsite_completed}</td>" for m in report.monthly_delivery)
        row_oa = "".join(f"<td>{m.offer_accepts_actual}</td>" for m in report.monthly_delivery)
        row_target = "".join(f"<td>{m.offer_accept_target}</td>" for m in report.monthly_delivery)
        row_gap = "".join(
            f'<td class="{"gap-positive" if (m.offer_accept_target - m.offer_accepts_actual) > 0 else "gap-negative"}">'
            f'{m.offer_accept_target - m.offer_accepts_actual}</td>'
            for m in report.monthly_delivery
        )
        monthly_html = f"""
        <h2>YTD Month-on-Month Delivery Glidepath</h2>
        <table>
            <thead><tr><th>Metric</th>{month_headers}</tr></thead>
            <tbody>
                <tr><td>No Of Sourcers</td>{row_sourcers}</tr>
                <tr><td>OS Inclines Actuals</td>{row_os}</tr>
                <tr><td>Onsite Completed</td>{row_onsite}</tr>
                <tr class="highlight-row"><td>Offer Accepts Actuals</td>{row_oa}</tr>
                <tr><td>Offer Accept Target</td>{row_target}</tr>
                <tr><td>GAP</td>{row_gap}</tr>
            </tbody>
        </table>"""

    # ── Pipeline slate HTML ──
    slate_html = ""
    if report.skill_groups:
        sg_rows = ""
        for sg in report.skill_groups:
            sg_rows += f"""<tr>
                <td class="left">{sg.skill_group}</td>
                <td>{sg.demands}</td>
                <td>{sg.rr_awaiting}</td><td>{sg.rr_incline}</td><td>{sg.rr_reject}</td>
                <td>{sg.oa_scheduled}</td><td>{sg.oa_incline}</td><td>{sg.oa_reject}</td>
                <td>{sg.bps_awaiting}</td><td>{sg.bps_scheduled}</td><td>{sg.bps_incline}</td><td>{sg.bps_reject}</td>
                <td>{sg.os_awaiting}</td><td>{sg.os_scheduled}</td><td>{sg.os_incline}</td><td>{sg.os_reject}</td>
                <td>{sg.offer_made}</td><td>{sg.offer_accept}</td><td>{sg.offer_renege}</td><td>{sg.onboard}</td>
            </tr>"""

        slate_html = f"""
        <h2>Active Pipeline - YTD Slate</h2>
        <div class="table-scroll">
        <table class="slate">
            <thead><tr>
                <th>Skill Group</th><th>Dem</th>
                <th>RR Aw</th><th>RR In</th><th>RR Rj</th>
                <th>OA Sc</th><th>OA In</th><th>OA Rj</th>
                <th>BPS Aw</th><th>BPS Sc</th><th>BPS In</th><th>BPS Rj</th>
                <th>OS Aw</th><th>OS Sc</th><th>OS In</th><th>OS Rj</th>
                <th>Off Md</th><th>Off Ac</th><th>Off Rn</th><th>Onbrd</th>
            </tr></thead>
            <tbody>
                {sg_rows}
                <tr class="grand-total">
                    <td class="left"><strong>Grand Total</strong></td>
                    <td><strong>{t['demands']}</strong></td>
                    <td><strong>{t['rr_awaiting']}</strong></td><td><strong>{t['rr_incline']}</strong></td><td><strong>{t['rr_reject']}</strong></td>
                    <td><strong>{t['oa_scheduled']}</strong></td><td><strong>{t['oa_incline']}</strong></td><td><strong>{t['oa_reject']}</strong></td>
                    <td><strong>{t['bps_awaiting']}</strong></td><td><strong>{t['bps_scheduled']}</strong></td><td><strong>{t['bps_incline']}</strong></td><td><strong>{t['bps_reject']}</strong></td>
                    <td><strong>{t['os_awaiting']}</strong></td><td><strong>{t['os_scheduled']}</strong></td><td><strong>{t['os_incline']}</strong></td><td><strong>{t['os_reject']}</strong></td>
                    <td><strong>{t['offer_made']}</strong></td><td><strong>{t['offer_accept']}</strong></td><td><strong>{t['offer_renege']}</strong></td><td><strong>{t['onboard']}</strong></td>
                </tr>
            </tbody>
        </table>
        </div>
        <div class="metrics-bar">
            <span>OA Completed: {metrics['oa_completed']}</span>
            <span>BPS Completed: {metrics['bps_completed']}</span>
            <span>OS Completed: {metrics['os_completed']}</span>
            <span>Offers Released: {metrics['offers_released']}</span>
        </div>
        <div class="metrics-bar">
            <span>OA Pass: {_pct(metrics['oa_pass_pct'])}</span>
            <span>BPS→OS: {_pct(metrics['bps_to_os_pct'])}</span>
            <span>OS Incline: {_pct(metrics['os_to_incline_pct'])}</span>
            <span>Offer Accept: {_pct(metrics['offer_accept_pct'])}</span>
        </div>"""

    # ── CTC / Sourcing insights HTML ──
    ctc_html = ""
    if report.ctc_insights:
        items = "".join(
            f"<li>{i.percentage}% ({i.count}/{i.total}) — {i.reason}</li>"
            for i in report.ctc_insights
        )
        ctc_html = f"""
        <h2>Sourcing Insights</h2>
        <h3>Capture-the-Conversation - Candidate Analysis</h3>
        <ol>{items}</ol>"""

    if report.source_hire_pct is not None or report.source_linkedin_pct is not None:
        parts = []
        if report.source_hire_pct is not None:
            parts.append(f"{report.source_hire_pct:.1f}% from Hire")
        if report.source_linkedin_pct is not None:
            parts.append(f"{report.source_linkedin_pct:.1f}% from LinkedIn")
        ctc_html += f"""
        <h3>Source Mix</h3>
        <p>YTD pipeline of {report.total_sourced} candidates: {' and '.join(parts)}.</p>"""

    # ── Support section ──
    support_html = ""
    if report.support_items:
        items = "".join(f"<li>{s}</li>" for s in report.support_items)
        support_html = f"<h2>Support Required</h2><ul>{items}</ul>"

    # ── Full page ──
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{report.report_title}</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', Calibri, Arial, sans-serif; background: #f4f6f9; color: #232f3e; padding: 20px; }}
    .container {{ max-width: 1200px; margin: 0 auto; background: #fff; border-radius: 8px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 32px; }}
    h1 {{ color: #232f3e; text-align: center; margin-bottom: 8px; font-size: 1.6em; }}
    h2 {{ color: #0073bb; margin: 24px 0 12px; font-size: 1.2em; border-bottom: 2px solid #0073bb; padding-bottom: 4px; }}
    h3 {{ color: #232f3e; margin: 12px 0 8px; font-size: 1em; }}
    p, li {{ font-size: 0.9em; line-height: 1.6; }}
    ul, ol {{ margin-left: 24px; margin-bottom: 12px; }}
    .summary-cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 16px 0; }}
    .card {{ background: #f0f4f8; border-radius: 6px; padding: 16px; text-align: center; }}
    .card .number {{ font-size: 1.8em; font-weight: 700; color: #0073bb; }}
    .card .label {{ font-size: 0.8em; color: #555; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 0.8em; }}
    th {{ background: #0073bb; color: #fff; padding: 6px 8px; text-align: center; white-space: pre-line; }}
    td {{ padding: 5px 8px; text-align: center; border: 1px solid #ddd; }}
    td.left {{ text-align: left; }}
    .grand-total td {{ background: #d9e2f3; font-weight: 700; }}
    .highlight-row td {{ background: #e8f5e9; }}
    .gap-positive {{ color: #d32f2f; font-weight: 700; }}
    .gap-negative {{ color: #2e7d32; font-weight: 700; }}
    .metrics-bar {{ display: flex; gap: 24px; justify-content: center; margin: 8px 0; font-size: 0.85em; }}
    .metrics-bar span {{ background: #f0f4f8; padding: 4px 12px; border-radius: 4px; }}
    .biz-card {{ background: #fafbfc; border-left: 3px solid #0073bb; padding: 12px 16px; margin: 8px 0; border-radius: 0 6px 6px 0; }}
    .biz-card h3 {{ margin: 0 0 8px; }}
    .table-scroll {{ overflow-x: auto; }}
    .slate {{ min-width: 900px; }}
    .actions {{ text-align: center; margin: 24px 0; }}
    .btn {{ display: inline-block; padding: 10px 24px; background: #0073bb; color: #fff; border: none; border-radius: 6px; font-size: 1em; cursor: pointer; text-decoration: none; margin: 0 8px; }}
    .btn:hover {{ background: #005a8e; }}
    .btn-secondary {{ background: #6c757d; }}
    .btn-secondary:hover {{ background: #545b62; }}
    .modal-overlay {{ display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; justify-content: center; align-items: center; }}
    .modal-overlay.active {{ display: flex; }}
    .modal {{ background: #fff; border-radius: 8px; padding: 28px; width: 520px; max-width: 90vw; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }}
    .modal h2 {{ color: #232f3e; margin-bottom: 16px; font-size: 1.2em; border: none; }}
    .modal label {{ display: block; font-weight: 600; margin: 10px 0 4px; font-size: 0.9em; }}
    .modal input[type="email"], .modal input[type="text"] {{ width: 100%; padding: 8px 12px; border: 1px solid #ccc; border-radius: 4px; font-size: 0.9em; }}
    .modal .checkbox-row {{ display: flex; align-items: center; gap: 8px; margin: 12px 0; }}
    .modal .checkbox-row input {{ width: auto; }}
    .modal .btn-row {{ display: flex; gap: 8px; margin-top: 18px; }}
    .modal .btn-row .btn {{ flex: 1; text-align: center; }}
    .toast {{ display: none; position: fixed; top: 20px; right: 20px; padding: 14px 24px; border-radius: 6px; color: #fff; font-size: 0.95em; z-index: 2000; box-shadow: 0 4px 16px rgba(0,0,0,0.15); }}
    .toast.success {{ background: #2e7d32; display: block; }}
    .toast.error {{ background: #d32f2f; display: block; }}
    .spinner {{ display: inline-block; width: 16px; height: 16px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; animation: spin 0.6s linear infinite; vertical-align: middle; margin-right: 6px; }}
    @keyframes spin {{ to {{ transform: rotate(360deg); }} }}
</style>
</head>
<body>
<div class="container">
    <h1>{report.report_title}</h1>
    <p style="text-align:center;color:#666;margin-bottom:20px;">FGBS {report.report_year} — Generated Report</p>

    <div class="summary-cards">
        <div class="card"><div class="number">{report.ytd_os_inclines}</div><div class="label">OS Inclines (YTD)</div></div>
        <div class="card"><div class="number">{report.ytd_offer_accepts}</div><div class="label">Offer Accepts (YTD)</div></div>
        <div class="card"><div class="number">{report.total_requisitions}</div><div class="label">Active Requisitions</div></div>
        <div class="card"><div class="number">{report.total_active_pipeline}</div><div class="label">Active Pipeline</div></div>
        <div class="card"><div class="number">{_pct(report.bps_to_os_pct)}</div><div class="label">BPS → Onsite</div></div>
        <div class="card"><div class="number">{_pct(report.os_to_incline_pct)}</div><div class="label">OS → Incline</div></div>
        <div class="card"><div class="number">{_pct(report.offer_acceptance_pct)}</div><div class="label">Offer Accept Rate</div></div>
    </div>

    <h2>Highlight &amp; Demand Updates</h2>
    <p>In {report.report_year}, we've delivered <strong>{report.ytd_os_inclines}</strong> OS inclines
    across L4-L6 roles, leading to <strong>{report.ytd_offer_accepts}</strong> Offer Accepts,
    <strong>{report.ytd_offer_stage}</strong> at Offer Stage and
    <strong>{report.ytd_offer_declines}</strong> Offer Declines.</p>
    <p style="margin-top:8px;">Working on <strong>{report.total_requisitions}</strong> requisitions with a pipeline of
    <strong>{report.total_active_pipeline}</strong> candidates at advanced stages.
    BPS-to-Onsite: {_pct(report.bps_to_os_pct)} | OS-to-Incline: {_pct(report.os_to_incline_pct)} |
    Offer Acceptance: {_pct(report.offer_acceptance_pct)}.</p>

    <h2>Business-wise Updates</h2>
    {biz_html}

    {monthly_html}
    {slate_html}
    {support_html}
    {ctc_html}

    <div class="actions">
        <a class="btn" href="/api/report/download" target="_blank">Download Word Document</a>
        <button class="btn" onclick="document.getElementById('emailModal').classList.add('active')" type="button">Send via Email</button>
    </div>

    <!-- Email Modal -->
    <div class="modal-overlay" id="emailModal">
        <div class="modal">
            <h2>Send Report via Email</h2>
            <form id="emailForm" onsubmit="sendEmail(event)">
                <label for="to_emails">To (comma-separated) *</label>
                <input type="text" id="to_emails" name="to_emails" placeholder="leader1@company.com, leader2@company.com" required>

                <label for="cc_emails">CC (optional)</label>
                <input type="text" id="cc_emails" name="cc_emails" placeholder="manager@company.com">

                <label for="subject">Subject</label>
                <input type="text" id="subject" name="subject" value="Weekly Funnel Report - FGBS {report.report_year}">

                <div class="checkbox-row">
                    <input type="checkbox" id="attach_docx" name="attach_docx" checked>
                    <label for="attach_docx" style="margin:0;font-weight:normal;">Attach Word document</label>
                </div>

                <div class="btn-row">
                    <button type="button" class="btn btn-secondary" onclick="document.getElementById('emailModal').classList.remove('active')">Cancel</button>
                    <button type="submit" class="btn" id="sendBtn">Send Email</button>
                </div>
            </form>
        </div>
    </div>

    <!-- Toast notification -->
    <div class="toast" id="toast"></div>

    <script>
    async function sendEmail(e) {{
        e.preventDefault();
        const btn = document.getElementById('sendBtn');
        const origText = btn.textContent;
        btn.innerHTML = '<span class="spinner"></span>Sending...';
        btn.disabled = true;

        const form = new FormData();
        form.append('to_emails', document.getElementById('to_emails').value);
        form.append('cc_emails', document.getElementById('cc_emails').value);
        form.append('subject', document.getElementById('subject').value);
        form.append('attach_docx', document.getElementById('attach_docx').checked ? 'true' : 'false');

        try {{
            const resp = await fetch('/api/report/send-email', {{ method: 'POST', body: form }});
            const data = await resp.json();
            showToast(data.message, data.success ? 'success' : 'error');
            if (data.success) {{
                document.getElementById('emailModal').classList.remove('active');
            }}
        }} catch (err) {{
            showToast('Network error: ' + err.message, 'error');
        }} finally {{
            btn.textContent = origText;
            btn.disabled = false;
        }}
    }}

    function showToast(msg, type) {{
        const t = document.getElementById('toast');
        t.textContent = msg;
        t.className = 'toast ' + type;
        setTimeout(() => {{ t.className = 'toast'; }}, 5000);
    }}

    // Close modal on overlay click
    document.getElementById('emailModal').addEventListener('click', function(e) {{
        if (e.target === this) this.classList.remove('active');
    }});
    </script>
</div>
</body>
</html>"""
