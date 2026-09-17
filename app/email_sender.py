import asyncio
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from pathlib import Path
import smtplib
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
    """Construct a multipart MIME email message containing the report and attachments."""
    msg = MIMEMultipart("mixed")
    msg["From"] = settings.gmail_user
    msg["To"] = settings.email_recipient
    msg["Subject"] = f"GitHub Repository Finder Report - {len(repositories)} Repositories Found"

    # Create the text and HTML bodies
    top_repos = repositories[: settings.report_top_n]
    summary_lines = [
        "GitHub Repository Finder Discovery Report",
        "=" * 42,
        f"Total unique repositories found: {len(repositories)}",
        "",
    ]

    # Rising stars text block
    rising_stars_html = ""
    if rising_stars:
        summary_lines.append("🌟 Rising Stars & Fast Movers:")
        for item in rising_stars:
            r = item["repository"]
            growth = item.get("stars_gained", 0)
            status = f"+{growth:,} stars" if growth > 0 else "✨ New"
            summary_lines.append(f"  • {r.full_name} ({status}, total: {r.stars:,}) - {r.html_url}")
        summary_lines.append("")

        rising_rows = "".join(
            f"<tr>"
            f"<td><a href='{item['repository'].html_url}'><strong>{item['repository'].full_name}</strong></a></td>"
            f"<td style='color: #28a745; font-weight: bold;'>{'+' + str(item.get('stars_gained', 0)) + ' ⭐' if item.get('stars_gained', 0) > 0 else '✨ New'}</td>"
            f"<td>{item['repository'].stars:,}</td>"
            f"<td>{item['repository'].quality_score:.1f}</td>"
            f"<td>{', '.join(item['repository'].matched_topics) or 'N/A'}</td>"
            f"</tr>"
            for item in rising_stars
        )
        rising_stars_html = f"""
        <h3 style="color: #28a745; margin-top: 20px;">🌟 Rising Stars & Fast Movers</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; border-color: #ddd; width: 100%;">
          <thead style="background-color: #f0fff4;">
            <tr>
              <th>Repository</th>
              <th>Growth</th>
              <th>Total Stars</th>
              <th>Quality Score</th>
              <th>Topics</th>
            </tr>
          </thead>
          <tbody>
            {rising_rows}
          </tbody>
        </table>
        """

    summary_lines.append("Top Repositories:")
    for idx, repo in enumerate(top_repos, 1):
        summary_lines.append(
            f"{idx}. {repo.full_name} (Score: {repo.quality_score:.1f}, Stars: {repo.stars:,}) - {repo.html_url}"
        )

    summary_lines.extend(
        [
            "",
            "The full Markdown report and JSON data are attached.",
        ]
    )
    plain_text = "\n".join(summary_lines)

    html_rows = "".join(
        f"<tr>"
        f"<td><strong>{idx}</strong></td>"
        f"<td><a href='{repo.html_url}'>{repo.full_name}</a></td>"
        f"<td>{repo.quality_score:.1f}</td>"
        f"<td>{repo.stars:,}</td>"
        f"<td>{repo.language or 'N/A'}</td>"
        f"</tr>"
        for idx, repo in enumerate(top_repos, 1)
    )

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.5; color: #333;">
        <h2 style="color: #0366d6;">GitHub Repository Finder Report</h2>
        <p>Total unique repositories identified: <strong>{len(repositories)}</strong></p>
        {rising_stars_html}
        <h3 style="color: #0366d6; margin-top: 20px;">Top Repositories</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; border-color: #ddd; width: 100%;">
          <thead style="background-color: #f6f8fa;">
            <tr>
              <th>#</th>
              <th>Repository</th>
              <th>Quality Score</th>
              <th>Stars</th>
              <th>Language</th>
            </tr>
          </thead>
          <tbody>
            {html_rows}
          </tbody>
        </table>
        <p style="margin-top: 20px; font-size: 0.9em; color: #666;">
          Full report and JSON export are attached.
        </p>
      </body>
    </html>
    """

    body_alternative = MIMEMultipart("alternative")
    body_alternative.attach(MIMEText(plain_text, "plain", "utf-8"))
    body_alternative.attach(MIMEText(html_body, "html", "utf-8"))
    msg.attach(body_alternative)

    # Attach Markdown report
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

    # Attach JSON data
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
