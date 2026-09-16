from datetime import datetime, timezone

from app.models import Repository
from app.ranking import calculate_quality_score


def test_quality_score_is_between_zero_and_one_hundred() -> None:
    repo = Repository(
        id=1,
        full_name="example/project",
        name="project",
        owner="example",
        html_url="https://github.com/example/project",
        stars=10_000,
        forks=1_000,
        pushed_at=datetime.now(timezone.utc),
        search_score=10.0,
    )

    score = calculate_quality_score(repo)

    assert 0 < score <= 100


def test_archived_repository_is_penalized() -> None:
    base_kwargs = dict(
        id=1,
        full_name="example/project",
        name="project",
        owner="example",
        html_url="https://github.com/example/project",
        stars=10_000,
        forks=1_000,
        pushed_at=datetime.now(timezone.utc),
        search_score=10.0,
    )

    active = Repository(**base_kwargs)
    archived = Repository(
        **(
            base_kwargs
            | {
                "id": 2,
                "full_name": "example/archived",
                "archived": True,
            }
        )
    )

    assert calculate_quality_score(archived) < calculate_quality_score(active)
