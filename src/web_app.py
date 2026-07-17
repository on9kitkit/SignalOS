from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from src.state_store import locked_update_json_list, read_json_list


STATE_DIR = Path(".signalos_state")
ARTICLE_HISTORY_PATH = STATE_DIR / "article_history.json"
FEEDBACK_PATH = STATE_DIR / "feedback.json"
WEEKLY_REPORT_DIRS = (
    Path("weekly_reports"),
    Path("src/weekly_reports"),
)

app = FastAPI(title="SignalOS Dashboard")


def _load_article_history() -> list[dict[str, Any]]:
    data = read_json_list(ARTICLE_HISTORY_PATH)
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


def _latest_weekly_report_path() -> Path | None:
    for report_dir in WEEKLY_REPORT_DIRS:
        if not report_dir.is_dir():
            continue

        report_paths = [path for path in report_dir.glob("*.md") if path.is_file()]
        if report_paths:
            return max(report_paths, key=_weekly_report_sort_key)

    return None


def _weekly_report_sort_key(report_path: Path) -> tuple[float, str]:
    try:
        modified_at = report_path.stat().st_mtime
    except OSError:
        modified_at = 0.0

    return (modified_at, report_path.name)


def _load_latest_weekly_report() -> tuple[str, str] | None:
    report_path = _latest_weekly_report_path()
    if report_path is None:
        return None

    try:
        report_content = report_path.read_text(encoding="utf-8")
    except OSError:
        return None

    return (report_path.name, report_content)


def _simple_markdown_to_html(markdown_text: str) -> str:
    html_parts: list[str] = []
    paragraph_lines: list[str] = []
    bullet_items: list[str] = []

    def flush_paragraph() -> None:
        if not paragraph_lines:
            return

        paragraph_text = " ".join(line.strip() for line in paragraph_lines)
        html_parts.append(f"<p>{escape(paragraph_text)}</p>")
        paragraph_lines.clear()

    def flush_bullets() -> None:
        if not bullet_items:
            return

        items_html = "".join(f"<li>{escape(item)}</li>" for item in bullet_items)
        html_parts.append(f"<ul>{items_html}</ul>")
        bullet_items.clear()

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_paragraph()
            flush_bullets()
            continue

        if line.startswith("### "):
            flush_paragraph()
            flush_bullets()
            html_parts.append(f"<h5>{escape(line[4:].strip())}</h5>")
            continue

        if line.startswith("## "):
            flush_paragraph()
            flush_bullets()
            html_parts.append(f"<h4>{escape(line[3:].strip())}</h4>")
            continue

        if line.startswith("# "):
            flush_paragraph()
            flush_bullets()
            html_parts.append(f"<h3>{escape(line[2:].strip())}</h3>")
            continue

        if line.startswith("- "):
            flush_paragraph()
            bullet_items.append(line[2:].strip())
            continue

        flush_bullets()
        paragraph_lines.append(line)

    flush_paragraph()
    flush_bullets()

    if not html_parts:
        return "<p>This weekly report is empty.</p>"

    return "\n".join(html_parts)


def _load_feedback_entries() -> list[dict[str, Any]]:
    data = read_json_list(FEEDBACK_PATH)
    return [item for item in data if isinstance(item, dict)]


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
    def upsert_feedback(current_items: list[Any]) -> list[Any]:
        feedback_entries = [
            item for item in current_items if isinstance(item, dict)
        ]
        fingerprint = str(entry["fingerprint"])
        updated_entries: list[Any] = []
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

        return updated_entries

    locked_update_json_list(FEEDBACK_PATH, upsert_feedback)


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


def _score_number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    article_count = len(latest_articles)
    rated_count = sum(
        1
        for article in latest_articles
        if _plain_text(article.get("fingerprint")) in feedback_by_article
    )
    score_values = [
        score
        for article in latest_articles
        if (score := _score_number(article.get("final_score"))) is not None
    ]
    average_score = (
        f"{sum(score_values) / len(score_values):.1f}"
        if score_values
        else "N/A"
    )
    feedback_status = (
        f"{rated_count}/{article_count} rated"
        if article_count
        else "No feedback yet"
    )
    weekly_report = _load_latest_weekly_report()
    if weekly_report is None:
        weekly_report_html = """
        <section class="weekly-panel weekly-panel-empty" aria-label="Weekly Intelligence">
            <div class="weekly-panel-header">
                <div>
                    <p class="eyebrow">Weekly Intelligence</p>
                    <h2 class="weekly-title">Strategic weekly readout</h2>
                </div>
                <span class="weekly-report-badge">No report</span>
            </div>
            <div class="weekly-empty-state">
                <p>No weekly report generated yet.</p>
            </div>
        </section>
        """
    else:
        report_name, report_content = weekly_report
        weekly_report_name = _html_text(report_name, "Latest weekly report")
        weekly_report_content_html = _simple_markdown_to_html(report_content)
        weekly_report_html = f"""
        <section class="weekly-panel" aria-label="Weekly Intelligence">
            <div class="weekly-panel-header">
                <div>
                    <p class="eyebrow">Weekly Intelligence</p>
                    <h2 class="weekly-title">Strategic weekly readout</h2>
                </div>
                <span class="weekly-report-badge">{weekly_report_name}</span>
            </div>
            <div class="weekly-content">
                {weekly_report_content_html}
            </div>
        </section>
        """
    success_banner_html = ""
    if rated == "1":
        success_banner_html = """
        <section class="success-banner" role="status">
            <span class="success-dot" aria-hidden="true"></span>
            <p>Feedback saved. SignalOS is learning your preferences.</p>
        </section>
        """

    article_cards: list[str] = []

    for article_index, article in enumerate(latest_articles, start=1):
        card_class = "article-card article-card-featured" if article_index == 1 else "article-card"
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
            <div class="feedback-panel" data-feedback-region aria-label="Article feedback">
                <p class="label">Feedback</p>
                <div class="rating-row">
                    {"".join(
                        f'''
                        <form class="rating-form" method="post" action="/feedback" data-feedback-form>
                            <input type="hidden" name="fingerprint" value="{fingerprint}">
                            <input type="hidden" name="rating" value="{rating_value}">
                            <button class="rating-button" type="submit" data-rating-value="{rating_value}" aria-label="Rate this article {rating_value} out of 5">
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
            <div class="saved-feedback" data-feedback-region aria-label="Saved article feedback">
                <span class="saved-kicker">Feedback saved</span>
                <strong>Your rating: {saved_rating}/5</strong>
            </div>
            """

        article_cards.append(f"""
        <article class="{card_class}">
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
                    --panel: rgba(12, 19, 34, 0.82);
                    --panel-strong: rgba(15, 24, 42, 0.96);
                    --panel-soft: rgba(7, 10, 18, 0.42);
                    --text: #edf3ff;
                    --muted: #9ca9c5;
                    --line: rgba(148, 163, 184, 0.18);
                    --line-strong: rgba(125, 211, 252, 0.34);
                    --accent: #7dd3fc;
                    --signal: #a7f3d0;
                    --gold: #fde68a;
                    --shadow: 0 24px 80px rgba(0, 0, 0, 0.34);
                    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                }}

                * {{
                    box-sizing: border-box;
                }}

                body {{
                    min-height: 100vh;
                    margin: 0;
                    background:
                        radial-gradient(circle at 12% 0%, rgba(56, 189, 248, 0.18), transparent 34rem),
                        radial-gradient(circle at 90% 8%, rgba(167, 243, 208, 0.12), transparent 30rem),
                        linear-gradient(135deg, #070a12 0%, #0d1424 44%, #111827 100%);
                    background-attachment: fixed;
                    color: var(--text);
                }}

                main {{
                    width: min(1220px, calc(100% - 40px));
                    margin: 0 auto;
                    padding: 42px 0 40px;
                }}

                .page-header {{
                    display: grid;
                    grid-template-columns: minmax(0, 1.35fr) minmax(300px, 0.65fr);
                    align-items: stretch;
                    gap: 24px;
                    margin-bottom: 22px;
                    padding: 30px;
                    border: 1px solid rgba(125, 211, 252, 0.18);
                    border-radius: 18px;
                    background:
                        linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(8, 13, 24, 0.74)),
                        radial-gradient(circle at 16% 0%, rgba(125, 211, 252, 0.16), transparent 26rem);
                    box-shadow: var(--shadow);
                    backdrop-filter: blur(18px);
                }}

                .hero-copy {{
                    display: flex;
                    min-height: 220px;
                    flex-direction: column;
                    justify-content: center;
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

                .meta-pill-soft {{
                    border-color: rgba(167, 243, 208, 0.22);
                    background: rgba(16, 185, 129, 0.08);
                    color: #c8ffe6;
                }}

                .hero-stats {{
                    display: grid;
                    grid-template-columns: 1fr;
                    gap: 12px;
                }}

                .hero-stat {{
                    display: grid;
                    align-content: center;
                    min-height: 0;
                    padding: 18px;
                    border: 1px solid var(--line);
                    border-radius: 8px;
                    background: linear-gradient(135deg, rgba(7, 10, 18, 0.58), rgba(15, 23, 42, 0.38));
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
                }}

                .stat-number {{
                    display: block;
                    color: #dffcff;
                    font-size: 2.25rem;
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
                    margin: 0 0 24px;
                    padding: 14px 16px;
                    border: 1px solid rgba(167, 243, 208, 0.34);
                    border-radius: 8px;
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

                .weekly-panel {{
                    display: grid;
                    gap: 18px;
                    margin: 0 0 30px;
                    padding: 24px;
                    border: 1px solid rgba(125, 211, 252, 0.18);
                    border-radius: 8px;
                    background:
                        linear-gradient(135deg, rgba(14, 165, 233, 0.1), transparent 34%),
                        rgba(12, 19, 34, 0.78);
                    box-shadow: 0 18px 60px rgba(0, 0, 0, 0.22);
                    backdrop-filter: blur(16px);
                }}

                .weekly-panel-header {{
                    display: flex;
                    align-items: flex-start;
                    justify-content: space-between;
                    gap: 18px;
                }}

                .weekly-title {{
                    margin: 0;
                    font-size: 1.5rem;
                    line-height: 1.2;
                }}

                .weekly-report-badge {{
                    display: inline-flex;
                    align-items: center;
                    max-width: min(100%, 360px);
                    min-height: 34px;
                    padding: 8px 12px;
                    overflow: hidden;
                    border: 1px solid rgba(167, 243, 208, 0.24);
                    border-radius: 999px;
                    background: rgba(16, 185, 129, 0.08);
                    color: #d1fae5;
                    font-size: 0.82rem;
                    font-weight: 850;
                    text-overflow: ellipsis;
                    white-space: nowrap;
                }}

                .weekly-content {{
                    display: grid;
                    gap: 12px;
                    max-height: 460px;
                    overflow: auto;
                    padding: 18px;
                    border: 1px solid rgba(148, 163, 184, 0.14);
                    border-radius: 8px;
                    background: rgba(7, 10, 18, 0.3);
                }}

                .weekly-content h3,
                .weekly-content h4,
                .weekly-content h5 {{
                    margin: 0;
                    color: #f8fbff;
                    line-height: 1.25;
                    letter-spacing: 0;
                }}

                .weekly-content h3 {{
                    font-size: 1.25rem;
                }}

                .weekly-content h4 {{
                    color: #dffcff;
                    font-size: 1.08rem;
                }}

                .weekly-content h5 {{
                    color: var(--signal);
                    font-size: 0.95rem;
                    text-transform: uppercase;
                }}

                .weekly-content p {{
                    color: #d0d8e8;
                }}

                .weekly-content ul {{
                    display: grid;
                    gap: 8px;
                    margin: 0;
                    padding-left: 1.2rem;
                    color: #d0d8e8;
                    line-height: 1.58;
                }}

                .weekly-content li::marker {{
                    color: var(--signal);
                }}

                .weekly-empty-state {{
                    padding: 18px;
                    border: 1px dashed rgba(148, 163, 184, 0.32);
                    border-radius: 8px;
                    background: rgba(7, 10, 18, 0.26);
                }}

                .section-heading {{
                    display: flex;
                    align-items: flex-end;
                    justify-content: space-between;
                    gap: 20px;
                    margin: 28px 0 16px;
                }}

                .section-title {{
                    margin: 0;
                    font-size: 1.45rem;
                    line-height: 1.2;
                }}

                .feedback-status {{
                    display: grid;
                    gap: 4px;
                    min-width: 180px;
                    padding: 12px 14px;
                    border: 1px solid rgba(167, 243, 208, 0.2);
                    border-radius: 8px;
                    background: rgba(7, 10, 18, 0.32);
                    text-align: right;
                }}

                .feedback-status span {{
                    color: var(--muted);
                    font-size: 0.76rem;
                    font-weight: 800;
                    letter-spacing: 0.08em;
                    text-transform: uppercase;
                }}

                .feedback-status strong {{
                    color: var(--signal);
                    font-size: 1rem;
                }}

                .article-grid {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
                    gap: 20px;
                }}

                .article-card {{
                    display: flex;
                    position: relative;
                    min-height: 380px;
                    flex-direction: column;
                    gap: 20px;
                    padding: 24px;
                    border: 1px solid var(--line);
                    border-radius: 8px;
                    background: var(--panel);
                    box-shadow: 0 18px 60px rgba(0, 0, 0, 0.22);
                    backdrop-filter: blur(16px);
                    overflow: hidden;
                    transition: border-color 180ms ease, transform 180ms ease, background 180ms ease, box-shadow 180ms ease;
                }}

                .article-card::before {{
                    content: "";
                    position: absolute;
                    inset: 0;
                    border-top: 1px solid rgba(255, 255, 255, 0.05);
                    pointer-events: none;
                }}

                .article-card:hover {{
                    transform: translateY(-5px);
                    border-color: rgba(125, 211, 252, 0.46);
                    background: var(--panel-strong);
                    box-shadow: 0 28px 80px rgba(0, 0, 0, 0.34);
                }}

                .article-card-featured {{
                    border-color: rgba(125, 211, 252, 0.42);
                    background:
                        linear-gradient(145deg, rgba(14, 165, 233, 0.13), transparent 44%),
                        var(--panel);
                }}

                .article-card-featured .signal-badge {{
                    border-color: rgba(125, 211, 252, 0.34);
                    background: rgba(14, 165, 233, 0.16);
                    color: #e0f7ff;
                }}

                .card-topline {{
                    display: flex;
                    align-items: flex-start;
                    justify-content: space-between;
                    gap: 12px;
                }}

                .badge-row {{
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    min-width: 0;
                    flex-wrap: wrap;
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
                    font-size: 1.22rem;
                    line-height: 1.32;
                    letter-spacing: 0;
                }}

                .article-card-featured h2 {{
                    font-size: 1.38rem;
                }}

                .card-section {{
                    padding-top: 4px;
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
                    line-height: 1.62;
                }}

                .article-link {{
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: fit-content;
                    min-height: 40px;
                    padding: 10px 15px;
                    border: 1px solid rgba(125, 211, 252, 0.34);
                    border-radius: 8px;
                    background: linear-gradient(135deg, rgba(56, 189, 248, 0.22), rgba(167, 243, 208, 0.12));
                    color: var(--text);
                    font-size: 0.9rem;
                    font-weight: 850;
                    text-decoration: none;
                    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
                    transition: border-color 180ms ease, transform 180ms ease, background 180ms ease, box-shadow 180ms ease;
                }}

                .article-link:hover {{
                    transform: translateY(-2px);
                    border-color: rgba(167, 243, 208, 0.58);
                    background: linear-gradient(135deg, rgba(56, 189, 248, 0.32), rgba(167, 243, 208, 0.2));
                    box-shadow: 0 10px 24px rgba(8, 145, 178, 0.14);
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
                    gap: 10px;
                    min-width: 224px;
                    padding: 13px;
                    border: 1px solid rgba(125, 211, 252, 0.18);
                    border-radius: 8px;
                    background: linear-gradient(135deg, rgba(7, 10, 18, 0.42), rgba(15, 23, 42, 0.28));
                }}

                .rating-row {{
                    display: flex;
                    gap: 7px;
                    flex-wrap: wrap;
                }}

                .rating-form {{
                    margin: 0;
                }}

                .rating-button {{
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: 36px;
                    height: 36px;
                    border: 1px solid rgba(167, 243, 208, 0.28);
                    border-radius: 8px;
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
                    transform: translateY(-2px);
                    border-color: rgba(167, 243, 208, 0.64);
                    background: rgba(167, 243, 208, 0.18);
                    outline: none;
                }}

                .rating-button:disabled {{
                    cursor: wait;
                    opacity: 0.62;
                    transform: none;
                }}

                .saved-feedback {{
                    display: grid;
                    gap: 6px;
                    min-width: 224px;
                    padding: 14px 15px;
                    border: 1px solid rgba(167, 243, 208, 0.46);
                    border-radius: 8px;
                    background:
                        linear-gradient(135deg, rgba(20, 184, 166, 0.24), rgba(34, 197, 94, 0.12)),
                        rgba(7, 10, 18, 0.24);
                    color: var(--text);
                    box-shadow:
                        inset 0 1px 0 rgba(255, 255, 255, 0.07),
                        0 14px 34px rgba(20, 184, 166, 0.08);
                }}

                .saved-kicker {{
                    color: var(--signal);
                    font-size: 0.72rem;
                    font-weight: 900;
                    letter-spacing: 0.1em;
                    text-transform: uppercase;
                }}

                .saved-feedback strong {{
                    color: #f0fdfa;
                    font-size: 1.02rem;
                }}

                .empty-state {{
                    padding: 28px;
                    border: 1px dashed rgba(148, 163, 184, 0.32);
                    border-radius: 8px;
                    background: rgba(15, 23, 42, 0.64);
                    text-align: center;
                }}

                .dashboard-footer {{
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    gap: 12px;
                    flex-wrap: wrap;
                    margin-top: 28px;
                    padding: 16px;
                    border: 1px solid rgba(148, 163, 184, 0.14);
                    border-radius: 8px;
                    background: rgba(7, 10, 18, 0.24);
                    color: var(--muted);
                    font-size: 0.84rem;
                }}

                .dashboard-footer span {{
                    color: var(--accent);
                    font-weight: 900;
                    letter-spacing: 0.08em;
                    text-transform: uppercase;
                }}

                .dashboard-footer strong {{
                    color: #dbeafe;
                    font-weight: 800;
                }}

                @media (min-width: 940px) {{
                    .article-card-featured {{
                        grid-column: span 2;
                        min-height: 340px;
                    }}
                }}

                @media (max-width: 900px) {{
                    .page-header {{
                        grid-template-columns: 1fr;
                    }}

                    .hero-copy {{
                        min-height: auto;
                    }}

                    .hero-stats {{
                        grid-template-columns: repeat(3, minmax(0, 1fr));
                    }}
                }}

                @media (max-width: 760px) {{
                    main {{
                        width: min(100% - 28px, 1180px);
                        padding-top: 24px;
                    }}

                    .page-header {{
                        padding: 22px;
                        border-radius: 12px;
                    }}

                    h1 {{
                        font-size: 2.25rem;
                    }}

                    .hero-stats {{
                        grid-template-columns: 1fr;
                    }}

                    .weekly-panel-header {{
                        align-items: stretch;
                        flex-direction: column;
                    }}

                    .weekly-report-badge {{
                        max-width: 100%;
                    }}

                    .section-heading {{
                        align-items: stretch;
                        flex-direction: column;
                    }}

                    .feedback-status {{
                        text-align: left;
                    }}

                    .article-grid {{
                        grid-template-columns: 1fr;
                    }}

                    .article-card {{
                        min-height: auto;
                    }}

                    .card-actions {{
                        align-items: stretch;
                        flex-direction: column;
                    }}

                    .article-link,
                    .feedback-panel,
                    .saved-feedback {{
                        width: 100%;
                    }}
                }}
            </style>
        </head>
        <body>
            <main>
                <header class="page-header">
                    <div class="hero-copy">
                        <p class="eyebrow">Personal intelligence OS</p>
                        <h1>SignalOS Dashboard</h1>
                        <p class="subtitle">Latest strategic signals from article history, ranked into a clean briefing surface.</p>
                        <div class="header-meta">
                            <span class="meta-pill">Latest digest: {latest_digest_date}</span>
                            <span class="meta-pill meta-pill-soft">Feedback status: {feedback_status}</span>
                        </div>
                    </div>
                    <aside class="hero-stats" aria-label="Dashboard stats">
                        <div class="hero-stat">
                            <span class="stat-number">{article_count}</span>
                            <span class="stat-label">signals shown</span>
                        </div>
                        <div class="hero-stat">
                            <span class="stat-number">{rated_count}</span>
                            <span class="stat-label">rated signals</span>
                        </div>
                        <div class="hero-stat">
                            <span class="stat-number">{average_score}</span>
                            <span class="stat-label">avg score</span>
                        </div>
                    </aside>
                </header>
                {success_banner_html}
                <section class="success-banner feedback-toast" data-feedback-toast role="status" hidden>
                    <span class="success-dot" aria-hidden="true"></span>
                    <p>Feedback saved. SignalOS is learning your preferences.</p>
                </section>
                {weekly_report_html}
                <section class="section-heading" aria-label="Daily Signals">
                    <div>
                        <p class="eyebrow">Daily Signals</p>
                        <h2 class="section-title">Today's ranked brief</h2>
                    </div>
                    <div class="feedback-status">
                        <span>Feedback status</span>
                        <strong>{feedback_status}</strong>
                    </div>
                </section>
                <section class="article-grid" aria-label="Latest articles">
                    {article_cards_html}
                </section>
                <footer class="dashboard-footer" aria-label="Dashboard status">
                    <span>SignalOS status</span>
                    <strong>{article_count} signals shown</strong>
                    <strong>{rated_count} rated</strong>
                    <strong>Average score {average_score}</strong>
                </footer>
            </main>
            <script>
                (() => {{
                    const feedbackForms = document.querySelectorAll("[data-feedback-form]");
                    const feedbackToast = document.querySelector("[data-feedback-toast]");
                    let toastTimer;

                    const showFeedbackToast = () => {{
                        if (!feedbackToast) {{
                            return;
                        }}

                        feedbackToast.hidden = false;
                        window.clearTimeout(toastTimer);
                        toastTimer = window.setTimeout(() => {{
                            feedbackToast.hidden = true;
                        }}, 4000);
                    }};

                    const createSavedFeedback = (rating) => {{
                        const savedFeedback = document.createElement("div");
                        savedFeedback.className = "saved-feedback";
                        savedFeedback.dataset.feedbackRegion = "";
                        savedFeedback.setAttribute("aria-label", "Saved article feedback");

                        const savedKicker = document.createElement("span");
                        savedKicker.className = "saved-kicker";
                        savedKicker.textContent = "Feedback saved";

                        const savedRating = document.createElement("strong");
                        savedRating.textContent = `Your rating: ${{rating}}/5`;

                        savedFeedback.append(savedKicker, savedRating);
                        return savedFeedback;
                    }};

                    const submitFeedback = async (event) => {{
                        event.preventDefault();

                        const form = event.currentTarget;
                        const feedbackRegion = form.closest("[data-feedback-region]");
                        const formData = new FormData(form);
                        const rating = formData.get("rating");

                        if (!feedbackRegion || typeof rating !== "string") {{
                            form.submit();
                            return;
                        }}

                        const ratingButtons = feedbackRegion.querySelectorAll(".rating-button");
                        ratingButtons.forEach((button) => {{
                            button.disabled = true;
                        }});

                        try {{
                            const response = await fetch(form.action, {{
                                method: form.method.toUpperCase(),
                                headers: {{
                                    "Content-Type": "application/x-www-form-urlencoded",
                                }},
                                body: new URLSearchParams(formData),
                            }});

                            if (!response.ok) {{
                                throw new Error("Feedback request failed");
                            }}

                            feedbackRegion.replaceWith(createSavedFeedback(rating));
                            showFeedbackToast();
                        }} catch (error) {{
                            form.submit();
                        }}
                    }};

                    feedbackForms.forEach((form) => {{
                        form.addEventListener("submit", submitFeedback);
                    }});
                }})();
            </script>
        </body>
    </html>
    """
