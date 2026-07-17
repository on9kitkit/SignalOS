from __future__ import annotations

import fcntl
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator


JsonList = list[Any]
JsonDict = dict[str, Any]
JsonListUpdater = Callable[[JsonList], JsonList]
JsonDictUpdater = Callable[[JsonDict], JsonDict]


class StateStoreError(RuntimeError):
    """A sanitized state-storage failure."""

    def __init__(self, path: Path, category: str) -> None:
        super().__init__(f"State storage failed for '{path.name}': {category}")


class StateCorruptionError(RuntimeError):
    """Raised when an existing state file is not valid JSON of the expected type."""

    def __init__(self, path: Path, category: str) -> None:
        super().__init__(f"State file '{path.name}' is corrupt: {category}")


_MISSING = object()


def _read_json_value(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as state_file:
            return json.load(state_file)
    except FileNotFoundError:
        return _MISSING
    except json.JSONDecodeError:
        raise StateCorruptionError(path, "malformed JSON") from None
    except UnicodeDecodeError:
        raise StateCorruptionError(path, "invalid UTF-8") from None
    except OSError:
        raise StateStoreError(path, "read error") from None


def read_json_list(path: Path) -> JsonList:
    """Read a JSON list, returning an empty list when the file is missing."""
    value = _read_json_value(path)
    if value is _MISSING:
        return []
    if not isinstance(value, list):
        raise StateCorruptionError(path, "expected JSON list")
    return value


def read_json_dict(path: Path) -> JsonDict:
    """Read a JSON object, returning an empty dictionary when the file is missing."""
    value = _read_json_value(path)
    if value is _MISSING:
        return {}
    if not isinstance(value, dict):
        raise StateCorruptionError(path, "expected JSON object")
    return value


def _backup_valid_state(path: Path) -> None:
    value = _read_json_value(path)
    if value is _MISSING:
        return

    backup_path = path.with_name(f"{path.name}.bak")
    try:
        shutil.copy2(path, backup_path)
    except OSError:
        raise StateStoreError(path, "backup error") from None


def write_json_atomic(path: Path, value: Any) -> None:
    """Write JSON through a flushed same-directory temporary file and atomic replace."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise StateStoreError(path, "directory creation error") from None

    file_descriptor = -1
    temporary_path: Path | None = None

    try:
        file_descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=path.parent,
        )
        temporary_path = Path(temporary_name)

        temporary_file = os.fdopen(
            file_descriptor,
            "w",
            encoding="utf-8",
        )
        file_descriptor = -1

        with temporary_file:
            json.dump(value, temporary_file, indent=2, ensure_ascii=False)
            temporary_file.write("\n")
            temporary_file.flush()
            os.fsync(temporary_file.fileno())

        _backup_valid_state(path)
        os.replace(temporary_path, path)
        temporary_path = None
    except StateStoreError:
        raise
    except (TypeError, ValueError):
        raise StateStoreError(path, "serialization error") from None
    except OSError:
        raise StateStoreError(path, "write error") from None
    finally:
        if file_descriptor >= 0:
            os.close(file_descriptor)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


@contextmanager
def _exclusive_state_lock(path: Path) -> Iterator[None]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock_file = path.with_name(f"{path.name}.lock").open(
            "a",
            encoding="utf-8",
        )
    except OSError:
        raise StateStoreError(path, "lock setup error") from None

    with lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        except OSError:
            raise StateStoreError(path, "lock acquisition error") from None

        try:
            yield
        finally:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            except OSError:
                raise StateStoreError(path, "lock release error") from None


def locked_update_json_list(path: Path, updater: JsonListUpdater) -> JsonList:
    """Run a JSON-list read, update, backup, and atomic write under one lock."""
    with _exclusive_state_lock(path):
        current_value = read_json_list(path)
        updated_value = updater(current_value)
        if not isinstance(updated_value, list):
            raise StateStoreError(path, "list updater returned invalid data")
        write_json_atomic(path, updated_value)
        return updated_value


def locked_update_json_dict(path: Path, updater: JsonDictUpdater) -> JsonDict:
    """Run a JSON-object read, update, backup, and atomic write under one lock."""
    with _exclusive_state_lock(path):
        current_value = read_json_dict(path)
        updated_value = updater(current_value)
        if not isinstance(updated_value, dict):
            raise StateStoreError(path, "dictionary updater returned invalid data")
        write_json_atomic(path, updated_value)
        return updated_value
