

# SignalOS

SignalOS is an autonomous AI intelligence agent that collects high-signal AI, technology, and builder-relevant news, ranks it using an LLM, filters stale or repeated stories, and delivers a concise daily digest to Discord.

The goal is not to create another generic news summariser. SignalOS is designed as a personalised intelligence layer for student-builders, programmers, and early-stage founders who want to know which developments actually matter for their projects, skills, and opportunities.

## What it does

SignalOS runs automatically in the cloud and performs the full pipeline:

```text
RSS feeds
→ article collection
→ freshness filtering
→ repeat prevention
→ GPT-based ranking
→ source diversity filtering
→ Markdown digest generation
→ Discord delivery
```

## Current features

- Fetches articles from selected AI and technology RSS feeds
- Uses an OpenAI model to rank articles by relevance, quality, and importance
- Filters for fresh articles from the last few days
- Prevents repeated articles across different runs using article fingerprints
- Applies source diversity so the digest is not dominated by one publication
- Generates a clean Markdown digest
- Sends the digest to Discord using a webhook
- Runs automatically using GitHub Actions
- Stores lightweight seen-article memory using GitHub Actions cache

## Tech stack

- Python 3.11+
- OpenAI API
- RSS feeds via `feedparser`
- Discord webhooks
- GitHub Actions
- GitHub Actions cache
- Markdown output

## Project structure

```text
SignalOS/
├── .github/
│   └── workflows/
│       └── morning.yml
├── src/
│   ├── config.py
│   ├── delivery.py
│   ├── digest.py
│   ├── main.py
│   ├── models.py
│   ├── news_fetcher.py
│   └── ranker.py
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

## Roadmap

Planned upgrades:

- Add more high-quality RSS sources
- Add stronger article deduplication using semantic similarity
- Add weekly intelligence summaries
- Add user feedback scoring
- Add trend detection across multiple days
- Add a lightweight web dashboard
- Support multiple user profiles
- Turn the engine into a micro-SaaS prototype

## Why this project exists

Most news feeds create noise. SignalOS is built to create leverage.

The long-term vision is a personalised intelligence system that helps ambitious builders notice important shifts early, connect them to their own projects, and convert information into action.