import json
from pathlib import Path

from .models import Repository


def save_json(
    repositories: list[Repository],
    path: Path,
) -> None:
    """Save normalized repository data to JSON."""

    path.parent.mkdir(parents=True, exist_ok=True)

    payload = [
        repository.model_dump(mode="json")
        for repository in repositories
    ]

    path.write_text(
        json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
