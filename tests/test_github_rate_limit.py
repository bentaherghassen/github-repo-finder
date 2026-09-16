from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
import time
import httpx
import pytest

from app.config import Settings
from app.github_client import (
    GitHubAPIError,
    GitHubClient,
    GitHubRateLimitError,
    RateLimitInfo,
    parse_rate_limit_headers,
    parse_retry_after,
)


def test_parse_retry_after_integer_seconds() -> None:
    assert parse_retry_after("120") == 120.0
    assert parse_retry_after("0") == 0.0
    assert parse_retry_after("-5") == 0.0


def test_parse_retry_after_http_date() -> None:
    future = datetime.now(timezone.utc) + timedelta(seconds=90)
    date_str = format_datetime(future, usegmt=True)
    val = parse_retry_after(date_str)
    assert val is not None
    assert 85 <= val <= 95


def test_parse_retry_after_none_or_invalid() -> None:
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("not-a-number-or-date") is None


def test_parse_rate_limit_headers() -> None:
    headers = httpx.Headers(
        {
            "X-RateLimit-Limit": "30",
            "X-RateLimit-Remaining": "5",
            "X-RateLimit-Reset": "1700000000",
            "X-RateLimit-Used": "25",
            "X-RateLimit-Resource": "search",
            "Retry-After": "45",
        }
    )
    info = parse_rate_limit_headers(headers)
    assert info.limit == 30
    assert info.remaining == 5
    assert info.reset_timestamp == 1700000000
    assert info.used == 25
    assert info.resource == "search"
    assert info.retry_after == 45.0
    assert info.reset_datetime == datetime.fromtimestamp(1700000000, tz=timezone.utc)


def test_rate_limit_info_is_exhausted() -> None:
    future_epoch = int(time.time()) + 100
    info_active = RateLimitInfo(remaining=5, reset_timestamp=future_epoch)
    assert not info_active.is_exhausted

    info_exhausted = RateLimitInfo(remaining=0, reset_timestamp=future_epoch)
    assert info_exhausted.is_exhausted

    past_epoch = int(time.time()) - 10
    info_past = RateLimitInfo(remaining=0, reset_timestamp=past_epoch)
    assert not info_past.is_exhausted


@pytest.mark.anyio
async def test_search_repositories_waits_and_retries_on_rate_limit() -> None:
    calls = 0
    now_epoch = int(time.time())

    def custom_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            # First call returns 429 with small Retry-After
            return httpx.Response(
                429,
                headers={"Retry-After": "0.05"},
                text='{"message": "You have exceeded a secondary rate limit."}',
            )
        # Second call succeeds
        return httpx.Response(
            200,
            headers={
                "X-RateLimit-Limit": "30",
                "X-RateLimit-Remaining": "29",
                "X-RateLimit-Reset": str(now_epoch + 60),
            },
            json={"items": [{"id": 1, "name": "sample"}]},
        )

    transport = httpx.MockTransport(custom_handler)
    settings = Settings(
        max_rate_limit_wait_seconds=10.0,
        rate_limit_max_retries=2,
    )
    client = GitHubClient(settings)
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="https://api.github.com",
    )

    items = await client.search_repositories("test", per_page=5)
    assert len(items) == 1
    assert items[0]["name"] == "sample"
    assert calls == 2


@pytest.mark.anyio
async def test_search_repositories_stops_when_wait_exceeds_max_wait() -> None:
    def custom_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 500),
            },
            text='{"message": "API rate limit exceeded"}',
        )

    transport = httpx.MockTransport(custom_handler)
    settings = Settings(
        max_rate_limit_wait_seconds=60.0,  # Max wait is 60s, but reset is 500s
        rate_limit_max_retries=2,
    )
    client = GitHubClient(settings)
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="https://api.github.com",
    )

    with pytest.raises(GitHubRateLimitError) as exc_info:
        await client.search_repositories("test", per_page=5)

    assert exc_info.value.status_code == 403
    assert exc_info.value.rate_limit_info.remaining == 0
    assert "exceeds maximum configured wait" in str(exc_info.value)


@pytest.mark.anyio
async def test_search_repositories_stops_when_max_retries_exceeded() -> None:
    calls = 0

    def custom_handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            429,
            headers={"Retry-After": "0.01"},
            text='{"message": "You have exceeded a secondary rate limit."}',
        )

    transport = httpx.MockTransport(custom_handler)
    settings = Settings(
        max_rate_limit_wait_seconds=10.0,
        rate_limit_max_retries=1,  # Only 1 retry allowed
    )
    client = GitHubClient(settings)
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="https://api.github.com",
    )

    with pytest.raises(GitHubRateLimitError) as exc_info:
        await client.search_repositories("test", per_page=5)

    assert exc_info.value.status_code == 429
    assert "Exceeded maximum rate-limit retries" in str(exc_info.value)
    # Initial request + 1 retry = 2 calls
    assert calls == 2


@pytest.mark.anyio
async def test_non_rate_limit_403_raises_github_api_error() -> None:
    def custom_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            headers={
                "X-RateLimit-Remaining": "20",
                "X-RateLimit-Reset": str(int(time.time()) + 100),
            },
            text='{"message": "Resource protected by organization policy"}',
        )

    transport = httpx.MockTransport(custom_handler)
    settings = Settings()
    client = GitHubClient(settings)
    client._client = httpx.AsyncClient(
        transport=transport,
        base_url="https://api.github.com",
    )

    with pytest.raises(GitHubAPIError) as exc_info:
        await client.search_repositories("test", per_page=5)

    # Must be regular GitHubAPIError, NOT GitHubRateLimitError
    assert not isinstance(exc_info.value, GitHubRateLimitError)
    assert "Status=403" in str(exc_info.value)
