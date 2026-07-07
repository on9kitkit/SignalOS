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


@app.get("/", response_class=HTMLResponse)
def dashboard_home() -> str:
    article_history = _load_article_history()
    latest_articles = _latest_digest_articles(article_history)

    article_cards = ""

    for article in latest_articles:
        article_cards += f"""
        <article>
            <h2>{article.get("title", "Untitled")}</h2>
            <p><strong>Source:</strong> {article.get("source", "Unknown")}</p>
            <p><strong>Score:</strong> {article.get("final_score", "Unknown")}/10</p>
            <p><strong>Why it matters:</strong> {article.get("reason", "")}</p>
            <p><strong>Action:</strong> {article.get("action_takeaway", "")}</p>
            <p><a href="{article.get("url", "#")}" target="_blank">Open article</a></p>
            <hr>
        </article>
        """

    if not article_cards:
        article_cards = "<p>No article history found yet. Run the daily agent first.</p>"

    return f"""
    <!doctype html>
    <html>
        <head>
            <title>SignalOS Dashboard</title>
        </head>
        <body>
            <h1>SignalOS Dashboard</h1>
            <p>Latest strategic signals from article history.</p>
            {article_cards}
        </body>
    </html>
    """