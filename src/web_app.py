from html import escape
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse


STATE_DIR = Path(".signalos_state")
ARTICLE_HISTORY_PATH = STATE_DIR / "article_history.json"

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


def _html_text(value: Any, fallback: str = "") -> str:
    if value is None or value == "":
        return escape(fallback)

    return escape(str(value))


@app.get("/", response_class=HTMLResponse)
def dashboard_home() -> str:
    article_history = _load_article_history()
    latest_articles = _latest_digest_articles(article_history)

    article_cards: list[str] = []

    for article in latest_articles:
        title = _html_text(article.get("title"), "Untitled")
        source = _html_text(article.get("source"), "Unknown source")
        score = _html_text(article.get("final_score"), "Unknown")
        reason = _html_text(article.get("reason"), "No reason captured yet.")
        action_takeaway = _html_text(
            article.get("action_takeaway"),
            "No action captured yet.",
        )
        article_url = _html_text(article.get("url"), "#")

        article_cards.append(f"""
        <article class="article-card">
            <div class="card-topline">
                <span class="source-badge">{source}</span>
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
            <a class="article-link" href="{article_url}" target="_blank" rel="noopener noreferrer">
                Open article
            </a>
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

                .source-badge,
                .score-badge {{
                    display: inline-flex;
                    align-items: center;
                    min-height: 32px;
                    max-width: 70%;
                    padding: 7px 11px;
                    border-radius: 999px;
                    font-size: 0.78rem;
                    font-weight: 800;
                    line-height: 1;
                }}

                .source-badge {{
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
                    margin-top: auto;
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
                    </div>
                    <aside class="header-stat" aria-label="Latest article count">
                        <span class="stat-number">{len(latest_articles)}</span>
                        <span class="stat-label">latest signals</span>
                    </aside>
                </header>
                <section class="article-grid" aria-label="Latest articles">
                    {article_cards_html}
                </section>
            </main>
        </body>
    </html>
    """
