from dataclasses import dataclass


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    source: str
    published: str
    summary: str


@dataclass(frozen=True)
class RankedArticle:
    article: Article
    relevance_score: int
    quality_score: int
    importance_score: int
    final_score: float
    reason: str
    action_takeaway: str