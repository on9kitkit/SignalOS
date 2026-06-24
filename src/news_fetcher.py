from typing import Iterable
import feedparser

from src.models import Article


RSS_FEEDS: dict[str, str] = {
    "OpenAI Blog": "https://openai.com/news/rss.xml",
    "Anthropic News": "https://www.anthropic.com/news/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
}


def fetch_articles(limit_per_source: int = 10) -> list[Article]:
    articles: list[Article] = []

    for source, feed_url in RSS_FEEDS.items():
        feed = feedparser.parse(feed_url)

        for entry in feed.entries[:limit_per_source]:
            article = Article(
                title=getattr(entry, "title", "").strip(),
                url=getattr(entry, "link", "").strip(),
                source=source,
                published=getattr(entry, "published", "Unknown"),
                summary=getattr(entry, "summary", "").strip(),
            )

            if article.title and article.url:
                articles.append(article)

    return articles