import json
import os
from typing import Any

from openai import OpenAI

from src.config import USER_PROFILE, get_ranker_model
from src.models import Article, RankedArticle


MAX_ARTICLE_SUMMARY_CHARS = 350
MAX_RANKER_OUTPUT_TOKENS = 4_000


def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Add it to SignalOS/.env or your shell environment."
        )

    return OpenAI(api_key=api_key)


def _normalise_prompt_text(value: str) -> str:
    return " ".join(value.split())


def _format_articles_for_prompt(articles: list[Article]) -> str:
    article_payload = [
        {
            "article_index": index,
            "title": _normalise_prompt_text(article.title),
            "source": _normalise_prompt_text(article.source),
            "published": _normalise_prompt_text(article.published),
            "summary": _normalise_prompt_text(article.summary)[
                :MAX_ARTICLE_SUMMARY_CHARS
            ],
        }
        for index, article in enumerate(articles)
    ]

    return json.dumps(
        article_payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _extract_ranker_payload(raw_text: str) -> list[dict[str, Any]]:
    cleaned_text = raw_text.strip()

    if cleaned_text.startswith("```"):
        cleaned_text = cleaned_text.removeprefix("```json").removeprefix("```")
        cleaned_text = cleaned_text.removesuffix("```").strip()

    try:
        parsed = json.loads(cleaned_text)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Ranker returned invalid JSON: {raw_text}") from error

    if isinstance(parsed, dict):
        articles = parsed.get("articles")
        if isinstance(articles, list):
            return [item for item in articles if isinstance(item, dict)]

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]

    raise RuntimeError("Ranker response must be a JSON object with an 'articles' list or a JSON list.")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_score(value: int, minimum: int = 0, maximum: int = 10) -> int:
    return max(minimum, min(maximum, value))


def _fallback_final_score(
    relevance_score: int,
    quality_score: int,
    importance_score: int,
) -> float:
    return (relevance_score * 0.45) + (quality_score * 0.25) + (importance_score * 0.30)


def _ranked_article_from_payload(
    payload: dict[str, Any],
    articles: list[Article],
) -> RankedArticle | None:
    article_index = _safe_int(
        payload.get("article_index", payload.get("index")),
        default=-1,
    )

    if article_index < 0 or article_index >= len(articles):
        return None

    relevance_score = _clamp_score(_safe_int(payload.get("relevance_score")))
    quality_score = _clamp_score(_safe_int(payload.get("quality_score")))
    importance_score = _clamp_score(_safe_int(payload.get("importance_score")))

    final_score = _safe_float(
        payload.get("final_score"),
        default=_fallback_final_score(
            relevance_score,
            quality_score,
            importance_score,
        ),
    )

    reason = str(payload.get("reason", "")).strip()
    action_takeaway = str(payload.get("action_takeaway", "")).strip()

    return RankedArticle(
        article=articles[article_index],
        relevance_score=relevance_score,
        quality_score=quality_score,
        importance_score=importance_score,
        final_score=final_score,
        reason=reason,
        action_takeaway=action_takeaway,
    )


def rank_articles(articles: list[Article], top_n: int = 3) -> list[RankedArticle]:
    if not articles:
        return []

    model_name = get_ranker_model()
    client = _get_openai_client()
    formatted_articles = _format_articles_for_prompt(articles)

    prompt = f"""
You are SignalOS, a strategic article-ranking engine.

User profile:
{USER_PROFILE}

Rank the provided articles for strategic value.

CRITICAL ANTI-HALLUCINATION RULES:
- You must only rank articles from the provided list.
- You must never invent or rewrite article titles, sources, URLs, dates, summaries, or facts.
- You must return article indexes only.
- Do not include title, source, URL, published date, or summary in your output.
- The Python application will attach the original article object using the returned index.

Scoring:
- relevance_score: integer from 0 to 10
- quality_score: integer from 0 to 10
- importance_score: integer from 0 to 10
- final_score: number from 0 to 10

Prioritise articles that affect:
- AI/ML progress
- local AI and Apple Silicon
- developer tools
- startups
- finance/economics affecting technology
- education SaaS opportunities
- practical project ideas

Reject:
- vague AI hype
- celebrity drama
- weak opinion pieces
- duplicate stories
- articles with no strategic value

Return at most {top_n} ranked objects as valid JSON.

Required JSON format:
{{
  "articles": [
    {{
      "article_index": 0,
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
{formatted_articles}
""".strip()

    response = client.responses.create(
        model=model_name,
        input=prompt,
        max_output_tokens=MAX_RANKER_OUTPUT_TOKENS,
    )

    payloads = _extract_ranker_payload(response.output_text)
    ranked_articles: list[RankedArticle] = []
    seen_indexes: set[int] = set()

    for payload in payloads:
        article_index = _safe_int(
            payload.get("article_index", payload.get("index")),
            default=-1,
        )

        if article_index in seen_indexes:
            continue

        ranked_article = _ranked_article_from_payload(payload, articles)

        if ranked_article is None:
            continue

        ranked_articles.append(ranked_article)
        seen_indexes.add(article_index)

    ranked_articles.sort(key=lambda item: item.final_score, reverse=True)
    return ranked_articles[:top_n]


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
