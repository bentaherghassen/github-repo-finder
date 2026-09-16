from unittest.mock import AsyncMock, patch
import pytest

from app.config import Settings
from app.github_client import GitHubRateLimitError, RateLimitInfo
import main


@pytest.mark.anyio
async def test_main_run_halts_on_rate_limit_error() -> None:
    # 3 topics
    mock_topics = ["topic1", "topic2", "topic3"]

    rate_err = GitHubRateLimitError(
        "Rate limit exceeded",
        status_code=429,
        rate_limit_info=RateLimitInfo(retry_after=60.0),
        wait_seconds=60.0,
    )

    searched_topics = []

    async def mock_search(topic: str, *, per_page: int):
        searched_topics.append(topic)
        if topic == "topic1":
            return [
                {
                    "id": 1,
                    "name": "repo1",
                    "full_name": "owner/repo1",
                    "owner": {"login": "owner"},
                    "html_url": "https://github.com/owner/repo1",
                    "stargazers_count": 100,
                    "forks_count": 10,
                    "open_issues_count": 2,
                    "score": 5.0,
                }
            ]
        elif topic == "topic2":
            raise rate_err
        return []

    mock_client = AsyncMock()
    mock_client.search_repositories.side_effect = mock_search
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    test_settings = Settings(request_delay=0.0)

    with (
        patch("main.get_settings", return_value=test_settings),
        patch("main.load_topics", return_value=mock_topics),
        patch("main.GitHubClient", return_value=mock_client),
        patch("main.save_json") as mock_save_json,
        patch("main.write_markdown_report") as mock_write_report,
        patch("main.send_report_email", new_callable=AsyncMock) as mock_send_email,
    ):
        await main.run()

        # It queried topic1 (succeeded), topic2 (hit rate limit and halted)
        # It must NOT query topic3!
        assert searched_topics == ["topic1", "topic2"]
        assert "topic3" not in searched_topics

        # It still saved the report and JSON with data retrieved so far
        mock_save_json.assert_called_once()
        mock_write_report.assert_called_once()
        mock_send_email.assert_called_once()

        # Check repository from topic1 was ranked and saved
        repos_saved = mock_save_json.call_args[0][0]
        assert len(repos_saved) == 1
        assert repos_saved[0].name == "repo1"
