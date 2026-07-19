from __future__ import annotations

import os
from pathlib import Path


ALLOWED_SOURCE_ROOT = Path(r"E:\大学\竞赛\软件杯\知识库文档")
ALLOWED_PROJECT_ROOT = Path(r"D:\Work Space\Energy-Maintenance")


class PathBoundaryError(ValueError):
    pass


def canonical_path(value: str | os.PathLike[str], *, must_exist: bool = False) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        raise PathBoundaryError(f"absolute path required: {candidate}")
    try:
        return candidate.resolve(strict=must_exist)
    except (FileNotFoundError, OSError) as exc:
        raise PathBoundaryError(f"cannot resolve path: {candidate}") from exc


def is_within(path: Path, root: Path) -> bool:
    path_key = os.path.normcase(str(path))
    root_key = os.path.normcase(str(root))
    try:
        return os.path.commonpath((path_key, root_key)) == root_key
    except ValueError:
        return False


def assert_path_within(
    value: str | os.PathLike[str],
    root: str | os.PathLike[str],
    *,
    must_exist: bool = False,
) -> Path:
    resolved_root = canonical_path(root, must_exist=True)
    resolved_path = canonical_path(value, must_exist=must_exist)
    if not is_within(resolved_path, resolved_root):
        raise PathBoundaryError(f"path escapes allowed root: {resolved_path}")
    return resolved_path


def assert_source_path(value: str | os.PathLike[str], *, must_exist: bool = False) -> Path:
    return assert_path_within(value, ALLOWED_SOURCE_ROOT, must_exist=must_exist)


def assert_project_path(value: str | os.PathLike[str], *, must_exist: bool = False) -> Path:
    return assert_path_within(value, ALLOWED_PROJECT_ROOT, must_exist=must_exist)


def assert_allowed_path(value: str | os.PathLike[str], *, must_exist: bool = False) -> Path:
    errors: list[Exception] = []
    for root in (ALLOWED_SOURCE_ROOT, ALLOWED_PROJECT_ROOT):
        try:
            return assert_path_within(value, root, must_exist=must_exist)
        except PathBoundaryError as exc:
            errors.append(exc)
    raise PathBoundaryError(f"path is outside all allowed roots: {value}") from errors[-1]
