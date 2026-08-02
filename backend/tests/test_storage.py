"""作業ディレクトリ管理（`storage.py`）のテスト。

アップロード名は外部入力なので、パストラバーサルを許さないことを重点的に見る。
"""

from __future__ import annotations

import io

import pytest

from backend.app.core import storage


@pytest.fixture(autouse=True)
def workdir(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ML_MOTION_WORKDIR", str(tmp_path))


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("movie.mp4", "movie.mp4"),
        ("東京駅.mp4", "東京駅.mp4"),  # 日本語は残す
        ("../../etc/passwd.mp4", "passwd.mp4"),  # ディレクトリ要素を捨てる
        (r"C:\Users\me\clip.mp4", "clip.mp4"),
        ("my video (1).mp4", "my_video_1.mp4"),
        ("", "input.mp4"),
        ("..", "input.mp4"),
        ("....mp4", "input.mp4"),  # 記号だけの stem は fallback
    ],
)
def test_sanitize_filename(raw: str, expected: str) -> None:
    assert storage.sanitize_filename(raw) == expected


def test_sanitize_filename_never_contains_separators() -> None:
    for raw in ("../../a.mp4", "a/b/c.mp4", "..\\..\\b.mp4"):
        assert "/" not in storage.sanitize_filename(raw)
        assert "\\" not in storage.sanitize_filename(raw)


@pytest.mark.parametrize("name", ["a.mp4", "a.MP4", "a.mov", "a.avi"])
def test_validate_video_suffix_accepts_supported(name: str) -> None:
    assert storage.validate_video_suffix(name) in storage.ALLOWED_VIDEO_SUFFIXES


@pytest.mark.parametrize("name", ["a.txt", "a.mkv", "a", "a.exe"])
def test_validate_video_suffix_rejects_others(name: str) -> None:
    with pytest.raises(storage.StorageError):
        storage.validate_video_suffix(name)


def test_save_and_find_upload_roundtrip() -> None:
    ref = storage.save_upload(io.BytesIO(b"video-bytes"), "clip.mp4")
    assert ref.size == len(b"video-bytes")
    assert ref.stem == "clip"
    assert ref.path.read_bytes() == b"video-bytes"

    found = storage.find_upload(ref.upload_id)
    assert found is not None
    assert found.path == ref.path


def test_save_upload_rejects_empty_file() -> None:
    with pytest.raises(storage.StorageError, match="空のファイル"):
        storage.save_upload(io.BytesIO(b""), "clip.mp4")


def test_save_upload_enforces_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(storage, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(storage.StorageError, match="大きすぎます"):
        storage.save_upload(io.BytesIO(b"x" * 100), "clip.mp4")
    # 失敗したアップロードのディレクトリは残さない。
    assert list(storage.uploads_root().iterdir()) == []


@pytest.mark.parametrize("bad_id", ["../../etc", "..", "/etc", "zzzz", "", "a" * 40])
def test_find_upload_rejects_unsafe_ids(bad_id: str) -> None:
    assert storage.find_upload(bad_id) is None


def test_prune_keeps_newest_directories() -> None:
    for index in range(5):
        directory = storage.runs_root() / f"{index:012x}"
        directory.mkdir()
        # mtime を明示的にずらして順序を確定させる。
        import os

        os.utime(directory, (index, index))

    storage.prune(storage.runs_root(), keep=2)
    remaining = sorted(p.name for p in storage.runs_root().iterdir())
    assert remaining == ["000000000003", "000000000004"]


def test_new_run_dir_creates_unique_directories() -> None:
    first_id, first = storage.new_run_dir()
    second_id, second = storage.new_run_dir()
    assert first_id != second_id
    assert first.is_dir() and second.is_dir()


def test_media_url() -> None:
    assert storage.media_url("abc123", "annotated_clip.mp4") == "/media/abc123/annotated_clip.mp4"


def test_resolve_run_file_returns_existing_file() -> None:
    run_id, directory = storage.new_run_dir()
    (directory / "annotated_clip.mp4").write_bytes(b"mp4")
    resolved = storage.resolve_run_file(run_id, "annotated_clip.mp4")
    assert resolved is not None
    assert resolved.read_bytes() == b"mp4"


def test_resolve_run_file_rejects_traversal(tmp_path) -> None:
    """`/media` 経由で作業ディレクトリの外を読めないこと。"""
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret")
    run_id, _ = storage.new_run_dir()

    for filename in ("../../secret.txt", "..%2Fsecret.txt", "/etc/passwd", ".."):
        assert storage.resolve_run_file(run_id, filename) is None
    assert storage.resolve_run_file("../..", "secret.txt") is None


def test_resolve_run_file_returns_none_for_missing_file() -> None:
    run_id, _ = storage.new_run_dir()
    assert storage.resolve_run_file(run_id, "nope.mp4") is None
