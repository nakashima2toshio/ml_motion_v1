"""アップロードと解析成果物の作業ディレクトリ管理。

Streamlit 版は `tempfile.mkdtemp()` を毎回作り、`st.session_state` が生きている間
だけ結果を参照していた。React 版はリクエストが分かれるため、置き場所を決めて
ID で引けるようにする。

    <root>/uploads/<upload_id>/<元のファイル名>       … アップロードした動画
    <root>/runs/<run_id>/annotated_<stem>.mp4        … 注釈付き動画（/media で配信）

`<root>` は環境変数 `ML_MOTION_WORKDIR`、無ければ OS の一時ディレクトリ配下。
ローカル開発用なので永続化・共有は考えない（古いものから自動で捨てる）。
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

# 受け付ける動画の拡張子（Streamlit 版 `st.file_uploader(type=[...])` と一致させる）。
ALLOWED_VIDEO_SUFFIXES: frozenset[str] = frozenset({".mp4", ".mov", ".avi"})

# アップロード 1 件のサイズ上限。ローカル用途なので大きめだが、無制限にはしない。
MAX_UPLOAD_BYTES = 2 * 1024 * 1024 * 1024  # 2 GiB

# 保持する世代数（超えたら古い順に削除）。
MAX_UPLOADS = 10
MAX_RUNS = 20

# ファイル名として安全でない文字。パス区切りも含めてまとめて潰す。
_UNSAFE = re.compile(r"[^0-9A-Za-z._\-\u3040-\u30ff\u4e00-\u9fff]+")


class StorageError(ValueError):
    """アップロードの検証エラー（呼び出し側で 400 にする）。"""


@dataclass(frozen=True)
class UploadRef:
    """保存済みアップロードの参照。"""

    upload_id: str
    path: Path
    filename: str
    size: int

    @property
    def stem(self) -> str:
        return Path(self.filename).stem


def workspace_root() -> Path:
    """作業ディレクトリのルート。無ければ作る。"""
    configured = os.getenv("ML_MOTION_WORKDIR")
    root = Path(configured) if configured else Path(tempfile.gettempdir()) / "ml_motion_react"
    root.mkdir(parents=True, exist_ok=True)
    return root


def runs_root() -> Path:
    """注釈付き動画の置き場（`/media` としてマウントする）。"""
    root = workspace_root() / "runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


def uploads_root() -> Path:
    root = workspace_root() / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def sanitize_filename(name: str, fallback: str = "input.mp4") -> str:
    """アップロード名をファイル名として安全な形に正規化する。

    ディレクトリ要素（`../`, `C:\\`）は捨て、記号は `_` に潰す。日本語は残す。
    """
    base = name.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not base or base in {".", ".."}:
        return fallback
    stem, dot, suffix = base.rpartition(".")
    if not dot:  # 拡張子なし
        stem, suffix = base, ""
    # ドットだけの stem（"..", "..."）はファイル名として紛らわしいので fallback にする。
    cleaned_stem = _UNSAFE.sub("_", stem).strip("_")
    if not cleaned_stem.strip("."):
        cleaned_stem = "input"
    cleaned_suffix = _UNSAFE.sub("", suffix).lower()
    # 極端に長い名前は切る（ファイルシステム上限対策）。
    cleaned_stem = cleaned_stem[:80]
    return f"{cleaned_stem}.{cleaned_suffix}" if cleaned_suffix else cleaned_stem


def validate_video_suffix(filename: str) -> str:
    """拡張子を検証して小文字で返す。未対応なら StorageError。"""
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_SUFFIXES:
        allowed = " / ".join(sorted(ALLOWED_VIDEO_SUFFIXES))
        raise StorageError(f"未対応のファイル形式です: {suffix or '(拡張子なし)'}（対応: {allowed}）")
    return suffix


def save_upload(stream: BinaryIO, filename: str, chunk_size: int = 1024 * 1024) -> UploadRef:
    """アップロードをストリーミング保存する（全体をメモリに載せない）。

    Raises:
        StorageError: 拡張子が未対応、または上限サイズ超過。
    """
    validate_video_suffix(filename)
    safe_name = sanitize_filename(filename)

    upload_id = uuid.uuid4().hex[:12]
    directory = uploads_root() / upload_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / safe_name

    size = 0
    try:
        with path.open("wb") as out:
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise StorageError(
                        f"ファイルが大きすぎます（上限 {MAX_UPLOAD_BYTES // (1024 * 1024)} MB）"
                    )
                out.write(chunk)
    except StorageError:
        shutil.rmtree(directory, ignore_errors=True)
        raise

    if size == 0:
        shutil.rmtree(directory, ignore_errors=True)
        raise StorageError("空のファイルです")

    prune(uploads_root(), MAX_UPLOADS)
    return UploadRef(upload_id=upload_id, path=path, filename=safe_name, size=size)


def find_upload(upload_id: str) -> UploadRef | None:
    """upload_id から保存済みファイルを引く。未知の ID なら None。"""
    if not is_safe_id(upload_id):
        return None
    directory = uploads_root() / upload_id
    if not directory.is_dir():
        return None
    files = [p for p in directory.iterdir() if p.is_file()]
    if not files:
        return None
    path = files[0]
    return UploadRef(upload_id=upload_id, path=path, filename=path.name, size=path.stat().st_size)


def new_run_dir() -> tuple[str, Path]:
    """解析 1 回分の出力ディレクトリを作り `(run_id, path)` を返す。"""
    run_id = uuid.uuid4().hex[:12]
    directory = runs_root() / run_id
    directory.mkdir(parents=True, exist_ok=True)
    prune(runs_root(), MAX_RUNS)
    return run_id, directory


def media_url(run_id: str, filename: str) -> str:
    """`/media` マウント配下の公開 URL。"""
    return f"/media/{run_id}/{filename}"


def prune(root: Path, keep: int) -> None:
    """更新時刻の古いディレクトリから、`keep` 件になるまで削除する。"""
    if not root.is_dir():
        return
    directories = sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime)
    for directory in directories[: max(0, len(directories) - keep)]:
        shutil.rmtree(directory, ignore_errors=True)


def is_safe_id(value: str) -> bool:
    """ID は 16 進のみ。パストラバーサル（`..`, `/`）を弾く。"""
    return bool(value) and len(value) <= 32 and all(c in "0123456789abcdef" for c in value)


def resolve_run_file(run_id: str, filename: str) -> Path | None:
    """`/media` 配信用に `runs/<run_id>/<filename>` を安全に解決する。

    ID・ファイル名を検証したうえで、実パスが runs ルート配下に収まることも
    確認する（シンボリックリンク経由の抜け道を塞ぐ）。存在しなければ None。
    """
    if not is_safe_id(run_id) or filename != sanitize_filename(filename, fallback=""):
        return None
    root = runs_root().resolve()
    path = (root / run_id / filename).resolve()
    if not path.is_file() or root not in path.parents:
        return None
    return path
