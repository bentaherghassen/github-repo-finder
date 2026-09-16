from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
import sqlite3
from typing import Any, Generator

from .models import Repository


@contextmanager
def get_db_connection(db_path: Path) -> Generator[sqlite3.Connection, None, None]:
    """Provide a transactional SQLite database connection with row access by column name."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    """Initialize SQLite database tables and indexes for historical tracking."""
    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS repositories (
                id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                name TEXT NOT NULL,
                owner TEXT NOT NULL,
                html_url TEXT NOT NULL,
                description TEXT,
                language TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
                captured_at TEXT NOT NULL,
                stars INTEGER NOT NULL,
                forks INTEGER NOT NULL,
                open_issues INTEGER NOT NULL,
                quality_score REAL NOT NULL
            )
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS repository_topics (
                repository_id INTEGER NOT NULL REFERENCES repositories(id) ON DELETE CASCADE,
                topic TEXT NOT NULL,
                PRIMARY KEY (repository_id, topic)
            )
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_snapshots_repo_time
            ON snapshots (repository_id, captured_at)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_snapshots_captured_at
            ON snapshots (captured_at)
            """
        )


def record_snapshots(
    db_path: Path,
    repositories: list[Repository],
    captured_at: datetime | None = None,
) -> None:
    """Upsert repository records and save a new timestamped snapshot."""
    timestamp = (captured_at or datetime.now(timezone.utc)).isoformat()

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        for repo in repositories:
            # 1. Upsert repository record
            cursor.execute(
                """
                INSERT INTO repositories (
                    id, full_name, name, owner, html_url,
                    description, language, first_seen_at, last_seen_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    full_name=excluded.full_name,
                    name=excluded.name,
                    owner=excluded.owner,
                    html_url=excluded.html_url,
                    description=excluded.description,
                    language=excluded.language,
                    last_seen_at=excluded.last_seen_at
                """,
                (
                    repo.id,
                    repo.full_name,
                    repo.name,
                    repo.owner,
                    repo.html_url,
                    repo.description,
                    repo.language,
                    timestamp,
                    timestamp,
                ),
            )

            # 2. Record historical snapshot
            cursor.execute(
                """
                INSERT INTO snapshots (
                    repository_id, captured_at, stars,
                    forks, open_issues, quality_score
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    repo.id,
                    timestamp,
                    repo.stars,
                    repo.forks,
                    repo.open_issues,
                    repo.quality_score,
                ),
            )

            # 3. Associate topics
            for topic in repo.matched_topics:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO repository_topics (repository_id, topic)
                    VALUES (?, ?)
                    """,
                    (repo.id, topic),
                )


def calculate_star_velocities(
    db_path: Path,
    repositories: list[Repository],
    days: int = 7,
) -> dict[int, dict[str, Any]]:
    """Compute star growth velocity and discovery status for a list of repositories."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    results: dict[int, dict[str, Any]] = {}

    with get_db_connection(db_path) as conn:
        cursor = conn.cursor()

        for repo in repositories:
            # Query all snapshots for this repository ordered chronologically
            cursor.execute(
                """
                SELECT stars, captured_at
                FROM snapshots
                WHERE repository_id = ?
                ORDER BY captured_at ASC
                """,
                (repo.id,),
            )
            snapshots = cursor.fetchall()

            if not snapshots:
                results[repo.id] = {
                    "stars_gained": 0,
                    "is_new": True,
                    "previous_stars": None,
                    "current_stars": repo.stars,
                }
                continue

            current_stars = snapshots[-1]["stars"]

            if len(snapshots) == 1:
                # Only 1 snapshot exists: newly tracked
                results[repo.id] = {
                    "stars_gained": 0,
                    "is_new": True,
                    "previous_stars": None,
                    "current_stars": current_stars,
                }
                continue

            # Compare against earliest snapshot within the window, or the one immediately prior to latest
            baseline = snapshots[0]
            for s in snapshots[:-1]:
                if s["captured_at"] >= cutoff:
                    baseline = s
                    break
            else:
                baseline = snapshots[-2]

            stars_gained = max(0, current_stars - baseline["stars"])

            results[repo.id] = {
                "stars_gained": stars_gained,
                "is_new": False,
                "previous_stars": baseline["stars"],
                "current_stars": current_stars,
            }

    return results


def get_rising_stars(
    db_path: Path,
    repositories: list[Repository],
    limit: int = 5,
    days: int = 7,
) -> list[dict[str, Any]]:
    """Return top repositories exhibiting strong star growth velocity or notable new discoveries."""
    velocities = calculate_star_velocities(db_path, repositories, days=days)

    enriched: list[dict[str, Any]] = []
    for repo in repositories:
        v = velocities.get(repo.id, {"stars_gained": 0, "is_new": True})
        enriched.append(
            {
                "repository": repo,
                "stars_gained": v["stars_gained"],
                "is_new": v["is_new"],
                "quality_score": repo.quality_score,
            }
        )

    # Sort primarily by stars_gained, secondary by quality_score
    enriched.sort(
        key=lambda item: (
            item["stars_gained"],
            item["quality_score"],
            item["repository"].stars,
        ),
        reverse=True,
    )

    return enriched[:limit]
