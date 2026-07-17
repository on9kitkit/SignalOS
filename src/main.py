import hashlib
from collections import deque
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv

from src.delivery import send_to_discord
from src.digest import create_article_feedback_messages, create_markdown_digest
from src.models import Article, RankedArticle
from src.news_fetcher import fetch_articles
from src.ranker import apply_source_diversity, rank_articles
from src.state_store import locked_update_json_list, read_json_list


STATE_DIR = Path(".signalos_state")
SEEN_ARTICLES_PATH = STATE_DIR / "seen_articles.json"
ARTICLE_HISTORY_PATH = STATE_DIR / "article_history.json"
MAX_SEEN_ARTICLES = 300
MAX_ARTICLE_HISTORY_ITEMS = 90
FRESH_ARTICLE_WINDOW_DAYS = 3
MAX_RANKING_CANDIDATES = 32
TRACKING_QUERY_PARAMETERS: frozenset[str] = frozenset({
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
})


def _normalise_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _normalise_url_for_deduplication(url: str) -> str | None:
    try:
        parsed_url = urlsplit(url.strip())
    except ValueError:
        return None

    scheme = parsed_url.scheme.lower()
    try:
        hostname = parsed_url.hostname
        port = parsed_url.port
    except ValueError:
        return None

    if scheme not in {"http", "https"} or hostname is None:
        return None

    normalised_host = hostname.lower()
    if ":" in normalised_host:
        normalised_host = f"[{normalised_host}]"

    is_default_port = (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    )
    netloc = (
        normalised_host
        if port is None or is_default_port
        else f"{normalised_host}:{port}"
    )

    query_items = [
        (key, value)
        for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_PARAMETERS
    ]
    normalised_query = urlencode(
        sorted(query_items, key=lambda item: (item[0].lower(), item[1])),
        doseq=True,
    )
    path = parsed_url.path or "/"

    if path == "/" and not normalised_query:
        return None

    return urlunsplit((scheme, netloc, path, normalised_query, ""))


def _article_deduplication_key(article: Article) -> tuple[str, str]:
    normalised_url = _normalise_url_for_deduplication(article.url)
    if normalised_url is not None:
        return ("url", normalised_url)

    return ("title", _normalise_text(article.title))


def _deduplicate_articles(articles: list[Article]) -> list[Article]:
    deduplicated_articles: list[Article] = []
    seen_keys: set[tuple[str, str]] = set()

    for article in articles:
        deduplication_key = _article_deduplication_key(article)
        if deduplication_key in seen_keys:
            continue

        deduplicated_articles.append(article)
        seen_keys.add(deduplication_key)

    return deduplicated_articles


def _select_source_balanced_articles(
    articles: list[Article],
    limit: int = MAX_RANKING_CANDIDATES,
) -> list[Article]:
    if limit <= 0:
        return []

    articles_by_source: dict[str, deque[Article]] = {}
    for article in articles:
        articles_by_source.setdefault(article.source, deque()).append(article)

    active_sources = list(articles_by_source)
    selected_articles: list[Article] = []

    while active_sources and len(selected_articles) < limit:
        next_active_sources: list[str] = []

        for source in active_sources:
            source_articles = articles_by_source[source]
            selected_articles.append(source_articles.popleft())

            if source_articles:
                next_active_sources.append(source)

            if len(selected_articles) == limit:
                break

        active_sources = next_active_sources

    return selected_articles


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
    data = read_json_list(SEEN_ARTICLES_PATH)
    return [str(item) for item in data]


def _save_seen_article_ids(seen_article_ids: list[str]) -> None:
    def merge_seen_ids(current_items: list[Any]) -> list[Any]:
        merged_ids: list[Any] = [str(item) for item in current_items]
        merged_lookup = set(merged_ids)

        for article_id in seen_article_ids:
            if article_id not in merged_lookup:
                merged_ids.append(article_id)
                merged_lookup.add(article_id)

        return merged_ids[-MAX_SEEN_ARTICLES:]

    locked_update_json_list(SEEN_ARTICLES_PATH, merge_seen_ids)


def _load_article_history() -> list[dict[str, Any]]:
    data = read_json_list(ARTICLE_HISTORY_PATH)
    return [item for item in data if isinstance(item, dict)]


def _save_article_history(article_history: list[dict[str, Any]]) -> None:
    def merge_article_history(current_items: list[Any]) -> list[Any]:
        merged_history: list[Any] = [
            item for item in current_items if isinstance(item, dict)
        ]
        existing_fingerprints = {
            str(item.get("fingerprint"))
            for item in merged_history
            if item.get("fingerprint")
        }

        for item in article_history:
            fingerprint = item.get("fingerprint")
            if fingerprint:
                fingerprint_text = str(fingerprint)
                if fingerprint_text in existing_fingerprints:
                    continue
                existing_fingerprints.add(fingerprint_text)
            elif item in merged_history:
                continue

            merged_history.append(item)

        return merged_history[-MAX_ARTICLE_HISTORY_ITEMS:]

    locked_update_json_list(ARTICLE_HISTORY_PATH, merge_article_history)


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
    print(f"Articles fetched: {len(articles)}")

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

    deduplicated_articles = _deduplicate_articles(candidate_articles)
    ranking_candidates = _select_source_balanced_articles(deduplicated_articles)

    print(f"Articles after normal filtering: {len(candidate_articles)}")
    print(f"Articles after deduplication: {len(deduplicated_articles)}")
    print(f"Articles submitted for ranking: {len(ranking_candidates)}")

    ranked_articles = rank_articles(ranking_candidates, top_n=10)

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

    for article_message in create_article_feedback_messages(top_articles):
        send_to_discord(article_message)

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
