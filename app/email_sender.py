"""Send the funnel report via email with the HTML body inline and DOCX attached."""

import logging
import os
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


def _get_smtp_config() -> dict:
    """Load SMTP configuration from environment variables."""
    return {
        "host": os.getenv("SMTP_HOST", ""),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "username": os.getenv("SMTP_USERNAME", ""),
        "password": os.getenv("SMTP_PASSWORD", ""),
        "use_tls": os.getenv("SMTP_USE_TLS", "true").lower() == "true",
        "from_email": os.getenv("SMTP_FROM_EMAIL", ""),
        "from_name": os.getenv("SMTP_FROM_NAME", "Funnel Report Generator"),
    }


def send_report_email(
    to_emails: list[str],
    subject: str,
    html_body: str,
    cc_emails: list[str] = None,
    docx_bytes: Optional[bytes] = None,
    docx_filename: str = "Weekly_Funnel_Report.docx",
) -> dict:
    """
    Send the funnel report email.

    - html_body: the full report rendered as HTML (displayed inline)
    - docx_bytes: optional Word doc attached for offline reference
    """
    config = _get_smtp_config()

    if not config["host"]:
        raise ValueError(
            "SMTP not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, "
            "SMTP_PASSWORD, and SMTP_FROM_EMAIL in your .env file."
        )

    # Build the email
    msg = MIMEMultipart("mixed")
    msg["From"] = f"{config['from_name']} <{config['from_email']}>"
    msg["To"] = ", ".join(to_emails)
    if cc_emails:
        msg["Cc"] = ", ".join(cc_emails)
    msg["Subject"] = subject

    # Strip the full-page wrapper styles for email compatibility and
    # inject email-safe inline styles instead
    email_html = _make_email_safe_html(html_body)
    msg.attach(MIMEText(email_html, "html", "utf-8"))

    # Attach the Word document if provided
    if docx_bytes:
        attachment = MIMEApplication(docx_bytes, Name=docx_filename)
        attachment["Content-Disposition"] = f'attachment; filename="{docx_filename}"'
        msg.attach(attachment)

    # Send
    all_recipients = list(to_emails)
    if cc_emails:
        all_recipients.extend(cc_emails)

    try:
        if config["use_tls"]:
            server = smtplib.SMTP(config["host"], config["port"])
            server.ehlo()
            server.starttls()
            server.ehlo()
        else:
            server = smtplib.SMTP(config["host"], config["port"])
            server.ehlo()

        if config["username"] and config["password"]:
            server.login(config["username"], config["password"])

        server.sendmail(config["from_email"], all_recipients, msg.as_string())
        server.quit()

        logger.info(f"Report email sent to {all_recipients}")
        return {
            "success": True,
            "message": f"Email sent to {', '.join(to_emails)}",
            "recipients": to_emails,
            "cc": cc_emails or [],
        }
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return {"success": False, "message": f"SMTP error: {str(e)}"}
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        return {"success": False, "message": f"Failed to send: {str(e)}"}


def _make_email_safe_html(html: str) -> str:
    """
    Adjust the report HTML for email clients.

    Email clients ignore <style> blocks and external CSS, so we keep
    the inline styles that are already on elements. We also remove the
    download button and background styling that won't render in email.
    """
    # Remove the download/email action buttons from the email body
    import re
    html = re.sub(
        r'<div class="actions">.*?</div>',
        '',
        html,
        flags=re.DOTALL,
    )
    # Replace body background for email
    html = html.replace(
        "background: #f4f6f9;",
        "background: #ffffff;",
    )
    # Remove box-shadow (not supported in most email clients)
    html = html.replace(
        "box-shadow: 0 2px 12px rgba(0,0,0,0.08);",
        "",
    )
    return html
