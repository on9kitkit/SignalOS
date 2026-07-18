import json
from types import SimpleNamespace
from typing import Any

import pytest

from src import main, ranker
from src.models import Article


def _article(index: int, source: str | None = None) -> Article:
    return Article(
        title=f"Original title {index}",
        url=f"https://example.test/original/{index}",
        source=source or f"Source {index}",
        published="2026-07-19T08:00:00Z",
        summary=f"Original summary {index}",
    )


def _mock_ranker_response(
    monkeypatch: pytest.MonkeyPatch,
    payloads: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    class FakeResponses:
        def create(self, **kwargs: Any) -> SimpleNamespace:
            calls.append(kwargs)
            return SimpleNamespace(
                output_text=json.dumps({"articles": payloads}),
            )

    fake_client = SimpleNamespace(responses=FakeResponses())
    monkeypatch.setattr(ranker, "_get_openai_client", lambda: fake_client)
    monkeypatch.setattr(ranker, "get_ranker_model", lambda: "test-ranker-model")
    return calls


def _ranking_payload(article_index: int, **metadata: Any) -> dict[str, Any]:
    return {
        "article_index": article_index,
        "relevance_score": 9,
        "quality_score": 8,
        "importance_score": 9,
        "final_score": 8.8,
        "reason": "Test reason",
        "action_takeaway": "Test action",
        **metadata,
    }


def test_candidate_preselection_never_exceeds_configured_cap() -> None:
    articles = [
        _article(index, source=f"Source {index % 7}")
        for index in range(main.MAX_RANKING_CANDIDATES + 15)
    ]

    selected = main._select_source_balanced_articles(articles)

    assert len(selected) == main.MAX_RANKING_CANDIDATES
    assert len(selected) <= main.MAX_RANKING_CANDIDATES


def test_ranked_output_preserves_original_article_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    articles = [_article(1), _article(2)]
    calls = _mock_ranker_response(monkeypatch, [_ranking_payload(1)])

    ranked_articles = ranker.rank_articles(articles, top_n=1)

    assert len(calls) == 1
    assert len(ranked_articles) == 1
    assert ranked_articles[0].article is articles[1]
    assert ranked_articles[0].article.title == "Original title 2"
    assert ranked_articles[0].article.url == "https://example.test/original/2"
    assert ranked_articles[0].article.source == "Source 2"


def test_model_metadata_cannot_override_trusted_index_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    articles = [_article(1), _article(2)]
    _mock_ranker_response(
        monkeypatch,
        [
            _ranking_payload(
                0,
                title="Model-generated title",
                url="https://model-generated.invalid/article",
                source="Model-generated source",
            ),
            _ranking_payload(99, title="Out-of-range article"),
        ],
    )

    ranked_articles = ranker.rank_articles(articles, top_n=2)

    assert len(ranked_articles) == 1
    assert ranked_articles[0].article is articles[0]
    assert ranked_articles[0].article.title == "Original title 1"
    assert ranked_articles[0].article.url == "https://example.test/original/1"
    assert ranked_articles[0].article.source == "Source 1"
