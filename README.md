# PR Review Bot

A Python GitHub App that automatically reviews pull requests using **Google Gemini (free tier)** and posts a score (0-100) with a PASS/FAIL verdict. Each branch can have custom review instructions that guide the AI reviewer.

## Features

- 🔔 Webhook-based automatic PR reviews on `opened`, `synchronize`, and `reopened` events
- 🤖 AI-powered review using Google Gemini (free — no credit card needed)
- 📊 Score 0-100 with PASS/FAIL threshold (configurable, default 70)
- 📝 Structured review with category breakdowns (bugs, security, performance, maintainability)
- 🌿 Branch-specific review instructions
- 🖥️ Web dashboard to manage repositories, branches, and instructions
- 🔐 HMAC-SHA256 webhook signature verification + Basic-auth protected dashboard
- 💾 Idempotent event processing (no duplicate reviews)

## Architecture

```
GitHub PR event → Webhook (FastAPI) → Verify signature → Fetch diff
  → Load branch instructions from DB → Send to Gemini → Parse JSON review
  → Compute score → Post PR comment → Store in review history
```

## Tech Stack

| Component | Technology |
|---|---|
| Framework | FastAPI + Uvicorn |
| GitHub SDK | PyGithub |
| Database | SQLite (SQLAlchemy ORM) |
| AI | Google Gemini `gemini-3.5-flash-lite` (free tier) |

## Prerequisites

- Python 3.11+ with [pyenv](https://github.com/pyenv/pyenv) + [pyenv-virtualenv](https://github.com/pyenv/pyenv-virtualenv)
- A free [Google Gemini API key](https://aistudio.google.com/apikey)
- A GitHub App with webhook configured (see below)
- [ngrok](https://ngrok.com/) or similar tunnel for local development

## Setup

### 1. Create the GitHub App

1. Go to **GitHub → Settings → Developer settings → GitHub Apps → New GitHub App**
2. **GitHub App name:** `pr-review-bot`
3. **Webhook URL:** `https://<your-ngrok-url>/webhooks/github`
4. **Webhook secret:** generate one (`openssl rand -hex 16`)
5. **Permissions:**
   - **Pull requests:** Read & write
   - **Contents:** Read only
6. **Subscribe to events:**
   - ✅ Pull requests
7. Click **Create GitHub App**
8. Download the **private key** (`*.pem` file) and note the **App ID**
9. **Install the app** on the repos you want to review (Settings → Install App → select repos)

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY_PATH=/path/to/private-key.pem
GITHUB_WEBHOOK_SECRET=your-random-hex-secret

# Free key from https://aistudio.google.com/apikey
GEMINI_API_KEY=AIza...
DASHBOARD_USERNAME=admin
DASHBOARD_PASSWORD=change-me
PASS_THRESHOLD=70
```

### 3. Run the app

```bash
# Create the virtual environment with pyenv
pyenv install 3.11.9        # if not already installed
pyenv virtualenv 3.11.9 pr-review-bot
pyenv local pr-review-bot

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn pr_review.main:app --reload --port 8000
```

### 4. Expose to GitHub

In a separate terminal, expose your local server:

```bash
ngrok http 8000
```

Copy the ngrok HTTPS URL and use it as the **Webhook URL** in your GitHub App settings (with `/webhooks/github`).

### 5. Configure repos & branches

1. Open the dashboard: `http://localhost:8000/dashboard` (login with your dashboard credentials)
2. Add a repository (owner, repo name, and the GitHub App **installation ID**)
3. Add branch instructions — e.g. for `main`:
   ```
   - Enforce TypeScript strict mode
   - No inline SQL — use the repository layer
   - Every endpoint needs unit tests
   - Check for missing error handling
   ```

### 6. Open a PR — automatic review starts

The bot posts a comment like:

---

## AI Code Review — ✅ PASS

**Score: 82/100** (threshold: 70)

Solid implementation with clean separation of concerns...

### Category Breakdown
- 🐛 **Bugs** — 22/25
- 🔒 **Security** — 20/25
- ⚡ **Performance** — 21/25
- 🔧 **Maintainability** — 19/25

### Suggestions
1. Add input validation on user-provided IDs
2. Extract the duplicate retry logic into a shared helper

---

## Finding the Installation ID

The installation ID is not your App ID. To find it:

1. Go to your GitHub App settings → **Install App**
2. Click the installation URL and inspect the URL: `https://github.com/apps/pr-review-bot/installations/1234567` — the number is the installation ID
3. Or call `GET https://api.github.com/app/installations` with a JWT (see PyGithub docs), or simply check the webhook payloads in GitHub's **Advanced** tab (they contain `installation.id`)

## API Endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/webhooks/github` | GitHub webhook receiver |
| GET | `/health` | Health check |
| GET | `/dashboard` | Dashboard (Basic auth) |
| POST | `/dashboard/repos` | Add repository |
| GET | `/dashboard/repos/{id}` | Repo detail + branch config |
| POST | `/dashboard/repos/{id}/branches` | Add/update branch instructions |

## Development

```bash
pip install -r requirements-dev.txt
pytest
ruff check .
```

## Deployment

### Docker

```bash
cp .env .env
cp private-key.pem ./private-key.pem   # must match GITHUB_APP_PRIVATE_KEY_PATH
docker compose up -d
```

### Production notes

- Set `PASS_THRESHOLD` in `.env`
- Protect the dashboard with strong credentials (or put it behind a reverse proxy with auth)
- Swapping SQLite for PostgreSQL is a connection-string change via `DATABASE_URL`
- The app processes events with a background task; for high traffic use Celery or a queue

## License

MIT