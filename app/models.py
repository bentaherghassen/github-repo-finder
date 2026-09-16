from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Repository(BaseModel):
    """Normalized GitHub repository data used by the application."""

    model_config = ConfigDict(extra="ignore")

    id: int
    full_name: str
    name: str
    owner: str
    description: str | None = None
    html_url: str
    language: str | None = None

    stars: int = 0
    forks: int = 0
    open_issues: int = 0

    topics: list[str] = Field(default_factory=list)

    created_at: datetime | None = None
    updated_at: datetime | None = None
    pushed_at: datetime | None = None

    default_branch: str | None = None

    archived: bool = False
    fork: bool = False

    search_score: float = 0.0
    matched_topics: list[str] = Field(default_factory=list)
    quality_score: float = 0.0

    @classmethod
    def from_github(cls, item: dict, matched_topic: str) -> "Repository":
        """Convert a GitHub repository API response into our model."""
        return cls(
            id=item["id"],
            full_name=item["full_name"],
            name=item["name"],
            owner=item["owner"]["login"],
            description=item.get("description"),
            html_url=item["html_url"],
            language=item.get("language"),
            stars=item.get("stargazers_count", 0),
            forks=item.get("forks_count", 0),
            open_issues=item.get("open_issues_count", 0),
            topics=item.get("topics") or [],
            created_at=item.get("created_at"),
            updated_at=item.get("updated_at"),
            pushed_at=item.get("pushed_at"),
            default_branch=item.get("default_branch"),
            archived=item.get("archived", False),
            fork=item.get("fork", False),
            search_score=item.get("score", 0.0),
            matched_topics=[matched_topic],
        )
