import json
import os
from typing import Any

from openai import OpenAI

from src.config import USER_PROFILE
from src.models import Article, RankedArticle


def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Add it to SignalOS/.env or your shell environment."
        )

    return OpenAI(api_key=api_key)




def rank_articles(articles: list[Article], top_n: int = 3) -> list[RankedArticle]:
    client = _get_openai_client()
    article_payload = [
        {
            "index": index,
            "title": article.title,
            "source": article.source,
            "published": article.published,
            "summary": article.summary[:700],
            "url": article.url,
        }
        for index, article in enumerate(articles)
    ]

    prompt = f"""
You are a strategic intelligence analyst.

User profile:
{USER_PROFILE}

Rank the following articles.

Scoring:
- relevance_score: 0-10
- quality_score: 0-10
- importance_score: 0-10
- final_score: weighted score from 0-10

Prioritise articles that affect:
- AI/ML progress
- local AI and Apple Silicon
- developer tools
- startups
- finance/economics affecting technology
- education SaaS opportunities
- practical project ideas

Maximum 1 article per source in the final top 3

Reject:
- vague AI hype
- celebrity drama
- weak opinion pieces
- duplicate stories
- articles with no strategic value

Return exactly {top_n} articles as valid JSON.

Required JSON format:
{{
  "articles": [
    {{
      "index": 0,
      "relevance_score": 9,
      "quality_score": 8,
      "importance_score": 9,
      "final_score": 8.8,
      "reason": "Why this matters to the user.",
      "action_takeaway": "What the user should learn, build, or watch next."
    }}
  ]
}}

Articles:
{json.dumps(article_payload, ensure_ascii=False)}
"""

    response = client.responses.create(
        model="gpt-5.5",
        input=prompt,
    )

    data: dict[str, Any] = json.loads(response.output_text)
    ranked: list[RankedArticle] = []

    for item in data["articles"]:
        article = articles[item["index"]]
        ranked.append(
            RankedArticle(
                article=article,
                relevance_score=int(item["relevance_score"]),
                quality_score=int(item["quality_score"]),
                importance_score=int(item["importance_score"]),
                final_score=float(item["final_score"]),
                reason=str(item["reason"]),
                action_takeaway=str(item["action_takeaway"]),
            )
        )

    return sorted(ranked, key=lambda item: item.final_score, reverse=True)


def apply_source_diversity(
    ranked_articles: list[RankedArticle],
    max_per_source: int = 1,
    final_count: int = 3,
) -> list[RankedArticle]:
    selected: list[RankedArticle] = []
    source_counts: dict[str, int] = {}

    for ranked in ranked_articles:
        source = ranked.article.source
        current_count = source_counts.get(source, 0)

        if current_count >= max_per_source:
            continue

        selected.append(ranked)
        source_counts[source] = current_count + 1

        if len(selected) == final_count:
            break

    return selected