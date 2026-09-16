from datetime import datetime, timezone
from pathlib import Path
import smtplib
from unittest.mock import MagicMock, patch
import pytest

from app.config import Settings
from app.email_sender import (
    _build_email_message,
    _is_placeholder_credential,
    send_report_email,
)
from app.models import Repository


def test_is_placeholder_credential() -> None:
    assert _is_placeholder_credential("your_email@gmail.com") is True
    assert _is_placeholder_credential("recipient@example.com") is True
    assert _is_placeholder_credential("abcd efgh ijkl mnop") is True
    assert _is_placeholder_credential("") is True
    assert _is_placeholder_credential(None) is True
    assert _is_placeholder_credential("valid.developer@gmail.com") is False
    assert _is_placeholder_credential("secrettoken12345") is False


@pytest.mark.anyio
async def test_send_report_email_disabled(tmp_path: Path) -> None:
    settings = Settings(email_notifications_enabled=False)
    result = await send_report_email(settings, [], tmp_path / "dummy.md")
    assert result is False


@pytest.mark.anyio
async def test_send_report_email_placeholder_skipped(tmp_path: Path) -> None:
    settings = Settings(
        email_notifications_enabled=True,
        gmail_user="your_email@gmail.com",
        gmail_app_password="abcd efgh ijkl mnop",
        email_recipient="recipient@example.com",
    )
    result = await send_report_email(settings, [], tmp_path / "dummy.md")
    assert result is False


def test_build_email_message(tmp_path: Path) -> None:
    report_file = tmp_path / "latest.md"
    report_file.write_text("# Test Report Content", encoding="utf-8")

    json_file = tmp_path / "repositories.json"
    json_file.write_text("[]", encoding="utf-8")

    settings = Settings(
        gmail_user="dev@gmail.com",
        gmail_app_password="password1234",
        email_recipient="notify@gmail.com",
    )

    repo = Repository(
        id=101,
        full_name="org/cool-project",
        name="cool-project",
        owner="org",
        html_url="https://github.com/org/cool-project",
        stars=500,
        forks=50,
        pushed_at=datetime.now(timezone.utc),
        search_score=15.0,
        quality_score=85.0,
    )

    msg = _build_email_message(settings, [repo], report_file, json_file)
    assert msg["From"] == "dev@gmail.com"
    assert msg["To"] == "notify@gmail.com"
    assert "1 Repositories Found" in msg["Subject"]

    # Check payload has body and 2 attachments
    payloads = msg.get_payload()
    assert len(payloads) == 3


@pytest.mark.anyio
async def test_send_report_email_success(tmp_path: Path) -> None:
    report_file = tmp_path / "latest.md"
    report_file.write_text("report", encoding="utf-8")

    settings = Settings(
        email_notifications_enabled=True,
        gmail_user="myuser@gmail.com",
        gmail_app_password="app password here",
        email_recipient="receiver@domain.com",
    )

    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp

    with patch("smtplib.SMTP_SSL", return_value=mock_smtp) as mock_ssl:
        result = await send_report_email(settings, [], report_file)
        assert result is True
        mock_ssl.assert_called_once_with("smtp.gmail.com", 465, timeout=settings.request_timeout)
        # Spaces should be removed from app password
        mock_smtp.login.assert_called_once_with("myuser@gmail.com", "apppasswordhere")
        mock_smtp.send_message.assert_called_once()


@pytest.mark.anyio
async def test_send_report_email_auth_failure(tmp_path: Path) -> None:
    report_file = tmp_path / "latest.md"
    report_file.write_text("report", encoding="utf-8")

    settings = Settings(
        email_notifications_enabled=True,
        gmail_user="myuser@gmail.com",
        gmail_app_password="invalid_password",
        email_recipient="receiver@domain.com",
    )

    mock_smtp = MagicMock()
    mock_smtp.__enter__.return_value = mock_smtp
    mock_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")

    with patch("smtplib.SMTP_SSL", return_value=mock_smtp):
        result = await send_report_email(settings, [], report_file)
        # Must return False and not raise exception
        assert result is False
