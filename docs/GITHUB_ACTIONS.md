# GitHub Actions Automation Guide

This project includes automated CI/CD and scheduled execution workflows powered by GitHub Actions.

---

## 1. Daily Discovery Digest Workflow (`daily_digest.yml`)

The daily digest workflow runs autonomously in the cloud to:
1. Check out the latest code and install dependencies.
2. Run unit tests to ensure stability.
3. Execute `python main.py` with full rate-limit compliance and pacing.
4. Deliver the formatted discovery report and JSON data to your Gmail inbox.
5. Commit and push the updated `reports/latest.md` and `data/repositories.json` back to the repository.
6. Upload the reports as downloadable GitHub Action artifacts (retained for 30 days).

### Triggering
- **Automatic Schedule**: Runs every morning at **08:00 UTC** (configurable via the cron expression in `.github/workflows/daily_digest.yml`).
- **Manual Trigger**:
  1. Go to your GitHub repository in your browser.
  2. Click the **Actions** tab.
  3. Select **"Daily Repository Discovery Digest"** in the left sidebar.
  4. Click **Run workflow**, choose options (e.g. deliver email `true`/`false`), and click **Run workflow**.

---

## 2. Required GitHub Repository Secrets

To enable automated email delivery and authenticated GitHub searches, add these secrets to your repository:

1. Go to your GitHub repository:
   ```text
   Settings → Secrets and variables → Actions → Repository secrets
   ```
2. Click **New repository secret** and add the following:

| Secret Name | Description | Example / Note |
|---|---|---|
| `GMAIL_USER` | Your Gmail address | `yourname@gmail.com` |
| `GMAIL_APP_PASSWORD` | 16-character Google App Password | `abcd efgh ijkl mnop` (see [GMAIL_SETUP.md](GMAIL_SETUP.md)) |
| `EMAIL_RECIPIENT` | Email address where reports will be delivered | `recipient@example.com` |
| `GH_PAT` *(Optional)* | Fine-grained GitHub Personal Access Token | Grants 5,000 req/hr instead of standard GITHUB_TOKEN |

> [!NOTE]
> If `GH_PAT` is not provided, the workflow automatically falls back to GitHub Actions' built-in `GITHUB_TOKEN`.

---

## 3. Workflow Permissions for Committing Reports

For the workflow to push updated `reports/latest.md` and `data/repositories.json` back to your repo:

1. Go to your repository **Settings**.
2. Under the **Code and automation** section, click **Actions** → **General**.
3. Scroll down to **Workflow permissions**.
4. Select **"Read and write permissions"**.
5. Click **Save**.

---

## 4. Continuous Integration Workflow (`ci.yml`)

Runs automatically on every `push` and `pull_request` targeting the `main` branch to execute the test suite across Python 3.11 and Python 3.12, ensuring no regressions are introduced.
