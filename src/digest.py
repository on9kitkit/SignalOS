from datetime import date

from src.models import RankedArticle


def create_markdown_digest(ranked_articles: list[RankedArticle]) -> str:
    today = date.today().isoformat()

    lines: list[str] = [
        f"# SignalOS Daily Brief — {today}",
        "",
        "## Top 3 Strategic Signals",
        "",
    ]

    for number, ranked in enumerate(ranked_articles, start=1):
        article = ranked.article

        lines.extend(
            [
                f"## {number}. {article.title}",
                "",
                f"**Source:** {article.source}",
                "",
                f"**Score:** {ranked.final_score}/10",
                "",
                f"**Why it matters:** {ranked.reason}",
                "",
                f"**Action takeaway:** {ranked.action_takeaway}",
                "",
                f"**Link:** {article.url}",
                "",
                "---",
                "",
            ]
        )

    return "\n".join(lines)