import hashlib
import json
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from src.delivery import send_to_discord
from src.digest import create_markdown_digest
from src.models import Article, RankedArticle
from src.news_fetcher import fetch_articles
from src.ranker import apply_source_diversity, rank_articles


STATE_DIR = Path(".signalos_state")
SEEN_ARTICLES_PATH = STATE_DIR / "seen_articles.json"
MAX_SEEN_ARTICLES = 300


def _normalise_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


def _article_fingerprint(article: Article) -> str:
    fingerprint_source = f"{_normalise_text(article.title)}|{article.url.strip()}"
    return hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()


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


def main() -> None:
    load_dotenv()

    articles = fetch_articles(limit_per_source=8)

    if not articles:
        raise RuntimeError("No articles were fetched.")

    seen_article_ids = _load_seen_article_ids()
    unseen_articles = _filter_seen_articles(articles, seen_article_ids)

    if len(unseen_articles) < 3:
        unseen_articles = articles

    ranked_articles = rank_articles(unseen_articles, top_n=10)

    top_articles = apply_source_diversity(
        ranked_articles,
        max_per_source=1,
        final_count=3,
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
    _save_seen_article_ids(updated_seen_article_ids)


if __name__ == "__main__":
    main()