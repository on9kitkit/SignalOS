# SignalOS

SignalOS is a personal intelligence system that converts high-volume AI, technology, business, and education news into four personalised, actionable signals.

**Four signals. Zero noise.**

[Watch the public demo](https://youtu.be/AhzTTNRnJaY) · [Run Demo Mode](#deterministic-demo-mode) · [Quick start](#quick-start) · [Architecture](#how-signalos-works)

## Why SignalOS exists

News feeds create information overload, while generic summaries rarely account for what someone is trying to learn, build, or decide. SignalOS ranks information against the user's goals, active projects, preferred topics, and current focus, then turns the strongest items into concrete next actions.

## Core capabilities

| Area | What is implemented |
| --- | --- |
| Ingestion | Curated RSS feeds spanning AI labs, developer tooling, technology, business, and education |
| Local selection | Freshness and seen-article filtering, URL/title deduplication, and deterministic source-balanced preselection |
| Cost control | No more than 32 candidates reach the ranking model; article summaries and model output are also capped |
| GPT-5.6 ranking | Profile-aware scoring for relevance, quality, importance, and actionability through the OpenAI Responses API |
| Reliability | Trusted article-index mapping attaches model analysis to the original Python `Article` objects |
| Daily output | Four source-diverse signals with a reason and an action takeaway |
| Personalisation | An editable Custom Intelligence Profile plus a temporary current-focus control |
| Experience | FastAPI dashboard, local feedback persistence, Weekly Intelligence, and small vanilla JavaScript interactions |
| Delivery and automation | Discord delivery plus scheduled daily and weekly GitHub Actions workflows |
| Reviewer path | Deterministic synthetic Demo Mode with no OpenAI, Discord, or RSS credentials required |
| Quality | Automated tests for ranking safeguards, state storage, profiles, demo loading, feedback, and dashboard behaviour |

Feedback is stored for future ranking improvements. It is not currently used to retrain the model or automatically change subsequent rankings.

## Public demo

[Watch the SignalOS Build Week demo on YouTube](https://youtu.be/AhzTTNRnJaY).

For hands-on evaluation, [Deterministic Demo Mode](#deterministic-demo-mode) loads a complete local dashboard experience without paid calls or credentials.

## How SignalOS works

```text
RSS feeds
→ freshness and seen-article filtering
→ URL/title deduplication
→ source-balanced candidate selection (maximum 32)
→ Intelligence Profile and current focus
→ GPT-5.6 strategic ranking
→ trusted index mapping
→ four source-diverse actionable signals
→ dashboard, Discord, local feedback state, and Weekly Intelligence
```

The model receives a compact, indexed candidate list and returns analysis tied to candidate indexes. Python validates each index and maps it back to the original trusted object, so model output cannot replace the source title, publisher, or URL.

The daily pipeline saves selected signals to local history. The weekly pipeline analyses the most recent seven days of that history and produces a separate Markdown intelligence report.

## Intelligence Profile

The dashboard editor supports:

- role
- goals
- active projects
- preferred topics
- excluded topics
- briefing style (`concise`, `strategic`, `technical`, or `opportunity-focused`)
- current focus

The validated profile is stored locally in `.signalos_state/profile.json` and supplied as context during ranking. Current focus is a steering field for the next briefings and remains active until edited or cleared; it does not alter article fetching or trusted article metadata.

## Deterministic Demo Mode

This is the fastest path for judges and reviewers. It installs checked-in synthetic fixtures, starts the local dashboard, and does not call OpenAI, Discord, or RSS services.

```bash
git clone https://github.com/on9kitkit/SignalOS.git
cd SignalOS
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 scripts/load_demo_data.py
python3 -m uvicorn src.web_app:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). You should see four synthetic signals, two saved ratings, two unrated signals for testing feedback, a populated Custom Intelligence Profile, and a synthetic Weekly Intelligence report.

The loader protects existing runtime data and refuses to overwrite it. To intentionally replace existing local runtime files with the synthetic fixtures, run:

```bash
python3 scripts/load_demo_data.py --force
```

## Quick start

### Prerequisites

- Python 3.11 or newer
- Git
- OpenAI and Discord credentials for the live daily and weekly pipelines

### Install

```bash
git clone https://github.com/on9kitkit/SignalOS.git
cd SignalOS
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
cp .env.example .env
```

Add your own `OPENAI_API_KEY` and `DISCORD_WEBHOOK_URL` values to the local `.env` file. Never commit that file.

Model selection is optional and can be overridden with `SIGNALOS_RANKER_MODEL` and `SIGNALOS_WEEKLY_MODEL`; both default to `gpt-5.6-luna`.

### Run the live daily pipeline

```bash
python3 -m src.main
```

This fetches RSS articles, prints and saves the daily digest, sends four article messages to Discord, and updates local history.

### Open the dashboard

```bash
python3 -m uvicorn src.web_app:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Run the daily pipeline first to populate live article history, or use Demo Mode for a credential-free preview.

### Generate Weekly Intelligence

```bash
python3 -m src.weekly_summary
```

This requires recent daily article history and the live service credentials.

## Testing

Run the automated suite from the repository root:

```bash
python3 -m pytest
```

Run a syntax compilation check with:

```bash
python3 -m compileall -q src scripts tests
```

The current suite covers the profile model, deterministic demo loader, atomic state storage, ranking safeguards, trusted index mapping, feedback persistence, and dashboard routes.

Current validation: **22 tests passed** on Python 3.11.

## OpenAI Build Week development

SignalOS existed before OpenAI Build Week as an early command-line and Discord intelligence prototype. Repository history shows the Build Week work extending that foundation with:

- the FastAPI dashboard and its editing and feedback interactions
- Custom Intelligence Profiles and profile-aware ranking
- Weekly Intelligence generation and presentation
- trusted candidate-index mapping and ranking reliability improvements
- source-balanced preselection, prompt limits, configurable models, and workflow cost controls
- sanitised delivery failures plus atomic and locked JSON state storage
- deterministic Demo Mode and synthetic reviewer fixtures
- automated tests, repository-wide auditing, and submission documentation

The entire product is not presented as having been created during Build Week; the submission focuses on the substantial intelligence, interface, reliability, testing, and reviewer-experience work added to the original prototype.

## GPT-5.6 and Codex

GPT-5.6 is the runtime intelligence layer. It ranks indexed candidates, produces the strategic reason and action takeaway for each selected signal, adapts ranking to the Intelligence Profile, and synthesises the weekly report from saved daily history. The runtime model names remain configurable so cost and capability can be adjusted without changing Python code.

Codex served as an engineering collaborator for scoped implementation, debugging, repository-wide auditing, testing, UI iteration, reliability work, and documentation support.

Human ownership remains central: the creator defined the product vision, designed the architecture and constraints, directed the implementation, reviewed changes, validated behaviour, and made the final product decisions.

## Repository structure

```text
SignalOS/
├── .github/workflows/       # Scheduled daily and weekly pipelines
├── demo_data/               # Deterministic synthetic reviewer fixtures
├── scripts/
│   └── load_demo_data.py    # Safe demo-state loader
├── src/
│   ├── config.py            # Lazy model configuration
│   ├── delivery.py          # Discord delivery and message splitting
│   ├── digest.py            # Daily Markdown formatting
│   ├── main.py              # Daily pipeline and candidate preselection
│   ├── news_fetcher.py      # Curated RSS ingestion
│   ├── profile.py           # Intelligence Profile validation/storage
│   ├── ranker.py            # GPT ranking and trusted index mapping
│   ├── state_store.py       # Atomic JSON storage and file locking
│   ├── web_app.py           # FastAPI dashboard and feedback routes
│   └── weekly_summary.py    # Weekly Intelligence pipeline
├── tests/                   # Automated unit and route tests
├── .env.example
├── LICENSE
├── README.md
└── requirements.txt
```

## Security and data handling

- Secrets are loaded from environment variables locally or GitHub Actions secrets; the local `.env` file is excluded from Git.
- Article history, seen-article state, feedback, and the Intelligence Profile remain in the local `.signalos_state/` directory.
- Shared state helpers use same-directory temporary files, `fsync`, atomic replacement, backups, corruption detection, and macOS/Linux file locking for read-modify-write updates.
- Discord delivery errors are sanitised so failures do not include credential-bearing webhook URLs or response bodies.
- Demo Mode needs no external service secrets and uses clearly synthetic data.

These are practical safeguards for a local, single-user project, not a claim of production security certification.

## Limitations and roadmap

Current limitations are deliberate:

- The dashboard is local-first and single-user, with no authentication or database-backed tenancy.
- Feedback is persisted but is not yet connected to an automatic learning or ranking-adjustment loop.
- Coverage and freshness depend on the configured RSS feeds and upstream availability.
- Live ranking, weekly analysis, and Discord delivery require external service credentials.

The next useful steps are feedback-aware ranking, article-history search and filtering, and authenticated database-backed storage before any public multi-user deployment.

## License

This project is licensed under the [MIT License](LICENSE).
