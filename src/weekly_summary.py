import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from src.delivery import send_to_discord


STATE_DIR = Path(".signalos_state")
ARTICLE_HISTORY_PATH = STATE_DIR / "article_history.json"
WEEKLY_REPORTS_DIR = Path("weekly_reports")
WEEKLY_LOOKBACK_DAYS = 7
MODEL_NAME = "gpt-5.5"


def _get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Add it to SignalOS/.env or GitHub Secrets."
        )

    return OpenAI(api_key=api_key)


def _load_article_history() -> list[dict[str, Any]]:
    if not ARTICLE_HISTORY_PATH.exists():
        raise RuntimeError(
            "article_history.json does not exist yet. Run the daily agent first."
        )

    with ARTICLE_HISTORY_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise RuntimeError("article_history.json must contain a JSON list.")

    return [item for item in data if isinstance(item, dict)]


def _parse_digest_date(entry: dict[str, Any]) -> date | None:
    raw_date = entry.get("digest_date")

    if not isinstance(raw_date, str):
        return None

    try:
        return date.fromisoformat(raw_date)
    except ValueError:
        return None


def _filter_recent_history(
    article_history: list[dict[str, Any]],
    lookback_days: int = WEEKLY_LOOKBACK_DAYS,
) -> list[dict[str, Any]]:
    cutoff = datetime.now().date() - timedelta(days=lookback_days)
    recent_items: list[dict[str, Any]] = []

    for entry in article_history:
        digest_date = _parse_digest_date(entry)

        if digest_date is None:
            continue

        if digest_date >= cutoff:
            recent_items.append(entry)

    return recent_items


def _format_history_for_prompt(article_history: list[dict[str, Any]]) -> str:
    formatted_items: list[str] = []

    for index, entry in enumerate(article_history, start=1):
        formatted_items.append(
            "\n".join(
                [
                    f"Article {index}",
                    f"Date: {entry.get('digest_date', 'Unknown')}",
                    f"Title: {entry.get('title', 'Unknown')}",
                    f"Source: {entry.get('source', 'Unknown')}",
                    f"URL: {entry.get('url', 'Unknown')}",
                    f"Reason: {entry.get('reason', 'Unknown')}",
                    f"Action takeaway: {entry.get('action_takeaway', 'Unknown')}",
                ]
            )
        )

    return "\n\n".join(formatted_items)


def create_weekly_summary(article_history: list[dict[str, Any]]) -> str:
    if not article_history:
        raise RuntimeError("No recent article history available for weekly summary.")

    client = _get_openai_client()
    formatted_history = _format_history_for_prompt(article_history)

    prompt = f"""
You are SignalOS, a strategic intelligence analyst for an ambitious student-builder working on AI, Python, local LLMs, education SaaS, data science, and software projects.

Create a weekly intelligence report from the selected daily articles below.

Do not summarise every article one by one. Identify patterns, opportunities, and what the user should do next.

Return Markdown using exactly this structure:

# SignalOS Weekly Intelligence Report

## 1. Executive Brief
A short paragraph explaining the biggest shift this week.

## 2. Key Patterns
- 3 to 5 bullet points explaining repeated themes.

## 3. Highest-Leverage Opportunity
Explain the single best opportunity for a student-builder to exploit.

## 4. Skill Compounding Plan
- 3 concrete skills or concepts the user should learn or build next.

## 5. Build Action For Next Week
A specific project action the user can actually complete next week.

## 6. Watchlist
- 3 things to monitor next week.

Article history:
{formatted_history}
""".strip()

    response = client.responses.create(
        model=MODEL_NAME,
        input=prompt,
    )

    return response.output_text.strip()


def save_weekly_summary(summary: str) -> Path:
    WEEKLY_REPORTS_DIR.mkdir(exist_ok=True)
    report_path = WEEKLY_REPORTS_DIR / f"{date.today().isoformat()}.md"

    with report_path.open("w", encoding="utf-8") as file:
        file.write(summary)

    return report_path


def main() -> None:
    load_dotenv()

    article_history = _load_article_history()
    recent_history = _filter_recent_history(article_history)
    summary = create_weekly_summary(recent_history)

    print(summary)
    save_weekly_summary(summary)
    send_to_discord(summary)


if __name__ == "__main__":
    main()
