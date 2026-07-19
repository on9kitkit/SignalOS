from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Mapping, cast

from src.state_store import StateCorruptionError, read_json_dict, write_json_atomic


BriefingStyle = Literal[
    "concise",
    "strategic",
    "technical",
    "opportunity-focused",
]

SUPPORTED_BRIEFING_STYLES: tuple[BriefingStyle, ...] = (
    "concise",
    "strategic",
    "technical",
    "opportunity-focused",
)
PROFILE_PATH = Path(".signalos_state/profile.json")
MAX_PROFILE_PAYLOAD_BYTES = 24_000
MAX_ROLE_CHARS = 160
MAX_CURRENT_FOCUS_CHARS = 800
MAX_LIST_ITEM_CHARS = 160
MAX_GOALS = 12
MAX_ACTIVE_PROJECTS = 12
MAX_PREFERRED_TOPICS = 20
MAX_EXCLUDED_TOPICS = 20


class ProfileValidationError(ValueError):
    """Raised when submitted profile data cannot be accepted safely."""


@dataclass(frozen=True)
class IntelligenceProfile:
    role: str
    goals: list[str]
    active_projects: list[str]
    preferred_topics: list[str]
    excluded_topics: list[str]
    briefing_style: BriefingStyle
    current_focus: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "goals": list(self.goals),
            "active_projects": list(self.active_projects),
            "preferred_topics": list(self.preferred_topics),
            "excluded_topics": list(self.excluded_topics),
            "briefing_style": self.briefing_style,
            "current_focus": self.current_focus,
        }


def default_profile() -> IntelligenceProfile:
    return IntelligenceProfile(
        role="Student-builder and software engineer",
        goals=[
            "Build a collaborative education SaaS",
            "Improve AI and data science skills",
            "Find commercially useful technology shifts",
        ],
        active_projects=[
            "SignalOS",
            "Multiplayer revision platform",
            "Local AI experiments on Apple Silicon",
        ],
        preferred_topics=[
            "AI agents",
            "developer tools",
            "education technology",
            "local inference",
            "AI economics",
        ],
        excluded_topics=[
            "celebrity news",
            "generic gadget announcements",
        ],
        briefing_style="strategic",
        current_focus=(
            "Prioritise developments that could create a product or technical "
            "advantage this month."
        ),
    )


def _clean_text(
    value: Any,
    fallback: str,
    maximum_chars: int,
    *,
    strict: bool,
    allow_empty: bool,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        if strict:
            raise ProfileValidationError(f"{field_name} must be text.")
        return fallback

    cleaned = " ".join(value.split())
    if not cleaned and not allow_empty:
        if strict:
            raise ProfileValidationError(f"{field_name} cannot be empty.")
        return fallback

    if len(cleaned) > maximum_chars:
        if strict:
            raise ProfileValidationError(
                f"{field_name} must be {maximum_chars} characters or fewer."
            )
        return cleaned[:maximum_chars].rstrip()

    return cleaned


def _clean_list(
    value: Any,
    fallback: list[str],
    maximum_items: int,
    *,
    strict: bool,
    field_name: str,
) -> list[str]:
    if not isinstance(value, list):
        if strict:
            raise ProfileValidationError(f"{field_name} must be a list.")
        return list(fallback)

    cleaned_items: list[str] = []
    seen_items: set[str] = set()

    for item in value:
        if not isinstance(item, str):
            if strict:
                raise ProfileValidationError(
                    f"Every {field_name} item must be text."
                )
            continue

        cleaned = " ".join(item.split())
        if not cleaned:
            continue
        if len(cleaned) > MAX_LIST_ITEM_CHARS:
            if strict:
                raise ProfileValidationError(
                    f"Each {field_name} item must be {MAX_LIST_ITEM_CHARS} "
                    "characters or fewer."
                )
            cleaned = cleaned[:MAX_LIST_ITEM_CHARS].rstrip()

        deduplication_key = cleaned.casefold()
        if deduplication_key in seen_items:
            continue

        if len(cleaned_items) >= maximum_items:
            if strict:
                raise ProfileValidationError(
                    f"{field_name} supports at most {maximum_items} items."
                )
            break

        cleaned_items.append(cleaned)
        seen_items.add(deduplication_key)

    return cleaned_items


def profile_from_mapping(
    values: Mapping[str, Any],
    *,
    strict: bool = False,
) -> IntelligenceProfile:
    defaults = default_profile()
    style_value = values.get("briefing_style", defaults.briefing_style)

    if style_value not in SUPPORTED_BRIEFING_STYLES:
        if strict:
            raise ProfileValidationError("Unsupported briefing style.")
        style_value = defaults.briefing_style

    return IntelligenceProfile(
        role=_clean_text(
            values.get("role", defaults.role),
            defaults.role,
            MAX_ROLE_CHARS,
            strict=strict,
            allow_empty=False,
            field_name="Role",
        ),
        goals=_clean_list(
            values.get("goals", defaults.goals),
            defaults.goals,
            MAX_GOALS,
            strict=strict,
            field_name="goals",
        ),
        active_projects=_clean_list(
            values.get("active_projects", defaults.active_projects),
            defaults.active_projects,
            MAX_ACTIVE_PROJECTS,
            strict=strict,
            field_name="active projects",
        ),
        preferred_topics=_clean_list(
            values.get("preferred_topics", defaults.preferred_topics),
            defaults.preferred_topics,
            MAX_PREFERRED_TOPICS,
            strict=strict,
            field_name="preferred topics",
        ),
        excluded_topics=_clean_list(
            values.get("excluded_topics", defaults.excluded_topics),
            defaults.excluded_topics,
            MAX_EXCLUDED_TOPICS,
            strict=strict,
            field_name="excluded topics",
        ),
        briefing_style=cast(BriefingStyle, style_value),
        current_focus=_clean_text(
            values.get("current_focus", defaults.current_focus),
            defaults.current_focus,
            MAX_CURRENT_FOCUS_CHARS,
            strict=strict,
            allow_empty=True,
            field_name="Current focus",
        ),
    )


def profile_from_form_fields(values: Mapping[str, str]) -> IntelligenceProfile:
    profile_values: dict[str, Any] = dict(values)
    for field_name in (
        "goals",
        "active_projects",
        "preferred_topics",
        "excluded_topics",
    ):
        profile_values[field_name] = values.get(field_name, "").splitlines()

    return profile_from_mapping(profile_values, strict=True)


def load_profile(path: Path = PROFILE_PATH) -> IntelligenceProfile:
    try:
        stored_profile = read_json_dict(path)
    except StateCorruptionError:
        return default_profile()

    return profile_from_mapping(stored_profile)


def save_profile(
    profile: IntelligenceProfile,
    path: Path = PROFILE_PATH,
) -> None:
    write_json_atomic(path, profile.to_dict())
