from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.database import (
    calculate_star_velocities,
    get_rising_stars,
    init_db,
    record_snapshots,
)
from app.models import Repository
from app.reports import write_markdown_report


def make_repo(
    repo_id: int,
    name: str = "repo",
    stars: int = 100,
    score: float = 80.0,
    topics: list[str] | None = None,
) -> Repository:
    return Repository(
        id=repo_id,
        full_name=f"test-owner/{name}",
        name=name,
        owner="test-owner",
        html_url=f"https://github.com/test-owner/{name}",
        stars=stars,
        forks=10,
        open_issues=2,
        pushed_at=datetime.now(timezone.utc),
        search_score=10.0,
        quality_score=score,
        matched_topics=topics or ["fastapi"],
    )


def test_init_db_creates_tables(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    init_db(db_file)
    assert db_file.exists()


def test_single_snapshot_identified_as_new(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    init_db(db_file)

    repo = make_repo(101, stars=50)
    record_snapshots(db_file, [repo])

    velocities = calculate_star_velocities(db_file, [repo])
    assert 101 in velocities
    assert velocities[101]["is_new"] is True
    assert velocities[101]["stars_gained"] == 0
    assert velocities[101]["current_stars"] == 50


def test_multiple_snapshots_calculate_star_velocity(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    init_db(db_file)

    repo_day1 = make_repo(201, stars=100)
    time_day1 = datetime.now(timezone.utc) - timedelta(days=2)
    record_snapshots(db_file, [repo_day1], captured_at=time_day1)

    # Day 2: gained 25 stars
    repo_day2 = make_repo(201, stars=125)
    time_day2 = datetime.now(timezone.utc)
    record_snapshots(db_file, [repo_day2], captured_at=time_day2)

    velocities = calculate_star_velocities(db_file, [repo_day2], days=7)
    assert velocities[201]["is_new"] is False
    assert velocities[201]["stars_gained"] == 25
    assert velocities[201]["previous_stars"] == 100
    assert velocities[201]["current_stars"] == 125


def test_get_rising_stars_ranks_by_velocity(tmp_path: Path) -> None:
    db_file = tmp_path / "test.db"
    init_db(db_file)

    past = datetime.now(timezone.utc) - timedelta(days=3)
    now = datetime.now(timezone.utc)

    # Repo A: gained 100 stars
    record_snapshots(db_file, [make_repo(1, name="repoA", stars=500, score=70.0)], captured_at=past)
    record_snapshots(db_file, [make_repo(1, name="repoA", stars=600, score=70.0)], captured_at=now)

    # Repo B: gained 10 stars
    record_snapshots(db_file, [make_repo(2, name="repoB", stars=1000, score=90.0)], captured_at=past)
    record_snapshots(db_file, [make_repo(2, name="repoB", stars=1010, score=90.0)], captured_at=now)

    # Repo C: gained 250 stars
    record_snapshots(db_file, [make_repo(3, name="repoC", stars=50, score=85.0)], captured_at=past)
    record_snapshots(db_file, [make_repo(3, name="repoC", stars=300, score=85.0)], captured_at=now)

    current_repos = [
        make_repo(1, name="repoA", stars=600, score=70.0),
        make_repo(2, name="repoB", stars=1010, score=90.0),
        make_repo(3, name="repoC", stars=300, score=85.0),
    ]

    rising = get_rising_stars(db_file, current_repos, limit=2)
    assert len(rising) == 2
    # Repo C gained 250 (rank 1), Repo A gained 100 (rank 2)
    assert rising[0]["repository"].id == 3
    assert rising[0]["stars_gained"] == 250
    assert rising[1]["repository"].id == 1
    assert rising[1]["stars_gained"] == 100


def test_report_includes_rising_stars_section(tmp_path: Path) -> None:
    report_file = tmp_path / "report.md"
    repo = make_repo(1, name="super-agent", stars=1500)

    rising_stars = [
        {
            "repository": repo,
            "stars_gained": 120,
            "is_new": False,
            "quality_score": 92.0,
        }
    ]

    write_markdown_report(
        [repo],
        ["fastapi"],
        report_file,
        top_n=5,
        rising_stars=rising_stars,
    )

    content = report_file.read_text(encoding="utf-8")
    assert "## 🌟 Rising Stars & Fast Movers" in content
    assert "super-agent" in content
    assert "+120 ⭐" in content
