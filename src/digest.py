from datetime import date

from src.models import RankedArticle


FEEDBACK_SCALE: list[str] = [
    "1 = useless",
    "2 = weak",
    "3 = decent",
    "4 = useful",
    "5 = extremely useful",
]


def _article_lines(
    ranked_article: RankedArticle,
    article_number: int,
    total_articles: int,
) -> list[str]:
    article = ranked_article.article

    return [
        f"## Signal {article_number}/{total_articles}: {article.title}",
        "",
        f"**Source:** {article.source}",
        f"**Published:** {article.published}",
        f"**URL:** {article.url}",
        "",
        "**Scores**",
        f"- Relevance: {ranked_article.relevance_score}/10",
        f"- Quality: {ranked_article.quality_score}/10",
        f"- Importance: {ranked_article.importance_score}/10",
        f"- Final score: {ranked_article.final_score:.2f}/10",
        "",
        "**Why it matters**",
        ranked_article.reason,
        "",
        "**Action takeaway**",
        ranked_article.action_takeaway,
        "",
    ]


def _article_feedback_lines(article_number: int) -> list[str]:
    return [
        "**Feedback for this article**",
        f"Reply with `Article {article_number}: <1-5>`",
        "",
        *[f"- {rating}" for rating in FEEDBACK_SCALE],
        "",
        "Optional: add what should be more or less included.",
        "",
    ]


def create_markdown_digest(ranked_articles: list[RankedArticle]) -> str:
    today = date.today().isoformat()
    signal_count = len(ranked_articles)

    lines: list[str] = [
        f"# SignalOS Daily Brief — {today}",
        "",
        f"## Top {signal_count} Strategic Signals",
        "",
    ]

    for index, ranked_article in enumerate(ranked_articles, start=1):
        lines.extend(_article_lines(ranked_article, index, signal_count))
        lines.extend(_article_feedback_lines(index))
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def create_article_feedback_messages(
    ranked_articles: list[RankedArticle],
) -> list[str]:
    today = date.today().isoformat()
    total_articles = len(ranked_articles)
    messages: list[str] = []

    for index, ranked_article in enumerate(ranked_articles, start=1):
        lines: list[str] = [
            f"# SignalOS Daily Brief — {today}",
            "",
            f"Part {index}/{total_articles}",
            "",
        ]
        lines.extend(_article_lines(ranked_article, index, total_articles))
        lines.extend(_article_feedback_lines(index))
        messages.append("\n".join(lines))

    return messages