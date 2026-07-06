from datetime import date

from src.models import RankedArticle


def create_markdown_digest(ranked_articles: list[RankedArticle]) -> str:
    today = date.today().isoformat()

    signal_count = len(ranked_articles)

    lines: list[str] = [
        f"# SignalOS Daily Brief — {today}",
        "",
        f"## Top {signal_count} Strategic Signals",
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

    lines.extend(
        [
            "## Feedback",
            "",
            "Rate today's digest from 1–5:",
            "",
            "- 1 = useless",
            "- 2 = weak",
            "- 3 = decent",
            "- 4 = useful",
            "- 5 = extremely useful",
            "",
            "Optional: reply with what should be more or less included.",
            "",
        ]
    )

    return "\n".join(lines)