from pathlib import Path

import pytest

from src.state_store import (
    StateCorruptionError,
    locked_update_json_list,
    read_json_list,
    write_json_atomic,
)


def test_read_missing_json_list_returns_empty(tmp_path: Path) -> None:
    state_path = tmp_path / "state" / "missing.json"

    assert read_json_list(state_path) == []


def test_write_then_read_preserves_data(tmp_path: Path) -> None:
    state_path = tmp_path / "state" / "items.json"
    items = [
        {"fingerprint": "article-1", "rating": 4},
        {"fingerprint": "article-2", "rating": 5},
    ]

    write_json_atomic(state_path, items)

    assert read_json_list(state_path) == items


def test_locked_update_can_upsert_without_duplicates(tmp_path: Path) -> None:
    state_path = tmp_path / "state" / "feedback.json"
    write_json_atomic(
        state_path,
        [
            {"fingerprint": "article-1", "rating": 1},
            {"fingerprint": "article-2", "rating": 3},
        ],
    )

    def upsert(items: list[object]) -> list[object]:
        updated_items = [
            item
            for item in items
            if not (
                isinstance(item, dict)
                and item.get("fingerprint") == "article-1"
            )
        ]
        updated_items.append({"fingerprint": "article-1", "rating": 5})
        return updated_items

    updated_items = locked_update_json_list(state_path, upsert)

    assert updated_items == [
        {"fingerprint": "article-2", "rating": 3},
        {"fingerprint": "article-1", "rating": 5},
    ]
    assert read_json_list(state_path) == updated_items
    assert sum(
        item.get("fingerprint") == "article-1"
        for item in updated_items
        if isinstance(item, dict)
    ) == 1


def test_read_corrupt_json_list_raises_corruption_error(tmp_path: Path) -> None:
    state_path = tmp_path / "state" / "corrupt.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(StateCorruptionError, match="malformed JSON"):
        read_json_list(state_path)
