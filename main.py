import asyncio
import logging

from app.config import BASE_DIR, get_settings
from app.database import (
    calculate_star_velocities,
    get_rising_stars,
    init_db,
    record_snapshots,
)
from app.email_sender import send_report_email
from app.github_client import GitHubAPIError, GitHubRateLimitError, GitHubClient
from app.models import Repository
from app.ranking import rank_repositories
from app.reports import write_markdown_report
from app.storage import save_json
from app.topics import load_topics


def configure_logging(level: str) -> None:
    """Configure application logging."""

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


async def run() -> None:
    """Execute the repository discovery workflow."""

    settings = get_settings()
    configure_logging(settings.log_level)

    logger = logging.getLogger(__name__)

    topics_path = BASE_DIR / "config" / "topics.txt"
    topics = load_topics(topics_path)

    logger.info("Loaded %d topics.", len(topics))

    repositories_by_id: dict[int, Repository] = {}

    async with GitHubClient(settings) as github:
        for idx, topic in enumerate(topics):
            logger.info("Searching GitHub for topic: %s", topic)

            try:
                items = await github.search_repositories(
                    topic,
                    per_page=settings.results_per_topic,
                )
            except GitHubRateLimitError as exc:
                logger.error(
                    "GitHub rate limit reached: %s. Stopping discovery loop to avoid hammering "
                    "GitHub and comply with GitHub's API terms.",
                    exc,
                )
                break
            except GitHubAPIError:
                logger.exception(
                    "GitHub search failed for topic: %s",
                    topic,
                )
                continue

            for item in items:
                try:
                    repo = Repository.from_github(
                        item,
                        matched_topic=topic,
                    )
                except (KeyError, TypeError, ValueError):
                    logger.warning(
                        "Skipping malformed repository returned for %s.",
                        topic,
                    )
                    continue

                existing = repositories_by_id.get(repo.id)

                if existing is None:
                    repositories_by_id[repo.id] = repo
                    continue

                known_topics = {
                    value.casefold()
                    for value in existing.matched_topics
                }

                if topic.casefold() not in known_topics:
                    existing.matched_topics.append(topic)

            # Pace consecutive requests to prevent secondary rate limits
            if idx < len(topics) - 1 and settings.request_delay > 0:
                await asyncio.sleep(settings.request_delay)

    repositories = rank_repositories(
        list(repositories_by_id.values())
    )

    db_path = BASE_DIR / "data" / "history.db"
    init_db(db_path)

    velocities = {}
    rising_stars = []

    if repositories:
        record_snapshots(db_path, repositories)
        velocities = calculate_star_velocities(db_path, repositories)
        rising_stars = get_rising_stars(db_path, repositories, limit=5)
        logger.info("Recorded %d snapshots to SQLite database.", len(repositories))
        if rising_stars:
            logger.info("Identified %d rising stars and notable discoveries.", len(rising_stars))

    json_path = BASE_DIR / "data" / "repositories.json"
    report_path = BASE_DIR / "reports" / "latest.md"

    save_json(
        repositories,
        json_path,
    )

    write_markdown_report(
        repositories,
        topics,
        report_path,
        top_n=settings.report_top_n,
        velocities=velocities,
        rising_stars=rising_stars,
    )

    logger.info(
        "Finished. Saved %d unique repositories.",
        len(repositories),
    )
    logger.info("JSON: %s", json_path)
    logger.info("Report: %s", report_path)
    logger.info("SQLite Database: %s", db_path)

    await send_report_email(
        settings,
        repositories,
        report_path,
        json_path,
        rising_stars=rising_stars,
    )


if __name__ == "__main__":
    asyncio.run(run())
