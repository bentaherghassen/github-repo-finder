# GitHub Repository Finder

A modern Python workflow that finds and ranks top GitHub repositories for a configurable list of topics.

## Features

- Reads topics from a text file
- Uses GitHub's official REST API
- Async HTTP requests with `httpx`
- GitHub token support through `.env`
- Rate-limit compliance: respects `403`/`429`, reads `Retry-After` and `X-RateLimit-Reset`
- Header-based waiting instead of blind retrying or hammering GitHub
- Configurable request pacing delay to prevent secondary rate limits
- Gmail/Google App Password authentication for email report delivery
- Retry handling for network and timeout failures
- Transparent repository quality scoring
- Deduplication across topics
- JSON output for automation
- Markdown report for humans
- Logging
- Type hints
- Unit tests
- Clear project structure

## Requirements

- Python 3.11+
- GitHub account
- GitHub personal access token recommended

## Quick start

### 1. Create a virtual environment

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure GitHub authentication

Copy:

```text
.env.example
```

to:

```text
.env
```

Then edit `.env`:

```env
GITHUB_TOKEN=your_token_here
```

See:

```text
docs/GITHUB_API.md
```

for a full step-by-step guide.

### 4. Add your topics

Edit:

```text
config/topics.txt
```

Example:

```text
Django
FastAPI
React accessibility
AI agents
Python automation
Docker
PostgreSQL
```

### 5. Run

```bash
python main.py
```

Outputs:

```text
data/repositories.json
reports/latest.md
```

## How ranking works

GitHub stars alone do not always identify the most useful repository.

This project combines:

- Stars
- Forks
- Recent activity
- GitHub search relevance
- Archive/fork penalties

The calculation is intentionally transparent and lives in:

```text
app/ranking.py
```

You can change the weights there.

## Project structure

```text
github_repo_finder/
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── daily_digest.yml
├── app/
│   ├── __init__.py
│   ├── config.py
│   ├── email_sender.py
│   ├── github_client.py
│   ├── models.py
│   ├── ranking.py
│   ├── reports.py
│   ├── storage.py
│   └── topics.py
├── config/
│   └── topics.txt
├── data/
│   └── .gitkeep
├── docs/
│   ├── GITHUB_ACTIONS.md
│   ├── GITHUB_API.md
│   └── GMAIL_SETUP.md
├── reports/
│   └── .gitkeep
├── tests/
│   ├── test_email_sender.py
│   ├── test_github_rate_limit.py
│   ├── test_ranking.py
│   ├── test_rate_limit_workflow.py
│   └── test_topics.py
├── .env.example
├── .gitignore
├── main.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Configuration

| Variable | Default | Meaning |
|---|---:|---|
| `GITHUB_TOKEN` | empty | GitHub personal access token |
| `GITHUB_API_URL` | `https://api.github.com` | REST API base URL |
| `GITHUB_API_VERSION` | `2022-11-28` | GitHub API version |
| `RESULTS_PER_TOPIC` | `10` | Results fetched for each topic |
| `REPORT_TOP_N` | `5` | Repositories included per topic |
| `REQUEST_TIMEOUT` | `20` | HTTP timeout (seconds) |
| `REQUEST_DELAY` | `1.0` | Pacing delay between topic requests (seconds) |
| `MAX_RATE_LIMIT_WAIT_SECONDS` | `300.0` | Max wait time when rate-limited before stopping |
| `RATE_LIMIT_MAX_RETRIES` | `2` | Max retry attempts for rate-limited requests |
| `EMAIL_NOTIFICATIONS_ENABLED` | `false` | Deliver report via Gmail when set to `true` |
| `GMAIL_USER` | empty | Gmail address used for sending |
| `GMAIL_APP_PASSWORD` | empty | 16-character Google App Password |
| `EMAIL_RECIPIENT` | empty | Recipient email address for discovery reports |
| `LOG_LEVEL` | `INFO` | Logging level |

## Tests

Install test dependencies:

```bash
pip install pytest
```

Run:

```bash
pytest
```

## Security

Never hard-code your GitHub token.

Do not commit `.env`.

If a token becomes public, revoke it immediately and create a new one.

## Ideas for extending the workflow

- GitHub Actions scheduled runs
- SQLite repository history
- CSV output
- Email reports
- Telegram notifications
- RSS feeds
- Language filters
- Minimum stars
- Repository age filters
- README analysis
- AI summaries
- Web dashboard
