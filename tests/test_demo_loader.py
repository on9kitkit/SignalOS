import json
from pathlib import Path

import pytest

from scripts import load_demo_data


def _demo_repository(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    demo_directory = tmp_path / "demo_data"
    demo_directory.mkdir()
    profile = {
        "role": "Synthetic demo builder",
        "goals": ["Ship a demo"],
        "active_projects": ["SignalOS"],
        "preferred_topics": ["AI agents"],
        "excluded_topics": ["noise"],
        "briefing_style": "strategic",
        "current_focus": "Prepare a reviewer briefing.",
    }

    (demo_directory / "article_history.json").write_text("[]\n", encoding="utf-8")
    (demo_directory / "feedback.json").write_text("[]\n", encoding="utf-8")
    (demo_directory / "weekly_report.md").write_text("# Demo\n", encoding="utf-8")
    (demo_directory / "profile.json").write_text(
        json.dumps(profile),
        encoding="utf-8",
    )
    return tmp_path, profile


def test_demo_loader_installs_profile_json(tmp_path: Path) -> None:
    repository_root, expected_profile = _demo_repository(tmp_path)

    created_files = load_demo_data._copy_demo_files(repository_root, force=False)
    profile_path = repository_root / ".signalos_state" / "profile.json"

    assert profile_path in created_files
    assert json.loads(profile_path.read_text(encoding="utf-8")) == expected_profile


def test_demo_profile_preserves_refuse_and_force_behavior(tmp_path: Path) -> None:
    repository_root, expected_profile = _demo_repository(tmp_path)
    load_demo_data._copy_demo_files(repository_root, force=False)
    profile_path = repository_root / ".signalos_state" / "profile.json"
    profile_path.write_text('{"role": "Keep me"}\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        load_demo_data._copy_demo_files(repository_root, force=False)

    assert json.loads(profile_path.read_text(encoding="utf-8")) == {
        "role": "Keep me",
    }

    load_demo_data._copy_demo_files(repository_root, force=True)
    assert json.loads(profile_path.read_text(encoding="utf-8")) == expected_profile
