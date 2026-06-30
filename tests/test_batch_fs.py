"""pipeline.batch.discover_media のファイルシステム探索の単体テスト（tmp_path 使用）。"""

from __future__ import annotations

from pipeline.batch import discover_media


def test_discover_media_filters_and_sorts(tmp_path):
    # 動画と非動画を混在配置。
    for name in ["b.mp4", "a.MOV", "note.txt", "c.mkv", "img.png", "d.avi"]:
        (tmp_path / name).write_bytes(b"x")
    found = discover_media(str(tmp_path))
    names = [p.rsplit("/", 1)[-1] for p in found]
    assert names == ["a.MOV", "b.mp4", "c.mkv", "d.avi"]  # 動画のみ・ソート済み
    assert all(p.startswith(str(tmp_path)) for p in found)  # 絶対パス


def test_discover_media_empty_dir(tmp_path):
    assert discover_media(str(tmp_path)) == []


def test_discover_media_nonexistent_dir(tmp_path):
    missing = tmp_path / "does_not_exist"
    assert discover_media(str(missing)) == []


def test_discover_media_ignores_subdirectories(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "nested.mp4").write_bytes(b"x")  # 直下ではないので対象外
    (tmp_path / "top.mp4").write_bytes(b"x")
    found = [p.rsplit("/", 1)[-1] for p in discover_media(str(tmp_path))]
    assert found == ["top.mp4"]
