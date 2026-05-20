"""Send funnel report via email with DOCX attachment."""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _build_email_body(report) -> str:
    """Build a plain-text + HTML summary for the email body."""
    html = f"""<html><body style="font-family: Calibri, Arial, sans-serif; color: #232f3e;">
<h2 style="color: #0073bb;">Weekly Funnel Report - FGBS {report.report_year}</h2>

<h3>Highlight & Demand Updates</h3>
<p>In <b>{report.report_year}</b>, we've delivered <b>{report.ytd_os_inclines}</b> OS inclines
across L4-L6 roles, leading to <b>{report.ytd_offer_accepts}</b> Offer Accepts,
<b>{report.ytd_offer_stage}</b> at Offer Stage and <b>{report.ytd_offer_declines}</b> Offer Declines.</p>

<p>Working on <b>{report.total_requisitions}</b> requisitions with a pipeline of
<b>{report.total_active_pipeline}</b> candidates at advanced stages.</p>

<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-size:13px;">
<tr style="background:#0073bb; color:#fff;">
<th>Metric</th><th>Value</th>
</tr>
<tr><td>BPS → Onsite</td><td>{f"{report.bps_to_os_pct:.1f}%" if report.bps_to_os_pct else "N/A"}</td></tr>
<tr><td>OS → Incline</td><td>{f"{report.os_to_incline_pct:.1f}%" if report.os_to_incline_pct else "N/A"}</td></tr>
<tr><td>Offer Accept Rate</td><td>{f"{report.offer_acceptance_pct:.1f}%" if report.offer_acceptance_pct else "N/A"}</td></tr>
</table>

<h3>Business-wise Updates</h3>
<ul>
"""
    for biz in report.business_updates:
        html += f"<li><b>{biz.business_name}</b>: {biz.os_inclines} OS inclines → {biz.offer_accepts} offer accepts"
        if biz.incline_conversion_pct is not None:
            html += f" (Conv: {biz.incline_conversion_pct:.0f}%)"
        html += "</li>\n"

    html += """</ul>
<p style="color:#666; font-size:12px;">Full report attached as Word document.</p>
</body></html>"""
    return html


def send_report_email(
    to_emails: list[str],
    cc_emails: list[str],
    subject: str,
    docx_bytes: bytes,
    smtp_host: str,
    smtp_port: int,
    smtp_user: str,
    smtp_pass: str,
    report,
) -> dict:
    """Send the report email with DOCX attachment."""
    try:
        msg = MIMEMultipart("mixed")
        msg["From"] = smtp_user
        msg["To"] = ", ".join(to_emails)
        if cc_emails:
            msg["Cc"] = ", ".join(cc_emails)
        msg["Subject"] = subject

        # HTML body with report summary
        html_body = _build_email_body(report)
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        # Attach Word document
        attachment = MIMEApplication(docx_bytes, Name="Weekly_Funnel_Report.docx")
        attachment["Content-Disposition"] = 'attachment; filename="Weekly_Funnel_Report.docx"'
        msg.attach(attachment)

        # Send
        all_recipients = list(to_emails) + list(cc_emails)

        server = smtplib.SMTP(smtp_host, smtp_port)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, all_recipients, msg.as_string())
        server.quit()

        return {
            "success": True,
            "message": f"Email sent to {', '.join(to_emails)}",
        }
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "message": "Authentication failed. Check username/password. For Outlook, use an App Password."}
    except smtplib.SMTPException as e:
        return {"success": False, "message": f"SMTP error: {str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"Failed: {str(e)}"}
