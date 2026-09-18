import asyncio
import logging
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

from .config import Settings
from .models import Repository

logger = logging.getLogger(__name__)

# Common dummy/placeholder values
DUMMY_VALUES = {
    "your_email@gmail.com",
    "recipient@example.com",
    "abcd efgh ijkl mnop",
    "",
}


def _is_placeholder_credential(val: str | None) -> bool:
    if not val:
        return True
    return val.strip().lower() in DUMMY_VALUES or "example.com" in val.lower()

def _build_email_message(
    settings: Settings,
    repositories: list[Repository],
    report_path: Path,
    json_path: Path | None = None,
    rising_stars: list[dict[str, Any]] | None = None,
) -> MIMEMultipart:
    """Construct a screen-reader-friendly MIME email message containing the report and attachments."""
    msg = MIMEMultipart("mixed")
    msg["From"] = settings.gmail_user
    msg["To"] = settings.email_recipient
    msg["Subject"] = f"{len(repositories)} Repositories Found for today"

    top_repos = repositories[: settings.report_top_n]
    
    # --- Plain Text Version ---
    summary_lines = [
        "GitHub Repository Finder Discovery Report",
        "=" * 42,
        f"Total unique repositories found: {len(repositories)}",
        "",
    ]

    if rising_stars:
        summary_lines.append("🌟 Rising Stars & Fast Movers:")
        for item in rising_stars:
            r = item["repository"]
            growth = item.get("stars_gained", 0)
            status = f"+{growth:,} stars" if growth > 0 else "New"
            summary_lines.append(f"  - {r.full_name} ({status}, total stars: {r.stars:,}): {r.html_url}")
        summary_lines.append("")

    summary_lines.append("Top Repositories:")
    for idx, repo in enumerate(top_repos, 1):
        summary_lines.append(
            f"{idx}. {repo.full_name}, Language: {repo.language or 'N/A'}, Quality Score: {repo.quality_score:.1f}, Stars: {repo.stars:,}: {repo.html_url}"
        )

    summary_lines.extend(
        [
            "",
            "The full Markdown report and JSON data are attached.",
        ]
    )
    plain_text = "\n".join(summary_lines)

    # --- Screen-Reader Friendly HTML Version ---
    # Using clean lists and semantic headings instead of complex nested tables
    
    rising_stars_html = ""
    if rising_stars:
        rising_items = "".join(
            f"<li>"
            f"<a href='{item['repository'].html_url}'><strong>{item['repository'].full_name}</strong></a> — "
            f"<span>{'+' + str(item.get('stars_gained', 0)) + ' stars gained' if item.get('stars_gained', 0) > 0 else 'New arrival'}</span>, "
            f"<span>Total stars: {item['repository'].stars:,}</span>, "
            f"<span>Quality score: {item['repository'].quality_score:.1f}</span>"
            f"</li>"
            for item in rising_stars
        )
        rising_stars_html = f"""
        <section aria-labelledby="rising-stars-heading">
          <h2 id="rising-stars-heading" style="color: #28a745; font-size: 1.2em; margin-top: 24px;">🌟 Rising Stars & Fast Movers</h2>
          <ul style="padding-left: 20px; line-height: 1.8;">
            {rising_items}
          </ul>
        </section>
        """

    top_repos_items = "".join(
        f"<li>"
        f"<a href='{repo.html_url}'><strong>{repo.full_name}</strong></a> — "
        f"<span>Language: {repo.language or 'N/A'}</span>, "
        f"<span>Quality score: {repo.quality_score:.1f}</span>, "
        f"<span>Stars: {repo.stars:,}</span>"
        f"</li>"
        for repo in top_repos
    )

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #222; background-color: #fff; padding: 10px;">
        <h1 style="color: #0366d6; font-size: 1.4em;">GitHub Repository Finder Report</h1>
        <p>Total unique repositories identified: <strong>{len(repositories)}</strong></p>
        
        {rising_stars_html}
        
        <section aria-labelledby="top-repos-heading">
          <h2 id="top-repos-heading" style="color: #0366d6; font-size: 1.2em; margin-top: 24px;">Top Repositories</h2>
          <ol style="padding-left: 20px; line-height: 1.8;">
            {top_repos_items}
          </ol>
        </section>
        
        <p style="margin-top: 24px; font-size: 0.95em; color: #555;">
          Note: The full report and JSON export files are attached to this email.
        </p>
      </body>
    </html>
    """

    body_alternative = MIMEMultipart("alternative")
    body_alternative.attach(MIMEText(plain_text, "plain", "utf-8"))
    body_alternative.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(body_alternative)

    # Attachments handling remains unchanged below...
    if report_path.is_file():
        try:
            report_data = report_path.read_bytes()
            part = MIMEBase("text", "markdown")
            part.set_payload(report_data)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{report_path.name}"',
            )
            msg.attach(part)
        except Exception:
            logger.exception("Failed to attach markdown report %s", report_path)

    if json_path and json_path.is_file():
        try:
            json_data = json_path.read_bytes()
            part = MIMEBase("application", "json")
            part.set_payload(json_data)
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition",
                f'attachment; filename="{json_path.name}"',
            )
            msg.attach(part)
        except Exception:
            logger.exception("Failed to attach JSON export %s", json_path)

    return msg
    
def _send_email_sync(
    settings: Settings,
    msg: MIMEMultipart,
) -> bool:
    """Send email synchronously using Gmail SMTP SSL with Google App Password."""
    smtp_host = "smtp.gmail.com"
    smtp_port = 465

    # Remove spaces from Google App Password if present (Google displays them as 4x4)
    app_password = settings.gmail_app_password.replace(" ", "") if settings.gmail_app_password else ""

    logger.info("Connecting to %s:%d via SSL...", smtp_host, smtp_port)
    try:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=settings.request_timeout) as server:
            server.login(settings.gmail_user, app_password)
            server.send_message(msg)
        logger.info("Email report successfully sent to %s", settings.email_recipient)
        return True
    except smtplib.SMTPAuthenticationError as exc:
        logger.error(
            "Gmail authentication failed (%s). Please verify your GMAIL_USER and "
            "GMAIL_APP_PASSWORD in .env. Ensure you are using a Google App Password "
            "(see docs/GMAIL_SETUP.md for instructions).",
            exc,
        )
        return False
    except smtplib.SMTPException as exc:
        logger.error("Gmail SMTP error while sending report: %s", exc)
        return False
    except OSError as exc:
        logger.error("Network error while connecting to Gmail SMTP: %s", exc)
        return False


async def send_report_email(
    settings: Settings,
    repositories: list[Repository],
    report_path: Path,
    json_path: Path | None = None,
    rising_stars: list[dict[str, Any]] | None = None,
) -> bool:
    """Send discovery report via Gmail using Google App Password authentication."""
    if not settings.email_notifications_enabled:
        logger.debug("Email notifications are disabled (EMAIL_NOTIFICATIONS_ENABLED=false).")
        return False

    if not settings.gmail_user or not settings.gmail_app_password or not settings.email_recipient:
        logger.warning(
            "Email notifications enabled but Gmail credentials are not fully configured in .env."
        )
        return False

    if (
        _is_placeholder_credential(settings.gmail_user)
        or _is_placeholder_credential(settings.gmail_app_password)
        or _is_placeholder_credential(settings.email_recipient)
    ):
        logger.info(
            "Gmail notifications skipped: placeholder/dummy credentials found in .env. "
            "Set real GMAIL_USER, GMAIL_APP_PASSWORD, and EMAIL_RECIPIENT when ready."
        )
        return False

    msg = _build_email_message(
        settings,
        repositories,
        report_path,
        json_path,
        rising_stars=rising_stars,
    )
    return await asyncio.to_thread(_send_email_sync, settings, msg)
