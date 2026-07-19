from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any


ARTICLE_REQUIRED_FIELDS = frozenset({
    "digest_date",
    "fingerprint",
    "title",
    "source",
    "url",
    "final_score",
    "reason",
    "action_takeaway",
})
FEEDBACK_REQUIRED_FIELDS = frozenset({
    "created_at",
    "digest_date",
    "fingerprint",
    "title",
    "source",
    "rating",
})
PROFILE_REQUIRED_FIELDS = frozenset({
    "role",
    "goals",
    "active_projects",
    "preferred_topics",
    "excluded_topics",
    "briefing_style",
    "current_focus",
})
PROFILE_LIST_FIELDS = (
    "goals",
    "active_projects",
    "preferred_topics",
    "excluded_topics",
)
SUPPORTED_BRIEFING_STYLES = frozenset({
    "concise",
    "strategic",
    "technical",
    "opportunity-focused",
})


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load deterministic synthetic data for the SignalOS dashboard.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing demo-loaded runtime files.",
    )
    return parser.parse_args()


def _load_json_list(path: Path, required_fields: frozenset[str]) -> list[dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as source_file:
            value = json.load(source_file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot load demo fixture '{path.name}': {type(error).__name__}") from None

    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise RuntimeError(f"Demo fixture '{path.name}' must contain a JSON list of objects.")

    records = list(value)
    for index, record in enumerate(records, start=1):
        missing_fields = required_fields.difference(record)
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise RuntimeError(
                f"Demo fixture '{path.name}' record {index} is missing: {missing}.",
            )

    return records


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as source_file:
            value = json.load(source_file)
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Cannot load demo fixture '{path.name}': {type(error).__name__}") from None

    if not isinstance(value, dict):
        raise RuntimeError(f"Demo fixture '{path.name}' must contain a JSON object.")

    return value


def _validate_fixtures(demo_data_directory: Path) -> None:
    articles = _load_json_list(
        demo_data_directory / "article_history.json",
        ARTICLE_REQUIRED_FIELDS,
    )
    feedback = _load_json_list(
        demo_data_directory / "feedback.json",
        FEEDBACK_REQUIRED_FIELDS,
    )
    profile = _load_json_object(demo_data_directory / "profile.json")

    if len(articles) != 4:
        raise RuntimeError("Demo article history must contain exactly four records.")
    if not 1 <= len(feedback) <= 2:
        raise RuntimeError("Demo feedback must contain one or two records.")

    article_fingerprints = {str(article["fingerprint"]) for article in articles}
    feedback_fingerprints = {str(entry["fingerprint"]) for entry in feedback}
    if not feedback_fingerprints.issubset(article_fingerprints):
        raise RuntimeError("Demo feedback refers to an unknown article fingerprint.")
    if len(article_fingerprints - feedback_fingerprints) < 2:
        raise RuntimeError("At least two demo articles must remain unrated.")

    missing_profile_fields = PROFILE_REQUIRED_FIELDS.difference(profile)
    if missing_profile_fields:
        missing = ", ".join(sorted(missing_profile_fields))
        raise RuntimeError(f"Demo profile is missing: {missing}.")
    if not isinstance(profile["role"], str) or not profile["role"].strip():
        raise RuntimeError("Demo profile role must be non-empty text.")
    if not isinstance(profile["current_focus"], str):
        raise RuntimeError("Demo profile current focus must be text.")
    if (
        not isinstance(profile["briefing_style"], str)
        or profile["briefing_style"] not in SUPPORTED_BRIEFING_STYLES
    ):
        raise RuntimeError("Demo profile has an unsupported briefing style.")
    for field_name in PROFILE_LIST_FIELDS:
        field_value = profile[field_name]
        if not isinstance(field_value, list) or not all(
            isinstance(item, str) and item.strip() for item in field_value
        ):
            raise RuntimeError(
                f"Demo profile {field_name} must be a list of non-empty strings."
            )


def _copy_demo_files(repository_root: Path, force: bool) -> list[Path]:
    demo_data_directory = repository_root / "demo_data"
    state_directory = repository_root / ".signalos_state"
    weekly_reports_directory = repository_root / "weekly_reports"
    copies = (
        (
            demo_data_directory / "article_history.json",
            state_directory / "article_history.json",
        ),
        (
            demo_data_directory / "feedback.json",
            state_directory / "feedback.json",
        ),
        (
            demo_data_directory / "profile.json",
            state_directory / "profile.json",
        ),
        (
            demo_data_directory / "weekly_report.md",
            weekly_reports_directory / "demo-weekly-report.md",
        ),
    )

    existing_destinations = [destination for _, destination in copies if destination.exists()]
    if existing_destinations and not force:
        existing = ", ".join(str(path.relative_to(repository_root)) for path in existing_destinations)
        raise RuntimeError(
            f"Refusing to overwrite existing runtime files: {existing}. Use --force to replace them.",
        )

    state_directory.mkdir(parents=True, exist_ok=True)
    weekly_reports_directory.mkdir(parents=True, exist_ok=True)

    created_files: list[Path] = []
    for source, destination in copies:
        shutil.copyfile(source, destination)
        created_files.append(destination)

    return created_files


def main() -> int:
    arguments = _parse_arguments()
    repository_root = Path(__file__).resolve().parents[1]

    try:
        _validate_fixtures(repository_root / "demo_data")
        created_files = _copy_demo_files(repository_root, force=arguments.force)
    except RuntimeError as error:
        print(f"Demo data load failed: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Demo data load failed: {type(error).__name__}", file=sys.stderr)
        return 1

    for path in created_files:
        print(f"Created: {path.relative_to(repository_root)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
