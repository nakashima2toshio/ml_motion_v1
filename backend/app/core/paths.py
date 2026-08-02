"""ユーザー入力のパスを安全に解決する。

本番/最適化画面はディレクトリや重みのパスを**文字列でユーザーから受け取る**
（`data/incoming`、`output_batch`、`yolo11s.pt` 等）。Streamlit 版はローカル実行
専用だったので無制限だったが、React 版は HTTP API になるため、`../../etc` のような
入力でリポジトリ外を読み書きできてしまう。

そこで**許可ルート配下だけ**を通す。既定の許可ルートはリポジトリルート。
リポジトリ外のディレクトリを使いたい場合は環境変数
`ML_MOTION_ALLOWED_ROOTS`（`os.pathsep` 区切り）で追加する。

シンボリックリンク経由の抜け道を塞ぐため、`Path.resolve()` した実パスで判定する。
標準ライブラリのみに依存し単体テストできる。
"""

from __future__ import annotations

import os
from pathlib import Path

# 追加の許可ルートを指定する環境変数（`:`（Windows は `;`）区切り）。
ALLOWED_ROOTS_ENV = "ML_MOTION_ALLOWED_ROOTS"


class PathNotAllowedError(ValueError):
    """許可ルート外を指すパス（呼び出し側で 400 にする）。"""


def repo_root() -> Path:
    """リポジトリのルート（このファイルから 4 階層上）。"""
    return Path(__file__).resolve().parents[3]


def allowed_roots() -> list[Path]:
    """許可ルートの一覧。リポジトリルート ＋ 環境変数で追加した分。"""
    roots = [repo_root()]
    extra = os.getenv(ALLOWED_ROOTS_ENV, "")
    for entry in extra.split(os.pathsep):
        path = entry.strip()
        if not path:
            continue
        try:
            roots.append(Path(path).expanduser().resolve())
        except OSError:  # 解決できないパスは無視する
            continue
    return roots


def is_within(path: Path, root: Path) -> bool:
    """`path` が `root` 自身か、その配下かどうか（解決済みパス前提）。"""
    return path == root or root in path.parents


def resolve_user_path(raw: str, *, must_exist: bool = False, must_be_dir: bool = False) -> Path:
    """ユーザー入力のパスを許可ルート内に限定して解決する。

    相対パスはリポジトリルート基準で解決する（Streamlit 版が
    `data/incoming` のような相対パスを想定していたため）。

    Raises:
        PathNotAllowedError: 空文字・許可ルート外・存在要件を満たさない場合。
    """
    text = raw.strip()
    if not text:
        raise PathNotAllowedError("パスを入力してください。")

    root = repo_root()
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate

    try:
        resolved = candidate.resolve()
    except OSError as e:  # 循環シンボリックリンク等
        raise PathNotAllowedError(f"パスを解決できません: {raw}（{e}）") from e

    if not any(is_within(resolved, allowed) for allowed in allowed_roots()):
        raise PathNotAllowedError(
            f"リポジトリ外のパスは指定できません: {raw}"
            f"（許可: {root} 配下。追加するには環境変数 {ALLOWED_ROOTS_ENV} を設定）"
        )

    if must_exist and not resolved.exists():
        raise PathNotAllowedError(f"存在しないパスです: {raw}")
    if must_be_dir and resolved.exists() and not resolved.is_dir():
        raise PathNotAllowedError(f"ディレクトリではありません: {raw}")

    return resolved


def to_display(path: Path) -> str:
    """画面表示用に、可能ならリポジトリルートからの相対パスにする。"""
    try:
        return str(path.relative_to(repo_root()))
    except ValueError:
        return str(path)
