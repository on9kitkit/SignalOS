import asyncio
from pathlib import Path
from typing import Any

import httpx
import pytest

from src import web_app
from src.state_store import read_json_list, write_json_atomic


def _test_articles() -> list[dict[str, Any]]:
    return [
        {
            "digest_date": "2026-07-19",
            "fingerprint": f"article-{index}",
            "title": f"Test Signal {index}",
            "source": f"Test Source {index}",
            "final_score": 9.0 - (index / 10),
            "reason": f"Reason {index}",
            "action_takeaway": f"Action {index}",
            "url": f"https://example.test/articles/{index}",
        }
        for index in range(1, 5)
    ]


@pytest.fixture
def dashboard_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    state_dir = tmp_path / "state"
    article_history_path = state_dir / "article_history.json"
    feedback_path = state_dir / "feedback.json"
    weekly_report_dirs = (
        tmp_path / "weekly_reports",
        tmp_path / "src_weekly_reports",
    )
    articles = _test_articles()
    write_json_atomic(article_history_path, articles)

    monkeypatch.setattr(web_app, "STATE_DIR", state_dir)
    monkeypatch.setattr(web_app, "ARTICLE_HISTORY_PATH", article_history_path)
    monkeypatch.setattr(web_app, "FEEDBACK_PATH", feedback_path)
    monkeypatch.setattr(web_app, "WEEKLY_REPORT_DIRS", weekly_report_dirs)

    return {
        "articles": articles,
        "article_history_path": article_history_path,
        "feedback_path": feedback_path,
        "weekly_report_dirs": weekly_report_dirs,
    }


def _request(method: str, url: str, **kwargs: Any) -> httpx.Response:
    async def send_request() -> httpx.Response:
        transport = httpx.ASGITransport(app=web_app.app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
            follow_redirects=False,
        ) as client:
            return await client.request(method, url, **kwargs)

    return asyncio.run(send_request())


def test_dashboard_get_renders_four_articles(
    dashboard_paths: dict[str, Any],
) -> None:
    response = _request("GET", "/")

    assert response.status_code == 200
    assert "SignalOS Dashboard" in response.text
    assert response.text.count('<article class="article-card') == 4
    for article in dashboard_paths["articles"]:
        assert article["title"] in response.text


def test_valid_feedback_post_persists_and_redirects(
    dashboard_paths: dict[str, Any],
) -> None:
    response = _request(
        "POST",
        "/feedback",
        data={"fingerprint": "article-2", "rating": "5"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/?rated=1"

    feedback_entries = read_json_list(dashboard_paths["feedback_path"])
    assert len(feedback_entries) == 1
    assert feedback_entries[0]["fingerprint"] == "article-2"
    assert feedback_entries[0]["rating"] == 5
    assert feedback_entries[0]["title"] == "Test Signal 2"
    assert feedback_entries[0]["source"] == "Test Source 2"
    assert feedback_entries[0]["digest_date"] == "2026-07-19"
    assert feedback_entries[0]["created_at"]


def test_invalid_rating_redirects_without_writing_feedback(
    dashboard_paths: dict[str, Any],
) -> None:
    response = _request(
        "POST",
        "/feedback",
        data={"fingerprint": "article-1", "rating": "6"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert read_json_list(dashboard_paths["feedback_path"]) == []


def test_unknown_fingerprint_does_not_create_feedback(
    dashboard_paths: dict[str, Any],
) -> None:
    response = _request(
        "POST",
        "/feedback",
        data={"fingerprint": "unknown-article", "rating": "4"},
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert read_json_list(dashboard_paths["feedback_path"]) == []
