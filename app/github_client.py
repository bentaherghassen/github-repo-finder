import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import time
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import Settings

logger = logging.getLogger(__name__)


@dataclass
class RateLimitInfo:
    """Parsed GitHub API rate-limit metadata."""

    limit: int | None = None
    remaining: int | None = None
    reset_timestamp: int | None = None
    retry_after: float | None = None
    resource: str | None = None
    used: int | None = None

    @property
    def reset_datetime(self) -> datetime | None:
        """UTC datetime when the current rate limit window resets."""
        if self.reset_timestamp is not None:
            return datetime.fromtimestamp(self.reset_timestamp, tz=timezone.utc)
        return None

    @property
    def seconds_until_reset(self) -> float:
        """Number of seconds remaining until the rate limit resets."""
        if self.reset_timestamp is not None:
            return max(0.0, self.reset_timestamp - time.time())
        return 0.0

    @property
    def is_exhausted(self) -> bool:
        """True if the limit is known to be completely exhausted and not yet reset."""
        return (
            self.remaining is not None
            and self.remaining == 0
            and self.seconds_until_reset > 0
        )


def parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header value (seconds or RFC 7231 / RFC 9110 HTTP-date)."""
    if not value:
        return None
    cleaned = value.strip()
    try:
        return max(0.0, float(cleaned))
    except ValueError:
        pass

    try:
        target_dt = parsedate_to_datetime(cleaned)
        now = datetime.now(timezone.utc)
        return max(0.0, (target_dt - now).total_seconds())
    except Exception:
        return None


def parse_rate_limit_headers(headers: httpx.Headers) -> RateLimitInfo:
    """Extract and parse GitHub rate limit headers from an HTTP response."""
    def safe_int(key: str) -> int | None:
        raw = headers.get(key)
        if raw is None:
            return None
        try:
            return int(raw)
        except ValueError:
            return None

    return RateLimitInfo(
        limit=safe_int("X-RateLimit-Limit"),
        remaining=safe_int("X-RateLimit-Remaining"),
        reset_timestamp=safe_int("X-RateLimit-Reset"),
        retry_after=parse_retry_after(headers.get("Retry-After")),
        resource=headers.get("X-RateLimit-Resource"),
        used=safe_int("X-RateLimit-Used"),
    )


class GitHubAPIError(RuntimeError):
    """Raised when GitHub returns an unsuccessful API response."""


class GitHubRateLimitError(GitHubAPIError):
    """Raised when GitHub returns a rate-limit response (403/429) or wait budget is exceeded."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        rate_limit_info: RateLimitInfo,
        is_secondary: bool = False,
        wait_seconds: float = 0.0,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.rate_limit_info = rate_limit_info
        self.is_secondary = is_secondary
        self.wait_seconds = wait_seconds


class GitHubClient:
    """Asynchronous client for the GitHub REST API respecting rate limits and API terms."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": settings.github_api_version,
            "User-Agent": "github-repo-finder/1.0",
        }

        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"

        self._client = httpx.AsyncClient(
            base_url=settings.github_api_url.rstrip("/"),
            headers=headers,
            timeout=settings.request_timeout,
        )
        self._last_rate_limit: RateLimitInfo | None = None

    @property
    def last_rate_limit(self) -> RateLimitInfo | None:
        """The most recently recorded rate-limit metadata."""
        return self._last_rate_limit

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception_type(
            (httpx.TimeoutException, httpx.NetworkError)
        ),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _send_request(
        self,
        url: str,
        params: dict[str, Any],
    ) -> httpx.Response:
        """Send low-level HTTP GET request with network/timeout retries."""
        return await self._client.get(url, params=params)

    async def search_repositories(
        self,
        topic: str,
        *,
        per_page: int,
    ) -> list[dict[str, Any]]:
        """Search GitHub repositories for a topic respecting rate limits.

        If a rate limit (403 or 429) is encountered, the method checks Retry-After
        and X-RateLimit-Reset headers to wait the appropriate duration before retrying,
        up to `rate_limit_max_retries` attempts.
        """
        # Proactively check if known rate limit is exhausted before making a request
        if self._last_rate_limit and self._last_rate_limit.is_exhausted:
            wait_time = self._last_rate_limit.seconds_until_reset + 1.0
            if wait_time > self._settings.max_rate_limit_wait_seconds:
                raise GitHubRateLimitError(
                    f"GitHub rate limit currently exhausted. Reset in {wait_time:.1f}s, "
                    f"which exceeds maximum allowed wait of {self._settings.max_rate_limit_wait_seconds:.1f}s. "
                    "Halting requests to respect GitHub API terms.",
                    status_code=403,
                    rate_limit_info=self._last_rate_limit,
                    wait_seconds=wait_time,
                )
            logger.info(
                "Known rate limit exhausted. Waiting %.1fs until %s before querying topic: %s",
                wait_time,
                self._last_rate_limit.reset_datetime,
                topic,
            )
            await asyncio.sleep(wait_time)

        params = {
            "q": topic,
            "sort": "stars",
            "order": "desc",
            "per_page": min(per_page, 100),
        }

        attempts = 0
        while True:
            response = await self._send_request(
                "/search/repositories",
                params=params,
            )

            # Update rate-limit tracking from response headers
            rate_info = parse_rate_limit_headers(response.headers)
            self._last_rate_limit = rate_info

            if not response.is_error:
                payload = response.json()
                return payload.get("items", [])

            # Check if this error is a rate limit response (403 or 429)
            is_rate_limit = False
            is_secondary = False
            response_text = response.text[:500]
            text_lower = response_text.lower()

            if response.status_code == 429:
                is_rate_limit = True
                is_secondary = True
            elif response.status_code == 403:
                if rate_info.remaining == 0:
                    is_rate_limit = True
                    is_secondary = False
                elif rate_info.retry_after is not None or "rate limit" in text_lower:
                    is_rate_limit = True
                    is_secondary = "secondary" in text_lower or rate_info.retry_after is not None

            if not is_rate_limit:
                remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
                reset = response.headers.get("X-RateLimit-Reset", "unknown")
                raise GitHubAPIError(
                    "GitHub API request failed. "
                    f"Status={response.status_code}, "
                    f"rate_limit_remaining={remaining}, "
                    f"rate_limit_reset={reset}, "
                    f"response={response_text}"
                )

            # Determine appropriate wait duration according to GitHub headers
            if rate_info.retry_after is not None:
                wait_seconds = rate_info.retry_after
            elif rate_info.reset_timestamp is not None:
                # Add 1.0 second safety margin past epoch reset boundary
                wait_seconds = rate_info.seconds_until_reset + 1.0
            else:
                # GitHub documentation recommends at least 1 minute when no header is present
                wait_seconds = 60.0

            limit_type = "Secondary" if is_secondary else "Primary"
            reset_display = rate_info.reset_datetime.isoformat() if rate_info.reset_datetime else "unknown"

            if wait_seconds > self._settings.max_rate_limit_wait_seconds:
                raise GitHubRateLimitError(
                    f"{limit_type} rate limit reached (status {response.status_code}). "
                    f"Required wait of {wait_seconds:.1f}s exceeds maximum configured wait of "
                    f"{self._settings.max_rate_limit_wait_seconds:.1f}s. "
                    f"Reset time: {reset_display}. Halting to comply with GitHub API terms.",
                    status_code=response.status_code,
                    rate_limit_info=rate_info,
                    is_secondary=is_secondary,
                    wait_seconds=wait_seconds,
                )

            attempts += 1
            if attempts > self._settings.rate_limit_max_retries:
                raise GitHubRateLimitError(
                    f"{limit_type} rate limit reached (status {response.status_code}). "
                    f"Exceeded maximum rate-limit retries ({self._settings.rate_limit_max_retries}). "
                    f"Reset time: {reset_display}. Halting to comply with GitHub API terms.",
                    status_code=response.status_code,
                    rate_limit_info=rate_info,
                    is_secondary=is_secondary,
                    wait_seconds=wait_seconds,
                )

            logger.warning(
                "%s rate limit reached (status %d). Respecting headers: waiting %.1fs until %s "
                "before retrying (attempt %d/%d)...",
                limit_type,
                response.status_code,
                wait_seconds,
                reset_display,
                attempts,
                self._settings.rate_limit_max_retries,
            )

            await asyncio.sleep(wait_seconds)
