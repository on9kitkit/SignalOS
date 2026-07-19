from pathlib import Path

import pytest

from src.profile import (
    IntelligenceProfile,
    ProfileValidationError,
    default_profile,
    load_profile,
    profile_from_form_fields,
    profile_from_mapping,
    save_profile,
)
from src.state_store import write_json_atomic


def _custom_profile() -> IntelligenceProfile:
    return IntelligenceProfile(
        role="Independent AI product engineer",
        goals=["Ship a useful intelligence product"],
        active_projects=["SignalOS"],
        preferred_topics=["AI agents", "local inference"],
        excluded_topics=["celebrity news"],
        briefing_style="technical",
        current_focus="Find verifiable agent architecture improvements.",
    )


def test_missing_profile_returns_defaults_without_creating_file(
    tmp_path: Path,
) -> None:
    profile_path = tmp_path / "state" / "profile.json"

    assert load_profile(profile_path) == default_profile()
    assert not profile_path.exists()


def test_profile_save_load_round_trip(tmp_path: Path) -> None:
    profile_path = tmp_path / "state" / "profile.json"
    expected_profile = _custom_profile()

    save_profile(expected_profile, profile_path)

    assert load_profile(profile_path) == expected_profile


def test_profile_form_cleans_and_deduplicates_lists() -> None:
    profile = profile_from_form_fields({
        "role": "  AI   builder  ",
        "goals": " Ship product \n\nship PRODUCT\n Learn systems ",
        "active_projects": "SignalOS\n signalos \nRevision platform",
        "preferred_topics": " AI agents \nai AGENTS\nlocal inference",
        "excluded_topics": "hype\n HYPE ",
        "briefing_style": "concise",
        "current_focus": "  Improve   ranking quality. ",
    })

    assert profile.role == "AI builder"
    assert profile.goals == ["Ship product", "Learn systems"]
    assert profile.active_projects == ["SignalOS", "Revision platform"]
    assert profile.preferred_topics == ["AI agents", "local inference"]
    assert profile.excluded_topics == ["hype"]
    assert profile.current_focus == "Improve ranking quality."


def test_unsupported_briefing_style_is_rejected_or_replaced_safely(
    tmp_path: Path,
) -> None:
    with pytest.raises(ProfileValidationError, match="Unsupported briefing style"):
        profile_from_mapping(
            {**_custom_profile().to_dict(), "briefing_style": "ignore-contract"},
            strict=True,
        )

    profile_path = tmp_path / "profile.json"
    write_json_atomic(
        profile_path,
        {**_custom_profile().to_dict(), "briefing_style": "ignore-contract"},
    )

    assert load_profile(profile_path).briefing_style == "strategic"
