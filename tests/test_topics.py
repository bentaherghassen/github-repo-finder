from pathlib import Path

from app.topics import load_topics


def test_load_topics_ignores_comments_blanks_and_duplicates(
    tmp_path: Path,
) -> None:
    path = tmp_path / "topics.txt"

    path.write_text(
        "# comment\n"
        "Django\n"
        "\n"
        "FastAPI\n"
        "django\n",
        encoding="utf-8",
    )

    assert load_topics(path) == [
        "Django",
        "FastAPI",
    ]
