

# SignalOS

SignalOS is a personal intelligence system that collects high-signal AI, technology, business, and education news, filters and ranks it using GPT, and turns it into four actionable daily signals.

The signals are delivered through Discord and displayed in a FastAPI dashboard with feedback controls, persistent article history, and weekly intelligence reports.

The goal is not to create another generic news summariser. SignalOS is designed for student-builders, programmers, and early-stage founders who need to know which developments actually matter for their projects, skills, and opportunities.

## What it does

SignalOS runs automatically in the cloud and performs the full pipeline:

```text
RSS feeds
→ article normalisation
→ freshness filtering
→ deduplication
→ source-balanced candidate selection
→ User profile + current focus
→ GPT strategic ranking
→ four actionable signals
→ Discord delivery
→ FastAPI dashboard
→ feedback and weekly intelligence
```

## Current features

- Fetches articles from selected AI, technology, business, and education RSS feeds
- Filters stale articles and previously seen stories
- Deduplicates articles using stable fingerprints and normalised metadata
- Applies source-balanced candidate preselection
- Caps ranking input to control API cost
- Uses GPT to rank articles by relevance, quality, importance, and actionability
- Maps model-returned indexes back to original trusted article objects
- Produces four daily strategic signals
- Generates reasons and concrete action takeaways
- Delivers signals through Discord
- Displays intelligence in a FastAPI dashboard
- Stores article feedback
- Customises ranking with a local intelligence profile and temporary focus
- Generates weekly intelligence reports
- Uses atomic JSON writes, locking, backups, and corruption detection
- Runs daily and weekly workflows with GitHub Actions
- Includes a deterministic no-secrets Demo Mode for reviewers

### Custom Intelligence Profile

The dashboard profile editor lets one local user customise their role, goals, active projects, preferred and excluded topics, briefing style, and current focus. The validated profile is stored in `.signalos_state/profile.json` and is added to future ranking prompts as context; it does not change article fetching or trusted article metadata.

The current focus is a temporary steering field for redirecting the next briefing toward a specific product, technical, or learning priority. It remains in effect until it is edited or cleared. The feature is intentionally local-first and single-user, with no accounts, database, or secret values in the profile.

## Tech stack

- Python 3.11+
- FastAPI
- Uvicorn
- OpenAI API
- GPT-5.6
- RSS feeds via `feedparser`
- Discord webhooks
- Vanilla JavaScript
- HTML and CSS
- GitHub Actions
- JSON state storage
- File locking and atomic writes
- Markdown reporting

## Project structure

```text
SignalOS/
├── .github/
│   └── workflows/
│       ├── morning.yml
│       └── weekly.yml
├── demo_data/
│   ├── article_history.json
│   ├── feedback.json
│   └── weekly_report.md
├── scripts/
│   └── load_demo_data.py
├── src/
│   ├── config.py
│   ├── delivery.py
│   ├── digest.py
│   ├── main.py
│   ├── models.py
│   ├── news_fetcher.py
│   ├── ranker.py
│   ├── state_store.py
│   ├── web_app.py
│   └── weekly_summary.py
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

## How it works

### 1. Article collection

SignalOS fetches recent articles from a curated set of RSS feeds focused on AI and technology.

### 2. Freshness filtering

Articles are filtered so the digest prefers genuinely recent stories instead of old RSS items that remain near the top of a feed.

### 3. Repeat prevention

Each selected article is converted into a stable fingerprint based on its title and URL. SignalOS stores those fingerprints in a lightweight state file so the same story is not repeatedly sent across different days.

### 4. AI ranking

Candidate articles are passed to an OpenAI model, which ranks them using:

- Relevance to the user profile
- Article quality
- Strategic importance
- Practical actionability

### 5. Digest generation

The selected articles are formatted into a Markdown digest with reasoning and action takeaways.

### 6. Discord delivery

The digest is sent to Discord using a webhook. Long digests are split into multiple Discord-safe chunks instead of being silently cut off.

## Demo Mode

Demo Mode gives reviewers and OpenAI Build Week judges a deterministic SignalOS dashboard without requiring API keys, Discord credentials, RSS fetching, or paid model calls. It uses clearly synthetic sample articles, feedback, a matching intelligence profile, and a weekly report; it does not run the daily pipeline.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 scripts/load_demo_data.py
uvicorn src.web_app:app --reload
```

Then open `http://127.0.0.1:8000` in a browser. The dashboard will show four demo signals, two existing ratings, two unrated signals for testing the feedback controls, a synthetic custom profile, and a weekly intelligence report.

The loader refuses to overwrite existing runtime files. To intentionally replace them with the synthetic fixtures, run:

```bash
python3 scripts/load_demo_data.py --force
```

Demo Mode makes no network or API calls, needs no secrets, and is intended only as a safe reviewer experience.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/on9kitkit/SignalOS.git
cd SignalOS
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create a `.env` file

Copy the example file:

```bash
cp .env.example .env
```

Then add your own values:

```env
OPENAI_API_KEY=your_openai_api_key_here
DISCORD_WEBHOOK_URL=your_discord_webhook_url_here
```

Never commit `.env` to GitHub.

### 5. Run locally

```bash
python -m src.main
```

If everything is configured correctly, SignalOS will print the digest locally and send it to Discord.

## Tests

```bash
python3 -m pytest
```

## GitHub Actions automation

SignalOS is designed to run automatically through GitHub Actions.

The workflow:

- Checks out the repository
- Installs Python dependencies
- Restores seen-article history from cache
- Runs the agent
- Sends the digest to Discord
- Saves updated seen-article history for future runs

Required GitHub Secrets:

```text
OPENAI_API_KEY
DISCORD_WEBHOOK_URL
```

## Security notes

This repository should not contain secrets. API keys and webhooks are loaded from environment variables or GitHub Secrets.

Ignored local files include:

```text
.env
.venv/
__pycache__/
digests/
.signalos_state/
```

## OpenAI Build Week development

SignalOS existed before OpenAI Build Week as an early command-line and Discord intelligence prototype.

During Build Week, it was meaningfully extended with:

- a FastAPI intelligence dashboard
- weekly intelligence reports
- persistent article feedback
- a local custom intelligence profile and temporary briefing focus
- progressive-enhancement JavaScript interactions
- source-balanced candidate preselection
- ranking token and cost controls
- configurable model selection
- GitHub Actions concurrency safeguards
- sanitised delivery failures
- atomic and locked JSON state storage
- a deterministic reviewer Demo Mode
- repository-wide security and reliability auditing with Codex

The dated Git history and Codex sessions document these additions.

## Roadmap

Planned upgrades:

- Use explicit feedback signals in future ranking
- Add editable and undoable feedback
- Add saved build ideas
- Add dashboard search and filtering
- Add trend detection across multiple weeks
- Add semantic article similarity
- Add authentication and database-backed multi-user storage
- Benchmark local inference workflows on Apple Silicon
- Turn SignalOS into a focused personal-intelligence SaaS

## Why this project exists

Most news feeds create noise. SignalOS is built to create leverage.

The long-term vision is a personalised intelligence system that helps ambitious builders notice important shifts early, connect them to their own projects, and convert information into action.
