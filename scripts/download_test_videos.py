#!/usr/bin/env python3
"""テスト用動画ダウンローダ（supervision 公式アセット）.

ml_motion_v1 の開発・テストで使う mp4 を `data/raw/` に取得する。
動画本体は Git にコミットしない方針（`.gitignore` で除外済み）。
このスクリプトだけをリポジトリに含め、各自が実行して取得する。

取得元は依存ライブラリ ``supervision`` 同梱の公式アセット
(``supervision.assets``) で、YOLO11 検出・ByteTrack 追跡・
supervision ゾーン解析（カウント/滞留/侵入）のデモにそのまま使える。

Examples
--------
    # 推奨セット（車両 + 歩行者）を data/raw/ に取得
    python scripts/download_test_videos.py

    # 利用可能なアセット一覧を表示
    python scripts/download_test_videos.py --list

    # 個別指定
    python scripts/download_test_videos.py --assets VEHICLES PEOPLE_WALKING SUBWAY

    # すべて取得
    python scripts/download_test_videos.py --all

    # 出力先を変更
    python scripts/download_test_videos.py --out data/raw
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# このプロジェクトで P1（検出MVP）→ P2（ゾーン解析）を回す推奨セット。
DEFAULT_ASSETS: list[str] = ["VEHICLES", "PEOPLE_WALKING"]

# 各アセットの用途メモ（--list 表示用）。supervision のバージョンにより
# 提供アセットは増減するため、存在するものだけを案内する。
ASSET_NOTES: dict[str, str] = {
    "VEHICLES": "道路・車。車両カウント/ゾーン侵入の定番（P1検出・P2ゾーン解析）",
    "VEHICLES_2": "別アングルの車両シーン",
    "PEOPLE_WALKING": "歩行者。トラッキング/滞留時間（P2追跡）",
    "MARKET_SQUARE": "広場・群衆。密集シーンでの ID 付与の堅牢性",
    "SUBWAY": "改札・通路。ゾーン通過カウント",
    "GROCERY_STORE": "店内。人物トラッキングとゾーン解析",
    "MILK_BOTTLING_PLANT": "工場ライン。物体カウント",
    "BEACH": "屋外・人物。背景雑多な検出テスト",
    "BASKETBALL": "スポーツ。高速移動体のトラッキング",
    "SKIING": "スポーツ。高速移動体のトラッキング",
}


def _load_video_assets():
    """supervision の VideoAssets / download_assets を遅延 import する."""
    try:
        from supervision.assets import VideoAssets, download_assets
    except ImportError as exc:  # pragma: no cover - 環境依存
        sys.exit(
            "ERROR: supervision が見つかりません。`pip install -r requirements.txt` を実行してください。\n"
            f"  詳細: {exc}"
        )
    return VideoAssets, download_assets


def _available_asset_names(VideoAssets) -> list[str]:
    """インストール済み supervision が提供するアセット名の一覧."""
    return [name for name in VideoAssets.__members__]


def list_assets() -> None:
    VideoAssets, _ = _load_video_assets()
    available = _available_asset_names(VideoAssets)
    print("利用可能な supervision アセット（このバージョンで提供されるもの）:\n")
    for name in available:
        filename = VideoAssets[name].value
        note = ASSET_NOTES.get(name, "")
        mark = "★" if name in DEFAULT_ASSETS else " "
        print(f"  {mark} {name:<20} {filename:<28} {note}")
    print(f"\n★ = 既定の推奨セット（{', '.join(DEFAULT_ASSETS)}）")


def download(asset_names: list[str], out_dir: Path) -> None:
    VideoAssets, download_assets = _load_video_assets()
    available = set(_available_asset_names(VideoAssets))

    unknown = [n for n in asset_names if n not in available]
    if unknown:
        sys.exit(
            f"ERROR: 未対応のアセット: {', '.join(unknown)}\n"
            f"  --list で利用可能なアセットを確認してください。"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    # supervision の download_assets はカレントディレクトリに保存するため、
    # 取得先ディレクトリへ移動してから呼び出す。
    cwd = Path.cwd()
    os.chdir(out_dir)
    try:
        for name in asset_names:
            asset = VideoAssets[name]
            print(f"[download] {name} -> {out_dir / asset.value}")
            download_assets(asset)
    finally:
        os.chdir(cwd)

    print(f"\n完了: {len(asset_names)} 件を {out_dir} に取得しました。")
    print("（動画は .gitignore で除外済み。リポジトリにはコミットされません）")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list", action="store_true", help="利用可能なアセット一覧を表示して終了")
    parser.add_argument("--all", action="store_true", help="提供されている全アセットを取得")
    parser.add_argument(
        "--assets",
        nargs="+",
        metavar="NAME",
        help=f"取得するアセット名（既定: {' '.join(DEFAULT_ASSETS)}）",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/raw"),
        help="保存先ディレクトリ（既定: data/raw）",
    )
    args = parser.parse_args(argv)

    if args.list:
        list_assets()
        return

    if args.all:
        VideoAssets, _ = _load_video_assets()
        asset_names = _available_asset_names(VideoAssets)
    elif args.assets:
        asset_names = args.assets
    else:
        asset_names = DEFAULT_ASSETS

    download(asset_names, args.out)


if __name__ == "__main__":
    main()
