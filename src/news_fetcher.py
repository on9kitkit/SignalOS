import feedparser
from src.models import Article


RSS_FEEDS: dict[str, str] = {
    # AI labs and model platforms
    "OpenAI News": "https://openai.com/news/rss.xml",
    "Anthropic News": "https://www.anthropic.com/news/rss.xml",
    "Google DeepMind": "https://deepmind.google/blog/rss.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "Apple Machine Learning Research": "https://machinelearning.apple.com/rss.xml",

    # Developer tooling and engineering infrastructure
    "GitHub Blog": "https://github.blog/feed/",
    "Cloudflare Blog": "https://blog.cloudflare.com/rss/",

    # AI, startup, and technology news
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "MIT Technology Review AI": "https://www.technologyreview.com/topic/artificial-intelligence/feed/",

    # UK-relevant business, technology, and education context
    "BBC Technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "BBC Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "BBC Education": "https://feeds.bbci.co.uk/news/education/rss.xml",
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