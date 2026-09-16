# How to Get a GitHub API Token

This workflow uses GitHub's official REST API.

GitHub allows some public API requests without authentication, but authenticated requests have more useful rate limits and are recommended for automated workflows.

## Recommended token type

For personal projects, use a **fine-grained personal access token** when possible.

GitHub documentation:

https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens

## Step 1: Sign in to GitHub

Open:

https://github.com

and sign in.

## Step 2: Open developer settings

Go to:

```text
Profile picture
→ Settings
→ Developer settings
→ Personal access tokens
→ Fine-grained tokens
```

You can also search GitHub settings for:

```text
Personal access tokens
```

## Step 3: Create a new token

Choose:

```text
Generate new token
```

Use a descriptive token name, for example:

```text
github-repo-finder
```

Choose an expiration date.

Shorter expiration periods are safer than permanent credentials.

## Step 4: Choose repository access

This project searches public GitHub repositories.

You should grant only the minimum permissions necessary.

Avoid giving the token:

- write access
- administration permissions
- access to private repositories

unless you specifically extend the project later and genuinely need those permissions.

## Step 5: Generate the token

Create the token.

GitHub may only show the full token once.

Copy it immediately and store it securely.

Treat it like a password.

Never:

- commit it to Git
- paste it into Python source files
- include it in screenshots
- add it to README files
- publish it online

## Step 6: Create your `.env` file

The project contains:

```text
.env.example
```

Copy it.

Windows:

```powershell
Copy-Item .env.example .env
```

Command Prompt:

```cmd
copy .env.example .env
```

macOS/Linux:

```bash
cp .env.example .env
```

## Step 7: Add the token

Open `.env` and replace:

```env
GITHUB_TOKEN=
```

with:

```env
GITHUB_TOKEN=your_actual_github_token
```

For example:

```env
GITHUB_TOKEN=github_pat_xxxxxxxxxxxxxxxxx
```

Do not use the example above as a real token.

## Step 8: Run the workflow

```bash
python main.py
```

If authentication and networking work correctly, the program will query GitHub and create:

```text
data/repositories.json
reports/latest.md
```

## API endpoint used

The program calls:

```text
GET /search/repositories
```

against:

```text
https://api.github.com
```

Conceptually, a topic such as:

```text
FastAPI
```

becomes a repository search request similar to:

```text
q=FastAPI
sort=stars
order=desc
```

## Authentication header

The workflow sends the token through an HTTP header:

```text
Authorization: Bearer YOUR_TOKEN
```

The token never needs to be added to the URL.

## API version header

GitHub's REST API supports version headers.

The project uses:

```text
X-GitHub-Api-Version
```

and allows the version to be changed through `.env`:

```env
GITHUB_API_VERSION=2022-11-28
```

## Common errors

### 401 Unauthorized

Usually means:

- token is invalid
- token expired
- `.env` was not loaded
- token was copied incorrectly

Check:

```env
GITHUB_TOKEN=...
```

### 403 Forbidden & 429 Too Many Requests (Rate Limits)

GitHub enforces two types of rate limits:

1. **Primary Rate Limits**:
   - Limit is per hour (e.g., 60 req/hour unauthenticated, 5,000 req/hour authenticated).
   - Search API has dedicated lower limits (10 req/min unauthenticated, 30 req/min authenticated).
   - When exceeded, GitHub returns HTTP `403` or `429` with `X-RateLimit-Remaining: 0`.
   - The `X-RateLimit-Reset` header indicates the UTC epoch timestamp when the window resets.

2. **Secondary Rate Limits**:
   - Triggered by rapid bursts, excessive concurrent requests, or high-volume queries.
   - GitHub returns HTTP `403` or `429` with an error message in the body and a `Retry-After` header.
   - The `Retry-After` header specifies the exact number of seconds to wait before retrying.
   - If `Retry-After` is omitted, official GitHub guidance instructs clients to wait at least 60 seconds.

### Rate Limit Compliance & Client Behavior

Continuing to send requests when rate limited violates GitHub's API terms and can lead to token or IP banning.

This project implements strict compliance:
- **Header-Based Waiting**: If rate-limited and the required wait is within `MAX_RATE_LIMIT_WAIT_SECONDS` (default: 300s), the client waits the specified time before retrying.
- **Circuit Breaker**: If the required wait exceeds `MAX_RATE_LIMIT_WAIT_SECONDS` or retries are exhausted, the client **stops** immediately rather than repeatedly hammering GitHub.
- **Request Pacing**: The `REQUEST_DELAY` setting (default: 1.0s) paces queries to avoid triggering secondary rate limits.

### 422 Validation Failed

GitHub rejected the search query.

Try using a simpler topic.

For example:

```text
Python automation
```

instead of a very long natural-language sentence.

### No repositories found

Try a broader search topic.

For example:

```text
FastAPI
```

instead of:

```text
high performance asynchronous Python API architecture example
```

## What if my token leaks?

Immediately revoke it.

Go to GitHub settings:

```text
Developer settings
→ Personal access tokens
```

Revoke the exposed token and generate a new one.

Deleting the token from your current source code is not enough if it has already been committed or published.

## Security recommendations

- Keep `.env` in `.gitignore`
- Use minimum permissions
- Use token expiration
- Rotate credentials periodically
- Never log the token
- Never include credentials in exception messages
