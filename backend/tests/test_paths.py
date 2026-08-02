"""ユーザー入力パスの解決（`core/paths.py`）のテスト。

本番/最適化画面はディレクトリや重みのパスを文字列で受け取るため、
**リポジトリ外へ出られないこと**を重点的に確認する。
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from backend.app.core.paths import (
    ALLOWED_ROOTS_ENV,
    PathNotAllowedError,
    allowed_roots,
    is_within,
    repo_root,
    resolve_user_path,
    to_display,
)


def test_repo_root_is_the_repository() -> None:
    """リポジトリルートの判定（pyproject.toml があること）。"""
    assert (repo_root() / "pyproject.toml").is_file()
    assert (repo_root() / "pipeline").is_dir()


def test_relative_path_resolves_under_repo_root() -> None:
    assert resolve_user_path("data/incoming") == repo_root() / "data" / "incoming"


def test_absolute_path_inside_repo_is_allowed() -> None:
    inside = str(repo_root() / "output_batch")
    assert resolve_user_path(inside) == repo_root() / "output_batch"


@pytest.mark.parametrize(
    "raw",
    [
        "../../etc",
        "../..",
        "/etc/passwd",
        "/tmp",
        "data/../../../etc",
        "~",
        "~/Videos",
    ],
)
def test_paths_outside_repo_are_rejected(raw: str) -> None:
    with pytest.raises(PathNotAllowedError, match="リポジトリ外"):
        resolve_user_path(raw)


@pytest.mark.parametrize("raw", ["", "   "])
def test_empty_path_is_rejected(raw: str) -> None:
    with pytest.raises(PathNotAllowedError, match="パスを入力"):
        resolve_user_path(raw)


def test_symlink_escaping_the_repo_is_rejected(tmp_path: Path) -> None:
    """シンボリックリンクでリポジトリ外へ抜けられないこと（実パスで判定する）。"""
    outside = tmp_path / "outside"
    outside.mkdir()
    link = repo_root() / "_test_escape_link"
    link.symlink_to(outside, target_is_directory=True)
    try:
        with pytest.raises(PathNotAllowedError, match="リポジトリ外"):
            resolve_user_path("_test_escape_link")
    finally:
        link.unlink()


def test_must_exist_rejects_missing_path() -> None:
    with pytest.raises(PathNotAllowedError, match="存在しない"):
        resolve_user_path("no/such/dir", must_exist=True)


def test_must_be_dir_rejects_file() -> None:
    with pytest.raises(PathNotAllowedError, match="ディレクトリではありません"):
        resolve_user_path("pyproject.toml", must_be_dir=True)


def test_must_be_dir_allows_not_yet_created_directory() -> None:
    """出力先はこれから作るので、存在しなくても通す。"""
    assert resolve_user_path("output_batch_not_created_yet", must_be_dir=True)


def test_extra_roots_can_be_added_via_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """リポジトリ外を使いたい場合は環境変数で許可を足せる。"""
    extra = tmp_path / "videos"
    extra.mkdir()

    with pytest.raises(PathNotAllowedError):
        resolve_user_path(str(extra))

    monkeypatch.setenv(ALLOWED_ROOTS_ENV, str(extra))
    assert resolve_user_path(str(extra)) == extra.resolve()
    assert resolve_user_path(str(extra / "sub")) == (extra / "sub").resolve()


def test_multiple_extra_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    first.mkdir()
    second.mkdir()
    monkeypatch.setenv(ALLOWED_ROOTS_ENV, os.pathsep.join([str(first), str(second)]))

    roots = allowed_roots()
    assert first.resolve() in roots
    assert second.resolve() in roots
    assert repo_root() in roots


def test_blank_entries_in_env_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ALLOWED_ROOTS_ENV, os.pathsep.join(["", "  ", ""]))
    assert allowed_roots() == [repo_root()]


def test_is_within() -> None:
    root = Path("/a/b")
    assert is_within(Path("/a/b"), root) is True
    assert is_within(Path("/a/b/c"), root) is True
    assert is_within(Path("/a"), root) is False
    assert is_within(Path("/a/bc"), root) is False


def test_to_display_uses_relative_path() -> None:
    assert to_display(repo_root() / "output_batch" / "x.mp4") == "output_batch/x.mp4"


def test_to_display_keeps_absolute_for_outside_paths() -> None:
    assert to_display(Path("/tmp/x.mp4")) == "/tmp/x.mp4"
