from datetime import datetime, timezone
from html import escape
import json
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse


STATE_DIR = Path(".signalos_state")
ARTICLE_HISTORY_PATH = STATE_DIR / "article_history.json"
FEEDBACK_PATH = STATE_DIR / "feedback.json"

app = FastAPI(title="SignalOS Dashboard")


def _load_article_history() -> list[dict[str, Any]]:
    if not ARTICLE_HISTORY_PATH.exists():
        return []

    with ARTICLE_HISTORY_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def _latest_digest_articles(article_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not article_history:
        return []

    latest_date = max(
        str(article.get("digest_date", ""))
        for article in article_history
    )

    return [
        article
        for article in article_history
        if article.get("digest_date") == latest_date
    ]


def _load_feedback_entries() -> list[dict[str, Any]]:
    if not FEEDBACK_PATH.exists():
        return []

    try:
        with FEEDBACK_PATH.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def _write_feedback_entries(feedback_entries: list[dict[str, Any]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_PATH.open("w", encoding="utf-8") as file:
        json.dump(feedback_entries, file, indent=2)
        file.write("\n")


def _feedback_by_fingerprint(
    feedback_entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    feedback_by_article: dict[str, dict[str, Any]] = {}

    for entry in feedback_entries:
        fingerprint = str(entry.get("fingerprint", ""))
        if fingerprint:
            feedback_by_article[fingerprint] = entry

    return feedback_by_article


def _save_feedback_entry(entry: dict[str, Any]) -> None:
    feedback_entries = _load_feedback_entries()
    fingerprint = str(entry["fingerprint"])
    updated_entries: list[dict[str, Any]] = []
    did_update = False

    for existing_entry in feedback_entries:
        if str(existing_entry.get("fingerprint", "")) != fingerprint:
            updated_entries.append(existing_entry)
            continue

        if did_update:
            continue

        updated_entry = existing_entry.copy()
        updated_entry.update({
            "digest_date": entry["digest_date"],
            "fingerprint": fingerprint,
            "title": entry["title"],
            "source": entry["source"],
            "rating": entry["rating"],
            "updated_at": entry["created_at"],
        })
        if not updated_entry.get("created_at"):
            updated_entry["created_at"] = entry["created_at"]

        updated_entries.append(updated_entry)
        did_update = True

    if not did_update:
        updated_entries.append(entry)

    _write_feedback_entries(updated_entries)


def _find_article_by_fingerprint(
    article_history: list[dict[str, Any]],
    fingerprint: str,
) -> dict[str, Any] | None:
    for article in reversed(article_history):
        if str(article.get("fingerprint", "")) == fingerprint:
            return article

    return None


def _first_form_value(form_data: dict[str, list[str]], field_name: str) -> str:
    values = form_data.get(field_name, [])
    if not values:
        return ""

    return values[0]


def _html_text(value: Any, fallback: str = "") -> str:
    if value is None or value == "":
        return escape(fallback)

    return escape(str(value))


def _plain_text(value: Any, fallback: str = "") -> str:
    if value is None or value == "":
        return fallback

    return str(value)


def _redirect_home() -> RedirectResponse:
    return RedirectResponse("/", status_code=303)


def _redirect_rated_home() -> RedirectResponse:
    return RedirectResponse("/?rated=1", status_code=303)


@app.post("/feedback")
async def submit_feedback(request: Request) -> RedirectResponse:
    body = await request.body()
    form_data = parse_qs(body.decode("utf-8", errors="replace"), keep_blank_values=True)
    fingerprint = _first_form_value(form_data, "fingerprint").strip()
    rating_text = _first_form_value(form_data, "rating").strip()

    try:
        rating = int(rating_text)
    except ValueError:
        return _redirect_home()

    if not fingerprint or rating not in range(1, 6):
        return _redirect_home()

    article_history = _load_article_history()
    article = _find_article_by_fingerprint(article_history, fingerprint)
    if article is None:
        return _redirect_home()

    _save_feedback_entry({
        "created_at": datetime.now(timezone.utc).isoformat(),
        "digest_date": _plain_text(article.get("digest_date")),
        "fingerprint": fingerprint,
        "title": _plain_text(article.get("title")),
        "source": _plain_text(article.get("source")),
        "rating": rating,
    })

    return _redirect_rated_home()


@app.get("/", response_class=HTMLResponse)
def dashboard_home(rated: str | None = None) -> str:
    article_history = _load_article_history()
    latest_articles = _latest_digest_articles(article_history)
    feedback_by_article = _feedback_by_fingerprint(_load_feedback_entries())
    latest_digest_date = _html_text(
        latest_articles[0].get("digest_date") if latest_articles else None,
        "No digest yet",
    )
    success_banner_html = ""
    if rated == "1":
        success_banner_html = """
        <section class="success-banner" role="status">
            <span class="success-dot" aria-hidden="true"></span>
            <p>Feedback saved. SignalOS is learning your preferences.</p>
        </section>
        """

    article_cards: list[str] = []
    article_count = len(latest_articles)

    for article_index, article in enumerate(latest_articles, start=1):
        title = _html_text(article.get("title"), "Untitled")
        source = _html_text(article.get("source"), "Unknown source")
        score = _html_text(article.get("final_score"), "Unknown")
        reason = _html_text(article.get("reason"), "No reason captured yet.")
        action_takeaway = _html_text(
            article.get("action_takeaway"),
            "No action captured yet.",
        )
        article_url = _html_text(article.get("url"), "#")
        fingerprint_raw = _plain_text(article.get("fingerprint"))
        fingerprint = escape(fingerprint_raw)
        saved_feedback = feedback_by_article.get(fingerprint_raw)
        if saved_feedback is None:
            feedback_html = f"""
            <div class="feedback-panel" aria-label="Article feedback">
                <p class="label">Feedback</p>
                <div class="rating-row">
                    {"".join(
                        f'''
                        <form class="rating-form" method="post" action="/feedback">
                            <input type="hidden" name="fingerprint" value="{fingerprint}">
                            <input type="hidden" name="rating" value="{rating_value}">
                            <button class="rating-button" type="submit" aria-label="Rate this article {rating_value} out of 5">
                                {rating_value}
                            </button>
                        </form>
                        '''
                        for rating_value in range(1, 6)
                    )}
                </div>
            </div>
            """
        else:
            saved_rating = _html_text(saved_feedback.get("rating"), "?")
            feedback_html = f"""
            <div class="saved-feedback" aria-label="Saved article feedback">
                <span class="saved-kicker">Feedback saved</span>
                <strong>Your rating: {saved_rating}/5</strong>
            </div>
            """

        article_cards.append(f"""
        <article class="article-card">
            <div class="card-topline">
                <div class="badge-row">
                    <span class="signal-badge">Signal {article_index}/{article_count}</span>
                    <span class="source-badge">{source}</span>
                </div>
                <span class="score-badge">{score}/10</span>
            </div>
            <h2>{title}</h2>
            <div class="card-section">
                <p class="label">Why it matters</p>
                <p>{reason}</p>
            </div>
            <div class="card-section">
                <p class="label">Action takeaway</p>
                <p>{action_takeaway}</p>
            </div>
            <div class="card-actions">
                <a class="article-link" href="{article_url}" target="_blank" rel="noopener noreferrer">
                    Open article
                </a>
                {feedback_html}
            </div>
        </article>
        """)

    if not article_cards:
        article_cards_html = """
        <section class="empty-state">
            <p>No article history found yet. Run the daily agent first.</p>
        </section>
        """
    else:
        article_cards_html = "\n".join(article_cards)

    return f"""
    <!doctype html>
    <html lang="en">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>SignalOS Dashboard</title>
            <style>
                :root {{
                    color-scheme: dark;
                    --panel: rgba(15, 23, 42, 0.78);
                    --panel-strong: rgba(18, 26, 45, 0.94);
                    --text: #edf3ff;
                    --muted: #9ca9c5;
                    --line: rgba(148, 163, 184, 0.18);
                    --accent: #7dd3fc;
                    --signal: #a7f3d0;
                    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                }}

                * {{
                    box-sizing: border-box;
                }}

                body {{
                    min-height: 100vh;
                    margin: 0;
                    background:
                        radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 34rem),
                        radial-gradient(circle at top right, rgba(167, 243, 208, 0.12), transparent 30rem),
                        linear-gradient(135deg, #070a12 0%, #0d1424 48%, #111827 100%);
                    color: var(--text);
                }}

                main {{
                    width: min(1180px, calc(100% - 40px));
                    margin: 0 auto;
                    padding: 44px 0 56px;
                }}

                .page-header {{
                    display: flex;
                    align-items: flex-end;
                    justify-content: space-between;
                    gap: 24px;
                    margin-bottom: 28px;
                    padding: 28px;
                    border: 1px solid var(--line);
                    border-radius: 28px;
                    background: linear-gradient(135deg, rgba(15, 23, 42, 0.76), rgba(15, 23, 42, 0.42));
                    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.28);
                    backdrop-filter: blur(18px);
                }}

                .eyebrow {{
                    margin: 0 0 10px;
                    color: var(--accent);
                    font-size: 0.78rem;
                    font-weight: 800;
                    letter-spacing: 0.14em;
                    text-transform: uppercase;
                }}

                h1 {{
                    margin: 0;
                    font-size: clamp(2.2rem, 4vw, 4.1rem);
                    line-height: 0.95;
                }}

                .subtitle {{
                    max-width: 660px;
                    margin: 16px 0 0;
                    color: var(--muted);
                    font-size: 1rem;
                    line-height: 1.7;
                }}

                .header-meta {{
                    display: flex;
                    flex-wrap: wrap;
                    gap: 10px;
                    margin-top: 18px;
                }}

                .meta-pill {{
                    display: inline-flex;
                    align-items: center;
                    min-height: 34px;
                    padding: 8px 12px;
                    border: 1px solid rgba(125, 211, 252, 0.24);
                    border-radius: 999px;
                    background: rgba(14, 165, 233, 0.08);
                    color: #cdeeff;
                    font-size: 0.82rem;
                    font-weight: 800;
                }}

                .header-stat {{
                    min-width: 150px;
                    padding: 18px;
                    border: 1px solid var(--line);
                    border-radius: 22px;
                    background: rgba(7, 10, 18, 0.42);
                    text-align: right;
                }}

                .stat-number {{
                    display: block;
                    color: var(--signal);
                    font-size: 2.4rem;
                    font-weight: 900;
                    line-height: 1;
                }}

                .stat-label {{
                    display: block;
                    margin-top: 8px;
                    color: var(--muted);
                    font-size: 0.82rem;
                }}

                .success-banner {{
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin: -10px 0 24px;
                    padding: 14px 16px;
                    border: 1px solid rgba(167, 243, 208, 0.3);
                    border-radius: 18px;
                    background: linear-gradient(135deg, rgba(20, 184, 166, 0.18), rgba(34, 197, 94, 0.1));
                    box-shadow: 0 16px 50px rgba(0, 0, 0, 0.2);
                }}

                .success-dot {{
                    width: 10px;
                    height: 10px;
                    flex: 0 0 auto;
                    border-radius: 999px;
                    background: var(--signal);
                    box-shadow: 0 0 0 6px rgba(167, 243, 208, 0.12);
                }}

                .article-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                    gap: 18px;
                }}

                .article-card {{
                    display: flex;
                    min-height: 360px;
                    flex-direction: column;
                    gap: 18px;
                    padding: 22px;
                    border: 1px solid var(--line);
                    border-radius: 24px;
                    background: var(--panel);
                    box-shadow: 0 18px 60px rgba(0, 0, 0, 0.24);
                    backdrop-filter: blur(16px);
                    transition: border-color 180ms ease, transform 180ms ease, background 180ms ease;
                }}

                .article-card:hover {{
                    transform: translateY(-3px);
                    border-color: rgba(125, 211, 252, 0.42);
                    background: var(--panel-strong);
                }}

                .card-topline {{
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    gap: 12px;
                }}

                .badge-row {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    min-width: 0;
                }}

                .signal-badge,
                .source-badge,
                .score-badge {{
                    display: inline-flex;
                    align-items: center;
                    min-height: 32px;
                    padding: 7px 11px;
                    border-radius: 999px;
                    font-size: 0.78rem;
                    font-weight: 800;
                    line-height: 1;
                }}

                .signal-badge {{
                    flex: 0 0 auto;
                    border: 1px solid rgba(167, 243, 208, 0.2);
                    background: rgba(16, 185, 129, 0.1);
                    color: #bbf7d0;
                }}

                .source-badge {{
                    max-width: 100%;
                    min-width: 0;
                    overflow: hidden;
                    border: 1px solid rgba(125, 211, 252, 0.2);
                    background: rgba(14, 165, 233, 0.1);
                    color: #bae6fd;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }}

                .score-badge {{
                    flex: 0 0 auto;
                    border: 1px solid rgba(250, 204, 21, 0.25);
                    background: rgba(250, 204, 21, 0.1);
                    color: #fde68a;
                }}

                h2 {{
                    margin: 0;
                    font-size: 1.25rem;
                    line-height: 1.35;
                }}

                .card-section {{
                    padding-top: 2px;
                }}

                .label {{
                    margin: 0 0 6px;
                    color: var(--accent);
                    font-size: 0.72rem;
                    font-weight: 900;
                    letter-spacing: 0.12em;
                    text-transform: uppercase;
                }}

                p {{
                    margin: 0;
                    color: #cbd5e1;
                    line-height: 1.6;
                }}

                .article-link {{
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: fit-content;
                    padding: 11px 15px;
                    border: 1px solid rgba(125, 211, 252, 0.34);
                    border-radius: 14px;
                    background: linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(167, 243, 208, 0.12));
                    color: var(--text);
                    font-size: 0.9rem;
                    font-weight: 850;
                    text-decoration: none;
                    transition: border-color 180ms ease, transform 180ms ease, background 180ms ease;
                }}

                .article-link:hover {{
                    transform: translateY(-1px);
                    border-color: rgba(167, 243, 208, 0.58);
                    background: linear-gradient(135deg, rgba(56, 189, 248, 0.32), rgba(167, 243, 208, 0.2));
                }}

                .card-actions {{
                    display: flex;
                    align-items: flex-end;
                    justify-content: space-between;
                    gap: 16px;
                    margin-top: auto;
                    flex-wrap: wrap;
                }}

                .feedback-panel {{
                    display: grid;
                    gap: 8px;
                    padding: 12px;
                    border: 1px solid rgba(125, 211, 252, 0.14);
                    border-radius: 16px;
                    background: rgba(7, 10, 18, 0.24);
                }}

                .rating-row {{
                    display: flex;
                    gap: 6px;
                    flex-wrap: wrap;
                }}

                .rating-form {{
                    margin: 0;
                }}

                .rating-button {{
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: 34px;
                    height: 34px;
                    border: 1px solid rgba(167, 243, 208, 0.28);
                    border-radius: 12px;
                    background: rgba(167, 243, 208, 0.08);
                    color: var(--text);
                    font: inherit;
                    font-size: 0.82rem;
                    font-weight: 900;
                    cursor: pointer;
                    transition: border-color 180ms ease, transform 180ms ease, background 180ms ease;
                }}

                .rating-button:hover,
                .rating-button:focus-visible {{
                    transform: translateY(-1px);
                    border-color: rgba(167, 243, 208, 0.64);
                    background: rgba(167, 243, 208, 0.18);
                    outline: none;
                }}

                .saved-feedback {{
                    display: grid;
                    gap: 4px;
                    min-width: 180px;
                    padding: 13px 14px;
                    border: 1px solid rgba(167, 243, 208, 0.32);
                    border-radius: 16px;
                    background: linear-gradient(135deg, rgba(20, 184, 166, 0.18), rgba(34, 197, 94, 0.1));
                    color: var(--text);
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
                }}

                .saved-kicker {{
                    color: var(--signal);
                    font-size: 0.72rem;
                    font-weight: 900;
                    letter-spacing: 0.1em;
                    text-transform: uppercase;
                }}

                .empty-state {{
                    padding: 28px;
                    border: 1px dashed rgba(148, 163, 184, 0.32);
                    border-radius: 24px;
                    background: rgba(15, 23, 42, 0.64);
                    text-align: center;
                }}

                @media (max-width: 760px) {{
                    main {{
                        width: min(100% - 28px, 1180px);
                        padding-top: 24px;
                    }}

                    .page-header {{
                        display: block;
                        padding: 22px;
                        border-radius: 22px;
                    }}

                    .header-stat {{
                        width: 100%;
                        margin-top: 20px;
                        text-align: left;
                    }}

                    .article-grid {{
                        grid-template-columns: 1fr;
                    }}

                    .article-card {{
                        min-height: auto;
                    }}
                }}
            </style>
        </head>
        <body>
            <main>
                <header class="page-header">
                    <div>
                        <p class="eyebrow">Personal intelligence OS</p>
                        <h1>SignalOS Dashboard</h1>
                        <p class="subtitle">Latest strategic signals from article history, ranked into a clean briefing surface.</p>
                        <div class="header-meta">
                            <span class="meta-pill">Latest digest: {latest_digest_date}</span>
                        </div>
                    </div>
                    <aside class="header-stat" aria-label="Latest article count">
                        <span class="stat-number">{len(latest_articles)}</span>
                        <span class="stat-label">latest signals</span>
                    </aside>
                </header>
                {success_banner_html}
                <section class="article-grid" aria-label="Latest articles">
                    {article_cards_html}
                </section>
            </main>
        </body>
    </html>
    """
