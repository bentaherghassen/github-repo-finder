from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Repository


def write_markdown_report(
    repositories: list[Repository],
    topics: list[str],
    path: Path,
    *,
    top_n: int,
    velocities: dict[int, dict[str, Any]] | None = None,
    rising_stars: list[dict[str, Any]] | None = None,
) -> None:
    """Create a readable Markdown report grouped by topic with rising stars spotlight."""

    path.parent.mkdir(parents=True, exist_ok=True)
    velocities = velocities or {}

    grouped: dict[str, list[Repository]] = defaultdict(list)

    for repository in repositories:
        for topic in repository.matched_topics:
            grouped[topic].append(repository)

    lines = [
        "# GitHub Repository Finder Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        (
            "Repositories are ranked using a heuristic that combines "
            "popularity, community adoption, recent activity, and "
            "GitHub search relevance."
        ),
        "",
    ]

    # Add Rising Stars & Fast Movers spotlight section if available
    if rising_stars:
        lines.extend(
            [
                "## 🌟 Rising Stars & Fast Movers",
                "",
                "Repositories showing notable star velocity or newly discovered momentum:",
                "",
                "| # | Repository | Star Growth | Total Stars | Quality Score | Topics |",
                "|---|---|---:|---:|---:|---|",
            ]
        )

        for idx, item in enumerate(rising_stars, 1):
            repo = item["repository"]
            growth = item.get("stars_gained", 0)
            is_new = item.get("is_new", False)

            if growth > 0:
                growth_badge = f"**+{growth:,} ⭐**"
            elif is_new:
                growth_badge = "*✨ New*"
            else:
                growth_badge = "Steady"

            topics_str = ", ".join(repo.matched_topics) or "N/A"
            lines.append(
                f"| {idx} | [{repo.full_name}]({repo.html_url}) | "
                f"{growth_badge} | {repo.stars:,} | {repo.quality_score:.1f} | {topics_str} |"
            )

        lines.append("")

    # Topic breakdown
    for topic in topics:
        lines.extend(
            [
                f"## {topic}",
                "",
            ]
        )

        ranked = sorted(
            grouped.get(topic, []),
            key=lambda repo: (
                repo.quality_score,
                repo.stars,
            ),
            reverse=True,
        )[:top_n]

        if not ranked:
            lines.extend(
                [
                    "No repositories found.",
                    "",
                ]
            )
            continue

        for index, repo in enumerate(ranked, start=1):
            vel_info = velocities.get(repo.id)
            growth_line = ""
            if vel_info:
                gained = vel_info.get("stars_gained", 0)
                if gained > 0:
                    growth_line = f"- **Star velocity:** +{gained:,} stars\n"
                elif vel_info.get("is_new"):
                    growth_line = "- **Status:** ✨ Newly tracked in this run\n"

            lines.extend(
                [
                    f"### {index}. [{repo.full_name}]({repo.html_url})",
                    "",
                    f"- **Quality score:** {repo.quality_score}",
                    f"- **Stars:** {repo.stars:,}",
                    growth_line.rstrip() if growth_line else "",
                    f"- **Forks:** {repo.forks:,}",
                    f"- **Language:** {repo.language or 'Not specified'}",
                    f"- **Open issues:** {repo.open_issues:,}",
                    (
                        "- **Last push:** "
                        f"{repo.pushed_at.isoformat() if repo.pushed_at else 'Unknown'}"
                    ),
                    f"- **Description:** {repo.description or 'No description'}",
                    "",
                ]
            )
            # Remove any empty strings from optional growth_line
            lines = [line for line in lines if line != ""]
            lines.append("")

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )
