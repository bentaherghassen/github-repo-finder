import math
from datetime import datetime, timezone

from .models import Repository


def _logarithmic_score(value: int) -> float:
    """Convert a very wide popularity range into a 0-100 score."""

    if value <= 0:
        return 0.0

    return min(
        100.0,
        (math.log10(value + 1) / 5.0) * 100.0,
    )


def _recency_score(pushed_at: datetime | None) -> float:
    """Reward repositories with recent pushes."""

    if pushed_at is None:
        return 0.0

    now = datetime.now(timezone.utc)
    age_days = max(
        (now - pushed_at).total_seconds() / 86_400,
        0.0,
    )

    maximum_age_days = 3650.0

    return max(
        0.0,
        100.0 - min(age_days, maximum_age_days)
        / maximum_age_days
        * 100.0,
    )


def calculate_quality_score(repo: Repository) -> float:
    """Calculate a transparent heuristic quality score from 0 to 100."""

    popularity = _logarithmic_score(repo.stars)
    community = _logarithmic_score(repo.forks)
    activity = _recency_score(repo.pushed_at)

    relevance = min(
        max(repo.search_score, 0.0) / 10.0 * 100.0,
        100.0,
    )

    score = (
        popularity * 0.45
        + community * 0.15
        + activity * 0.25
        + relevance * 0.15
    )

    if repo.archived:
        score *= 0.25

    if repo.fork:
        score *= 0.85

    return round(score, 2)


def rank_repositories(
    repositories: list[Repository],
) -> list[Repository]:
    """Score and rank repositories from highest quality score to lowest."""

    for repo in repositories:
        repo.quality_score = calculate_quality_score(repo)

    return sorted(
        repositories,
        key=lambda repo: (
            repo.quality_score,
            repo.stars,
            repo.forks,
        ),
        reverse=True,
    )
