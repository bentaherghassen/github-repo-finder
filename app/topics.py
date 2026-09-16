from pathlib import Path


def load_topics(path: Path) -> list[str]:
    """Load unique topics from a UTF-8 text file."""

    if not path.exists():
        raise FileNotFoundError(f"Topics file not found: {path}")

    topics: list[str] = []
    seen: set[str] = set()

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        topic = raw_line.strip()

        if not topic or topic.startswith("#"):
            continue

        normalized = topic.casefold()

        if normalized in seen:
            continue

        seen.add(normalized)
        topics.append(topic)

    if not topics:
        raise ValueError(f"No topics found in: {path}")

    return topics
