import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.delivery import send_to_discord
from src.digest import create_markdown_digest
from src.models import Article, RankedArticle
from src.news_fetcher import fetch_articles
from src.ranker import apply_source_diversity, rank_articles


STATE_DIR = Path(".signalos_state")
SEEN_ARTICLES_PATH = STATE_DIR / "seen_articles.json"
ARTICLE_HISTORY_PATH = STATE_DIR / "article_history.json"
MAX_SEEN_ARTICLES = 300
MAX_ARTICLE_HISTORY_ITEMS = 90
FRESH_ARTICLE_WINDOW_DAYS = 3


def _normalise_text(value: str) -> str:
    return " ".join(value.lower().strip().split())



def _article_fingerprint(article: Article) -> str:
    fingerprint_source = f"{_normalise_text(article.title)}|{article.url.strip()}"
    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()


# --- Fresh article helpers ---
def _parse_article_datetime(article: Article) -> datetime | None:
    published = article.published.strip()

    if not published or published.lower() == "unknown":
        return None

    try:
        parsed_datetime = parsedate_to_datetime(published)
    except (TypeError, ValueError):
        return None

    if parsed_datetime.tzinfo is None:
        return parsed_datetime.replace(tzinfo=timezone.utc)

    return parsed_datetime.astimezone(timezone.utc)


def _filter_fresh_articles(
    articles: list[Article],
    window_days: int = FRESH_ARTICLE_WINDOW_DAYS,
) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=window_days)
    fresh_articles: list[Article] = []

    for article in articles:
        published_at = _parse_article_datetime(article)

        if published_at is None:
            fresh_articles.append(article)
            continue

        if published_at >= cutoff:
            fresh_articles.append(article)

    return fresh_articles


def _load_seen_article_ids() -> list[str]:
    if not SEEN_ARTICLES_PATH.exists():
        return []

    with SEEN_ARTICLES_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise RuntimeError("seen_articles.json must contain a JSON list.")

    return [str(item) for item in data]


def _save_seen_article_ids(seen_article_ids: list[str]) -> None:
    STATE_DIR.mkdir(exist_ok=True)

    compact_history = seen_article_ids[-MAX_SEEN_ARTICLES:]

    with SEEN_ARTICLES_PATH.open("w", encoding="utf-8") as file:
        json.dump(compact_history, file, indent=2)


def _load_article_history() -> list[dict[str, Any]]:
    if not ARTICLE_HISTORY_PATH.exists():
        return []

    with ARTICLE_HISTORY_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise RuntimeError("article_history.json must contain a JSON list.")

    return [item for item in data if isinstance(item, dict)]


def _save_article_history(article_history: list[dict[str, Any]]) -> None:
    STATE_DIR.mkdir(exist_ok=True)

    compact_history = article_history[-MAX_ARTICLE_HISTORY_ITEMS:]

    with ARTICLE_HISTORY_PATH.open("w", encoding="utf-8") as file:
        json.dump(compact_history, file, indent=2, ensure_ascii=False)


def _filter_seen_articles(
    articles: list[Article],
    seen_article_ids: list[str],
) -> list[Article]:
    seen_lookup = set(seen_article_ids)

    return [
        article
        for article in articles
        if _article_fingerprint(article) not in seen_lookup
    ]


def _mark_ranked_articles_as_seen(
    ranked_articles: list[RankedArticle],
    seen_article_ids: list[str],
) -> list[str]:
    updated_seen_article_ids = list(seen_article_ids)
    seen_lookup = set(seen_article_ids)

    for ranked_article in ranked_articles:
        fingerprint = _article_fingerprint(ranked_article.article)

        if fingerprint not in seen_lookup:
            updated_seen_article_ids.append(fingerprint)
            seen_lookup.add(fingerprint)

    return updated_seen_article_ids


def _ranked_article_to_history_entry(ranked_article: RankedArticle) -> dict[str, Any]:
    article = ranked_article.article

    return {
        "digest_date": date.today().isoformat(),
        "fingerprint": _article_fingerprint(article),
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published": article.published,
        "summary": article.summary,
        "relevance_score": ranked_article.relevance_score,
        "quality_score": ranked_article.quality_score,
        "importance_score": ranked_article.importance_score,
        "final_score": ranked_article.final_score,
        "reason": ranked_article.reason,
        "action_takeaway": ranked_article.action_takeaway,
    }


def _append_ranked_articles_to_history(
    ranked_articles: list[RankedArticle],
    article_history: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    updated_history = list(article_history)
    existing_fingerprints = {
        str(item.get("fingerprint"))
        for item in updated_history
        if item.get("fingerprint")
    }

    for ranked_article in ranked_articles:
        entry = _ranked_article_to_history_entry(ranked_article)

        if entry["fingerprint"] in existing_fingerprints:
            continue

        updated_history.append(entry)
        existing_fingerprints.add(entry["fingerprint"])

    return updated_history


def main() -> None:
    load_dotenv()

    articles = fetch_articles(limit_per_source=8)

    if not articles:
        raise RuntimeError("No articles were fetched.")

    seen_article_ids = _load_seen_article_ids()
    article_history = _load_article_history()
    fresh_articles = _filter_fresh_articles(articles)
    fresh_unseen_articles = _filter_seen_articles(fresh_articles, seen_article_ids)

    if len(fresh_unseen_articles) >= 3:
        candidate_articles = fresh_unseen_articles
    else:
        candidate_articles = _filter_seen_articles(articles, seen_article_ids)

    if len(candidate_articles) < 3:
        candidate_articles = fresh_articles if len(fresh_articles) >= 3 else articles

    ranked_articles = rank_articles(candidate_articles, top_n=10)

    top_articles = apply_source_diversity(
        ranked_articles,
        max_per_source=1,
        final_count=4,
    )

    digest = create_markdown_digest(top_articles)

    print(digest)

    digest_dir = Path("digests")
    digest_dir.mkdir(exist_ok=True)

    digest_path = digest_dir / f"{date.today().isoformat()}.md"

    with digest_path.open("w", encoding="utf-8") as file:
        file.write(digest)

    send_to_discord(digest)

    updated_seen_article_ids = _mark_ranked_articles_as_seen(
        top_articles,
        seen_article_ids,
    )
    updated_article_history = _append_ranked_articles_to_history(
        top_articles,
        article_history,
    )

    _save_seen_article_ids(updated_seen_article_ids)
    _save_article_history(updated_article_history)


if __name__ == "__main__":
    main()