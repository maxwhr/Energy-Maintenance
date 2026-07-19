from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from task28a_path_safety import (
    ALLOWED_PROJECT_ROOT,
    ALLOWED_SOURCE_ROOT,
    PathBoundaryError,
    assert_project_path,
    assert_source_path,
)


def test_allows_existing_source_root_after_migration() -> None:
    assert_source_path(ALLOWED_SOURCE_ROOT, must_exist=True)


def test_allows_project_file_target() -> None:
    result = assert_project_path(ALLOWED_PROJECT_ROOT / ".runtime" / "task28a" / "allowed.txt")
    assert result.name == "allowed.txt"


def test_rejects_parent_escape() -> None:
    with pytest.raises(PathBoundaryError):
        assert_project_path(ALLOWED_PROJECT_ROOT / ".." / "task28a-escape" / "file.txt")


def test_rejects_other_drive_for_project_operation() -> None:
    with pytest.raises(PathBoundaryError):
        assert_project_path(ALLOWED_SOURCE_ROOT, must_exist=True)


def test_rejects_similar_prefix_directory() -> None:
    with pytest.raises(PathBoundaryError):
        assert_project_path(Path(r"D:\Work Space\Energy-Maintenance-copy\file.txt"))


def test_rejects_symbolic_link_or_junction_escape() -> None:
    sandbox = ALLOWED_PROJECT_ROOT / ".runtime" / "task28a" / "path-safety-test"
    sandbox.mkdir(parents=True, exist_ok=True)
    link = sandbox / "source-link"
    if link.exists() or link.is_symlink():
        link.unlink()
    try:
        os.symlink(ALLOWED_SOURCE_ROOT, link, target_is_directory=True)
    except OSError as exc:
        junction = sandbox / "source-junction"
        if junction.exists():
            os.rmdir(junction)
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(ALLOWED_SOURCE_ROOT)],
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            pytest.fail(
                "neither symbolic-link nor junction escape could be exercised: "
                f"symlink_winerror={exc.winerror}, junction_exit={completed.returncode}"
            )
        try:
            with pytest.raises(PathBoundaryError):
                assert_project_path(junction, must_exist=True)
        finally:
            os.rmdir(junction)
        return
    try:
        with pytest.raises(PathBoundaryError):
            assert_project_path(link, must_exist=True)
    finally:
        link.unlink(missing_ok=True)
